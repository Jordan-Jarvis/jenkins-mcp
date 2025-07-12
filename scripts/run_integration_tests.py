#!/usr/bin/env python3
"""Run MCP integration tests with proper setup"""

import subprocess
import sys
import os
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run MCP integration tests")
    parser.add_argument(
        "--performance", action="store_true", help="Run performance tests only"
    )
    parser.add_argument(
        "--real-jenkins", action="store_true", help="Run tests against real Jenkins"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Set up test environment
    env = os.environ.copy()
    env["MCP_TEST_MODE"] = "1"

    if args.debug:
        env["LOG_LEVEL"] = "DEBUG"
    else:
        env["LOG_LEVEL"] = "INFO"

    # Disable vector search for tests (since it can hang)
    env["DISABLE_VECTOR_SEARCH"] = "true"

    # Set cache directory for tests
    env["CACHE_DIR"] = "/tmp/mcp-jenkins-test"

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Test selection
    if args.performance:
        cmd.extend(["-m", "performance", "tests/mcp_integration/"])
    elif args.real_jenkins:
        cmd.extend(["-m", "real_jenkins", "tests/mcp_integration/"])
    else:
        cmd.extend(["tests/mcp_integration/", "-m", "not real_jenkins"])

    # Output options
    if args.verbose:
        cmd.extend(["-v", "-s"])
    else:
        cmd.extend(["--tb=short"])

    # Coverage options
    if args.coverage:
        cmd.extend(
            [
                "--cov=mcp_server",
                "--cov-report=html:test-results/coverage",
                "--cov-report=term-missing",
                "--cov-report=xml:test-results/coverage.xml",
            ]
        )

    # Additional options
    cmd.extend(["--durations=10", "--junitxml=test-results/junit.xml"])

    # Ensure test results directory exists
    test_results_dir = Path("test-results")
    test_results_dir.mkdir(exist_ok=True)

    print(f"Running command: {' '.join(cmd)}")
    print(f"Environment variables:")
    for key, value in env.items():
        if key.startswith(("MCP_", "LOG_", "DISABLE_", "CACHE_")):
            print(f"  {key}={value}")
    print()

    # Run the tests
    result = subprocess.run(cmd, env=env)

    # Print results summary
    if result.returncode == 0:
        print("\n✅ All tests passed!")
        if args.coverage:
            print(f"📊 Coverage report: test-results/coverage/index.html")
    else:
        print(f"\n❌ Tests failed with exit code {result.returncode}")
        print(f"📋 Test report: test-results/junit.xml")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
