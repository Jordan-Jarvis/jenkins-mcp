#!/usr/bin/env python3
"""Test script for HTTP streaming transport"""

import asyncio
import json
import httpx
from typing import Dict, Any


class HTTPStreamingClient:
    """Test client for HTTP streaming MCP server"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None
        self.protocol_version = "2025-06-18"

    async def initialize(self) -> Dict[str, Any]:
        """Initialize connection with the server"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": self.protocol_version,
                        "capabilities": {"tools": {}, "resources": {}},
                        "clientInfo": {"name": "test-client", "version": "1.0.0"},
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            # Extract session ID from response headers
            self.session_id = response.headers.get("Mcp-Session-Id")
            print(f"Session ID: {self.session_id}")

            return response.json()

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Mcp-Session-Id": self.session_id,
                    "MCP-Protocol-Version": self.protocol_version,
                },
            )

            return response.json()

    async def test_sse_streaming(self):
        """Test SSE streaming response"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/mcp",
                json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": self.session_id,
                    "MCP-Protocol-Version": self.protocol_version,
                },
                timeout=30.0,
            )

            if response.headers.get("content-type") == "text/event-stream":
                print("Received SSE stream:")
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        print(f"  Event: {data}")
            else:
                print("Received JSON response:")
                print(response.json())

    async def test_server_initiated_stream(self):
        """Test server-initiated SSE stream"""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                f"{self.base_url}/mcp",
                headers={
                    "Accept": "text/event-stream",
                    "Mcp-Session-Id": self.session_id,
                },
            ) as response:
                if response.status_code == 200:
                    print("Connected to server-initiated stream")
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            print(f"  Server event: {data}")
                        if line.startswith("event: "):
                            print(f"  Event type: {line[7:]}")
                else:
                    print(f"Failed to connect: {response.status_code}")

    async def terminate_session(self):
        """Terminate the session"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/mcp", headers={"Mcp-Session-Id": self.session_id}
            )

            print(f"Session terminated: {response.status_code}")


async def main():
    """Run tests"""
    client = HTTPStreamingClient()

    print("1. Testing initialization...")
    result = await client.initialize()
    print(f"   Result: {result}")

    print("\n2. Testing tools/list...")
    result = await client.list_tools()
    print(f"   Result: {result}")

    print("\n3. Testing SSE streaming...")
    await client.test_sse_streaming()

    print("\n4. Testing server-initiated stream (press Ctrl+C to stop)...")
    try:
        await asyncio.wait_for(client.test_server_initiated_stream(), timeout=10)
    except asyncio.TimeoutError:
        print("   Stream test completed (timeout)")

    print("\n5. Terminating session...")
    await client.terminate_session()


if __name__ == "__main__":
    asyncio.run(main())
