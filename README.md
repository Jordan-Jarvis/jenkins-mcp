# Jenkins MCP Server

A Model Context Protocol (MCP) server that enables AI assistants to interact with Jenkins through standardized tools.

## Features

- **Multi-Jenkins Support**: Connect to multiple Jenkins instances with automatic routing
- **Pipeline Management**: Trigger builds, monitor status, and retrieve detailed information
- **Log Analysis**: Stream and analyze massive pipeline logs (10+ GB) with intelligent processing
- **Hierarchical Discovery**: Navigate complex multi-level pipeline structures using wfapi
- **Smart Search**: Pattern-based grep and semantic search for log content
- **Diagnostics**: AI-powered failure analysis with configurable parameters (bundled defaults included)
- **Performance**: Parallel processing for fast analysis of large pipelines
- **HTTP Streaming**: Native support for MCP's streamable-http transport with SSE
- **Session Management**: Stateful sessions with automatic ID assignment and tracking
- **Protocol Versioning**: Full support for MCP protocol version negotiation

## Required Jenkins Plugins

For full functionality, the following Jenkins plugins are required:

### **Essential Plugins:**
- **Pipeline** (`workflow-aggregator`) - Core pipeline functionality
- **Pipeline: API** (`workflow-api`) - Required for wfapi endpoints used in sub-build discovery

### **Recommended Plugins:**
- **Pipeline: Stage View** (`pipeline-stage-view`) - Enhanced pipeline visualization
- **Pipeline: Job** (`workflow-job`) - Pipeline job types

The MCP server uses the Jenkins Tree API and wfapi for reliable sub-build discovery without requiring Blue Ocean.

## Quick Start

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Jenkins server with API access
- Jenkins API token (generate from your Jenkins user profile)

### Installation

#### Option 1: Development Installation (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd jenkins-mcp

# Install dependencies
python3 -m pip install -e .

# Start development environment
./scripts/start_dev_environment.sh
```

#### Option 2: Install from PyPI (Coming Soon)

```bash
# Install the latest stable release (will be available in future release)
pip install jenkins-mcp-server

# Run immediately with your Jenkins credentials
jenkins-mcp-server
```

The PyPI package will include all necessary diagnostic configurations bundled - no additional setup required beyond Jenkins credentials.

#### Option 3: Docker Installation (Production)

```bash
# Clone repository
git clone <repository-url>
cd jenkins-mcp

# Install dependencies
python3 -m pip install -e .

# Start development environment
./scripts/start_dev_environment.sh
```

### Configuration

All Jenkins instances must be configured using the YAML configuration file. Create a `config/mcp-config.yml` file:

#### Single Jenkins Instance

```yaml
# config/mcp-config.yml
jenkins_instances:
  my-jenkins:
    url: "https://your-jenkins-instance.com"
    username: "your.username@domain.com"
    token: "your-api-token"
    display_name: "My Jenkins Server"
    description: "Primary Jenkins instance"
    timeout: 30
    verify_ssl: true

settings:
  fallback_instance: "my-jenkins"
  enable_health_checks: true
  health_check_interval: 300

# Vector search configuration (optional)
vector:
  disable_vector_search: false
  host: "http://localhost:6333"
  collection_name: "jenkins-logs"
  embedding_model: "all-MiniLM-L6-v2"
  chunk_size: 50
  chunk_overlap: 5
  top_k_default: 5
  timeout: 30

# Cache configuration
cache:
  cache_dir: "/tmp/mcp-jenkins"
  max_size_mb: 1000
  retention_days: 7
  compression: true

# Cleanup configuration
cleanup:
  interval_hours: 24
  retention_days: 7
  max_concurrent: 5
```

#### Multiple Jenkins Instances

```yaml
# config/mcp-config.yml
jenkins_instances:
  prod-jenkins:
    url: "https://jenkins-prod.example.com"
    username: "user@example.com"
    token: "your-prod-token"
    display_name: "Production Jenkins"
    description: "Production environment"
    timeout: 30
    verify_ssl: true
    
  dev-jenkins:
    url: "https://jenkins-dev.example.com"
    username: "user@example.com"
    token: "your-dev-token"
    display_name: "Development Jenkins"
    description: "Development environment"
    timeout: 30
    verify_ssl: true

# Default instance for backward compatibility
default_instance:
  id: "default"
  url: "https://jenkins.example.com"
  username: "user@example.com"
  token: "fallback-token"
  display_name: "Default Jenkins"

settings:
  fallback_instance: "prod-jenkins"
  enable_health_checks: true
  health_check_interval: 300
  auto_discover_instances: false

# Vector search configuration
vector:
  disable_vector_search: false
  host: "http://localhost:6333"
  collection_name: "jenkins-logs"
  embedding_model: "all-MiniLM-L6-v2"
  chunk_size: 50
  chunk_overlap: 5
  top_k_default: 5
  timeout: 30

# Cache configuration
cache:
  cache_dir: "/tmp/mcp-jenkins"
  max_size_mb: 1000
  retention_days: 7
  compression: true

# Server configuration
server:
  transport: "stdio"
  log_level: "INFO"
  log_file: ""

# Cleanup configuration
cleanup:
  interval_hours: 24
  retention_days: 7
  max_concurrent: 5
```

Then run with:
```bash
python3 -m mcp_server.server --config config/mcp-config.yml
```

#### Configuration Sections Explained

**Jenkins Instances:**
- `jenkins_instances`: Define multiple Jenkins servers with credentials
- `default_instance`: Fallback instance for backward compatibility
- `settings.fallback_instance`: Which instance to use when none specified

**Vector Search (AI-powered log analysis):**
- `vector.disable_vector_search`: Set to `true` to disable vector features
- `vector.host`: Qdrant vector database URL (requires running Qdrant)
- `vector.collection_name`: Name for the log embeddings collection
- `vector.embedding_model`: SentenceTransformer model for text embeddings
- `vector.chunk_size`: Text chunk size for vectorization (default: 50)
- `vector.chunk_overlap`: Overlap between chunks (default: 5)
- `vector.top_k_default`: Default number of results to return (default: 5)
- `vector.timeout`: Request timeout for Qdrant operations (default: 30)

**Cache Management:**
- `cache.cache_dir`: Directory for storing downloaded build logs
- `cache.max_size_mb`: Maximum cache size before cleanup
- `cache.retention_days`: How long to keep cached logs
- `cache.compression`: Enable gzip compression for cached files

**Automatic Cleanup:**
- `cleanup.interval_hours`: How often to run cleanup (default: 24 hours)
- `cleanup.retention_days`: Delete logs older than this (default: 7 days)
- `cleanup.max_concurrent`: Maximum parallel cleanup operations

**Health Monitoring:**
- `settings.enable_health_checks`: Monitor Jenkins instance availability
- `settings.health_check_interval`: Seconds between health checks

For a complete example with all options, see `config/mcp-config.example.yml`.

#### Diagnostic Configuration (Optional)

The server includes intelligent build failure diagnostics with configurable parameters. The default bundled configuration works out-of-the-box, but you can customize diagnostic behavior:

**Use defaults (recommended):**
```bash
python3 -m mcp_server.server --config config/mcp-config.yml
```

**Override with custom parameters:**
```bash
# Method 1: Command line argument
python3 -m mcp_server.server --config config/mcp-config.yml --diagnostic-config /path/to/custom-diagnostic-parameters.yml

# Method 2: Environment variable
export JENKINS_MCP_DIAGNOSTIC_CONFIG="/path/to/custom-diagnostic-parameters.yml"
python3 -m mcp_server.server --config config/mcp-config.yml

# Method 3: Project config directory override
cp mcp_server/diagnostic_config/diagnostic-parameters.yml config/diagnostic-parameters.yml
# Edit config/diagnostic-parameters.yml as needed
python3 -m mcp_server.server --config config/mcp-config.yml
```

The diagnostic configuration controls:
- Semantic search patterns for failure analysis
- Error pattern recognition rules
- Recommendation generation logic
- Build processing limits and timeouts
- Display formatting and output settings

See `config/README-diagnostic-config.md` for detailed configuration options.

### Running the Server

#### Development Mode (Local Python)

**Standard I/O Transport (default):**
```bash
# Start MCP server locally with stdio transport
python3 -m mcp_server.server --config config/mcp-config.yml

# Or with MCP Inspector for testing
npx @modelcontextprotocol/inspector python3 -m mcp_server.server --config config/mcp-config.yml
```

**HTTP Streaming Transport (new):**
```bash
# Start server with streamable-http transport on port 8000
python3 -m mcp_server.server --transport streamable-http --port 8000 --config config/mcp-config.yml

# Custom host and port
python3 -m mcp_server.server --transport streamable-http --host 127.0.0.1 --port 3000 --config config/mcp-config.yml

# With custom diagnostic configuration
python3 -m mcp_server.server --transport streamable-http --port 8000 \
  --config config/mcp-config.yml --diagnostic-config /path/to/custom-diagnostic-parameters.yml

# Test with curl
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

**Server-Sent Events (SSE) Transport:**
```bash
# Start server with SSE transport
python3 -m mcp_server.server --transport sse --port 8000 --config config/mcp-config.yml

# The server will handle both POST requests and SSE streams
```

#### Production Mode (Docker - Recommended)

**Standard I/O Mode (default):**
```bash
# 1. Configure your Jenkins credentials in config/mcp-config.yml
# See Configuration section above for examples

# 2. Start the MCP server stack
docker-compose up -d

# 3. Check server health
docker-compose logs jenkins-mcp-server

# 4. Stop the stack
docker-compose down
```

**HTTP Streaming Mode (native HTTP transport):**
```bash
# 1. Configure your Jenkins credentials in config/mcp-config.yml

# 2. Start with HTTP streaming profile
docker-compose --profile http-streaming up -d

# The server will be available at http://localhost:8000
curl http://localhost:8000/health

# Test initialization
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

#### HTTP Proxy Mode (Legacy)

For compatibility with older MCP clients:

```bash
# 1. Configure your Jenkins credentials in config/mcp-config.yml

# 2. Start with HTTP proxy enabled
docker-compose --profile http-proxy up -d

# The MCP server will be available at http://localhost:8080
curl http://localhost:8080/health
```

## Usage

### Available Tools

- `trigger_build` - Start new builds with parameters
- `trigger_build_async` - Start builds without waiting for completion
- `get_jenkins_job_parameters` - Get job parameter definitions
- `get_log_context` - Retrieve specific log sections
- `filter_errors_grep` - Smart error pattern matching in logs
- `ripgrep_search` - Fast regex search in build logs
- `navigate_log` - Jump to specific log sections
- `semantic_search` - AI-powered log content search
- `trigger_build_with_subs` - List sub-build statuses
- `diagnose_build_failure` - Comprehensive failure analysis with sub-build discovery

### Client Configuration Examples

#### Claude Desktop (PyPI Installation)

Add to your Claude Desktop configuration (`~/.claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "jenkins": {
      "command": "jenkins-mcp-server",
      "args": [
        "--config",
        "config/mcp-config.yml"
      ]
    }
  }
}
```

#### Claude Desktop (Development Mode)

For development installations:

```json
{
  "mcpServers": {
    "jenkins": {
      "command": "python3",
      "args": [
        "-m", 
        "mcp_server.server",
        "--config",
        "config/mcp-config.yml"
      ]
    }
  }
}
```


#### HTTP Streaming Mode (New)

For native HTTP streaming transport:

```json
{
  "mcpServers": {
    "jenkins-http": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Security Note:** HTTP streaming mode does not currently implement authentication. For production use, ensure the server is protected by network-level security (firewall, VPN, or reverse proxy with authentication).

#### SSE Mode

For Server-Sent Events transport:

```json
{
  "mcpServers": {
    "jenkins-sse": {
      "type": "sse", 
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Security Note:** SSE mode does not currently implement authentication. For production use, ensure the server is protected by network-level security (firewall, VPN, or reverse proxy with authentication).

## Architecture

The server is built with a modular architecture:

- **Multi-Jenkins Manager**: Automatic routing between multiple Jenkins instances
- **Connection Manager**: Jenkins authentication and HTTP sessions
- **Build Manager**: Build lifecycle management
- **Log Fetcher**: Streaming log retrieval for massive files
- **Sub-build Discoverer**: Hierarchical pipeline discovery using wfapi
- **Tool Factory**: Dynamic tool registration with schema validation
- **Cache Manager**: Intelligent log caching for performance
- **Diagnostic Tools**: AI-powered failure analysis with parallel processing

## Testing

```bash
# Run integration tests
python3 -m pytest tests/mcp_integration/ -v

# Test with MCP Inspector
npx @modelcontextprotocol/inspector --cli python3 -m mcp_server.server

# Test specific tool
npx @modelcontextprotocol/inspector --cli -- python3 -m mcp_server.server \
  --method tools/call \
  --tool-name diagnose_build_failure \
  --tool-arg job_name=my-job \
  --tool-arg build_number=123 \
  --tool-arg jenkins_url=https://jenkins.example.com
```

## Troubleshooting

### Configuration Issues

**Problem**: `ConfigurationError: Transport must be one of: stdio, streamable-http, sse`  
**Solution**: Use `streamable-http` instead of `http` in configuration files.

**Problem**: `ModuleNotFoundError: No module named 'mcp'`  
**Solution**: Install missing dependencies: `pip install modelcontextprotocol`

**Problem**: Vector search not working  
**Solution**: 
1. Check if Qdrant is running: `curl http://localhost:6333/health`
2. Start Qdrant: `./scripts/start_dev_environment.sh`
3. Or disable vector search: `vector.disable_vector_search: true` in config

### Docker Issues

**Problem**: Qdrant connection failures in Docker  
**Solution**: Use `QDRANT_HOST=http://qdrant:6333` (not localhost) in Docker environment.

**Problem**: Jenkins connection timeouts  
**Solution**: 
1. Verify Jenkins URL is accessible from container
2. Check firewall settings
3. Increase timeout in configuration: `timeout: 60`

### Authentication Issues

**Problem**: Jenkins authentication failures  
**Solution**:
1. Generate new API token from Jenkins user profile
2. Verify username format (usually email address)
3. Test credentials: `curl -u username:token https://jenkins.example.com/api/json`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development instructions and architectural decisions.

## License

MIT License - see LICENSE file for details