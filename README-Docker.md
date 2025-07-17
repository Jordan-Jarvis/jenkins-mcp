# Jenkins MCP Enterprise Server - Docker Deployment

This directory contains Docker and Docker Compose configurations for running the Jenkins MCP Enterprise Server stack.

## Quick Start

### 1. Start the Stack
```bash
./start-jenkins_mcp_enterprise.sh
```

### 2. Access Services
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **MCP Proxy SSE Endpoint**: http://localhost:3006/sse
- **MCP Proxy Messages**: http://localhost:3006/message

## Architecture

The Docker stack includes:
- **Qdrant**: Vector database for semantic search
- **Jenkins MCP Enterprise Server**: Main MCP server with Jenkins integration
- **MCP Proxy**: HTTP-to-MCP bridge for web clients

## Configuration Files

- `docker-compose.mcp.yml` - Main Docker Compose configuration
- `Dockerfile.jenkins_mcp_enterprise` - Jenkins MCP Enterprise server container
- `Dockerfile.mcp-proxy` - MCP proxy container
- `mcpconfig.docker.json` - MCP proxy configuration for Docker
- `start-jenkins_mcp_enterprise.sh` - Startup script

## Manual Commands

### Start Services
```bash
docker-compose -f docker-compose.mcp.yml up -d
```

### View Logs
```bash
# All services
docker-compose -f docker-compose.mcp.yml logs -f

# Specific service
docker-compose -f docker-compose.mcp.yml logs -f jenkins_mcp_enterprise-server
docker-compose -f docker-compose.mcp.yml logs -f mcp-proxy
docker-compose -f docker-compose.mcp.yml logs -f qdrant
```

### Stop Services
```bash
docker-compose -f docker-compose.mcp.yml stop
```

### Stop and Remove Containers
```bash
docker-compose -f docker-compose.mcp.yml down
```

### Remove Everything Including Volumes
```bash
docker-compose -f docker-compose.mcp.yml down -v
```

## System Service (Auto-start on Boot)

### Install System Service
```bash
# Copy service file
sudo cp jenkins_mcp_enterprise.service /etc/systemd/system/

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable jenkins_mcp_enterprise.service

# Start service
sudo systemctl start jenkins_mcp_enterprise.service
```

### Manage System Service
```bash
# Check status
sudo systemctl status jenkins_mcp_enterprise.service

# Start/stop/restart
sudo systemctl start jenkins_mcp_enterprise.service
sudo systemctl stop jenkins_mcp_enterprise.service
sudo systemctl restart jenkins_mcp_enterprise.service

# View logs
sudo journalctl -u jenkins_mcp_enterprise.service -f
```

### Uninstall System Service
```bash
# Stop and disable service
sudo systemctl stop jenkins_mcp_enterprise.service
sudo systemctl disable jenkins_mcp_enterprise.service

# Remove service file
sudo rm /etc/systemd/system/jenkins_mcp_enterprise.service
sudo systemctl daemon-reload
```

## Health Checks

All services include health checks:
- **Qdrant**: `curl http://localhost:6333/health`
- **Jenkins MCP Enterprise Server**: Python import test
- **MCP Proxy**: `curl http://localhost:3006/sse`

## Troubleshooting

### Service Won't Start
```bash
# Check Docker is running
docker info

# Check service logs
docker-compose -f docker-compose.mcp.yml logs

# Check individual container
docker logs jenkins_mcp_enterprise-server
```

### Configuration Issues
```bash
# Validate config file
python3 -c "import yaml; yaml.safe_load(open('config/mcp-config.yml'))"

# Test MCP server manually
docker run --rm -it jenkins_mcp_enterprise-server python3 -m jenkins_mcp_enterprise.server --help
```

### Port Conflicts
If ports 3006 or 6333 are in use, modify `docker-compose.mcp.yml`:
```yaml
ports:
  - "3007:3006"  # Change external port
```

## Environment Variables

Key environment variables in Docker Compose:
- `QDRANT_HOST=http://qdrant:6333` - Qdrant connection
- `CACHE_DIR=/tmp/mcp-jenkins` - Cache directory
- `LOG_LEVEL=INFO` - Logging level

## Volumes

- `qdrant_data` - Persistent Qdrant vector storage
- `jenkins_mcp_enterprise_cache` - Jenkins log cache
- `./config:/app/config:ro` - Configuration files (read-only)

## Networking

All services run on the `jenkins_mcp_enterprise-network` Docker network, allowing internal communication while exposing only necessary ports to the host.