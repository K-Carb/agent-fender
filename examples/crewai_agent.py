"""
CrewAI-style agent with agent-fender safety layer.

Shows: preflight in task execution loop, safe_llm for agent calls,
check_tools for dangerous actions, safe_tool for tool execution.
Runs without API keys — uses mock implementations.
"""
import asyncio
from typing import Any

from agent_fender import AgentFender, FenderConfig

# ── Config ──────────────────────────────────────────────
config = FenderConfig(
    max_loop_count=4,
    max_tool_failures=2,
    dangerous_tools=frozenset({"send_email", "delete_record"}),
    llm_timeout_s=30.0,
    tool_timeout_s=10.0,
)
fender = AgentFender(config)


# ── Mock LLM ────────────────────────────────────────────
async def mock_llm(**kwargs: Any) -> dict[str, Any]:
    task_desc = kwargs.get("task", "")
    if "email" in task_desc:
        return {"content": "I will send an email to the user."}
    return {"content": "Task completed."}


# ── Mock Tool ───────────────────────────────────────────
async def mock_tool(tool_name: str, tool_args: str) -> str:
    if "fail" in tool_args:
        raise RuntimeError("execution failed")
    return f'{{"status": "done", "tool": "{tool_name}"}}'


# ── Simulated CrewAI Task Runner ────────────────────────
class MockTask:
    def __init__(self, description: str, tool_names: list[str]):
        self.description = description
        self.tool_names = tool_names


class MockCrew:
    def __init__(self, tasks: list[MockTask]):
        self.tasks = tasks
        self.tool_failures = 0
        self.action_history: list[str] = []
        self.loop_count = 0


async def run_crew(crew: MockCrew):
    for task in crew.tasks:
        print(f"\nTask: {task.description}")

        # Gate 1: circuit breaker before each task
        breaker = fender.preflight(
            loop_count=crew.loop_count,
            tool_failures=crew.tool_failures,
            action_history=crew.action_history,
        )
        if breaker.should_break:
            print(f"  [breaker] {breaker.reason}: {breaker.fallback_reply}")
            return breaker.fallback_reply

        # Gate 2: safe LLM call
        llm_result = await fender.safe_llm(mock_llm, task=task.description)
        if not llm_result.success:
            print(f"  [llm error] {llm_result.error_type}: {llm_result.user_message}")
            crew.tool_failures += 1
            continue

        print(f"  LLM: {llm_result.data['content']}")

        # Gate 4: dangerous tool gating
        approval = fender.check_tools(task.tool_names)
        if approval.requires_approval:
            print(f"  [approval needed] {approval.message}")
            continue

        # Gate 3: safe tool execution
        crew.action_history.extend(task.tool_names)
        for name in task.tool_names:
            tr = await fender.safe_tool(mock_tool, name, "{}")
            if not tr.success:
                crew.tool_failures += 1
                print(f"  [tool error] {name}: {tr.error_type}")
            else:
                print(f"  [tool ok] {name}: {tr.data}")

        crew.loop_count += 1


async def main():
    fender.start_session()

    tasks = [
        MockTask("Analyze user feedback", ["analyze_sentiment"]),
        MockTask("Send follow-up email to user", ["send_email"]),
        MockTask("Archive completed ticket", ["archive_ticket"]),
    ]
    crew = MockCrew(tasks)

    print("=== CrewAI-style agent with agent-fender ===\n")
    await run_crew(crew)

    print(f"\n{fender.stop_session().summary}")


if __name__ == "__main__":
    asyncio.run(main())
