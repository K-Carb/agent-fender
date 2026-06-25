"""
最简示例：用 agent-fender 给 LangGraph agent 加安全护栏。

展示：AgentGuard 四步调用 → preflight / safe_llm / check_tools / safe_tool
"""
import asyncio

from agent_fender import AgentGuard, GuardConfig


# ── Step 0: 创建配置和护栏 ────────────────────────────
config = GuardConfig(
    max_loop_count=3,
    max_tool_failures=2,
    dangerous_tools=frozenset({"delete_account", "transfer_money"}),
    llm_timeout_s=30.0,
    tool_timeout_s=10.0,
)
guard = AgentGuard(config)


# ── 模拟 LLM 和工具 ──────────────────────────────────
def fake_llm(**kwargs):
    """模拟 LLM：返回一个选中的工具调用"""
    tools = kwargs.get("tools", [])
    if tools:
        return {
            "message": {
                "tool_calls": [
                    {"function": {"name": tools[0]["function"]["name"], "arguments": "{}"}}
                ]
            }
        }
    return {"message": {"content": "你好，有什么可以帮你的？"}}


def fake_execute_tool(tool_name: str, tool_args: str) -> str:
    """模拟工具执行"""
    if tool_name == "broken_tool":
        raise RuntimeError("连接数据库失败")
    return '{"success": true, "data": "操作完成"}'


# ── 模拟一个 Action 节点的四步调用 ─────────────────────
async def demo_action_node():
    loop_count = 2
    tool_failures = 0

    # Step 1: 熔断检查
    breaker = guard.preflight(loop_count=loop_count, tool_failures=tool_failures)
    if breaker.should_break:
        print(f"[熔断] {breaker.reason}: {breaker.fallback_reply}")
        return

    # Step 2: LLM 安全调用
    llm_result = await guard.safe_llm(
        fake_llm, model="qwen",
        messages=[{"role": "user", "content": "查订单"}],
        tools=[{"function": {"name": "check_order"}}],
    )
    if not llm_result.success:
        print(f"[LLM 故障] {llm_result.error_type}: {llm_result.user_message}")
        return

    # Step 3: 危险工具检测
    tool_names = ["check_order"]
    approval = guard.check_tools(tool_names)
    if approval.requires_approval:
        print(f"[审批] {approval.message}")
        return

    # Step 4: 安全执行工具
    for tool_name in tool_names:
        tr = await guard.safe_tool(fake_execute_tool, tool_name, "{}")
        if not tr.success:
            tool_failures += 1
            print(f"[工具失败] {tr.error_type}: {tr.user_message}")
        else:
            print(f"[成功] {tool_name}: {tr.data}")

    # ── 演示危险工具检测 ──
    approval = guard.check_tools(["transfer_money"])
    print(f"[危险检测] requires_approval={approval.requires_approval}")


if __name__ == "__main__":
    asyncio.run(demo_action_node())
