#!/bin/bash

# Local CI Simulation Script
# This simulates what GitHub Actions would run

set -e  # Exit on any error

echo "🚀 Running GitHub Actions CI simulation locally..."
echo

# Set environment variables like CI would
export DISABLE_VECTOR_SEARCH=true
export LOG_LEVEL=WARNING

echo "📦 Step 1: Install dependencies"
python3 -m pip install -e . > /dev/null 2>&1
echo "✅ Dependencies installed"

echo "🧪 Step 2: Run basic validation tests"
python3 -m pytest tests/test_basic_validation.py -v --tb=short
echo "✅ Basic validation tests passed"

echo "🏗️ Step 3: Test Docker build"
docker build -t jenkins-mcp-test . > /dev/null 2>&1
echo "✅ Docker build successful"

echo "📋 Step 4: Validate package installation"
python3 -c "import mcp_server; print('✅ Package imports successfully')"
python3 -c "from mcp_server.server import main; print('✅ Server module imports successfully')" > /dev/null 2>&1

echo "🎯 Step 5: Run framework design validation"
python3 -m pytest tests/mcp_integration/test_simple_validation.py::TestSimpleValidation::test_framework_design_principles \
                  tests/mcp_integration/test_simple_validation.py::TestSimpleValidation::test_pytest_configuration \
                  -v --tb=short
echo "✅ Framework design validation passed"

echo
echo "🎉 All CI checks passed! ✅"
echo
echo "📊 Summary:"
echo "  ✅ Package structure validation"
echo "  ✅ Import tests"
echo "  ✅ Docker build"
echo "  ✅ Framework design validation"
echo "  ✅ Configuration handling"
echo
echo "🚀 Ready for GitHub Actions deployment!"