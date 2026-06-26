"""
Minimal example: adding safety guardrails to a LangGraph agent with agent-fender.

Demonstrates: AgentFender 4-step call → preflight / safe_llm / check_tools / safe_tool
"""
import asyncio

from agent_fender import AgentFender, FenderConfig


# ── Step 0: Create config and fender ───────────────────
config = FenderConfig(
    max_loop_count=3,
    max_tool_failures=2,
    dangerous_tools=frozenset({"delete_account", "transfer_money"}),
    llm_timeout_s=30.0,
    tool_timeout_s=10.0,
)
fender = AgentFender(config)


# ── Mock LLM and tools ──────────────────────────────────
def fake_llm(**kwargs):
    """Mock LLM: returns a selected tool call"""
    tools = kwargs.get("tools", [])
    if tools:
        return {
            "message": {
                "tool_calls": [
                    {"function": {"name": tools[0]["function"]["name"], "arguments": "{}"}}
                ]
            }
        }
    return {"message": {"content": "Hello, how can I help you?"}}


def fake_execute_tool(tool_name: str, tool_args: str) -> str:
    """Mock tool execution"""
    if tool_name == "broken_tool":
        raise RuntimeError("Database connection failed")
    return '{"success": true, "data": "Operation completed"}'


# ── Simulate a 4-step action node ─────────────────────
async def demo_action_node():
    loop_count = 2
    tool_failures = 0

    # Step 1: Circuit breaker check
    breaker = fender.preflight(loop_count=loop_count, tool_failures=tool_failures)
    if breaker.should_break:
        print(f"[breaker] {breaker.reason}: {breaker.fallback_reply}")
        return

    # Step 2: Safe LLM call
    llm_result = await fender.safe_llm(
        fake_llm, model="qwen",
        messages=[{"role": "user", "content": "Search the logs for errors"}],
        tools=[{"function": {"name": "search_logs"}}],
    )
    if not llm_result.success:
        print(f"[LLM error] {llm_result.error_type}: {llm_result.user_message}")
        return

    # Step 3: Dangerous tool check
    tool_names = ["search_logs"]
    approval = fender.check_tools(tool_names)
    if approval.requires_approval:
        print(f"[approval] {approval.message}")
        return

    # Step 4: Safe tool execution
    for tool_name in tool_names:
        tr = await fender.safe_tool(fake_execute_tool, tool_name, "{}")
        if not tr.success:
            tool_failures += 1
            print(f"[tool error] {tr.error_type}: {tr.user_message}")
        else:
            print(f"[success] {tool_name}: {tr.data}")

    # ── Demonstrate dangerous tool detection ──
    approval = fender.check_tools(["transfer_money"])
    print(f"[dangerous] requires_approval={approval.requires_approval}")


if __name__ == "__main__":
    asyncio.run(demo_action_node())
