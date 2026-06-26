"""
LangGraph agent with agent-fender safety layer.

Shows: preflight at node entry, safe_llm for LLM calls,
check_tools before execution, safe_tool for tool calls.
Runs without API keys — uses mock LLM and tools.
"""
import asyncio
from typing import Any

from agent_fender import AgentFender, FenderConfig

# ── Config ──────────────────────────────────────────────
config = FenderConfig(
    max_loop_count=5,
    max_tool_failures=3,
    dangerous_tools=frozenset({"delete_file", "execute_script"}),
    llm_timeout_s=30.0,
    tool_timeout_s=10.0,
)
fender = AgentFender(config)


# ── Mock LLM ────────────────────────────────────────────
async def mock_llm(**kwargs: Any) -> dict[str, Any]:
    messages = kwargs.get("messages", [])
    last = messages[-1]["content"] if messages else ""
    tools = kwargs.get("tools", [])
    if tools and "delete_file" in str(last):
        return {
            "message": {
                "tool_calls": [
                    {"function": {"name": "delete_file", "arguments": '{"path": "/tmp/log.txt"}'}}
                ]
            }
        }
    if tools:
        return {
            "message": {
                "tool_calls": [
                    {"function": {"name": tools[0]["function"]["name"], "arguments": "{}"}}
                ]
            }
        }
    return {"message": {"content": "How can I help?"}}


# ── Mock Tool ───────────────────────────────────────────
def mock_tool(tool_name: str, tool_args: str) -> str:
    if tool_name == "broken":
        raise RuntimeError("database unavailable")
    return f'{{"success": true, "tool": "{tool_name}"}}'


# ── Simulated LangGraph Action Node ─────────────────────
class AgentState:
    def __init__(self):
        self.messages: list[dict[str, str]] = []
        self.loop_count = 0
        self.tool_failures = 0
        self.action_history: list[str] = []
        self.final_reply: str | None = None


async def action_node(state: AgentState):
    # Gate 1: circuit breaker
    breaker = fender.preflight(
        loop_count=state.loop_count,
        tool_failures=state.tool_failures,
        action_history=state.action_history,
    )
    if breaker.should_break:
        state.final_reply = breaker.fallback_reply
        return

    # Gate 5: injection scan
    user_msg = state.messages[-1]["content"] if state.messages else ""
    if fender.check_injection(user_msg).is_suspicious:
        state.final_reply = "Suspicious input detected."
        return

    # Gate 2: safe LLM
    llm_result = await fender.safe_llm(
        mock_llm,
        messages=state.messages,
        tools=[{"function": {"name": "search_docs"}}],
    )
    if not llm_result.success:
        state.final_reply = llm_result.user_message
        return

    tool_calls = llm_result.data["message"].get("tool_calls", []) if llm_result.data else []
    if not tool_calls:
        state.final_reply = llm_result.data["message"]["content"]
        return

    tool_names = [tc["function"]["name"] for tc in tool_calls]
    state.action_history.extend(tool_names)

    # Gate 4: dangerous tool gating
    approval = fender.check_tools(tool_names)
    if approval.requires_approval:
        print(f"  [approval needed] {approval.message}")
        state.final_reply = f"Approval required: {approval.message}"
        return

    # Gate 3: safe tool execution
    for name in tool_names:
        tr = await fender.safe_tool(mock_tool, name, "{}")
        if not tr.success:
            state.tool_failures += 1
            print(f"  [tool error] {name}: {tr.error_type}")
        else:
            print(f"  [tool ok] {name}: {tr.data}")

    state.loop_count += 1


async def main():
    fender.start_session()

    state = AgentState()
    state.messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the latest error in the logs?"},
    ]

    print("=== LangGraph-style agent with agent-fender ===\n")

    for iteration in range(3):
        print(f"Iteration {iteration + 1}:")
        await action_node(state)
        if state.final_reply:
            print(f"  Final reply: {state.final_reply}")
            break
        state.messages.append({"role": "assistant", "content": "Processing..."})

    print(f"\n{fender.stop_session().summary}")


if __name__ == "__main__":
    asyncio.run(main())
