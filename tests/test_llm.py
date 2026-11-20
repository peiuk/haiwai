"""ask_json 走 Claude 时：回答被截断（JSON 不完整）要报 LLMUnavailable，不能变成 500。"""
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import app.llm as llm


class Out(BaseModel):
    items: list[int]


def fake_claude(monkeypatch, final):
    """final：get_final_message 的返回值，或要抛的异常。记下请求参数供断言。"""
    calls = {}

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            if isinstance(final, Exception):
                raise final
            return final

    def stream(**kwargs):
        calls.update(kwargs)
        return Stream()

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)))
    monkeypatch.setattr(llm.anthropic, "Anthropic", lambda **_: client)
    monkeypatch.setattr(llm, "get_settings", lambda: SimpleNamespace(llm_api_key="test", llm_api_base="", llm_model=""))
    return calls


def test_truncated_answer_is_llm_unavailable(monkeypatch):
    try:
        Out.model_validate_json('{"items":[1,2')  # 写到一半被 max_tokens 截断
    except ValueError as err:
        truncated = err
    fake_claude(monkeypatch, truncated)
    with pytest.raises(llm.LLMUnavailable, match="不完整"):
        llm.ask_json("s", "p", Out, "")


def test_openai_compatible_retries_without_reasoning_effort_on_400(monkeypatch):
    import httpx

    sent = []

    def post(url, headers, json, timeout):
        sent.append(dict(json))
        request = httpx.Request("POST", url)
        if "reasoning_effort" in json:  # 模拟不支持这个参数的模型
            return httpx.Response(400, json={"error": "unknown parameter"}, request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"items":[3]}'}}]}, request=request)

    monkeypatch.setattr(llm.httpx, "post", post)
    monkeypatch.setattr(llm, "get_settings", lambda: SimpleNamespace(llm_api_key="test", llm_api_base="https://x/v1", llm_model="m"))
    assert llm.ask_json("s", "p", Out, "").items == [3]
    assert [("reasoning_effort" in body) for body in sent] == [True, False]


def test_parsed_answer_is_returned_with_room_for_thinking(monkeypatch):
    calls = fake_claude(monkeypatch, SimpleNamespace(stop_reason="end_turn", parsed_output=Out(items=[1])))
    assert llm.ask_json("s", "p", Out, "").items == [1]
    assert calls["max_tokens"] >= 64000 and calls["output_format"] is Out
