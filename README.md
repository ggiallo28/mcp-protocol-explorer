# MCP (Model Context Protocol) Exploration

This repository contains a comprehensive exploration of the Model Context Protocol (MCP), focusing on understanding its capabilities, architecture, and practical implementation patterns.

## 🎯 What is MCP?

The Model Context Protocol is a standardized way for AI applications to securely connect to external data sources and tools. It provides a unified interface for:

* **Tools**: Functions that can be called by AI models
* **Resources**: Data sources that can be read and subscribed to  
* **Prompts**: Reusable prompt templates with parameters
* **Sampling**: AI model integration capabilities

## 📁 Repository Structure

```
mcp-exploration/
├── server.py              # Enhanced MCP File System Server
├── client.py              # Autonomous MCP Client Agent
├── README.md              # This file
└── examples/              # Additional examples and demos
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- `mcp==1.6.0` package
- `uvicorn==0.34.0` (for server)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd mcp-exploration
   ```

2. **Install dependencies:**
   ```bash
   # The scripts use inline dependencies, but you can also install globally:
   pip install mcp==1.6.0 uvicorn==0.34.0
   ```

### Running the Demo

1. **Start the MCP Server:**
   ```bash
   python server.py
   ```
   The server will start on `http://localhost:8080`

2. **Run the Client (in a separate terminal):**
   ```bash
   python client.py
   ```

## 🏗️ Architecture Overview

### 🖥️ Enhanced File System Server (`server.py`)

A comprehensive MCP server implementation featuring:

#### Core Capabilities
- **File System Operations**: Directory listing, file reading, search functionality
- **Chunked File Reading**: Handle large files efficiently with configurable chunk sizes
- **Resource Templates**: Dynamic URI-based resource access
- **Client Capability Testing**: Tools to test sampling, roots, and experimental features
- **Security Features**: File type validation, size limits, path sanitization

#### Available Tools
| Tool | Description |
|------|-------------|
| `list_directory` | Browse directory contents with rich metadata |
| `search_files` | Find files containing specific text with context |
| `get_file_info` | Get detailed file information and chunk metadata |
| `check_sampling_capability` | Test LLM integration capabilities |
| `check_roots_capability` | Test filesystem access permissions |
| `check_experimental_tools_capability` | Test experimental feature support |

#### Resource Endpoints
| Resource | Purpose |
|----------|---------|
| `fs://sample` | Server information and capabilities |
| `fs://chunks/{file_path}` | File chunking metadata and links |
| `fs://chunk/{file_path}/{index}` | Individual file chunks |

#### Interactive Prompts
- **Usage Instructions**: Comprehensive server usage guide
- **Exploration Guide**: Step-by-step filesystem navigation
- **Capability Testing Guide**: Client capability testing workflows
- **Result Summary**: Dynamic file processing summaries

### 🤖 Autonomous Client Agent (`client.py`)

An intelligent MCP client that demonstrates advanced interaction patterns:

#### Key Features
- **Automatic Discovery**: Finds and catalogs all server capabilities
- **Capability Testing**: Automatically tests client-server feature compatibility
- **Intelligent Workflows**: Structured exploration and demonstration patterns
- **Progress Tracking**: Real-time operation progress reporting
- **Error Resilience**: Graceful handling of failures and partial capabilities

#### Client Capabilities
- **Sampling**: LLM integration for server-requested completions
- **Roots**: Filesystem access and navigation
- **Experimental Tools**: Advanced feature support
- **Resource Subscriptions**: Dynamic content monitoring

## 🔧 Configuration

### Server Configuration

Edit the constants in `server.py`:

```python
CHUNK_SIZE = 1024                    # Characters per chunk
MAX_FILE_SIZE = 10 * 1024 * 1024    # 10MB file size limit
ALLOWED_EXTENSIONS = {'.txt', '.py', '.js', '.json', '.md', '.yaml', '.yml', '.xml', '.html', '.css'}
```

### Client Configuration

Edit the constants in `client.py`:

```python
MCP_SERVER_URL = "http://localhost:8080/sse"  # Server endpoint
CLIENT_NAME = "Enhanced-MCP-Agent"            # Client identifier
CLIENT_VERSION = "2.0.0"                     # Client version
```

## 📚 Usage Examples

### Basic File Operations

```python
# List directory contents
await session.call_tool("list_directory", {"directory_path": "/path/to/dir"})

# Search for files containing text
await session.call_tool("search_files", {
    "root_path": "/project", 
    "search_text": "function_name",
    "max_results": 10
})

# Get detailed file information
await session.call_tool("get_file_info", {"file_path": "/path/to/file.txt"})
```

### Resource Access

```python
# Read file chunking metadata
data, content = await session.read_resource("fs://chunks/large_file.txt")

# Read specific chunk
chunk_data, chunk_content = await session.read_resource("fs://chunk/large_file.txt/0")

# Read server information
info, data = await session.read_resource("fs://sample")
```

### Capability Testing

```python
# Test sampling capability
result = await session.call_tool("check_sampling_capability", {
    "prompt": "Test message for LLM"
})

# Test roots capability  
result = await session.call_tool("check_roots_capability", {})

# Test experimental tools
result = await session.call_tool("check_experimental_tools_capability", {})
```

### Using Prompts

```python
# Get usage instructions
result = await session.get_prompt("usage_instructions", {})

# Get exploration guide
result = await session.get_prompt("exploration_guide", {})

# Get capability testing guide
result = await session.get_prompt("capability_testing_guide", {})
```

## 🎨 Design Principles

### Autonomous Agent Architecture

The client is designed as an **autonomous agent** that:

1. **Discovers** server capabilities automatically
2. **Tests** client-server compatibility
3. **Adapts** behavior based on available features  
4. **Executes** intelligent workflows
5. **Reports** progress and results clearly

### Modular Resource Management

Resources, tools, and prompts are treated uniformly:

| Element | Exposed As | Called By LLM As | Executed Via |
|---------|------------|------------------|--------------|
| Prompt | Instruction module | `use_prompt(name, args)` | `get_prompt(...)` |
| Tool | Functional action | `call_tool(name, args)` | `call_tool(...)` |
| Resource | Context/content | `read_resource(uri)` | `read_resource(...)` |

### Security & Performance

- **Input validation** on all file operations
- **File type restrictions** for security
- **Size limits** to prevent resource exhaustion  
- **Chunked processing** for large files
- **Error boundaries** with graceful degradation

## 🔍 Advanced Features

### Chunked File Reading

Large files are automatically split into manageable chunks:

```python
# Get chunk metadata
chunks_info = await session.read_resource("fs://chunks/large_file.py")
# Returns: total_chunks, chunk_size, file_size, chunk_links[]

# Read individual chunks
for i in range(chunks_info['total_chunks']):
    chunk = await session.read_resource(f"fs://chunk/large_file.py/{i}")
```

### Dynamic Capability Testing

The system tests and adapts to different client configurations:

```python
# Client automatically discovers what's supported
capabilities = await client.test_client_capabilities()
# Returns: {'sampling': True, 'roots': False, 'experimental_tools': True}

# Workflows adapt based on capabilities
if capabilities['sampling']:
    # Use LLM integration features
    pass
else:
    # Fallback to basic functionality
    pass
```

### Progress Tracking

Long-running operations report progress:

```python
# Server can send progress updates
await session.send_progress_notification(
    progress_token="file-processing",
    progress=0.7,
    total=1.0
)
```

## 🧪 Testing & Development

### Running Tests

The client includes comprehensive demonstration modes:

```bash
# Run full capability demo
python client.py

# The demo will:
# 1. Test server connectivity
# 2. Discover all capabilities
# 3. Test client-server compatibility
# 4. Demonstrate file operations
# 5. Show resource access patterns
# 6. Execute prompt templates
```

### Adding New Features

#### Adding Server Tools

```python
@mcp.tool()
def my_new_tool(param1: str, param2: int) -> str:
    """Description of what the tool does"""
    # Implementation here
    return result
```

#### Adding Resource Endpoints

```python
@mcp.resource("fs://my-resource/{param}")
def get_my_resource(param: str) -> dict:
    """Resource description"""
    return {"data": f"Dynamic content for {param}"}
```

#### Adding Prompts

```python
@mcp.prompt()
def my_prompt_template(arg1: str) -> str:
    """Prompt description"""
    return f"Generated prompt with {arg1}"
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

*Built with ❤️ for exploring the future of AI-tool integration*
