# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp==1.6.0"
# ]
# ///

"""
MCP Client and Explorer - Separated Architecture

This module provides:
1. MCPClient: Core MCP protocol implementation
2. MCPExplorer: Educational exploration of MCP capabilities
3. Clear separation between protocol logic and exploration logic
"""

import asyncio
import json
from typing import Optional, List, Dict, Any, Callable
from abc import ABC, abstractmethod
from pydantic import ValidationError

from mcp import ClientSession, types, shared
from mcp.client.sse import sse_client
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS

# Configuration
MCP_SERVER_URL = "http://localhost:8080/sse"
ENABLE_DEBUG_LOGGING = True


class MCPLogger:
    """Simple logging utility with emoji indicators."""

    @staticmethod
    def log(message: str, level: str = "INFO"):
        emoji_map = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍",
        }
        if ENABLE_DEBUG_LOGGING or level != "DEBUG":
            print(f"{emoji_map.get(level, '📝')} [{level}] {message}")


class MCPClientHandler(ABC):
    """Abstract base class for handling MCP client events."""

    @abstractmethod
    async def on_sampling_request(
        self,
        context: shared.context.RequestContext,
        arguments: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult:
        """Handle sampling requests from MCP server."""
        pass

    @abstractmethod
    async def on_list_roots_request(
        self, context: shared.context.RequestContext
    ) -> types.ListRootsResult:
        """Handle root directory listing requests."""
        pass

    async def on_logging_message(self, level: str, message: str):
        """Handle logging messages from MCP server."""
        MCPLogger.log(f"MCP Server: {message}", level.upper())

    async def on_raw_message(self, message: types.JSONRPCMessage):
        """Handle raw JSON-RPC messages."""
        if ENABLE_DEBUG_LOGGING:
            MCPLogger.log(f"Raw message: {message}", "DEBUG")


class DefaultMCPHandler(MCPClientHandler):
    """Default implementation of MCP client event handlers."""

    async def on_sampling_request(
        self,
        context: shared.context.RequestContext,
        arguments: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult:
        """Default sampling handler - simulates basic AI responses."""
        MCPLogger.log("Handling sampling request", "DEBUG")

        # Check if this is a root listing request
        try:
            root = types.Root(**arguments.metadata)
            return await self._simulate_root_listing(root)
        except (ValidationError, TypeError, KeyError):
            # Regular text message
            return await self._simulate_text_response(arguments)

    async def on_list_roots_request(
        self, context: shared.context.RequestContext
    ) -> types.ListRootsResult:
        """Provide default root directories."""
        roots = [
            types.Root(uri="file:///workspace", name="Workspace"),
            types.Root(uri="file:///home/user/projects", name="Projects"),
            types.Root(uri="file:///tmp", name="Temporary Files"),
        ]
        MCPLogger.log(f"Providing {len(roots)} root directories")
        return types.ListRootsResult(roots=roots)

    async def _simulate_root_listing(
        self, root: types.Root
    ) -> types.CreateMessageResult:
        """Simulate directory listing for a root."""
        MCPLogger.log(f"Simulating directory listing for: {root.uri}")

        fake_listing = f"""Directory contents for {root.name}:
- main.py (Python script)
- requirements.txt (Dependencies)  
- utils/ (Utility modules)
- data/ (Data files)
- README.md (Documentation)
- .gitignore (Git ignore file)"""

        return types.CreateMessageResult(
            role="assistant",
            content=types.TextContent(type="text", text=fake_listing),
            model="mcp-client-v1",
        )

    async def _simulate_text_response(
        self, arguments: types.CreateMessageRequestParams
    ) -> types.CreateMessageResult:
        """Simulate AI response to text messages."""
        message_text = (
            arguments.messages[0].content.text if arguments.messages else "No message"
        )
        response_text = f"Simulated AI response to: {message_text}"

        return types.CreateMessageResult(
            role="assistant",
            content=types.TextContent(type="text", text=response_text),
            model="mcp-client-v1",
            stopReason="endTurn",
        )


class MCPClient:
    """
    Core MCP client implementation with clean protocol handling.

    This class handles the MCP protocol implementation without exploration logic.
    It provides a clean interface for MCP operations.
    """

    def __init__(self, server_url: str, handler: Optional[MCPClientHandler] = None):
        self.server_url = server_url
        self.handler = handler or DefaultMCPHandler()
        self.session: Optional[ClientSession] = None
        self._initialization_result: Optional[types.InitializeResult] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Establish connection to MCP server."""
        MCPLogger.log(f"Connecting to MCP server: {self.server_url}")

        self._read, self._write = await sse_client(self.server_url).__aenter__()
        self.session = ClientSession(
            self._read,
            self._write,
            sampling_callback=self.handler.on_sampling_request,
            list_roots_callback=self.handler.on_list_roots_request,
            logging_callback=self.handler.on_logging_message,
            message_handler=self.handler.on_raw_message,
        )

        await self.session.__aenter__()
        await self._initialize_protocol()

        MCPLogger.log("MCP client connected successfully", "SUCCESS")

    async def disconnect(self):
        """Clean disconnect from MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        MCPLogger.log("MCP client disconnected", "INFO")

    async def _initialize_protocol(self):
        """Handle MCP protocol initialization."""
        MCPLogger.log("Initializing MCP protocol...")

        # Define client capabilities
        capabilities = types.ClientCapabilities(
            sampling=types.SamplingCapability(),
            roots=types.RootsCapability(listChanged=True),
            experimental={"advanced_tools": {}},
        )

        # Send initialization request
        result = await self.session.send_request(
            types.ClientRequest(
                types.InitializeRequest(
                    method="initialize",
                    params=types.InitializeRequestParams(
                        protocolVersion=types.LATEST_PROTOCOL_VERSION,
                        capabilities=capabilities,
                        clientInfo=types.Implementation(
                            name="mcp-client", version="1.0.0"
                        ),
                    ),
                )
            ),
            types.InitializeResult,
        )

        # Verify protocol compatibility
        if result.protocolVersion not in SUPPORTED_PROTOCOL_VERSIONS:
            raise RuntimeError(
                f"Unsupported protocol version: {result.protocolVersion}. "
                f"Supported: {SUPPORTED_PROTOCOL_VERSIONS}"
            )

        # Send initialized notification
        await self.session.send_notification(
            types.ClientNotification(
                types.InitializedNotification(method="notifications/initialized")
            )
        )

        self._initialization_result = result
        MCPLogger.log("MCP protocol initialized successfully", "SUCCESS")

    # Protocol Operations
    async def ping(self):
        """Send ping to server."""
        await self.session.send_ping()

    async def list_prompts(self) -> types.ListPromptsResult:
        """List available prompts."""
        return await self.session.list_prompts()

    async def get_prompt(
        self, name: str, arguments: Dict[str, Any]
    ) -> types.GetPromptResult:
        """Execute a prompt with arguments."""
        return await self.session.get_prompt(name, arguments)

    async def list_tools(self) -> types.ListToolsResult:
        """List available tools."""
        return await self.session.list_tools()

    async def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> types.CallToolResult:
        """Call a tool with arguments."""
        return await self.session.call_tool(name, arguments)

    async def list_resources(self) -> types.ListResourcesResult:
        """List available resources."""
        return await self.session.list_resources()

    async def list_resource_templates(self) -> types.ListResourceTemplatesResult:
        """List resource templates."""
        return await self.session.list_resource_templates()

    async def read_resource(self, uri: str):
        """Read a resource."""
        return await self.session.read_resource(uri)

    async def subscribe_resource(self, uri: str):
        """Subscribe to resource changes."""
        await self.session.subscribe_resource(uri)

    async def unsubscribe_resource(self, uri: str):
        """Unsubscribe from resource changes."""
        await self.session.unsubscribe_resource(uri)

    async def send_progress_notification(
        self, progress_token: str, progress: float, total: float = 1.0
    ):
        """Send progress notification."""
        await self.session.send_progress_notification(progress_token, progress, total)

    # Getters for client state
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.session is not None and self._initialization_result is not None

    @property
    def server_info(self) -> Optional[types.Implementation]:
        """Get server information."""
        return (
            self._initialization_result.serverInfo
            if self._initialization_result
            else None
        )

    @property
    def protocol_version(self) -> Optional[str]:
        """Get negotiated protocol version."""
        return (
            self._initialization_result.protocolVersion
            if self._initialization_result
            else None
        )


class MCPExplorer:
    """
    Educational MCP exploration class.

    This class focuses on discovering and demonstrating MCP capabilities
    without being concerned with protocol implementation details.
    """

    def __init__(self, client: MCPClient):
        self.client = client
        self.exploration_results = {
            "prompts": [],
            "tools": [],
            "resources": [],
            "capabilities_tested": [],
        }

    async def run_full_exploration(self):
        """Run comprehensive MCP exploration."""
        MCPLogger.log("🚀 Starting comprehensive MCP exploration...")

        try:
            # Core capability exploration
            await self.explore_prompts()
            await self.explore_tools()
            await self.explore_resources()
            await self.test_protocol_features()

            # Generate exploration report
            await self.generate_exploration_report()

            MCPLogger.log("🎉 MCP exploration completed successfully!", "SUCCESS")

        except Exception as e:
            MCPLogger.log(f"Exploration failed: {e}", "ERROR")
            raise

    async def explore_prompts(self):
        """Discover and test prompt capabilities."""
        MCPLogger.log("🔍 Exploring prompts...")

        try:
            result = await self.client.list_prompts()
            prompts = result.prompts

            if not prompts:
                MCPLogger.log("No prompts available", "WARNING")
                return

            for prompt in prompts:
                MCPLogger.log(
                    f"Found prompt: '{prompt.name}' (requires {len(prompt.arguments)} args)"
                )
                self.exploration_results["prompts"].append(
                    {
                        "name": prompt.name,
                        "description": getattr(prompt, "description", "No description"),
                        "arguments": [arg.name for arg in prompt.arguments],
                    }
                )

                # Test first prompt
                if prompt == prompts[0]:
                    await self._test_prompt_execution(prompt)

        except Exception as e:
            MCPLogger.log(f"Error exploring prompts: {e}", "ERROR")

    async def _test_prompt_execution(self, prompt):
        """Test executing a prompt with sample data."""
        try:
            # Generate sample arguments
            sample_args = self._generate_sample_arguments(prompt.arguments)

            MCPLogger.log(f"Testing prompt '{prompt.name}' with: {sample_args}")
            result = await self.client.get_prompt(prompt.name, sample_args)

            for msg in result.messages:
                preview = self._truncate_text(msg.content.text, 100)
                MCPLogger.log(f"Prompt result ({msg.role}): {preview}")

        except Exception as e:
            MCPLogger.log(f"Prompt test failed for '{prompt.name}': {e}", "ERROR")

    async def explore_tools(self):
        """Discover and test tool capabilities."""
        MCPLogger.log("🔧 Exploring tools...")

        try:
            result = await self.client.list_tools()
            tools = result.tools

            if not tools:
                MCPLogger.log("No tools available", "WARNING")
                return

            for tool in tools:
                MCPLogger.log(f"Found tool: '{tool.name}' - {tool.description}")
                self.exploration_results["tools"].append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema,
                    }
                )

            # Test common tools
            await self._test_common_tools(tools)

        except Exception as e:
            MCPLogger.log(f"Error exploring tools: {e}", "ERROR")

    async def _test_common_tools(self, tools):
        """Test commonly available tools."""
        common_tool_tests = [
            ("list_directory", {"directory_path": "."}),
            ("check_sampling_capability", {"prompt": "Hello MCP!"}),
            ("check_experimental_tools_capability", {}),
            ("check_roots_capability", {}),
        ]

        available_tools = {tool.name for tool in tools}

        for tool_name, test_args in common_tool_tests:
            if tool_name in available_tools:
                await self._test_tool_execution(tool_name, test_args)

    async def _test_tool_execution(self, tool_name: str, args: Dict[str, Any]):
        """Test individual tool execution."""
        try:
            MCPLogger.log(f"Testing tool '{tool_name}' with: {args}")
            result = await self.client.call_tool(tool_name, args)

            for item in result.content:
                if hasattr(item, "text"):
                    preview = self._truncate_text(item.text, 150)
                    MCPLogger.log(f"Tool result: {preview}")
                else:
                    MCPLogger.log(f"Tool result: {type(item).__name__}")

        except Exception as e:
            MCPLogger.log(f"Tool test failed for '{tool_name}': {e}", "ERROR")

    async def explore_resources(self):
        """Discover and test resource capabilities."""
        MCPLogger.log("📚 Exploring resources...")

        try:
            # Explore resource templates
            templates_result = await self.client.list_resource_templates()
            if templates_result.resourceTemplates:
                MCPLogger.log(
                    f"Found {len(templates_result.resourceTemplates)} resource templates"
                )
                for template in templates_result.resourceTemplates:
                    MCPLogger.log(f"Template: {template.uriTemplate}")

            # Explore actual resources
            resources_result = await self.client.list_resources()
            resources = resources_result.resources

            if not resources:
                MCPLogger.log("No resources available", "WARNING")
                return

            MCPLogger.log(f"Found {len(resources)} resources")
            for resource in resources:
                MCPLogger.log(f"Resource: {resource.uri}")
                self.exploration_results["resources"].append(
                    {
                        "uri": resource.uri,
                        "name": getattr(resource, "name", resource.uri),
                        "mimeType": getattr(resource, "mimeType", "unknown"),
                    }
                )

            # Test resource reading
            await self._test_resource_access(resources[:3])  # Test first 3

        except Exception as e:
            MCPLogger.log(f"Error exploring resources: {e}", "ERROR")

    async def _test_resource_access(self, resources):
        """Test reading and subscribing to resources."""
        for resource in resources:
            try:
                # Test reading
                MCPLogger.log(f"Reading resource: {resource.uri}")
                metadata, content = await self.client.read_resource(resource.uri)

                content_preview = self._truncate_text(str(content), 100)
                MCPLogger.log(f"Resource content preview: {content_preview}")

                # Test subscription
                await self._test_resource_subscription(resource.uri)

            except Exception as e:
                MCPLogger.log(
                    f"Resource access failed for '{resource.uri}': {e}", "ERROR"
                )

    async def _test_resource_subscription(self, uri: str):
        """Test resource subscription lifecycle."""
        try:
            MCPLogger.log(f"Testing subscription for: {uri}")
            await self.client.subscribe_resource(uri)
            MCPLogger.log("Subscription successful", "SUCCESS")

            # Clean up
            await self.client.unsubscribe_resource(uri)
            MCPLogger.log("Unsubscription successful", "SUCCESS")

        except Exception as e:
            MCPLogger.log(f"Subscription test failed: {e}", "WARNING")

    async def test_protocol_features(self):
        """Test miscellaneous protocol features."""
        MCPLogger.log("🧪 Testing protocol features...")

        # Test ping
        try:
            await self.client.ping()
            MCPLogger.log("Ping test successful", "SUCCESS")
            self.exploration_results["capabilities_tested"].append("ping")
        except Exception as e:
            MCPLogger.log(f"Ping test failed: {e}", "ERROR")

        # Test progress notifications
        try:
            await self.client.send_progress_notification("exploration", 0.8)
            MCPLogger.log("Progress notification test successful", "SUCCESS")
            self.exploration_results["capabilities_tested"].append(
                "progress_notifications"
            )
        except Exception as e:
            MCPLogger.log(f"Progress notification test failed: {e}", "ERROR")

    async def generate_exploration_report(self):
        """Generate a summary of exploration results."""
        MCPLogger.log("📊 Generating exploration report...")

        report = f"""
=== MCP EXPLORATION REPORT ===
Server: {self.client.server_url}
Protocol Version: {self.client.protocol_version}
Server Info: {self.client.server_info.name if self.client.server_info else 'Unknown'}

Prompts Found: {len(self.exploration_results['prompts'])}
Tools Found: {len(self.exploration_results['tools'])}
Resources Found: {len(self.exploration_results['resources'])}
Capabilities Tested: {', '.join(self.exploration_results['capabilities_tested'])}

=== SUMMARY ===
✅ Connection: Successful
✅ Protocol Handshake: Successful  
✅ Capability Discovery: {len(self.exploration_results['prompts']) + len(self.exploration_results['tools']) + len(self.exploration_results['resources'])} items found
✅ Feature Testing: {len(self.exploration_results['capabilities_tested'])} features tested
        """

        print(report)

    # Utility methods
    def _generate_sample_arguments(self, arg_specs) -> Dict[str, Any]:
        """Generate sample arguments for testing."""
        args = {}
        for arg_spec in arg_specs:
            name = arg_spec.name.lower()
            if "path" in name:
                args[arg_spec.name] = "/sample/path.txt"
            elif "chunk" in name or "count" in name:
                args[arg_spec.name] = "5"
            elif "url" in name:
                args[arg_spec.name] = "https://example.com"
            else:
                args[arg_spec.name] = "sample_value"
        return args

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text with ellipsis if too long."""
        return text[:max_length] + "..." if len(text) > max_length else text


async def basic_client_usage():
    """Example of basic MCP client usage."""
    async with MCPClient(MCP_SERVER_URL) as client:
        # Basic operations
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools.tools]}")

        resources = await client.list_resources()
        print(f"Available resources: {[r.uri for r in resources.resources]}")


async def full_exploration_example():
    """Example of comprehensive MCP exploration."""
    handler = DefaultMCPHandler()

    async with MCPClient(MCP_SERVER_URL, handler) as client:
        explorer = MCPExplorer(client)
        await explorer.run_full_exploration()


async def main():
    """Main entry point with usage examples."""
    print("=" * 60)
    print("🔍 MCP CLIENT & EXPLORER")
    print("=" * 60)
    print("Choose exploration mode:")
    print("1. Basic client operations")
    print("2. Full capability exploration")
    print("=" * 60)

    try:
        # For this demo, run full exploration
        await full_exploration_example()
    except Exception as e:
        MCPLogger.log(f"Application error: {e}", "ERROR")
        raise


if __name__ == "__main__":
    asyncio.run(main())
