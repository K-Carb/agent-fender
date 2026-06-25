# agent-fender

给 AI Agent 加安全护栏——熔断器 + 审批检查 + 注入检测 + 去重 + 超时兜底 + 审计追踪。纯函数，零依赖。6 个防御组件，54 tests。

```bash
pip install git+https://github.com/Carb/agent-fender.git
```

## 30 秒快速开始

```python
from agent_fender import AgentGuard, GuardConfig

config = GuardConfig(
    max_loop_count=3,
    max_tool_failures=2,
    dangerous_tools=frozenset({"cancel_order", "delete_account"}),
    llm_timeout_s=60.0,
    tool_timeout_s=30.0,
)
guard = AgentGuard(config)

# Step 1: 熔断检查
breaker = guard.preflight(loop_count=2, tool_failures=0)
if breaker.should_break:
    return breaker.fallback_reply

# Step 2: LLM 安全调用
result = await guard.safe_llm(ollama.chat, model="qwen", messages=[...])
if not result.success:
    return result.user_message

# Step 3: 危险工具检测
approval = guard.check_tools(["cancel_order"])
if approval.requires_approval:
    ...  # 触发 interrupt 等人工审批

# Step 4: 工具安全执行
tr = await guard.safe_tool(execute_tool, "check_order", '{"order_id": "001"}')
```

## 解决什么问题

| 开发者会说的话 | 根因 | 对应组件 |
|---|---|---|
| "为什么一直转圈？" | LLM 或工具无超时 | `safe_llm()` + `safe_tool()` |
| "为什么账单这么贵？" | Agent 死循环反复调 LLM | `preflight()` loop_count |
| "为什么订单被取消了？" | 危险工具静默执行 | `check_tools()` |
| "为什么失败后还在重试？" | 工具失败累积 | `preflight()` tool_failures |
| "为什么偶尔好偶尔坏？" | 错误信息被吞 | `LLMResult.error_type` |

完整失败模式手册见 [docs/failure-modes.md](docs/failure-modes.md)。

## 设计

- **零依赖**：纯 Python 标准库，不绑定 LangGraph / Ollama / Pydantic
- **纯函数**：每个组件是独立可测的纯逻辑，不规定图结构
- **Result 模式**：所有返回值是 dataclass，AI copilot 看到类型签名就知道怎么处理
- **门面入口**：`AgentGuard` 四步 API 覆盖 Agent 完整生命周期

## 真实案例

[enterprise-agent](https://github.com/Carb/enterprise-agent) — 基于 LangGraph 的企业客服 Agent，使用 agent-fender 作为安全层。

## License

MIT
