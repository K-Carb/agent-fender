import asyncio

import pytest
from agent_fender.safe_llm import LLMResult, safe_llm_chat, safe_embed


class TestLLMResult:
    def test_success_result(self):
        result = LLMResult(success=True, data={"message": {"content": "hi"}})
        assert result.success is True
        assert result.data == {"message": {"content": "hi"}}
        assert result.error_type is None

    def test_error_result(self):
        result = LLMResult(success=False, error_type="timeout", user_message="超时")
        assert result.success is False
        assert result.error_type == "timeout"
        assert result.user_message == "超时"


class TestSafeLlmChat:
    @pytest.mark.asyncio
    async def test_sync_func_returns_success(self, sync_func):
        result = await safe_llm_chat(sync_func, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is True
        assert result.data["message"]["content"] == "你好"

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

    @pytest.mark.asyncio
    async def test_timeout(self):
        import time
        def slow_func(**kwargs):
            time.sleep(0.2)
            return {"message": {"content": "hi"}}
        result = await safe_llm_chat(slow_func, timeout_s=0.01,
                                     model="test",
                                     messages=[{"role": "user", "content": "hi"}],
                                     fallback_message="超时了")
        assert result.success is False
        assert result.error_type == "timeout"
        assert result.user_message == "超时了"

    @pytest.mark.asyncio
    async def test_generic_error(self, config):
        def bad_func(**kwargs):
            raise ValueError("something went wrong")
        result = await safe_llm_chat(bad_func, model="test",
                                     messages=[{"role": "user", "content": "hi"}])
        assert result.success is False
        assert result.error_type == "response"
        assert "something went wrong" in result.error_message


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
            raise asyncio.TimeoutError()
        result = await safe_embed(embed, timeout_s=0.001, model="test", input="hello")
        assert result.success is False
        assert result.error_type == "timeout"
