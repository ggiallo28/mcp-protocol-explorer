# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp==1.6.0",
#     "uvicorn==0.34.0"
# ]
# ///

"""
Enhanced MCP File System Server

A comprehensive Model Context Protocol server that provides:
- File system navigation and search capabilities
- Chunked file reading for large files
- Client capability testing (sampling, roots, experimental tools)
- Resource templates for dynamic content
- Interactive prompts for guidance
"""

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from mcp.types import (
    CreateMessageRequestParams,
    CreateMessageResult,
    SamplingMessage,
    TextContent,
    ClientCapabilities,
    SamplingCapability,
    RootsCapability,
    Root,
)
from starlette.routing import Route
from pathlib import Path
from typing import Literal, List, Dict, Any
from mcp.server.session import ServerSession
from pydantic import BaseModel
import asyncio
import logging

# Configuration
CHUNK_SIZE = 1024
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit for reading files
ALLOWED_EXTENSIONS = {'.txt', '.py', '.js', '.json', '.md', '.yaml', '.yml', '.xml', '.html', '.css'}

# Initialize FastMCP server
mcp = FastMCP(name="EnhancedFileSystemServer")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileInfo(BaseModel):
    """Model for file information"""
    name: str
    path: str
    size: int
    is_directory: bool
    extension: str = ""


class ChunkInfo(BaseModel):
    """Model for chunk information"""
    file_path: str
    total_chunks: int
    chunk_size: int
    file_size: int
    chunks: List[str]


# ================================
# RESOURCE ENDPOINTS
# ================================

@mcp.resource("fs://sample")
def get_sample_resource() -> Dict[str, Any]:
    """Return a sample resource payload with structured data."""
    return {
        "name": "Enhanced File System Server",
        "version": "2.0.0",
        "description": "A comprehensive MCP server for file system operations with chunking support.",
        "capabilities": {
            "file_reading": "Supports chunked reading of text files",
            "directory_listing": "Browse directory contents",
            "file_search": "Search for files containing specific text",
            "client_capability_testing": "Test various MCP client capabilities"
        },
        "usage": {
            "resources": [
                "fs://sample - This sample resource",
                "fs://chunks/{file_path} - Get file chunking metadata",
                "fs://chunk/{file_path}/{chunk_index} - Read specific file chunk"
            ],
            "tools": [
                "list_directory - Browse directory contents",
                "search_files - Find files containing text",
                "get_file_info - Get detailed file information",
                "check_sampling_capability - Test LLM sampling",
                "check_roots_capability - Test filesystem access",
                "check_experimental_tools_capability - Test experimental features"
            ]
        },
        "limits": {
            "max_file_size": f"{MAX_FILE_SIZE // (1024*1024)}MB",
            "chunk_size": f"{CHUNK_SIZE} characters",
            "allowed_extensions": list(ALLOWED_EXTENSIONS)
        }
    }


@mcp.resource("fs://chunk/{file_path}/{chunk_index}")
def get_file_chunk(file_path: str, chunk_index: int) -> str:
    """Return a specific chunk from a file with enhanced error handling."""
    try:
        path = Path(file_path).resolve()
        
        # Security check - ensure file exists and is readable
        if not path.is_file():
            return f"Error: '{file_path}' is not a valid file or does not exist"
        
        # Check file extension
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return f"Error: File type '{path.suffix}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Check file size
        if path.stat().st_size > MAX_FILE_SIZE:
            return f"Error: File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        
        # Read and return chunk
        text = path.read_text(encoding='utf-8', errors='replace')
        start = chunk_index * CHUNK_SIZE
        end = start + CHUNK_SIZE
        
        if start >= len(text):
            return f"Error: Chunk {chunk_index} does not exist. File has {(len(text) + CHUNK_SIZE - 1) // CHUNK_SIZE} chunks."
        
        chunk_content = text[start:end]
        metadata = {
            "chunk_index": chunk_index,
            "start_pos": start,
            "end_pos": min(end, len(text)),
            "chunk_length": len(chunk_content),
            "is_final_chunk": end >= len(text)
        }
        
        return f"--- Chunk {chunk_index} Metadata ---\n{metadata}\n\n--- Chunk Content ---\n{chunk_content}"
        
    except UnicodeDecodeError:
        return f"Error: Cannot decode file '{file_path}' as UTF-8 text"
    except PermissionError:
        return f"Error: Permission denied reading '{file_path}'"
    except Exception as e:
        logger.error(f"Error reading chunk {chunk_index} from {file_path}: {e}")
        return f"Error reading chunk: {str(e)}"


@mcp.resource("fs://chunks/{file_path}")
def read_file_chunks(file_path: str) -> Dict[str, Any]:
    """Get comprehensive chunk info and links for a file."""
    try:
        path = Path(file_path).resolve()
        
        if not path.is_file():
            return {"error": f"'{file_path}' is not a valid file"}
        
        # Check file extension
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return {"error": f"File type '{path.suffix}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}
        
        # Get file stats
        stat_info = path.stat()
        file_size = stat_info.st_size
        
        if file_size > MAX_FILE_SIZE:
            return {"error": f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"}
        
        # Read file content
        text = path.read_text(encoding='utf-8', errors='replace')
        total_chunks = max(1, (len(text) + CHUNK_SIZE - 1) // CHUNK_SIZE)
        chunk_links = [f"fs://chunk/{file_path}/{i}" for i in range(total_chunks)]
        
        return {
            "file_path": file_path,
            "file_name": path.name,
            "file_size_bytes": file_size,
            "content_length": len(text),
            "chunk_size": CHUNK_SIZE,
            "total_chunks": total_chunks,
            "chunks": chunk_links,
            "file_info": {
                "extension": path.suffix,
                "created": stat_info.st_ctime,
                "modified": stat_info.st_mtime,
                "is_readable": True
            },
            "preview": text[:200] + "..." if len(text) > 200 else text
        }
        
    except UnicodeDecodeError:
        return {"error": f"Cannot decode file '{file_path}' as UTF-8 text"}
    except PermissionError:
        return {"error": f"Permission denied accessing '{file_path}'"}
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")
        return {"error": f"Error processing file: {str(e)}"}


# ================================
# TOOL IMPLEMENTATIONS
# ================================

@mcp.tool()
def list_directory(directory_path: str, include_hidden: bool = False) -> List[str]:
    """List the contents of a directory with detailed information."""
    try:
        path = Path(directory_path).resolve()
        
        if not path.is_dir():
            return [f"Error: '{directory_path}' is not a valid directory"]
        
        items = []
        for item_path in sorted(path.iterdir()):
            # Skip hidden files unless requested
            if not include_hidden and item_path.name.startswith('.'):
                continue
                
            try:
                stat_info = item_path.stat()
                if item_path.is_dir():
                    items.append(f"📁 {item_path.name}/")
                else:
                    size_mb = stat_info.st_size / (1024 * 1024)
                    if size_mb >= 1:
                        size_str = f"{size_mb:.1f}MB"
                    elif stat_info.st_size >= 1024:
                        size_str = f"{stat_info.st_size // 1024}KB"
                    else:
                        size_str = f"{stat_info.st_size}B"
                    
                    icon = "📄"
                    if item_path.suffix.lower() in {'.py', '.js', '.html', '.css'}:
                        icon = "💻"
                    elif item_path.suffix.lower() in {'.txt', '.md', '.json', '.yaml', '.yml'}:
                        icon = "📝"
                    
                    items.append(f"{icon} {item_path.name} ({size_str})")
            except (PermissionError, OSError):
                items.append(f"❌ {item_path.name} (access denied)")
        
        if not items:
            return [f"Directory '{directory_path}' is empty or no readable items found"]
        
        return [f"📂 Contents of '{directory_path}':"] + items
        
    except PermissionError:
        return [f"Error: Permission denied accessing '{directory_path}'"]
    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}")
        return [f"Error listing directory: {str(e)}"]


@mcp.tool()
def search_files(root_path: str, search_text: str, max_results: int = 20) -> List[str]:
    """Search for files that contain a specific string with improved results."""
    try:
        path = Path(root_path).resolve()
        
        if not path.is_dir():
            return [f"Error: '{root_path}' is not a valid directory"]
        
        matching_files = []
        searched_count = 0
        
        for file_path in path.rglob("*"):
            if len(matching_files) >= max_results:
                break
                
            if file_path.is_file() and file_path.suffix.lower() in ALLOWED_EXTENSIONS:
                try:
                    # Skip large files
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                        
                    content = file_path.read_text(encoding='utf-8', errors='replace')
                    searched_count += 1
                    
                    if search_text.lower() in content.lower():
                        # Find the line containing the search text
                        lines = content.split('\n')
                        matching_line = None
                        line_num = 0
                        
                        for i, line in enumerate(lines, 1):
                            if search_text.lower() in line.lower():
                                matching_line = line.strip()[:100]
                                line_num = i
                                break
                        
                        result = f"📄 {file_path.relative_to(path)}"
                        if matching_line:
                            result += f" (line {line_num}: {matching_line})"
                        matching_files.append(result)
                        
                except (UnicodeDecodeError, PermissionError, OSError):
                    continue
        
        if not matching_files:
            return [f"No files contain '{search_text}' in '{root_path}' (searched {searched_count} files)"]
        
        results = [f"🔍 Found {len(matching_files)} files containing '{search_text}' (searched {searched_count} files):"]
        results.extend(matching_files[:max_results])
        
        if len(matching_files) >= max_results:
            results.append(f"... (showing first {max_results} results)")
            
        return results
        
    except Exception as e:
        logger.error(f"Error searching files in {root_path}: {e}")
        return [f"Error searching files: {str(e)}"]


@mcp.tool()
def get_file_info(file_path: str) -> List[str]:
    """Get detailed information about a file."""
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return [f"Error: '{file_path}' does not exist"]
        
        stat_info = path.stat()
        info = [
            f"📄 File Information for: {path.name}",
            f"   📁 Full Path: {path}",
            f"   📊 Size: {stat_info.st_size:,} bytes ({stat_info.st_size / (1024*1024):.2f} MB)",
            f"   🏷️  Type: {'Directory' if path.is_dir() else 'File'}",
        ]
        
        if not path.is_dir():
            info.extend([
                f"   📝 Extension: {path.suffix or 'None'}",
                f"   ✅ Readable: {'Yes' if path.suffix.lower() in ALLOWED_EXTENSIONS else 'No (unsupported type)'}",
                f"   📚 Too Large: {'Yes' if stat_info.st_size > MAX_FILE_SIZE else 'No'}",
            ])
            
            # If it's a readable text file, show chunk info
            if path.suffix.lower() in ALLOWED_EXTENSIONS and stat_info.st_size <= MAX_FILE_SIZE:
                try:
                    content = path.read_text(encoding='utf-8', errors='replace')
                    total_chunks = max(1, (len(content) + CHUNK_SIZE - 1) // CHUNK_SIZE)
                    info.extend([
                        f"   📦 Content Length: {len(content):,} characters",
                        f"   🧩 Total Chunks: {total_chunks}",
                        f"   🔗 Chunk Resource: fs://chunks/{file_path}",
                    ])
                except Exception:
                    info.append("   ❌ Content: Unable to read as text")
        else:
            try:
                items = list(path.iterdir())
                dirs = sum(1 for item in items if item.is_dir())
                files = len(items) - dirs
                info.extend([
                    f"   📁 Subdirectories: {dirs}",
                    f"   📄 Files: {files}",
                    f"   📊 Total Items: {len(items)}",
                ])
            except PermissionError:
                info.append("   ❌ Contents: Permission denied")
        
        # Add timestamps
        import datetime
        modified_time = datetime.datetime.fromtimestamp(stat_info.st_mtime)
        info.append(f"   🕒 Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting file info for {file_path}: {e}")
        return [f"Error getting file information: {str(e)}"]


# ================================
# CLIENT CAPABILITY TESTING TOOLS
# ================================

@mcp.tool()
async def check_experimental_tools_capability() -> str:
    """Check if the client supports experimental advanced tools."""
    try:
        context = mcp.get_context()
        if not context:
            return "Error: No session context available."

        capability = ClientCapabilities(experimental={"advanced_tools": {}})
        is_supported = context.session.check_client_capability(capability)
        
        result = "✅ Supported" if is_supported else "❌ Not supported"
        return f"Experimental Tools Capability: {result}"
        
    except Exception as e:
        logger.error(f"Error checking experimental tools capability: {e}")
        return f"Error checking capability: {str(e)}"


@mcp.tool()
async def check_sampling_capability(prompt: str = "Hello! Please respond with a brief greeting.") -> str:
    """Request an LLM completion from the client to test sampling capability."""
    try:
        context = mcp.get_context()
        if not context:
            return "Error: No session context available."

        if not context.session.check_client_capability(
            ClientCapabilities(sampling=SamplingCapability())
        ):
            return "❌ Error: Client does not support sampling capability."

        sampling_message = SamplingMessage(
            role="user", content=TextContent(type="text", text=prompt)
        )

        response = await context.session.create_message(
            messages=[sampling_message], max_tokens=100
        )

        if response and response.content:
            return f"✅ Sampling successful! Response: '{response.content.text[:200]}'"
        else:
            return "❌ No response received from sampling request."
            
    except Exception as e:
        logger.error(f"Error in sampling capability check: {e}")
        return f"Error during sampling: {str(e)}"


@mcp.tool()
async def check_roots_capability() -> List[str]:
    """Check if the client supports roots (filesystem access)."""
    try:
        context = mcp.get_context()
        if not context:
            return ["Error: No session context available."]

        if not context.session.check_client_capability(
            ClientCapabilities(roots=RootsCapability())
        ):
            return ["❌ Error: Client does not support roots capability."]

        response = await context.session.list_roots()
        if not response or not response.roots:
            return ["❌ Error: No roots found or accessible."]

        results = [f"✅ Roots capability supported! Found {len(response.roots)} root(s):"]
        
        for i, root in enumerate(response.roots[:5], 1):  # Limit to first 5 roots
            results.append(f"   {i}. {root.name}: {root.uri}")
            
        if len(response.roots) > 5:
            results.append(f"   ... and {len(response.roots) - 5} more roots")

        return results
        
    except Exception as e:
        logger.error(f"Error during root capability check: {e}")
        return [f"Error during root capability check: {str(e)}"]


# ================================
# PROMPT TEMPLATES
# ================================

@mcp.prompt()
def result_summary_prompt(file_path: str, total_chunks: str) -> str:
    """Summarize chunking result with enhanced details."""
    try:
        chunks = int(total_chunks)
        return (
            f"📊 **File Chunking Summary**\n\n"
            f"📄 **File:** `{file_path}`\n"
            f"🧩 **Total Chunks:** {chunks}\n"
            f"📦 **Chunk Size:** {CHUNK_SIZE:,} characters each\n\n"
            f"**Next Steps:**\n"
            f"• Use `fs://chunk/{file_path}/0` to read the first chunk\n"
            f"• Use `fs://chunk/{file_path}/{{N}}` to read chunk N (0 to {chunks-1})\n"
            f"• Use `fs://chunks/{file_path}` to get complete metadata\n\n"
            f"💡 **Tip:** Large files are automatically split for easier processing."
        )
    except ValueError:
        return f"File '{file_path}' has been processed. Use the chunk resources to view each part."


@mcp.prompt()
def usage_instructions() -> str:
    """Comprehensive usage instructions for the enhanced file system server."""
    return (
        "📖 **Enhanced File System Server - Usage Guide**\n\n"
        "## 🗂️ **Resources**\n"
        "• `fs://sample` → Server information and capabilities\n"
        "• `fs://chunks/{file_path}` → Get file metadata and chunk links\n"
        "• `fs://chunk/{file_path}/{index}` → Read specific chunk (0-based indexing)\n\n"
        "## 🛠️ **Tools**\n"
        "### File Operations\n"
        "• `list_directory(path, include_hidden=False)` → Browse directory contents\n"
        "• `search_files(root_path, search_text, max_results=20)` → Find files with text\n"
        "• `get_file_info(file_path)` → Get detailed file information\n\n"
        "### Capability Testing\n"
        "• `check_sampling_capability(prompt)` → Test LLM integration\n"
        "• `check_roots_capability()` → Test filesystem access\n"
        "• `check_experimental_tools_capability()` → Test experimental features\n\n"
        "## 📋 **Limitations**\n"
        f"• Maximum file size: {MAX_FILE_SIZE // (1024*1024)}MB\n"
        f"• Chunk size: {CHUNK_SIZE:,} characters\n"
        f"• Supported types: {', '.join(sorted(ALLOWED_EXTENSIONS))}\n"
        "• All operations are read-only for security\n\n"
        "## 💡 **Best Practices**\n"
        "1. Start with `list_directory()` to explore\n"
        "2. Use `get_file_info()` to check file details\n"
        "3. Use `fs://chunks/` for large file metadata\n"
        "4. Read chunks sequentially for better performance"
    )


@mcp.prompt()
def exploration_guide() -> str:
    """Step-by-step file system exploration guide."""
    return (
        "🧭 **File System Exploration Guide**\n\n"
        "## 🚀 **Quick Start Workflow**\n\n"
        "### Step 1: Explore Directory Structure\n"
        "```\nlist_directory('/your/target/path')\n```\n"
        "📁 This shows you all folders and files with sizes and types\n\n"
        "### Step 2: Get File Details\n"
        "```\nget_file_info('/path/to/interesting/file.txt')\n```\n"
        "📊 Check file size, type, and chunk information\n\n"
        "### Step 3: Search for Specific Content\n"
        "```\nsearch_files('/project/root', 'function_name')\n```\n"
        "🔍 Find files containing specific code or text\n\n"
        "### Step 4: Read Large Files Efficiently\n"
        "```\n1. fs://chunks/path/to/large/file.txt  # Get chunk metadata\n"
        "2. fs://chunk/path/to/large/file.txt/0   # Read first chunk\n"
        "3. fs://chunk/path/to/large/file.txt/1   # Read second chunk\n"
        "```\n"
        "📚 Process large files chunk by chunk\n\n"
        "## 🎯 **Advanced Tips**\n"
        "• Use `include_hidden=True` in `list_directory()` to see hidden files\n"
        "• Increase `max_results` in `search_files()` for broader searches\n"
        "• Check file info before reading to avoid processing huge files\n"
        "• Use the preview in `fs://chunks/` resource to quickly assess content\n\n"
        "## 🔧 **Troubleshooting**\n"
        "• **Permission denied?** Try a different directory\n"
        "• **File too large?** Use chunked reading approach\n"
        "• **Unsupported type?** Check the allowed extensions list\n"
        "• **No results?** Verify the path exists with `list_directory()`"
    )


@mcp.prompt()
def capability_testing_guide() -> str:
    """Guide for testing various MCP client capabilities."""
    return (
        "🧪 **Client Capability Testing Guide**\n\n"
        "## 🎯 **Available Capability Tests**\n\n"
        "### 1. Sampling Capability (LLM Integration)\n"
        "```\ncheck_sampling_capability('Custom prompt here')\n```\n"
        "🤖 Tests if the client can request LLM completions\n"
        "• **Success:** Client supports AI model integration\n"
        "• **Failure:** Client is operating in basic mode\n\n"
        "### 2. Roots Capability (File System Access)\n"
        "```\ncheck_roots_capability()\n```\n"
        "🗂️ Tests if the client can access filesystem roots\n"
        "• **Success:** Full filesystem navigation available\n"
        "• **Failure:** Limited to current directory only\n\n"
        "### 3. Experimental Tools\n"
        "```\ncheck_experimental_tools_capability()\n```\n"
        "🔬 Tests support for advanced/experimental features\n"
        "• **Success:** Client supports cutting-edge features\n"
        "• **Failure:** Client uses standard feature set\n\n"
        "## 📊 **Interpreting Results**\n"
        "• ✅ **Supported:** Feature is available and working\n"
        "• ❌ **Not Supported:** Feature is not available\n"
        "• 🔧 **Error:** Check client configuration\n\n"
        "## 💡 **What This Means**\n"
        "• **All supported:** You have a fully-featured MCP client\n"
        "• **Partial support:** Some advanced features may be limited\n"
        "• **Basic support:** Core functionality only\n\n"
        "Run these tests to understand your client's capabilities and optimize your workflow accordingly!"
    )


# ================================
# APPLICATION SETUP
# ================================

async def main():
    """Main server startup function."""
    logger.info("🚀 Starting Enhanced File System MCP Server...")
    logger.info(f"📋 Configuration:")
    logger.info(f"   • Chunk size: {CHUNK_SIZE:,} characters")
    logger.info(f"   • Max file size: {MAX_FILE_SIZE // (1024*1024)}MB")
    logger.info(f"   • Supported extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    logger.info("🌐 Server ready at http://localhost:8080")


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        mcp.sse_app(),
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
