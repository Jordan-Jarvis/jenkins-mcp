#!/bin/bash
# Start development environment with Qdrant

echo "🚀 Starting Jenkins MCP Enterprise Server Development Environment"
echo "======================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "📦 Starting Qdrant vector database..."
# docker-compose up -d qdrant

# Wait for Qdrant to be ready
echo "⏳ Waiting for Qdrant to be ready..."
RETRIES=30
while [ $RETRIES -gt 0 ]; do
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo "✅ Qdrant is ready!"
        break
    fi
    echo "   Still waiting for Qdrant..."
    sleep 2
    RETRIES=$((RETRIES-1))
done

if [ $RETRIES -eq 0 ]; then
    echo "❌ Qdrant failed to start within 60 seconds"
    docker-compose logs qdrant
    exit 1
fi

echo ""
echo "🎉 Development environment is ready!"
echo "====================================="
echo "📊 Qdrant API:       http://localhost:6333"
echo "🖥️  Qdrant Dashboard: http://localhost:6333/dashboard"
echo "📋 Health Check:     curl http://localhost:6333/health"
echo ""
echo "📁 Vector Data Storage: Docker volume 'qdrant_data'"
echo ""
echo "To stop the environment:"
echo "  docker-compose down"
echo ""
echo "To stop and remove data:"
echo "  docker-compose down -v"