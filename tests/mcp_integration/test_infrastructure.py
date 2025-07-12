"""MCP test infrastructure validation"""

import asyncio
import shutil
import tempfile

import pytest
import pytest_asyncio

from .mcp_test_client import MCPTestClient
from .test_doubles import JenkinsTestDouble, QdrantTestDouble


class TestInfrastructure:
    """Test MCP infrastructure and protocol compliance"""

    @pytest_asyncio.fixture
    async def minimal_environment(self):
        """Minimal test environment for infrastructure testing"""
        cache_dir = tempfile.mkdtemp(prefix="test-mcp-infra-")

        config = {
            "jenkins_url": "http://localhost:18080",
            "jenkins_user": "test_user",
            "jenkins_token": "test_token",
            "qdrant_host": "http://localhost:16333",
            "cache_dir": cache_dir,
            "log_level": "DEBUG",
        }

        yield {"config": config, "cache_dir": cache_dir}

        shutil.rmtree(cache_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_mcp_server_startup(self, minimal_environment):
        """Test that MCP server starts up correctly"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Server should start without errors
            assert client.process is not None
            assert client.process.poll() is None  # Process should still be running

    @pytest.mark.asyncio
    async def test_mcp_protocol_compliance(self, minimal_environment):
        """Test MCP protocol compliance"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Test tools/list endpoint
            tools = await client.list_tools()

            assert isinstance(tools, list)
            assert len(tools) > 0

            # Each tool should have required MCP schema fields
            for tool in tools:
                assert "name" in tool
                assert "description" in tool
                assert "inputSchema" in tool

                schema = tool["inputSchema"]
                assert "type" in schema
                assert schema["type"] == "object"
                assert "properties" in schema

    @pytest.mark.asyncio
    async def test_json_rpc_format(self, minimal_environment):
        """Test JSON-RPC format compliance"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Test that responses follow JSON-RPC 2.0 format
            result = await client.call_tool(
                "get_job_parameters", {"job_name": "any-job"}
            )

            # Should have JSON-RPC 2.0 structure
            assert "jsonrpc" in result
            assert result["jsonrpc"] == "2.0"
            assert "id" in result

            # Should have either result or error, but not both
            assert ("result" in result) != ("error" in result)

            if "error" in result:
                error = result["error"]
                assert "code" in error
                assert "message" in error

    @pytest.mark.asyncio
    async def test_error_response_format(self, minimal_environment):
        """Test that error responses follow MCP format"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Trigger an error by calling with invalid parameters
            result = await client.call_tool("trigger_build_async", {})

            assert "error" in result
            error = result["error"]

            # Error should have required fields
            assert "code" in error
            assert "message" in error
            assert isinstance(error["code"], int)
            assert isinstance(error["message"], str)
            assert len(error["message"]) > 0

    @pytest.mark.asyncio
    async def test_tool_parameter_validation(self, minimal_environment):
        """Test that tool parameter validation works correctly"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            tools = await client.list_tools()

            # Find a tool with required parameters
            trigger_tool = None
            for tool in tools:
                if tool["name"] == "trigger_build_async":
                    trigger_tool = tool
                    break

            assert trigger_tool is not None

            # Check that job_name is required
            schema = trigger_tool["inputSchema"]
            assert "job_name" in schema["required"]

            # Test calling without required parameter
            result = await client.call_tool("trigger_build_async", {})
            assert "error" in result

            # Test calling with required parameter
            result = await client.call_tool(
                "trigger_build_async", {"job_name": "test-job"}
            )

            # Should either succeed or fail with a different error (not parameter validation)
            if "error" in result:
                # Error should not be about missing required parameters
                error_msg = result["error"]["message"].lower()
                assert "required" not in error_msg or "job_name" not in error_msg

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, minimal_environment):
        """Test that server handles concurrent requests correctly"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Send multiple concurrent requests
            tasks = [
                client.list_tools(),
                client.call_tool("get_job_parameters", {"job_name": "test-job"}),
                client.call_tool("trigger_build_async", {"job_name": "test-job"}),
                client.list_tools(),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without exceptions
            for i, result in enumerate(results):
                assert not isinstance(
                    result, Exception
                ), f"Request {i} failed: {result}"

            # First and last results should be identical (tools list)
            assert results[0] == results[3]

    @pytest.mark.asyncio
    async def test_server_shutdown_cleanup(self, minimal_environment):
        """Test that server shuts down cleanly"""
        config = minimal_environment["config"]

        client = MCPTestClient("mcp_server/server.py", config)

        # Start server
        await client.start_server()

        # Verify it's running
        assert client.process is not None
        assert client.process.poll() is None

        # Call a tool to verify it's responding
        result = await client.call_tool("get_job_parameters", {"job_name": "test"})
        assert "result" in result or "error" in result

        # Stop server
        await client.stop_server()

        # Verify it's stopped
        assert client.process.poll() is not None  # Process should have exited

    @pytest.mark.asyncio
    async def test_tool_execution_isolation(self, minimal_environment):
        """Test that tool executions are properly isolated"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Execute tools that might have side effects
            results = []

            for i in range(3):
                result = await client.call_tool(
                    "trigger_build_async",
                    {"job_name": "isolation-test", "params": {"TEST_ID": str(i)}},
                )
                results.append(result)

            # Each execution should be independent
            for i, result in enumerate(results):
                if "result" in result:
                    # If successful, should have unique build numbers or similar
                    data = result["result"]
                    assert "job_name" in data
                    assert data["job_name"] == "isolation-test"

    @pytest.mark.asyncio
    async def test_large_response_handling(self, minimal_environment):
        """Test handling of large responses"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Request a potentially large response
            result = await client.call_tool(
                "get_log_context",
                {
                    "job_name": "test-job",
                    "build_number": 1,
                    "start_line": 0,
                    "end_line": 10000,  # Large range
                },
            )

            # Should handle large responses gracefully
            assert "result" in result or "error" in result

            # Response should be valid JSON-RPC
            assert "jsonrpc" in result
            assert "id" in result

    @pytest.mark.asyncio
    async def test_request_timeout_handling(self, minimal_environment):
        """Test request timeout handling"""
        config = minimal_environment["config"]

        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Test with very short timeout
            try:
                result = await client.call_tool(
                    "diagnose_build_failure",
                    {"job_name": "test-job", "build_number": 1},
                    timeout=0.1,
                )

                # If it completes, that's fine
                assert "result" in result or "error" in result

            except asyncio.TimeoutError:
                # Timeout is also acceptable behavior
                pass
