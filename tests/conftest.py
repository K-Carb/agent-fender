import pytest
from agent_fender.config import GuardConfig


@pytest.fixture
def config():
    return GuardConfig(
        max_loop_count=3,
        max_tool_failures=3,
        dangerous_tools=frozenset({"cancel_order", "modify_user_address"}),
        llm_timeout_s=60.0,
        tool_timeout_s=30.0,
    )


@pytest.fixture
def sync_func():
    """模拟同步 LLM 调用"""
    def chat(**kwargs):
        return {"message": {"content": "你好"}}
    return chat


@pytest.fixture
def sync_func_fail():
    """模拟同步 LLM 调用——连接失败"""
    def chat(**kwargs):
        raise ConnectionError("Connection refused")
    return chat


@pytest.fixture
async def async_func():
    """模拟异步 LLM 调用"""
    async def chat(**kwargs):
        return {"message": {"content": "你好"}}
    return chat


@pytest.fixture
def sync_tool():
    """模拟同步工具函数"""
    def execute(tool_name, tool_args):
        return '{"success": true}'
    return execute


@pytest.fixture
def sync_tool_fail():
    """模拟同步工具函数——执行失败"""
    def execute(tool_name, tool_args):
        raise RuntimeError("tool crashed")
    return execute
