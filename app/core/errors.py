class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def validation_message(errors: list[dict]) -> str:
    """把请求校验错误转成一句给用户看的中文。校验器里自己写的提示原样用，内置规则给通用说法。"""
    if not errors:
        return "填写的内容不对，请检查后再试"
    error = errors[0]
    kind = str(error.get("type", ""))
    ctx = error.get("ctx") or {}
    if kind == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ") or "填写的内容不对，请检查后再试"
    if kind == "missing":
        return "有必填项没填"
    if kind == "string_too_long":
        return f"内容太长了，最多 {ctx.get('max_length')} 个字"
    if kind == "string_too_short":
        return f"内容太短了，至少 {ctx.get('min_length')} 个字"
    if kind in {"too_long", "too_short"}:
        return "数量超出了允许的范围"
    return "填写的内容格式不对，请检查后再试"
