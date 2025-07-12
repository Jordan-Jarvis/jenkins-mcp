"""HTTP Streaming Server for Jenkins MCP

This module provides HTTP streaming support for the Jenkins MCP server,
implementing the Streamable HTTP transport as defined in the MCP specification.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

from .config import MCPConfig
from .di_container import DIContainer
from .logging_config import setup_logging
from .server import create_server, load_config_from_yaml
from .tool_factory import ToolFactory

# Setup logging
logger = logging.getLogger(__name__)


class HTTPStreamingServer:
    """HTTP Streaming server for MCP protocol"""

    def __init__(
        self,
        config: Optional[MCPConfig] = None,
        port: int = 8000,
        host: str = "0.0.0.0",
    ):
        self.config = config
        self.port = port
        self.host = host
        self.mcp_server = None
        self.app = FastAPI(
            title="Jenkins MCP HTTP Streaming Server",
            description="MCP server with HTTP streaming transport support",
            version="1.0.0",
        )
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes for MCP protocol"""

        @self.app.on_event("startup")
        async def startup_event():
            """Initialize MCP server on startup"""
            logger.info("Starting Jenkins MCP HTTP Streaming Server...")
            self.mcp_server = create_server(self.config)

        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Cleanup on shutdown"""
            logger.info("Shutting down Jenkins MCP HTTP Streaming Server...")

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "transport": "streamable-http"}

        @self.app.post("/mcp")
        async def handle_mcp_post(request: Request):
            """Handle MCP POST requests with optional SSE streaming"""
            try:
                # Get request headers
                accept_header = request.headers.get("accept", "")
                content_type = request.headers.get("content-type", "")
                session_id = request.headers.get("mcp-session-id")
                protocol_version = request.headers.get(
                    "mcp-protocol-version", "2025-06-18"
                )

                # Validate content type
                if "application/json" not in content_type:
                    raise HTTPException(
                        status_code=400, detail="Content-Type must be application/json"
                    )

                # Get request body
                body = await request.json()

                # Check if this is a JSON-RPC request
                if "jsonrpc" not in body or body["jsonrpc"] != "2.0":
                    raise HTTPException(
                        status_code=400, detail="Invalid JSON-RPC request"
                    )

                method = body.get("method")
                params = body.get("params", {})
                request_id = body.get("id")

                # Handle initialization specially to assign session ID
                if method == "initialize":
                    # Generate session ID if not present
                    if not session_id:
                        import uuid

                        session_id = str(uuid.uuid4())

                    # Process initialization
                    response = await self._handle_json_rpc_request(body)

                    # Return response with session ID header
                    return JSONResponse(
                        content=response, headers={"Mcp-Session-Id": session_id}
                    )

                # For other requests, require session ID
                if not session_id and method != "initialize":
                    raise HTTPException(
                        status_code=400, detail="Mcp-Session-Id header required"
                    )

                # Check if client wants SSE streaming
                wants_sse = "text/event-stream" in accept_header

                # Process the request
                if wants_sse and request_id is not None:
                    # Return SSE stream for requests that might need streaming
                    return EventSourceResponse(
                        self._stream_response(body, session_id),
                        media_type="text/event-stream",
                    )
                else:
                    # Return single JSON response
                    response = await self._handle_json_rpc_request(body)

                    # For notifications/responses without ID, return 202 Accepted
                    if request_id is None:
                        return Response(status_code=202)

                    return JSONResponse(content=response)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error handling MCP request: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e),
                    },
                }
                if body.get("id"):
                    error_response["id"] = body["id"]
                return JSONResponse(content=error_response, status_code=500)

        @self.app.get("/mcp")
        async def handle_mcp_get(request: Request):
            """Handle MCP GET requests for server-initiated SSE streams"""
            accept_header = request.headers.get("accept", "")
            session_id = request.headers.get("mcp-session-id")
            last_event_id = request.headers.get("last-event-id")

            # Validate accept header
            if "text/event-stream" not in accept_header:
                raise HTTPException(
                    status_code=405, detail="Method Not Allowed - SSE not supported"
                )

            # Require session ID for GET requests
            if not session_id:
                raise HTTPException(
                    status_code=400, detail="Mcp-Session-Id header required"
                )

            # Return SSE stream for server-initiated messages
            return EventSourceResponse(
                self._server_initiated_stream(session_id, last_event_id),
                media_type="text/event-stream",
            )

        @self.app.delete("/mcp")
        async def handle_mcp_delete(request: Request):
            """Handle session termination"""
            session_id = request.headers.get("mcp-session-id")

            if not session_id:
                raise HTTPException(
                    status_code=400, detail="Mcp-Session-Id header required"
                )

            # TODO: Implement session cleanup
            logger.info(f"Terminating session: {session_id}")

            return Response(status_code=204)

    async def _handle_json_rpc_request(self, request: dict) -> dict:
        """Process a JSON-RPC request through the MCP server"""
        # TODO: Integrate with FastMCP's request handling
        # For now, return a basic response
        method = request.get("method")
        request_id = request.get("id")

        # Simulate processing
        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}, "resources": {}},
                    "serverInfo": {"name": "Jenkins MCP Server", "version": "1.0.0"},
                },
            }
        elif method == "tools/list":
            # TODO: Get actual tools from MCP server
            response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": []}}
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "Method not found"},
            }

        return response

    async def _stream_response(self, request: dict, session_id: str):
        """Stream SSE response for a request"""
        # Send initial acknowledgment
        yield {
            "event": "message",
            "data": '{"type": "acknowledgment", "request_id": '
            + str(request.get("id"))
            + "}",
        }

        # Process the request
        response = await self._handle_json_rpc_request(request)

        # Send the response as SSE event
        import json

        yield {"event": "message", "data": json.dumps(response)}

    async def _server_initiated_stream(
        self, session_id: str, last_event_id: Optional[str] = None
    ):
        """Stream server-initiated messages"""
        # TODO: Implement actual server-initiated message streaming
        # For now, just keep the connection alive
        try:
            while True:
                await asyncio.sleep(30)  # Keep-alive every 30 seconds
                yield {"event": "ping", "data": '{"type": "keep-alive"}'}
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for session: {session_id}")
            raise

    def run(self):
        """Run the HTTP streaming server"""
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")


def main():
    """Main entry point for HTTP streaming server"""
    parser = argparse.ArgumentParser(description="Jenkins MCP HTTP Streaming Server")
    parser.add_argument("--config", type=str, help="Path to YAML configuration file")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on (default: 8000)"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging()

    # Load config if provided
    config = None
    if args.config:
        try:
            config = load_config_from_yaml(args.config)
            logger.info(f"Loaded configuration from: {args.config}")
        except Exception as e:
            logger.error(f"Failed to load config from {args.config}: {e}")
            sys.exit(1)

    # Create and run server
    server = HTTPStreamingServer(config=config, port=args.port, host=args.host)

    try:
        logger.info(f"Starting HTTP streaming server on {args.host}:{args.port}")
        server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
