"""
AutoGen-style agent with agent-fender safety layer.

Shows: preflight before each turn, safe_llm for model calls,
check_tools for function calls, safe_tool for execution.
Runs without API keys — uses mock implementations.
"""
import asyncio
from typing import Any

from agent_fender import AgentFender, FenderConfig

# ── Config ──────────────────────────────────────────────
config = FenderConfig(
    max_loop_count=5,
    max_tool_failures=2,
    dangerous_tools=frozenset({"execute_code", "write_file"}),
    llm_timeout_s=30.0,
    tool_timeout_s=10.0,
)
fender = AgentFender(config)


# ── Mock LLM ────────────────────────────────────────────
async def mock_llm(**kwargs: Any) -> dict[str, Any]:
    prompt = kwargs.get("prompt", "")
    if "weather" in prompt:
        return {"content": "The weather is sunny.", "tool_calls": ["get_weather"]}
    if "code" in prompt:
        return {"content": "Running the code.", "tool_calls": ["execute_code"]}
    return {"content": "I understand. What else?"}


# ── Mock Tools ──────────────────────────────────────────
async def get_weather(location: str) -> str:
    return f'{{"location": "{location}", "temp": "22C", "condition": "sunny"}}'


async def execute_code(code: str) -> str:
    return f'{{"output": "Code executed: {code[:20]}..."}}'


# ── Simulated AutoGen ConversableAgent ──────────────────
class MockConversableAgent:
    def __init__(self, name: str, system_message: str):
        self.name = name
        self.system_message = system_message
        self.action_history: list[str] = []

    async def generate_reply(self, messages: list[dict[str, str]]) -> str | None:
        loop_count = len(self.action_history)
        tool_failures = 0

        # Gate 1: circuit breaker
        breaker = fender.preflight(
            loop_count=loop_count,
            tool_failures=tool_failures,
            action_history=self.action_history,
        )
        if breaker.should_break:
            return breaker.fallback_reply

        # Gate 5: injection scan on last user message
        user_texts = [m["content"] for m in messages if m["role"] == "user"]
        if user_texts and fender.check_injection(user_texts[-1]).is_suspicious:
            return "Suspicious input detected."

        # Gate 2: safe LLM
        llm_result = await fender.safe_llm(
            mock_llm,
            prompt=messages[-1]["content"] if messages else "",
        )
        if not llm_result.success:
            return llm_result.user_message

        data = llm_result.data
        tool_calls = data.get("tool_calls", [])

        if not tool_calls:
            return data["content"]

        self.action_history.extend(tool_calls)

        # Gate 4: dangerous tool gating
        approval = fender.check_tools(tool_calls)
        if approval.requires_approval:
            print(f"  [{self.name}] approval needed: {approval.message}")
            return f"Approval required: {approval.message}"

        # Gate 3: safe tool execution
        results = []
        for name in tool_calls:
            if name == "get_weather":
                tr = await fender.safe_tool(get_weather, "London")
            elif name == "execute_code":
                tr = await fender.safe_tool(execute_code, "print('hello')")
            else:
                continue
            results.append(tr.data if tr.success else tr.user_message)
            if not tr.success:
                tool_failures += 1

        return f"{data['content']} Results: {', '.join(map(str, results))}"


async def main():
    fender.start_session()

    agent = MockConversableAgent("assistant", "You are a helpful AI.")

    conversation = [
        {"role": "user", "content": "What is the weather in London?"},
        {"role": "user", "content": "Can you run some Python code?"},
    ]

    print("=== AutoGen-style agent with agent-fender ===\n")

    for i, msg in enumerate(conversation):
        print(f"User: {msg['content']}")
        reply = await agent.generate_reply([msg])
        print(f"{agent.name}: {reply}\n")

    print(fender.stop_session().summary)


if __name__ == "__main__":
    asyncio.run(main())
