import pytest
from agent_fender.config import FenderConfig


@pytest.fixture
def config():
    return FenderConfig(
        max_loop_count=3,
        max_tool_failures=3,
        dangerous_tools=frozenset({"delete_file", "modify_config"}),
        llm_timeout_s=60.0,
        tool_timeout_s=30.0,
    )


@pytest.fixture
def sync_func():
    """Mock synchronous LLM call"""
    def chat(**kwargs):
        return {"message": {"content": "hello"}}
    return chat


@pytest.fixture
def sync_func_fail():
    """Mock synchronous LLM call — connection error"""
    def chat(**kwargs):
        raise ConnectionError("Connection refused")
    return chat


@pytest.fixture
async def async_func():
    """Mock async LLM call"""
    async def chat(**kwargs):
        return {"message": {"content": "hello"}}
    return chat


@pytest.fixture
def sync_tool():
    """Mock synchronous tool function"""
    def execute(tool_name, tool_args):
        return '{"success": true}'
    return execute


@pytest.fixture
def sync_tool_fail():
    """Mock synchronous tool function — execution error"""
    def execute(tool_name, tool_args):
        raise RuntimeError("tool crashed")
    return execute
