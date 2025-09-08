# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp==1.6.0",
#     "uvicorn==0.34.0"
# ]
# ///

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
from typing import Literal
from mcp.server.session import ServerSession
from pydantic import BaseModel

mcp = FastMCP(name="ReadOnlyFileSystem")

CHUNK_SIZE = 1024


class RootContent(BaseModel):
    type: str
    uri: str


@mcp.resource("fs://sample")
def get_sample_resource() -> dict:
    """Return a sample resource payload with structured data."""
    return {
        "name": "Sample Resource",
        "description": "This is a static example resource served by FastMCP.",
        "usage": {
            "info": "You can customize this endpoint to return dynamic content.",
            "example": "fs://sample",
        },
        "data": "Hello from the sample resource! 🎉",
    }


@mcp.resource("fs://chunk/{file_path}/{chunk_index}")
def get_file_chunk(file_path: str, chunk_index: int) -> str:
    """Return a specific chunk from a file"""
    path = Path(file_path)
    if not path.is_file():
        return f"Error: '{file_path}' is not a valid file"

    try:
        text = path.read_text()
        start = chunk_index * CHUNK_SIZE
        end = start + CHUNK_SIZE
        return text[start:end] if start < len(text) else ""
    except Exception as e:
        return f"Error reading chunk: {e}"


@mcp.resource("fs://chunks/{file_path}")
def read_file_chunks(file_path: str) -> dict:
    """Get chunk info and links for a file"""
    path = Path(file_path)
    if not path.is_file():
        return {"error": f"'{file_path}' is not a valid file"}

    try:
        text = path.read_text()
        total_chunks = (len(text) + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunk_links = [f"fs://chunk/{file_path}/{i}" for i in range(total_chunks)]
        return {
            "file": file_path,
            "length": len(text),
            "chunk_size": CHUNK_SIZE,
            "total_chunks": total_chunks,
            "chunks": chunk_links,
        }
    except Exception as e:
        return {"error": f"Error processing file: {e}"}


@mcp.tool()
def list_directory(directory_path: str) -> list[str]:
    """List the contents of a directory"""
    path = Path(directory_path)
    if path.is_dir():
        return [str(p.name) for p in path.iterdir()]
    return [f"Error: '{directory_path}' is not a valid directory"]


@mcp.tool()
def search_files(root_path: str, search_text: str) -> list[str]:
    """Search for files that contain a specific string"""
    path = Path(root_path)
    if not path.is_dir():
        return [f"Error: '{root_path}' is not a valid directory"]

    matching_files = []
    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                if search_text in file_path.read_text():
                    matching_files.append(str(file_path))
            except Exception:
                continue
    return (
        matching_files
        if matching_files
        else [f"No files contain '{search_text}' in '{root_path}'"]
    )


@mcp.tool()
async def check_experimental_tools_capability() -> str:
    """Check if the client supports experimental advanced tools."""
    context = mcp.get_context()
    if not context:
        return "Error: No session context available."

    capability = ClientCapabilities(experimental={"advanced_tools": {}})
    is_supported = context.session.check_client_capability(capability)
    return "Supported" if is_supported else "Not supported"


@mcp.tool()
async def check_sampling_capability(prompt: str) -> str:
    """Request an LLM completion from the client."""
    context = mcp.get_context()
    if not context:
        return "Error: No session context available."

    if not context.session.check_client_capability(
        ClientCapabilities(sampling=SamplingCapability())
    ):
        return "Error: Client does not support sampling capability."

    sampling_message = SamplingMessage(
        role="user", content=TextContent(type="text", text=prompt)
    )

    response = await context.session.create_message(
        messages=[sampling_message], max_tokens=100
    )

    if response and response.content:
        return response.content.text
    else:
        return "No response received."


async def get_root_content(context: ServerSession, root: Root) -> str:
    """Fetch the contents of a root directory given its URI."""
    response = await context.session.create_message(
        messages=[], max_tokens=0, metadata=root.model_dump()
    )
    if response and response.content:
        return response.content.text
    else:
        return "No response received."


@mcp.tool()
async def check_roots_capability() -> list[str]:
    """Check if the client supports roots (filesystem access)."""
    context = mcp.get_context()
    if not context:
        return ["Error: No session context available."]

    if not context.session.check_client_capability(
        ClientCapabilities(roots=RootsCapability())
    ):
        return ["Error: Client does not support roots capability."]

    try:
        response = await context.session.list_roots()
        roots = [root.uri for root in response.roots]

        if not roots:
            return ["Error: No roots found."]

        content = await get_root_content(context, response.roots[0])

        return roots + [content]
    except Exception as e:
        return [f"Error during root capability check: {str(e)}"]


@mcp.prompt()
def result_summary_prompt(file_path: str, total_chunks: int) -> str:
    """Summarize chunking result"""
    return f"The file '{file_path}' has been split into {total_chunks} chunk(s). Use the chunk resources to view each part."


@mcp.prompt()
def usage_instructions() -> str:
    """General usage instructions"""
    return (
        "📖 **Read-Only File System Usage Guide**\n\n"
        "**Resources:**\n"
        "- `fs://chunks/{file_path}` → Get file chunking info and chunk links\n"
        "- `fs://chunk/{file_path}/{chunk_index}` → Read a specific chunk from a file\n\n"
        "**Tools:**\n"
        "- `list_directory(directory_path)` → List contents of a directory\n"
        "- `search_files(root_path, search_text)` → Find files containing a string\n\n"
        "All operations are read-only. Use chunked reading for large files."
    )


@mcp.prompt()
def exploration_guide() -> str:
    """Step-by-step file navigation guide"""
    return (
        "🗂 **Explore Files Step-by-Step**\n\n"
        "1. 🔍 Use `list_directory('/your/path')` to browse a folder.\n"
        "2. 🧠 Use `search_files('/your/path', 'text')` to find files that contain certain content.\n"
        "3. 📦 Use `fs://chunks/{file_path}` to get chunk metadata and chunk links.\n"
        "4. 📖 Use `fs://chunk/{file_path}/{chunk_index}` to view the contents chunk-by-chunk.\n\n"
        "Follow these steps to safely inspect any file in a large or nested directory structure."
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8080)
