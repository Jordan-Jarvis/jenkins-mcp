"""MCP test client for integration testing"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPTestClient:
    """Test client that communicates with MCP server via stdio JSON-RPC"""

    def __init__(
        self,
        server_script: str = "mcp_server.server",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.server_script = server_script
        self.config = config or {}
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self._reader_task = None
        self._responses = {}
        self._server_ready = False

    async def start_server(self) -> None:
        """Start the MCP server process"""
        env = os.environ.copy()

        # Set test configuration via environment
        for key, value in self.config.items():
            if key == "jenkins_url":
                env["JENKINS_URL"] = str(value)
            elif key == "jenkins_user":
                env["JENKINS_USER"] = str(value)  # Server expects JENKINS_USER
            elif key == "jenkins_token":
                env["JENKINS_TOKEN"] = str(value)
            elif key == "cache_dir":
                env["CACHE_DIR"] = str(value)
            else:
                # For other config values, use TEST_ prefix
                env[f"TEST_{key.upper()}"] = str(value)

        # Disable vector search for testing
        env["DISABLE_VECTOR_SEARCH"] = "true"

        # Set a cache directory for testing
        if "CACHE_DIR" not in env:
            env["CACHE_DIR"] = str(Path(tempfile.gettempdir()) / "mcp-jenkins-test")

        # Start the server
        cmd = [sys.executable, "-m", self.server_script]
        logger.info(f"Starting MCP server with command: {cmd}")

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Start reader task
        self._reader_task = asyncio.create_task(self._read_responses())

        # Wait for server initialization
        await self._wait_for_server_ready()

    async def _wait_for_server_ready(self, timeout: float = 10.0):
        """Wait for server to be ready by sending initialization request"""
        start_time = time.time()

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                "clientInfo": {"name": "mcp-test-client", "version": "1.0.0"},
            },
        }

        await self._send_request(init_request)

        # Wait for initialize response
        while time.time() - start_time < timeout:
            if "init" in self._responses:
                response = self._responses["init"]
                if "result" in response:
                    self._server_ready = True
                    logger.info("MCP server initialized successfully")

                    # Send initialized notification
                    initialized_notif = {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    }
                    await self._send_request(initialized_notif)
                    return
                elif "error" in response:
                    raise RuntimeError(
                        f"Server initialization failed: {response['error']}"
                    )

            await asyncio.sleep(0.1)

        raise TimeoutError("Server failed to initialize within timeout")

    async def _read_responses(self):
        """Continuously read responses from the server"""
        while self.process and not self.process.stdout.at_eof():
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    response = json.loads(line_str)
                    if "id" in response:
                        self._responses[response["id"]] = response
                        logger.debug(f"Received response for request {response['id']}")
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to decode JSON response: {line_str}, error: {e}"
                    )
            except Exception as e:
                logger.error(f"Error reading server response: {e}")
                break

    async def _send_request(self, request: Dict[str, Any]):
        """Send a request to the server"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Server process not started")

        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        await self.process.stdin.drain()
        logger.debug(
            f"Sent request: {request.get('method', 'unknown')} (id: {request.get('id', 'none')})"
        )

    async def stop_server(self) -> None:
        """Stop the MCP server process"""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

            # Read any remaining stderr for debugging
            if self.process.stderr:
                stderr_data = await self.process.stderr.read()
                if stderr_data:
                    logger.debug(f"Server stderr: {stderr_data.decode('utf-8')}")

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Call a tool and return the result"""
        if not self._server_ready:
            raise RuntimeError("Server not ready. Did you call start_server()?")

        self.request_id += 1
        request_id = f"tool-{self.request_id}"

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        await self._send_request(request)

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < timeout:
            if request_id in self._responses:
                response = self._responses.pop(request_id)
                if "error" in response:
                    raise RuntimeError(f"Tool call error: {response['error']}")
                return response.get("result", {})
            await asyncio.sleep(0.1)

        raise TimeoutError(f"Tool call {tool_name} timed out after {timeout}s")

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools"""
        if not self._server_ready:
            raise RuntimeError("Server not ready. Did you call start_server()?")

        self.request_id += 1
        request_id = f"list-tools-{self.request_id}"

        request = {"jsonrpc": "2.0", "id": request_id, "method": "tools/list"}

        await self._send_request(request)

        # Wait for response
        start_time = time.time()
        while time.time() - start_time < 5.0:
            if request_id in self._responses:
                response = self._responses.pop(request_id)
                if "error" in response:
                    raise RuntimeError(f"List tools error: {response['error']}")
                return response.get("result", {}).get("tools", [])
            await asyncio.sleep(0.1)

        raise TimeoutError("List tools request timed out")

    async def __aenter__(self):
        await self.start_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_server()
