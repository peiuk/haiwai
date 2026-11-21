"""调用大模型拿结构化结果：每日资讯、后台「AI 判断是否广告号」共用。

LLM_API_BASE 留空用 Claude；填了就走 OpenAI 兼容接口（OpenAI、DeepSeek、Grok 等，填到 /v1 为止），此时 LLM_MODEL 必填。
"""
from typing import TypeVar

import anthropic
import httpx
from pydantic import BaseModel

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """没配密钥、调用失败或返回看不懂：调用方什么都不写。"""


def ask_json(system: str, prompt: str, schema: type[T], json_shape: str) -> T:
    """json_shape：给 OpenAI 兼容接口的格式说明（它们没有按 schema 输出的统一写法，只能在提示里讲清楚）。"""
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMUnavailable("还没有配置 AI 密钥（.env 里的 LLM_API_KEY）")
    if settings.llm_api_base:
        return _openai_compatible(settings, system + json_shape, prompt, schema)
    # 默认 10 分钟、再重试两次：AI 卡住时后台任务能挂半小时。和 OpenAI 兼容接口一样封顶 300 秒
    client = anthropic.Anthropic(api_key=settings.llm_api_key, timeout=300)
    try:
        # 用流式：思考也算在 max_tokens 里，一次 60 条资讯 16000 不够；超过约 2 万的上限 SDK 要求流式，否则会超时
        with client.beta.messages.stream(
            model=settings.llm_model or "claude-opus-5-5",
            max_tokens=64000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # 主模型拒答时由服务端换模型重试
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APIError as err:
        raise LLMUnavailable(f"AI 调用失败：{err}") from err
    except ValueError as err:  # 写到一半被截断或拒答，JSON 校验不过（pydantic 的 ValidationError 是 ValueError）
        raise LLMUnavailable(f"AI 返回的内容不完整：{err}") from err
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LLMUnavailable("AI 没有给出结果")
    return response.parsed_output


def _openai_compatible(settings, system: str, prompt: str, schema: type[T]) -> T:
    """OpenAI 兼容的 /chat/completions。用 json_object 模式（各家兼容接口普遍支持），再按 schema 校验。"""
    if not settings.llm_model:
        raise LLMUnavailable("用 OpenAI 兼容接口时要在 .env 里填 LLM_MODEL")
    body = {
        "model": settings.llm_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        # 推理模型（Grok 4.7 等）默认想得很久：5 条资讯 8 千多推理 token、近 2 分钟；low 约 24 秒、省 4/5 费用
        "reasoning_effort": "low",
    }
    url = f"{settings.llm_api_base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    try:
        # 300 秒：每日资讯给 GOV.UK 稿写几百字正文，一次输出上万字；nginx 的 proxy_read_timeout 也是 300
        response = httpx.post(url, headers=headers, json=body, timeout=300)
        if response.status_code == 400:  # 不支持 reasoning_effort 的模型会拒收，去掉再试一次
            body.pop("reasoning_effort")
            response = httpx.post(url, headers=headers, json=body, timeout=300)
        response.raise_for_status()
        return schema.model_validate_json(response.json()["choices"][0]["message"]["content"])
    except httpx.HTTPError as err:
        raise LLMUnavailable(f"AI 调用失败：{err}") from err
    except (KeyError, IndexError, TypeError, ValueError) as err:  # 返回格式不对（含 JSON 校验失败）
        raise LLMUnavailable(f"AI 返回的内容看不懂：{err}") from err
