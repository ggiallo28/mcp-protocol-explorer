# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp==1.6.0"
# ]
# ///

"""
Enhanced MCP Client - Autonomous Agent

A sophisticated Model Context Protocol client that demonstrates:
- Autonomous interaction with MCP servers
- Dynamic resource and tool discovery
- Intelligent capability testing
- Structured exploration workflows
- Client capability management (sampling, roots, experimental tools)
"""

from mcp import ClientSession, types, shared
from mcp.client.sse import sse_client
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from typing import List, Dict, Any, Optional, Tuple
from pydantic import ValidationError
import json
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

# Configuration
MCP_SERVER_URL = "http://localhost:8080/sse"
CLIENT_NAME = "Enhanced-MCP-Agent"
CLIENT_VERSION = "2.0.0"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ServerCapabilities:
    """Track discovered server capabilities"""
    prompts: List[types.Prompt] = None
    tools: List[types.Tool] = None
    resources: List[types.Resource] = None
    resource_templates: List[types.ResourceTemplate] = None
    
    def __post_init__(self):
        self.prompts = self.prompts or []
        self.tools = self.tools or []
        self.resources = self.resources or []
        self.resource_templates = self.resource_templates or []


class EnhancedMCPClient:
    """Enhanced MCP Client with autonomous capabilities"""
    
    def __init__(self, server_url: str = MCP_SERVER_URL):
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self.capabilities = ServerCapabilities()
        self.client_capabilities = {
            'sampling': False,
            'roots': False,
            'experimental_tools': False
        }
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            # Cleanup if needed
            pass
    
    # ================================
    # CLIENT CAPABILITY CALLBACKS
    # ================================
    
    async def sampling_callback(
        self,
        context: shared.context.RequestContext,
        arguments: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult:
        """Handle sampling requests from the server (LLM completions)"""
        logger.info("🤖 [Sampling] Server requested LLM completion")
        
        try:
            # Check if this is a roots-related request
            if hasattr(arguments, 'metadata') and arguments.metadata:
                root = types.Root(**arguments.metadata)
                return await self.handle_root_request(context, root)
            else:
                return await self.handle_text_sampling(context, arguments)
                
        except (ValidationError, TypeError) as e:
            logger.warning(f"Sampling callback validation error: {e}")
            return await self.handle_text_sampling(context, arguments)
    
    async def handle_root_request(
        self,
        context: shared.context.RequestContext,
        root: types.Root,
    ) -> types.CreateMessageResult:
        """Handle root directory listing requests"""
        logger.info(f"📁 [Roots] Processing root request: {root.uri}")
        
        try:
            # Simulate directory listing for the root
            if "file://" in root.uri:
                fake_listing = (
                    "📂 Root Directory Contents:\n"
                    "📁 src/\n"
                    "📁 docs/\n"
                    "📁 tests/\n"
                    "📄 README.md\n"
                    "📄 requirements.txt\n"
                    "💻 main.py\n"
                    "🔧 config.json"
                )
            else:
                fake_listing = f"📂 Contents of {root.name}:\n- Directory listing not available for {root.uri}"
            
            return types.CreateMessageResult(
                role="user",
                content=types.TextContent(type="text", text=fake_listing),
                model="root-reader-v2",
            )
            
        except Exception as e:
            logger.error(f"Error handling root request: {e}")
            return types.CreateMessageResult(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=f"Error accessing root {root.uri}: {str(e)}"
                ),
                model="root-reader-v2",
            )
    
    async def handle_text_sampling(
        self,
        context: shared.context.RequestContext,
        arguments: types.CreateMessageRequestParams,
    ) -> types.CreateMessageResult:
        """Handle regular text sampling requests"""
        if not arguments.messages:
            message_text = "Hello from the enhanced MCP client!"
        else:
            message_text = arguments.messages[0].content.text
        
        logger.info(f"💬 [Sampling] Processing message: {message_text[:50]}...")
        
        # Simulate an intelligent response
        response_text = (
            f"🤖 **Enhanced Client Response**\n\n"
            f"📥 **Received:** {message_text}\n"
            f"🕒 **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔧 **Client:** {CLIENT_NAME} v{CLIENT_VERSION}\n\n"
            f"✅ **Status:** Message processed successfully by autonomous agent"
        )
        
        return types.CreateMessageResult(
            role="assistant",
            content=types.TextContent(type="text", text=response_text),
            model="enhanced-mcp-client-v2",
            stopReason="endTurn",
        )
    
    async def list_roots_callback(
        self,
        context: shared.context.RequestContext,
    ) -> types.ListRootsResult:
        """Provide available filesystem roots"""
        logger.info("🗂️ [Roots] Client providing available roots")
        
        roots = [
            types.Root(uri="file:///", name="System Root"),
            types.Root(uri="file:///home", name="Home Directory"),
            types.Root(uri="file:///tmp", name="Temporary Directory"),
            types.Root(uri="file:///var/log", name="Log Directory"),
        ]
        
        return types.ListRootsResult(roots=roots)
    
    async def logging_callback(self, level: str, message: str):
        """Handle server logging messages"""
        logger.info(f"🔊 [Server-{level.upper()}] {message}")
    
    async def message_handler(self, message: types.JSONRPCMessage):
        """Handle incoming JSON-RPC messages"""
        logger.debug(f"📨 [Message] Received: {message}")
    
    # ================================
    # SESSION MANAGEMENT
    # ================================
    
    async def initialize_session(self) -> ClientSession:
        """Initialize the MCP session with full capabilities"""
        logger.info(f"🚀 Initializing session with {self.server_url}")
        
        # Create session with all callbacks
        read, write = await sse_client(self.server_url).__aenter__()
        
        session = ClientSession(
            read,
            write,
            sampling_callback=self.sampling_callback,
            list_roots_callback=self.list_roots_callback,
            logging_callback=self.logging_callback,
            message_handler=self.message_handler,
        )
        
        # Configure client capabilities
        sampling = types.SamplingCapability()
        roots = types.RootsCapability(listChanged=True)
        
        # Initialize the session
        result = await session.send_request(
            types.ClientRequest(
                types.InitializeRequest(
                    method="initialize",
                    params=types.InitializeRequestParams(
                        protocolVersion=types.LATEST_PROTOCOL_VERSION,
                        capabilities=types.ClientCapabilities(
                            sampling=sampling,
                            roots=roots,
                            experimental={"advanced_tools": {}}
                        ),
                        clientInfo=types.Implementation(
                            name=CLIENT_NAME,
                            version=CLIENT_VERSION
                        ),
                    ),
                )
            ),
            types.InitializeResult,
        )
        
        # Verify protocol compatibility
        if result.protocolVersion not in SUPPORTED_PROTOCOL_VERSIONS:
            raise RuntimeError(f"Unsupported protocol version: {result.protocolVersion}")
        
        # Send initialized notification
        await session.send_notification(
            types.ClientNotification(
                types.InitializedNotification(method="notifications/initialized")
            )
        )
        
        logger.info(f"✅ Session initialized with protocol version {result.protocolVersion}")
        self.session = session
        return session
    
    # ================================
    # DISCOVERY AND EXPLORATION
    # ================================
    
    async def discover_server_capabilities(self) -> ServerCapabilities:
        """Discover all server capabilities and cache them"""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        logger.info("🔍 Discovering server capabilities...")
        
        # Discover prompts
        try:
            prompts_result = await self.session.list_prompts()
            self.capabilities.prompts = prompts_result.prompts
            logger.info(f"📋 Found {len(self.capabilities.prompts)} prompts")
        except Exception as e:
            logger.warning(f"Failed to discover prompts: {e}")
        
        # Discover tools
        try:
            tools_result = await self.session.list_tools()
            self.capabilities.tools = tools_result.tools
            logger.info(f"🛠️ Found {len(self.capabilities.tools)} tools")
        except Exception as e:
            logger.warning(f"Failed to discover tools: {e}")
        
        # Discover resource templates
        try:
            templates_result = await self.session.list_resource_templates()
            self.capabilities.resource_templates = templates_result.resourceTemplates
            logger.info(f"📄 Found {len(self.capabilities.resource_templates)} resource templates")
        except Exception as e:
            logger.warning(f"Failed to discover resource templates: {e}")
        
        # Discover resources
        try:
            resources_result = await self.session.list_resources()
            self.capabilities.resources = resources_result.resources
            logger.info(f"🗂️ Found {len(self.capabilities.resources)} resources")
        except Exception as e:
            logger.warning(f"Failed to discover resources: {e}")
        
        return self.capabilities
    
    async def test_client_capabilities(self) -> Dict[str, bool]:
        """Test various client capabilities with the server"""
        logger.info("🧪 Testing client capabilities...")
        
        results = {}
        
        # Test sampling capability
        try:
            if any(t.name == "check_sampling_capability" for t in self.capabilities.tools):
                result = await self.session.call_tool(
                    "check_sampling_capability",
                    {"prompt": "Test prompt for capability checking"}
                )
                success = "✅ Supported" in result.content[0].text
                results['sampling'] = success
                logger.info(f"🤖 Sampling capability: {'✅' if success else '❌'}")
            else:
                results['sampling'] = False
                logger.info("🤖 Sampling capability: ❓ (tool not available)")
        except Exception as e:
            results['sampling'] = False
            logger.warning(f"Sampling test failed: {e}")
        
        # Test roots capability
        try:
            if any(t.name == "check_roots_capability" for t in self.capabilities.tools):
                result = await self.session.call_tool("check_roots_capability", {})
                success = "✅ Roots capability supported" in result.content[0].text
                results['roots'] = success
                logger.info(f"🗂️ Roots capability: {'✅' if success else '❌'}")
            else:
                results['roots'] = False
                logger.info("🗂️ Roots capability: ❓ (tool not available)")
        except Exception as e:
            results['roots'] = False
            logger.warning(f"Roots test failed: {e}")
        
        # Test experimental tools capability
        try:
            if any(t.name == "check_experimental_tools_capability" for t in self.capabilities.tools):
                result = await self.session.call_tool("check_experimental_tools_capability", {})
                success = "✅ Supported" in result.content[0].text
                results['experimental_tools'] = success
                logger.info(f"🔬 Experimental tools: {'✅' if success else '❌'}")
            else:
                results['experimental_tools'] = False
                logger.info("🔬 Experimental tools: ❓ (tool not available)")
        except Exception as e:
            results['experimental_tools'] = False
            logger.warning(f"Experimental tools test failed: {e}")
        
        self.client_capabilities = results
        return results
    
    # ================================
    # INTELLIGENT INTERACTIONS
    # ================================
    
    async def explore_filesystem(self, root_path: str = ".") -> None:
        """Intelligently explore the filesystem"""
        logger.info(f"🧭 Starting intelligent filesystem exploration from: {root_path}")
        
        # Step 1: List directory contents
        if any(t.name == "list_directory" for t in self.capabilities.tools):
            logger.info("📂 Step 1: Listing directory contents...")
            try:
                result = await self.session.call_tool(
                    "list_directory",
                    {"directory_path": root_path, "include_hidden": False}
                )
                print("\n" + "="*60)
                print("📂 DIRECTORY CONTENTS")
                print("="*60)
                for item in result.content:
                    print(item.text)
            except Exception as e:
                logger.error(f"Failed to list directory: {e}")
        
        # Step 2: Search for interesting files
        logger.info("🔍 Step 2: Searching for Python files...")
        if any(t.name == "search_files" for t in self.capabilities.tools):
            try:
                result = await self.session.call_tool(
                    "search_files",
                    {"root_path": root_path, "search_text": "def ", "max_results": 5}
                )
                print("\n" + "="*60)
                print("🔍 SEARCH RESULTS (Python functions)")
                print("="*60)
                for item in result.content:
                    print(item.text)
            except Exception as e:
                logger.error(f"Failed to search files: {e}")
        
        # Step 3: Get detailed info about a specific file
        logger.info("📊 Step 3: Getting detailed file information...")
        if any(t.name == "get_file_info" for t in self.capabilities.tools):
            try:
                # Try to get info about the client script itself
                result = await self.session.call_tool(
                    "get_file_info",
                    {"file_path": __file__}
                )
                print("\n" + "="*60)
                print("📊 FILE INFORMATION")
                print("="*60)
                for item in result.content:
                    print(item.text)
            except Exception as e:
                logger.error(f"Failed to get file info: {e}")
    
    async def demonstrate_resources(self) -> None:
        """Demonstrate resource usage"""
        logger.info("📚 Demonstrating resource capabilities...")
        
        # Read sample resource
        try:
            logger.info("📖 Reading sample resource...")
            data, content = await self.session.read_resource("fs://sample")
            print("\n" + "="*60)
            print("📚 SAMPLE RESOURCE")
            print("="*60)
            print(json.dumps(content, indent=2))
        except Exception as e:
            logger.error(f"Failed to read sample resource: {e}")
        
        # Demonstrate file chunking
        try:
            current_file = __file__
            logger.info(f"📦 Reading chunk metadata for: {current_file}")
            data, content = await self.session.read_resource(f"fs://chunks/{current_file}")
            print("\n" + "="*60)
            print("📦 FILE CHUNK METADATA")
            print("="*60)
            print(json.dumps(content, indent=2))
            
            # Read first chunk
            if isinstance(content, dict) and content.get('total_chunks', 0) > 0:
                logger.info("📖 Reading first chunk...")
                chunk_data, chunk_content = await self.session.read_resource(
                    f"fs://chunk/{current_file}/0"
                )
                print("\n" + "="*60)
                print("📖 FIRST CHUNK CONTENT")
                print("="*60)
                print(chunk_content)
                
        except Exception as e:
            logger.error(f"Failed to demonstrate chunking: {e}")
    
    async def demonstrate_prompts(self) -> None:
        """Demonstrate prompt usage"""
        logger.info("💬 Demonstrating prompt capabilities...")
        
        for prompt in self.capabilities.prompts[:3]:  # Show first 3 prompts
            try:
                logger.info(f"💬 Executing prompt: {prompt.name}")
                
                # Prepare arguments based on prompt requirements
                args = {}
                if prompt.arguments:
                    for arg in prompt.arguments:
                        if arg.name == "file_path":
                            args[arg.name] = __file__
                        elif arg.name == "total_chunks":
                            args[arg.name] = "5"
                        elif arg.name == "root_path":
                            args[arg.name] = "."
                        elif arg.name == "search_text":
                            args[arg.name] = "async"
                        elif arg.name == "prompt":
                            args[arg.name] = "Hello from the client!"
                
                result = await self.session.get_prompt(prompt.name, arguments=args)
                print(f"\n{'='*60}")
                print(f"💬 PROMPT: {prompt.name}")
                print("="*60)
                for msg in result.messages:
                    print(f"🧾 {msg.role.capitalize()}: {msg.content.text}")
                    
            except Exception as e:
                logger.error(f"Failed to execute prompt {prompt.name}: {e}")
    
    async def send_progress_updates(self) -> None:
        """Send progress notifications during operations"""
        logger.info("⏳ Sending progress updates...")
        
        try:
            for i in range(5):
                progress = (i + 1) / 5
                await self.session.send_progress_notification(
                    progress_token="demo-progress",
                    progress=progress,
                    total=1.0
                )
                logger.info(f"📊 Progress: {progress*100:.0f}%")
                await asyncio.sleep(0.5)  # Simulate work
                
        except Exception as e:
            logger.error(f"Failed to send progress updates: {e}")
    
    # ================================
    # MAIN EXECUTION WORKFLOW
    # ================================
    
    async def run_comprehensive_demo(self) -> None:
        """Run a comprehensive demonstration of all capabilities"""
        logger.info("🎯 Starting comprehensive MCP demonstration...")
        
        try:
            # Initialize session
            await self.initialize_session()
            
            # Test basic connectivity
            logger.info("🏓 Testing server connectivity...")
            await self.session.send_ping()
            logger.info("✅ Server connectivity confirmed")
            
            # Discover capabilities
            await self.discover_server_capabilities()
            
            # Test client capabilities
            await self.test_client_capabilities()
            
            # Print summary
            self.print_capabilities_summary()
            
            # Run demonstrations
            await self.demonstrate_prompts()
            await self.demonstrate_resources()
            await self.explore_filesystem()
            await self.send_progress_updates()
            
            # Final status
            logger.info("🎉 Comprehensive demonstration completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Demo failed: {e}")
            raise
    
    def print_capabilities_summary(self) -> None:
        """Print a summary of discovered capabilities"""
        print(f"\n{'='*80}")
        print(f"🎯 MCP SERVER CAPABILITIES SUMMARY")
        print(f"{'='*80}")
        
        print(f"📋 Prompts: {len(self.capabilities.prompts)}")
        for prompt in self.capabilities.prompts:
            args_str = f" ({len(prompt.arguments)} args)" if prompt.arguments else ""
            print(f"   💬 {prompt.name}{args_str}")
        
        print(f"\n🛠️ Tools: {len(self.capabilities.tools)}")
        for tool in self.capabilities.tools:
            print(f"   🔧 {tool.name}: {tool.description[:60]}...")
        
        print(f"\n📄 Resource Templates: {len(self.capabilities.resource_templates)}")
        for template in self.capabilities.resource_templates:
            print(f"   🗂️ {template.uriTemplate}")
        
        print(f"\n🗂️ Resources: {len(self.capabilities.resources)}")
        for resource in self.capabilities.resources:
            print(f"   📚 {resource.uri}")
        
        print(f"\n🧪 Client Capabilities:")
        for cap, supported in self.client_capabilities.items():
            status = "✅" if supported else "❌"
            print(f"   {status} {cap.replace('_', ' ').title()}")
        
        print(f"{'='*80}\n")


# ================================
# MAIN EXECUTION
# ================================

async def main():
    """Main execution function"""
    logger.info(f"🚀 Starting {CLIENT_NAME} v{CLIENT_VERSION}")
    
    try:
        async with EnhancedMCPClient() as client:
            await client.run_comprehensive_demo()
            
    except KeyboardInterrupt:
        logger.info("👋 Demo interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
