
import sys

import pytest
from agent_fender.safe_llm import LLMResult, safe_llm_chat, safe_embed


class TestLLMResult:
    def test_success_result(self):
        result = LLMResult(success=True, data={"message": {"content": "hi"}})
        assert result.success is True
        assert result.data == {"message": {"content": "hi"}}
        assert result.error_type is None

    def test_error_result(self):
        result = LLMResult(success=False, error_type="timeout", user_message="timed out")
        assert result.success is False
        assert result.error_type == "timeout"
        assert result.user_message == "timed out"


class TestSafeLlmChat:
    @pytest.mark.asyncio
    async def test_sync_func_returns_success(self, sync_func):
        result = await safe_llm_chat(sync_func, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is True
        assert result.data["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_async_func_returns_success(self, async_func):
        result = await safe_llm_chat(async_func, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is True

    @pytest.mark.asyncio
    async def test_connection_error(self, sync_func_fail):
        result = await safe_llm_chat(sync_func_fail, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "connection"
        assert result.user_message is not None

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.wait_for + to_thread timeout unreliable on 3.10")
    @pytest.mark.asyncio
    async def test_timeout(self):
        import time
        def slow_func(**kwargs):
            time.sleep(0.2)
            return {"message": {"content": "hi"}}
        result = await safe_llm_chat(slow_func, timeout_s=0.01,
                                     model="test",
                                     messages=[{"role": "user", "content": "hi"}],
                                     fallback_message="timed out")
        assert result.success is False
        assert result.error_type == "timeout"
        assert result.user_message == "timed out"

    @pytest.mark.asyncio
    async def test_generic_error(self, config):
        def bad_func(**kwargs):
            raise ValueError("something went wrong")
        result = await safe_llm_chat(bad_func, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "response"
        assert "something went wrong" in result.error_message


class TestLLMResultProperties:
    def test_is_retryable_timeout(self):
        result = LLMResult(success=False, error_type="timeout")
        assert result.is_retryable is True

    def test_is_retryable_connection(self):
        result = LLMResult(success=False, error_type="connection")
        assert result.is_retryable is True

    def test_is_retryable_response(self):
        result = LLMResult(success=False, error_type="response")
        assert result.is_retryable is False

    def test_is_retryable_success(self):
        result = LLMResult(success=True)
        assert result.is_retryable is False


class TestSafeEmbed:
    @pytest.mark.asyncio
    async def test_sync_embed_success(self):
        def embed(model, input):
            return {"embeddings": [[0.1, 0.2]]}
        result = await safe_embed(embed, model="test", input="hello")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_embed_timeout(self):
        def embed(model, input):
            raise TimeoutError()
        result = await safe_embed(embed, timeout_s=0.001, model="test", input="hello")
        assert result.success is False
        assert result.error_type == "timeout"

    @pytest.mark.asyncio
    async def test_embed_connection_error(self):
        def embed(model, input):
            raise ConnectionError("Connection refused")
        result = await safe_embed(embed, model="test", input="hello")
        assert result.success is False
        assert result.error_type == "connection"

    @pytest.mark.asyncio
    async def test_embed_custom_fallback(self):
        def embed(model, input):
            raise RuntimeError("bad")
        result = await safe_embed(embed, model="test", input="hello",
                                  fallback_message="Custom fallback")
        assert result.user_message == "Custom fallback"


class TestSafeLlmChatRetry:
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.wait_for + to_thread timeout unreliable on 3.10")
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        import time
        call_count = 0

        def flaky_func(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                time.sleep(0.1)
            return {"message": {"content": "ok"}}

        result = await safe_llm_chat(flaky_func, timeout_s=0.01,
                                     retries=2, retry_base_delay_s=0.01,
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_response_error(self):
        def bad_func(**kwargs):
            raise ValueError("bad")
        result = await safe_llm_chat(bad_func, retries=2, retry_base_delay_s=0.01,
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "response"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.wait_for + to_thread timeout unreliable on 3.10")
    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        import time
        def slow_func(**kwargs):
            time.sleep(0.1)
            return {}
        result = await safe_llm_chat(slow_func, timeout_s=0.01,
                                     retries=2, retry_base_delay_s=0.01,
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "timeout"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.wait_for + to_thread timeout unreliable on 3.10")
    @pytest.mark.asyncio
    async def test_retries_zero_is_no_retry(self):
        import time
        def slow_func(**kwargs):
            time.sleep(0.1)
            return {}
        result = await safe_llm_chat(slow_func, timeout_s=0.01,
                                     retries=0,
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        call_count = 0

        def flaky_conn(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("refused")
            return {"message": {"content": "ok"}}

        result = await safe_llm_chat(flaky_conn, retries=2, retry_base_delay_s=0.01,
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is True
        assert call_count == 2
