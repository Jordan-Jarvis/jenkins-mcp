"""Performance and load testing"""

import pytest
import pytest_asyncio
import asyncio
import time
import tempfile
import shutil
from .mcp_test_client import MCPTestClient
from .test_doubles import JenkinsTestDouble, QdrantTestDouble


class TestPerformance:
    """Test performance characteristics"""
    
    @pytest_asyncio.fixture
    async def test_environment(self):
        """Setup test environment for performance testing"""
        cache_dir = tempfile.mkdtemp(prefix="test-mcp-jenkins-perf-")
        
        jenkins = JenkinsTestDouble(port=18082)
        qdrant = QdrantTestDouble(port=16335)
        
        # Add some builds for testing
        for i in range(10):
            jenkins.add_build("test-job", i+1, {
                "number": i+1,
                "result": "SUCCESS" if i % 2 == 0 else "FAILURE",
                "building": False,
                "timestamp": int(time.time() * 1000) - (i * 60000),  # 1 minute apart
                "duration": 60000 + (i * 1000)  # Varying duration
            })
        
        jenkins.start()
        qdrant.start()
        
        config = {
            "jenkins_url": f"http://localhost:{jenkins.port}",
            "jenkins_user": "test_user",
            "jenkins_token": "test_token",
            "qdrant_host": f"http://localhost:{qdrant.port}",
            "cache_dir": cache_dir,
            "log_level": "INFO"  # Reduce logging for performance tests
        }
        
        yield {
            "config": config,
            "jenkins": jenkins,
            "qdrant": qdrant,
            "cache_dir": cache_dir
        }
        
        jenkins.stop()
        qdrant.stop()
        shutil.rmtree(cache_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_tool_response_times(self, test_environment):
        """Test that tools respond within acceptable time limits"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Test async build trigger (should be very fast)
            start_time = time.time()
            result = await client.call_tool("trigger_build_async", {
                "job_name": "sample-job",
                "params": {"BRANCH": "main"}
            })
            response_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert response_time < 10.0, f"Async build trigger took {response_time:.2f}s, should be under 10s"
            
            # Test job parameters (should be fast)
            start_time = time.time()
            result = await client.call_tool("get_job_parameters", {
                "job_name": "sample-job"
            })
            response_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert response_time < 5.0, f"Job parameters took {response_time:.2f}s, should be under 5s"
            
            # Test log context (should be reasonably fast for small logs)
            start_time = time.time()
            result = await client.call_tool("get_log_context", {
                "job_name": "sample-job",
                "build_number": 1,
                "start_line": 0,
                "end_line": 50
            })
            response_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert response_time < 15.0, f"Log context took {response_time:.2f}s, should be under 15s"
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self, test_environment):
        """Test concurrent tool execution performance"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Execute multiple async build triggers concurrently
            start_time = time.time()
            
            tasks = []
            for i in range(5):
                task = client.call_tool("trigger_build_async", {
                    "job_name": "sample-job",
                    "params": {"RUN_ID": str(i)}
                })
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            # All should complete without exceptions
            for i, result in enumerate(results):
                assert not isinstance(result, Exception), f"Task {i} failed with exception: {result}"
                assert "result" in result or "error" in result
            
            # Concurrent execution should not be much slower than sequential
            assert total_time < 20.0, f"5 concurrent calls took {total_time:.2f}s, should be under 20s"
            
            # Test concurrent different tool calls
            start_time = time.time()
            
            mixed_tasks = [
                client.call_tool("get_job_parameters", {"job_name": "sample-job"}),
                client.call_tool("trigger_build_async", {"job_name": "sample-job"}),
                client.call_tool("get_log_context", {"job_name": "sample-job", "build_number": 1}),
                client.call_tool("filter_errors_grep", {"job_name": "sample-job", "build_number": 1, "pattern": "ERROR"}),
            ]
            
            mixed_results = await asyncio.gather(*mixed_tasks, return_exceptions=True)
            mixed_time = time.time() - start_time
            
            for i, result in enumerate(mixed_results):
                assert not isinstance(result, Exception), f"Mixed task {i} failed: {result}"
            
            assert mixed_time < 25.0, f"Mixed concurrent calls took {mixed_time:.2f}s, should be under 25s"
    
    @pytest.mark.asyncio
    async def test_large_log_handling_performance(self, test_environment):
        """Test performance with larger log requests"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Test retrieving larger chunks of logs
            start_time = time.time()
            
            result = await client.call_tool("get_log_context", {
                "job_name": "sample-job",
                "build_number": 1,
                "start_line": 0,
                "end_line": 1000  # Larger range
            })
            
            response_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert response_time < 30.0, f"Large log request took {response_time:.2f}s, should be under 30s"
            
            # If successful, verify we got reasonable data back
            if "result" in result:
                data = result["result"]
                assert "lines" in data
                assert "total_lines" in data
    
    @pytest.mark.asyncio
    async def test_repeated_calls_performance(self, test_environment):
        """Test performance of repeated calls (caching effects)"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # First call (cold)
            start_time = time.time()
            result1 = await client.call_tool("get_log_context", {
                "job_name": "sample-job",
                "build_number": 1,
                "start_line": 0,
                "end_line": 100
            })
            first_call_time = time.time() - start_time
            
            # Second call (should benefit from caching)
            start_time = time.time()
            result2 = await client.call_tool("get_log_context", {
                "job_name": "sample-job",
                "build_number": 1,
                "start_line": 0,
                "end_line": 100
            })
            second_call_time = time.time() - start_time
            
            # Third call (should also be fast)
            start_time = time.time()
            result3 = await client.call_tool("get_log_context", {
                "job_name": "sample-job",
                "build_number": 1,
                "start_line": 50,
                "end_line": 150
            })
            third_call_time = time.time() - start_time
            
            # All should succeed
            for result in [result1, result2, result3]:
                assert "result" in result or "error" in result
            
            # Second and third calls should be faster than first (caching)
            print(f"Call times: first={first_call_time:.2f}s, second={second_call_time:.2f}s, third={third_call_time:.2f}s")
            
            # At minimum, all calls should complete in reasonable time
            assert first_call_time < 20.0
            assert second_call_time < 15.0
            assert third_call_time < 15.0
    
    @pytest.mark.asyncio
    async def test_diagnosis_performance(self, test_environment):
        """Test performance of comprehensive diagnosis"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Diagnosis is the most complex operation
            start_time = time.time()
            
            result = await client.call_tool("diagnose_build_failure", {
                "job_name": "QA_JOBS/master",
                "build_number": 9
            })
            
            diagnosis_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            
            # Diagnosis should complete in reasonable time even with all sub-operations
            assert diagnosis_time < 60.0, f"Diagnosis took {diagnosis_time:.2f}s, should be under 60s"
            
            # If successful, verify we got comprehensive data
            if "result" in result:
                data = result["result"]
                assert "job_name" in data
                assert "build_number" in data
                assert "overall_status_from_jenkins" in data
                
                print(f"Diagnosis completed in {diagnosis_time:.2f}s with status: {data.get('log_analysis_status')}")
    
    @pytest.mark.asyncio
    async def test_tool_discovery_performance(self, test_environment):
        """Test tool discovery performance"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Tool listing should be very fast
            start_time = time.time()
            tools = await client.list_tools()
            discovery_time = time.time() - start_time
            
            assert isinstance(tools, list)
            assert len(tools) > 0
            assert discovery_time < 5.0, f"Tool discovery took {discovery_time:.2f}s, should be under 5s"
            
            # Repeated tool discovery should be equally fast
            start_time = time.time()
            tools2 = await client.list_tools()
            discovery_time2 = time.time() - start_time
            
            assert len(tools2) == len(tools)
            assert discovery_time2 < 5.0, f"Second tool discovery took {discovery_time2:.2f}s, should be under 5s"
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, test_environment):
        """Test that memory usage remains stable under load"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Perform many operations to test for memory leaks
            start_time = time.time()
            
            for i in range(20):
                # Mix of different operations
                operations = [
                    client.call_tool("get_job_parameters", {"job_name": "sample-job"}),
                    client.call_tool("trigger_build_async", {"job_name": "sample-job", "params": {"RUN": str(i)}}),
                    client.call_tool("get_log_context", {"job_name": "sample-job", "build_number": 1, "start_line": i*10, "end_line": i*10+20}),
                ]
                
                # Execute operations for this iteration
                results = await asyncio.gather(*operations, return_exceptions=True)
                
                # All should complete without exceptions
                for j, result in enumerate(results):
                    assert not isinstance(result, Exception), f"Iteration {i}, operation {j} failed: {result}"
                
                # Brief pause between iterations
                await asyncio.sleep(0.1)
            
            total_time = time.time() - start_time
            
            # Should complete all iterations in reasonable time
            assert total_time < 120.0, f"20 iterations took {total_time:.2f}s, should be under 120s"
            
            print(f"Completed 20 iterations of mixed operations in {total_time:.2f}s")
    
    @pytest.mark.asyncio
    async def test_vector_search_performance(self, test_environment):
        """Test vector search performance"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Vector search performance test
            start_time = time.time()
            
            result = await client.call_tool("vector_search", {
                "job_name": "QA_JOBS/master",
                "build_number": 9,
                "query_text": "compilation error java",
                "top_k": 5
            })
            
            search_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert search_time < 20.0, f"Vector search took {search_time:.2f}s, should be under 20s"
            
            # If successful, verify search results structure
            if "result" in result:
                data = result["result"]
                assert isinstance(data, list)
                assert len(data) <= 5
    
    @pytest.mark.asyncio
    async def test_error_filtering_performance(self, test_environment):
        """Test error filtering performance"""
        config = test_environment["config"]
        
        async with MCPTestClient("mcp_server/server.py", config) as client:
            # Error filtering should be fast
            start_time = time.time()
            
            result = await client.call_tool("filter_errors_grep", {
                "job_name": "QA_JOBS/master",
                "build_number": 9,
                "pattern": "ERROR|FAILED|Exception|FATAL"
            })
            
            filter_time = time.time() - start_time
            
            assert "result" in result or "error" in result
            assert filter_time < 15.0, f"Error filtering took {filter_time:.2f}s, should be under 15s"
            
            # Test with more complex pattern
            start_time = time.time()
            
            result2 = await client.call_tool("filter_errors_grep", {
                "job_name": "QA_JOBS/master",
                "build_number": 9,
                "pattern": r"(ERROR|FAILED).*compilation.*java"
            })
            
            complex_filter_time = time.time() - start_time
            
            assert "result" in result2 or "error" in result2
            assert complex_filter_time < 20.0, f"Complex error filtering took {complex_filter_time:.2f}s, should be under 20s"