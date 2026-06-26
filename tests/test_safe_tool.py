import pytest
from agent_fender.safe_tool import SafeToolResult, safe_tool


class TestSafeToolResult:
    def test_success_result(self):
        result = SafeToolResult(success=True, data='{"success": true}')
        assert result.success is True
        assert result.data is not None

    def test_error_result(self):
        result = SafeToolResult(success=False, error_type="timeout", user_message="timed out")
        assert result.success is False
        assert result.error_type == "timeout"

    def test_is_retryable_timeout(self):
        result = SafeToolResult(success=False, error_type="timeout")
        assert result.is_retryable is True

    def test_is_retryable_execution_error(self):
        result = SafeToolResult(success=False, error_type="execution_error")
        assert result.is_retryable is False

    def test_is_retryable_success(self):
        result = SafeToolResult(success=True)
        assert result.is_retryable is False


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


class TestSafeToolRetry:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        import time
        call_count = 0

        def flaky_tool(name, args):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                time.sleep(0.1)
            return '{"success": true}'

        result = await safe_tool(flaky_tool, "test", '{}',
                                 timeout_s=0.01, retries=2, retry_base_delay_s=0.01)
        assert result.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_execution_error(self):
        def bad_tool(name, args):
            raise RuntimeError("bad")
        result = await safe_tool(bad_tool, "test", '{}',
                                 retries=2, retry_base_delay_s=0.01)
        assert result.success is False
        assert result.error_type == "execution_error"

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        import time
        def slow_tool(name, args):
            time.sleep(0.1)
            return '{}'
        result = await safe_tool(slow_tool, "test", '{}',
                                 timeout_s=0.01, retries=2, retry_base_delay_s=0.01)
        assert result.success is False
        assert result.error_type == "timeout"
