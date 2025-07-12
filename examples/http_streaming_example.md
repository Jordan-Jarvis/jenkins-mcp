# HTTP Streaming Example

This example demonstrates how to use the Jenkins MCP server with HTTP streaming transport.

## Starting the Server

### Local Development

```bash
# Start server with streamable-http transport (requires config file)
python3 -m mcp_server.server --transport streamable-http --port 8000 --config config/mcp-config.yml
```

### Docker

```bash
# Using docker-compose with HTTP streaming profile
# Configure Jenkins credentials in config/mcp-config.yml first
docker-compose --profile http-streaming up -d

# Or run directly with docker (mount config file)
docker run -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_PORT=8000 \
  jenkins-mcp-enterprise-server:latest \
  --config config/mcp-config.yml
```

## Client Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "jenkins-mcp-enterprise-streaming": {
      "type": "streamable-http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Testing with cURL

```bash
# 1. Initialize session
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'

# Extract the Mcp-Session-Id from response headers

# 2. List available tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Mcp-Session-Id: <session-id-from-step-1>" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'

# 3. Call a tool with SSE streaming
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: <session-id-from-step-1>" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "diagnose_build_failure",
      "arguments": {
        "job_name": "my-pipeline",
        "build_number": 123
      }
    }
  }'
```

### Python Client Example

```python
import httpx
import asyncio
import json

async def test_streaming():
    base_url = "http://localhost:8000"
    session_id = None
    
    async with httpx.AsyncClient() as client:
        # Initialize
        response = await client.post(
            f"{base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "python-client",
                        "version": "1.0.0"
                    }
                }
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        session_id = response.headers.get("Mcp-Session-Id")
        print(f"Session ID: {session_id}")
        
        # Call tool with streaming
        async with client.stream(
            "POST",
            f"{base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "diagnose_build_failure",
                    "arguments": {
                        "job_name": "my-pipeline",
                        "build_number": 123
                    }
                }
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": "2025-06-18"
            }
        ) as response:
            if response.headers.get("content-type") == "text/event-stream":
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        print(f"Received: {data}")

asyncio.run(test_streaming())
```

## Features

### Session Management

- Server automatically assigns session IDs during initialization
- Session IDs must be included in all subsequent requests
- Sessions can be terminated with DELETE request

### Streaming Responses

- Server detects when client accepts `text/event-stream`
- Long-running operations return SSE streams
- Each event includes JSON-RPC messages

### Protocol Version

- Server supports protocol version negotiation
- Default version: 2025-06-18
- Include `MCP-Protocol-Version` header in requests

### Server-Initiated Messages

- Connect to GET endpoint for server notifications
- Supports resumable streams with `Last-Event-ID`
- Keep-alive events maintain connection

## Advantages of HTTP Streaming

1. **Firewall Friendly**: Works through standard HTTP/HTTPS ports
2. **Load Balancer Compatible**: Can be deployed behind reverse proxies
3. **Stateful Sessions**: Maintains context across requests
4. **Streaming Support**: Efficient for long-running operations
5. **Standard Protocol**: Uses standard HTTP and SSE specifications