import pytest
from agent_fender.safe_tool import SafeToolResult, safe_tool


class TestSafeToolResult:
    def test_success_result(self):
        result = SafeToolResult(success=True, data='{"success": true}')
        assert result.success is True
        assert result.data is not None

    def test_error_result(self):
        result = SafeToolResult(success=False, error_type="timeout", user_message="超时")
        assert result.success is False
        assert result.error_type == "timeout"


class TestSafeTool:
    @pytest.mark.asyncio
    async def test_sync_tool_success(self, sync_tool):
        result = await safe_tool(sync_tool, "check_order", '{"order_id": "001"}')
        assert result.success is True
        assert "success" in result.data

    @pytest.mark.asyncio
    async def test_sync_tool_failure(self, sync_tool_fail):
        result = await safe_tool(sync_tool_fail, "bad_tool", '{}')
        assert result.success is False
        assert result.error_type == "execution_error"
        assert result.user_message is not None

    @pytest.mark.asyncio
    async def test_tool_timeout(self):
        import time
        def slow_tool(name, args):
            time.sleep(0.2)
            return '{"success": true}'
        result = await safe_tool(slow_tool, "slow_tool", '{}', timeout_s=0.01)
        assert result.success is False
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_async_tool_success(self):
        async def async_tool(name, args):
            return '{"success": true}'
        result = await safe_tool(async_tool, "test", '{}')
        assert result.success is True
