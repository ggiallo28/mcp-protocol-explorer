# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mcp==1.6.0"
# ]
# ///

# make it more authonomus, the prompt can be used to inject istructions
# so for example tools can be attached to the llm, resources can be provided as context always present, dependng on the tool response the agent decide if it needs to use a resource template.
# Here's a summary of how you've structured the design of your **autonomous MCP agent**, focusing on how it uses **resources**, **tools**, and **prompts** in a unified and intelligent way:

# ---

# ## 🧠 **Design Summary: Using Resources, Tools, and Prompts**

# ### 1. **Prompts as Agent Behavior Modulators**

# - You define a **core prompt** that gives the agent its default personality, strategy, and goals.
# - Server-defined prompts (like `usage_instructions` or `exploration_guide`) are exposed to the LLM as **optional modules**.
# - The agent treats prompts as **"virtual tools"**: the LLM can choose to invoke them via `use_prompt(...)`.
# - Prompts are **not automatically injected** — the agent selects and uses them only when useful based on user input.

# > 🔹 **Why:** This gives you control over the agent’s behavior while keeping it adaptive and context-aware.

# ---

# ### 2. **Tools as Functional Extensions**

# - Tools are listed in the agent's context and described clearly.
# - The LLM selects tools based on intent (e.g., searching, listing, navigating) using structured commands like `call_tool(...)`.
# - Tool outputs are not blindly passed to the user — the agent interprets them and decides the next action.

# > 🔹 **Why:** Tools give the agent capabilities to interact with the file system or data without needing hardcoded behavior.

# ---

# ### 3. **Resources as Context Providers**

# - Resources (like `fs://chunk/...` or `fs://sample`) are used to **enrich the agent’s reasoning context**.
# - Some resources are **pre-loaded** as background knowledge (e.g. metadata, small files).
# - The agent can also dynamically **read resources** when the LLM decides it's necessary via `read_resource(...)`.

# > 🔹 **Why:** Resources allow the agent to include real file/data content in its thinking or response, without hardcoding logic.

# ---

# ### 💡 Unification Strategy

# You designed the system so that **all three elements — prompts, tools, and resources — are treated uniformly** in the LLM’s reasoning process:

# | Element   | Exposed as | Called by LLM as     | Executed via         |
# |-----------|------------|----------------------|-----------------------|
# | Prompt    | Instruction module | `use_prompt(name, args)` | `get_prompt(...)`     |
# | Tool      | Functional action  | `call_tool(name, args)` | `call_tool(...)`      |
# | Resource  | Context / content  | `read_resource(uri)`    | `read_resource(...)`  |

# ---

# ### 🧭 Final Outcome

# You’ve built a **modular, adaptive agent** that:

# - Thinks independently using your core prompt
# - Selects server-side prompts, tools, or resources only when needed
# - Executes those choices automatically
# - Responds naturally based on the combined result

# It’s a beautiful blend of autonomy, modularity, and structured reasoning. Want me to turn this into documentation or an architecture diagram?

from mcp import ClientSession, types, shared
from mcp.client.sse import sse_client
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from typing import Literal
from pydantic import ValidationError
import json

MCP_SERVER_URL = "http://localhost:8080/sse"


async def list_roots_callback(
    context: shared.context.RequestContext,
) -> types.ListRootsResult:
    roots = [types.Root(uri="file:///path/to/directory", name="Project Directory")]
    return types.ListRootsResult(roots=roots)


async def handle_text_message(
    context: shared.context.RequestContext,
    arguments: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    message = arguments.messages[0].content.text
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text=f"In: {message} Out: Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )


async def handle_root_message(
    context: shared.context.RequestContext,
    root: types.Root,
) -> types.CreateMessageResult:
    fake_listing = "- main.py\n- requirements.txt\n- utils/\n- README.md"
    return types.CreateMessageResult(
        role="user",
        content=types.TextContent(
            type="text",
            text=fake_listing,
        ),
        model="root-reader",
    )


async def handle_sampling_message(
    context: shared.context.RequestContext, arguments: types.CreateMessageRequestParams
) -> types.CreateMessageResult:
    print("📩 [Sampling Message] Received:", arguments)

    try:
        root = types.Root(**arguments.metadata)
        return await handle_root_message(context, root)
    except (ValidationError, TypeError):
        return await handle_text_message(context, arguments)


async def logging_callback(level: str, message: str):
    print(f"[{level.upper()}] {message}")


async def message_handler(message: types.JSONRPCMessage):
    print(f"Received message: {message}")


async def initialize(session: ClientSession):
    sampling = types.SamplingCapability()
    roots = types.RootsCapability(
        listChanged=True,
    )

    result = await session.send_request(
        types.ClientRequest(
            types.InitializeRequest(
                method="initialize",
                params=types.InitializeRequestParams(
                    protocolVersion=types.LATEST_PROTOCOL_VERSION,
                    capabilities=types.ClientCapabilities(
                        sampling=sampling,
                        experimental={"advanced_tools": {}},
                        roots=roots,
                    ),
                    clientInfo=types.Implementation(name="mcp", version="0.1.0"),
                ),
            )
        ),
        types.InitializeResult,
    )

    if result.protocolVersion not in SUPPORTED_PROTOCOL_VERSIONS:
        raise RuntimeError(
            "Unsupported protocol version from the server: " f"{result.protocolVersion}"
        )

    await session.send_notification(
        types.ClientNotification(
            types.InitializedNotification(method="notifications/initialized")
        )
    )


async def run():
    async with sse_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(
            read,
            write,
            sampling_callback=handle_sampling_message,
            list_roots_callback=list_roots_callback,
            logging_callback=logging_callback,
            message_handler=message_handler,
        ) as session:
            await session.initialize()

            print("📡 Sending ping...")
            await session.send_ping()
            print("✅ Ping acknowledged.\n")

            print("⚙️ Setting logging level to INFO...")
            # await session.set_logging_level("info")

            # PROMPTS
            print("\n🔍 [Prompts] Listing available prompts...")
            prompts_result = await session.list_prompts()
            for p in prompts_result.prompts:
                print(f"  • {p.name} ({len(p.arguments)} arg(s))")

            if prompts_result.prompts:
                selected_prompt = prompts_result.prompts[0]
                print(f"\n💬 [Prompt] Executing '{selected_prompt.name}'...")
                prompt_result = await session.get_prompt(
                    selected_prompt.name,
                    arguments={"file_path": "/some/file.txt", "total_chunks": "5"},
                )
                for msg in prompt_result.messages:
                    print(f"   🧾 {msg.role.capitalize()} says: {msg.content.text}")

            # TOOLS
            print("\n🔧 [Tools] Listing available tools...")
            tools_result = await session.list_tools()
            tools = tools_result.tools
            for tool in tools:
                print(f"  • {tool.name}: {tool.description}")

            print("\n📁 [Tool] Calling 'list_directory' on current directory...")
            if any(t.name == "list_directory" for t in tools):
                tool_result = await session.call_tool(
                    "list_directory", {"directory_path": "."}
                )
                print("   📂 Contents:")
                for item in tool_result.content:
                    print(f"     - {item.text}")
            else:
                print("⚠️  'list_directory' tool not available.")

            print(
                "\n📁 [Tool] Calling 'check_experimental_tools_capability' for Sampling..."
            )
            if any(t.name == "check_experimental_tools_capability" for t in tools):
                tool_result = await session.call_tool(
                    "check_experimental_tools_capability", {}
                )
                print(tool_result)
                print("   📂 Contents:")
                for item in tool_result.content:
                    print(f"     - {item.text}")
            else:
                print("⚠️  'check_experimental_tools_capability' tool not available.")

            print("\n📁 [Tool] Calling 'check_sampling_capability' for Sampling...")
            if any(t.name == "check_sampling_capability" for t in tools):
                tool_result = await session.call_tool(
                    "check_sampling_capability", {"prompt": "Hi Model!"}
                )
                print(tool_result)
                print("   📂 Contents:")
                for item in tool_result.content:
                    print(f"     - {item.text}")
            else:
                print("⚠️  'check_sampling_capability' tool not available.")

            # RESOURCE LISTING
            print("\n🗂️ [Resources] Listing referenced resources...")
            resources = await session.list_resource_templates()
            if not resources.resourceTemplates:
                print("   ⚠️ No resources registered in the session.")
            else:
                for res in resources.resourceTemplates:
                    print(f"   • {res.uriTemplate}")

            # RESOURCES
            print("\n📖 [Resource] Reading metadata: fs://chunks/client.py")
            chunk_meta, meta_output = await session.read_resource(
                "fs://chunks/client.py"
            )
            print("   📦 Metadata:", chunk_meta)
            print("   📄 Contents:", meta_output)

            print("\n📖 [Resource] Reading chunk 0: fs://chunk/client.py/0")
            chunk_data, chunk_output = await session.read_resource(
                "fs://chunk/client.py/0"
            )
            print("   📦 Metadata:", chunk_data)
            print("   📄 Contents:", chunk_output)

            # Progress update example
            print("\n⏳ Sending fake progress notification...")
            await session.send_progress_notification(
                progress_token="loading", progress=0.7, total=1.0
            )
            print("✅ Progress update sent.\n")

            # List resources used
            print("\n🗂️ Listing referenced resources...")
            resource_list = await session.list_resources()
            print(resource_list)
            for res in resource_list.resources:
                print(f"   • {res.uri}")

            print("\n📖 [Resource] Reading metadata: fs://sample")
            chunk_meta, meta_output = await session.read_resource("fs://sample")
            print("   📦 Metadata:", chunk_meta)
            print("   📄 Contents:", meta_output)

            # subscribe and unsubscribe
            print("\n📖 [Subscribe/Unsubscribe] Validate on fs://sample")
            try:
                await session.subscribe_resource("fs://sample")
                await session.unsubscribe_resource("fs://sample")
                print("✅ Subscribed and unsubscribed.")
            except Exception as e:
                print(f"⚠️ Subscription failed: {e}")

            print("\n📁 [Tool] Calling 'check_roots_capability' for Sampling...")
            if any(t.name == "check_roots_capability" for t in tools):
                tool_result = await session.call_tool("check_roots_capability", {})
                print(tool_result)
                print("   📂 Contents:")
                for item in tool_result.content:
                    print(f"     - {item.text}")
            else:
                print("⚠️  'check_roots_capability' tool not available.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
