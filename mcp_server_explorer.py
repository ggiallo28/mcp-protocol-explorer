"""
LiteLLM MCP Server Routes - Enhanced and Simplified

This module provides FastAPI routes for integrating Model Context Protocol (MCP)
with LiteLLM proxy server. It includes both SSE streaming capabilities and REST API endpoints.

Key features:
- MCP tool discovery and execution
- Server-side event streaming for real-time communication  
- Tool registry management for both local and managed MCP servers
- Comprehensive error handling and logging
- Authentication integration with LiteLLM proxy
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from anyio import BrokenResourceError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, ValidationError

from litellm._logging import verbose_logger
from litellm.constants import MCP_TOOL_NAME_PREFIX
from litellm.litellm_core_utils.litellm_logging import Logging as LiteLLMLoggingObj
from litellm.proxy._types import UserAPIKeyAuth
from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
from litellm.types.mcp_server.mcp_server_manager import MCPInfo
from litellm.types.utils import StandardLoggingMCPToolCall
from litellm.utils import client

# Check MCP availability - graceful degradation for older Python versions
try:
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
    from mcp.types import EmbeddedResource as MCPEmbeddedResource
    from mcp.types import ImageContent as MCPImageContent
    from mcp.types import TextContent as MCPTextContent
    from mcp.types import Tool as MCPTool

    MCP_AVAILABLE = True

    # Import MCP-specific components
    from .mcp_server_manager import global_mcp_server_manager
    from .sse_transport import SseServerTransport
    from .tool_registry import global_mcp_tool_registry

except ImportError as import_error:
    verbose_logger.debug(f"MCP module not available: {import_error}")
    MCP_AVAILABLE = False


class MCPServerRoutes:
    """
    Encapsulates all MCP-related routes and server management.

    This class provides a clean interface for managing MCP servers,
    tools, and SSE communication within the LiteLLM proxy.
    """

    def __init__(self):
        self.router = APIRouter(prefix="/mcp", tags=["mcp"])
        self.server: Optional[Server] = None
        self.sse_transport: Optional[SseServerTransport] = None
        self._setup_routes()

        if MCP_AVAILABLE:
            self._initialize_mcp_server()

    def _setup_routes(self):
        """Set up FastAPI routes regardless of MCP availability."""

        @self.router.get("/health")
        async def health_check():
            """Health check endpoint for MCP server status."""
            return {
                "status": "healthy" if MCP_AVAILABLE else "unavailable",
                "mcp_available": MCP_AVAILABLE,
                "message": "MCP server is running"
                if MCP_AVAILABLE
                else "MCP not available - requires Python 3.10+",
            }

        if not MCP_AVAILABLE:

            @self.router.get("/{path:path}")
            async def mcp_unavailable():
                """Fallback for when MCP is not available."""
                raise HTTPException(
                    status_code=503,
                    detail="MCP functionality requires Python 3.10+ and mcp package",
                )

            return

        # MCP-specific routes
        self._setup_mcp_routes()
        self._setup_rest_api_routes()

    def _initialize_mcp_server(self):
        """Initialize the MCP server components."""
        if not MCP_AVAILABLE:
            return

        self.server = Server("litellm-mcp-server")
        self.sse_transport = SseServerTransport("/mcp/sse/messages")

        # Register MCP server handlers
        self._register_server_handlers()

    def _register_server_handlers(self):
        """Register handlers with the MCP server."""
        if not self.server:
            return

        @self.server.list_tools()
        async def list_tools() -> List[MCPTool]:
            """List all available MCP tools."""
            return await self._get_all_available_tools()

        @self.server.call_tool()
        async def call_tool_handler(
            name: str, arguments: Dict[str, Any] | None
        ) -> List[Union[MCPTextContent, MCPImageContent, MCPEmbeddedResource]]:
            """Handle MCP tool execution requests."""
            return await self._execute_mcp_tool(name, arguments)

    def _setup_mcp_routes(self):
        """Set up MCP-specific SSE routes."""

        @self.router.get("/", response_class=StreamingResponse)
        async def handle_sse(request: Request):
            """Handle SSE connections for real-time MCP communication."""
            verbose_logger.info("🔌 New SSE connection established")

            try:
                async with self.sse_transport.connect_sse(request) as streams:
                    options = InitializationOptions(
                        server_name="litellm-mcp-server",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    )

                    await self.server.run(streams[0], streams[1], options)

            except BrokenResourceError:
                verbose_logger.debug("SSE connection broken")
            except asyncio.CancelledError:
                verbose_logger.debug("SSE connection cancelled")
            except ValidationError as e:
                verbose_logger.error(f"SSE validation error: {e}")
            except Exception as e:
                verbose_logger.exception(f"SSE connection error: {e}")
                raise
            finally:
                await request.close()

        @self.router.post("/sse/messages")
        async def handle_sse_messages(request: Request):
            """Handle POST messages for SSE communication."""
            verbose_logger.info("📨 SSE message received")

            try:
                await self.sse_transport.handle_post_message(
                    request.scope, request.receive, request._send
                )
            except Exception as e:
                verbose_logger.exception(f"Error handling SSE message: {e}")
                raise
            finally:
                await request.close()

    def _setup_rest_api_routes(self):
        """Set up REST API routes for MCP functionality."""

        @self.router.get("/tools/list", dependencies=[Depends(user_api_key_auth)])
        async def list_tools_api() -> List["MCPToolWithServerInfo"]:
            """
            REST API endpoint to list all available MCP tools.

            Returns tools with information about their originating server,
            useful for understanding the MCP ecosystem and available capabilities.
            """
            return await self._list_tools_with_server_info()

        @self.router.post("/tools/call", dependencies=[Depends(user_api_key_auth)])
        async def call_tool_api(
            request: Request,
            user_api_key_dict: UserAPIKeyAuth = Depends(user_api_key_auth),
        ):
            """
            REST API endpoint to execute MCP tools.

            This endpoint allows direct tool execution via HTTP POST,
            providing an alternative to the SSE-based communication.
            """
            from litellm.proxy.proxy_server import (
                add_litellm_data_to_request,
                proxy_config,
            )

            try:
                data = await request.json()
                data = await add_litellm_data_to_request(
                    data=data,
                    request=request,
                    user_api_key_dict=user_api_key_dict,
                    proxy_config=proxy_config,
                )

                return await self._call_mcp_tool_with_logging(**data)

            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400, detail="Invalid JSON in request body"
                )
            except Exception as e:
                verbose_logger.exception("Error in tool call API")
                raise HTTPException(
                    status_code=500, detail=f"Tool execution failed: {str(e)}"
                )

    async def _get_all_available_tools(self) -> List[MCPTool]:
        """
        Aggregate all available tools from both local registry and managed servers.

        Returns:
            List of all available MCP tools with their metadata
        """
        tools = []

        # Get tools from local registry
        local_tools = global_mcp_tool_registry.list_tools()
        for tool in local_tools:
            tools.append(
                MCPTool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.input_schema,
                )
            )

        verbose_logger.debug(f"Found {len(local_tools)} local tools")

        # Get tools from managed MCP servers
        try:
            managed_tools = await global_mcp_server_manager.list_tools()
            if managed_tools:
                tools.extend(managed_tools)
                verbose_logger.debug(f"Found {len(managed_tools)} managed server tools")
        except Exception as e:
            verbose_logger.warning(f"Failed to get managed server tools: {e}")

        verbose_logger.info(f"Total available tools: {len(tools)}")
        return tools

    async def _list_tools_with_server_info(self) -> List["MCPToolWithServerInfo"]:
        """
        List tools with detailed server information for the REST API.

        Returns:
            List of tools with their associated server metadata
        """
        result = []

        # Get tools from each managed server individually to preserve server info
        for server in global_mcp_server_manager.mcp_servers:
            try:
                server_tools = await global_mcp_server_manager._get_tools_from_server(
                    server
                )
                for tool in server_tools:
                    result.append(
                        MCPToolWithServerInfo(
                            name=tool.name,
                            description=tool.description,
                            inputSchema=tool.inputSchema,
                            mcp_info=server.mcp_info,
                        )
                    )
            except Exception as e:
                verbose_logger.warning(
                    f"Failed to get tools from server {server.name}: {e}"
                )
                continue

        # Add local tools (no server info)
        local_tools = global_mcp_tool_registry.list_tools()
        for tool in local_tools:
            result.append(
                MCPToolWithServerInfo(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.input_schema,
                    mcp_info=None,  # Local tools don't have server info
                )
            )

        return result

    async def _execute_mcp_tool(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> List[Union[MCPTextContent, MCPImageContent, MCPEmbeddedResource]]:
        """
        Execute an MCP tool with comprehensive error handling.

        Args:
            name: Tool name to execute
            arguments: Tool arguments (optional)

        Returns:
            List of content items representing the tool's output

        Raises:
            HTTPException: If tool not found or execution fails
        """
        if arguments is None:
            arguments = {}

        verbose_logger.debug(f"Executing tool '{name}' with args: {arguments}")

        # Try managed server tools first
        if name in global_mcp_server_manager.tool_name_to_mcp_server_name_mapping:
            return await self._call_managed_server_tool(name, arguments)

        # Fall back to local tool registry
        return await self._call_local_registry_tool(name, arguments)

    async def _call_managed_server_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> List[Union[MCPTextContent, MCPImageContent, MCPEmbeddedResource]]:
        """Execute a tool from a managed MCP server."""
        try:
            result = await global_mcp_server_manager.call_tool(
                name=name, arguments=arguments
            )
            verbose_logger.debug(f"Managed tool '{name}' executed successfully")
            return result.content
        except Exception as e:
            verbose_logger.error(f"Managed tool '{name}' execution failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Tool execution failed: {str(e)}"
            )

    async def _call_local_registry_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> List[Union[MCPTextContent, MCPImageContent, MCPEmbeddedResource]]:
        """Execute a tool from the local registry."""
        tool = global_mcp_tool_registry.get_tool(name)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")

        try:
            result = tool.handler(**arguments)
            verbose_logger.debug(f"Local tool '{name}' executed successfully")
            return [MCPTextContent(text=str(result), type="text")]
        except TypeError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid arguments for tool '{name}': {str(e)}"
            )
        except Exception as e:
            verbose_logger.error(f"Local tool '{name}' execution failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Tool execution failed: {str(e)}"
            )

    @client
    async def _call_mcp_tool_with_logging(
        self, name: str, arguments: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> List[Union[MCPTextContent, MCPImageContent, MCPEmbeddedResource]]:
        """
        Execute MCP tool with comprehensive logging for observability.

        This method integrates with LiteLLM's logging system to provide
        detailed metrics and tracing for MCP tool usage.
        """
        if arguments is None:
            arguments = {}

        # Create logging metadata
        logging_metadata = self._create_logging_metadata(name, arguments)

        # Integrate with LiteLLM logging if available
        litellm_logging_obj: Optional[LiteLLMLoggingObj] = kwargs.get(
            "litellm_logging_obj"
        )
        if litellm_logging_obj:
            litellm_logging_obj.model_call_details[
                "mcp_tool_call_metadata"
            ] = logging_metadata
            litellm_logging_obj.model_call_details[
                "model"
            ] = f"{MCP_TOOL_NAME_PREFIX}: {name}"
            litellm_logging_obj.model_call_details[
                "custom_llm_provider"
            ] = logging_metadata.get("mcp_server_name", "unknown")

        # Execute the tool
        return await self._execute_mcp_tool(name, arguments)

    def _create_logging_metadata(
        self, name: str, arguments: Dict[str, Any]
    ) -> StandardLoggingMCPToolCall:
        """Create standardized logging metadata for tool calls."""
        mcp_server = global_mcp_server_manager._get_mcp_server_from_tool_name(name)

        if mcp_server and mcp_server.mcp_info:
            return StandardLoggingMCPToolCall(
                name=name,
                arguments=arguments,
                mcp_server_name=mcp_server.mcp_info.get("server_name"),
                mcp_server_logo_url=mcp_server.mcp_info.get("logo_url"),
            )
        else:
            return StandardLoggingMCPToolCall(
                name=name, arguments=arguments, mcp_server_name="local_registry"
            )


# Response models for API documentation
class MCPToolWithServerInfo(BaseModel):
    """
    MCP tool information including server metadata.

    Used by the REST API to provide comprehensive tool information
    including which server provides each tool.
    """

    name: str
    description: str
    inputSchema: Dict[str, Any]
    mcp_info: Optional[MCPInfo] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MCPToolCallRequest(BaseModel):
    """Request model for MCP tool execution via REST API."""

    name: str
    arguments: Optional[Dict[str, Any]] = None


class MCPToolCallResponse(BaseModel):
    """Response model for MCP tool execution results."""

    success: bool
    content: List[Dict[str, Any]]
    error_message: Optional[str] = None


# Global instance
if MCP_AVAILABLE:
    mcp_routes = MCPServerRoutes()
    router = mcp_routes.router
else:
    # Create a minimal router for when MCP is unavailable
    router = APIRouter(prefix="/mcp", tags=["mcp"])

    @router.get("/health")
    async def health_unavailable():
        return {
            "status": "unavailable",
            "mcp_available": False,
            "message": "MCP functionality requires Python 3.10+ and mcp package",
        }

    @router.get("/{path:path}")
    async def mcp_unavailable():
        raise HTTPException(
            status_code=503,
            detail="MCP functionality requires Python 3.10+ and mcp package",
        )
