import pytest
from httpx import Request, Response
import builtins

from tiny_code_agent.providers import factory
from tiny_code_agent.llm import LLMProviderError
from tiny_code_agent.llm import AssistantTurn, ToolCallResult
from tiny_code_agent.providers import (
    all_supported_models,
    build_llm_client,
    default_model_for_provider,
    supported_models_for_provider,
    supported_providers,
)
from tiny_code_agent.providers.openai import (
    OpenAIClient,
    _get_output_text,
    _get_tool_calls,
    _normalize_openai_error,
    _response_output_as_messages,
)


def _status_error(error_cls, status_code: int):
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(status_code, request=request)
    return error_cls("boom", response=response, body=None)


def _status_error_with_body(error_cls, status_code: int, body: dict):
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(status_code, request=request)
    return error_cls("boom", response=response, body=body)


def test_default_model_for_openai() -> None:
    assert default_model_for_provider("openai") == "gpt-5-mini"


def test_supported_provider_helpers() -> None:
    assert supported_providers() == ["openai"]
    assert supported_models_for_provider("openai") == ["gpt-5-mini", "gpt-5-nano"]
    assert all_supported_models() == ["gpt-5-mini", "gpt-5-nano"]


def test_supported_provider_helpers_scale_to_multiple_entries(monkeypatch) -> None:
    monkeypatch.setattr(
        factory,
        "PROVIDER_MODELS",
        {
            "openai": ["gpt-5-mini", "gpt-5-nano"],
            "anthropic": ["claude-3-7-sonnet", "claude-3-5-haiku"],
        },
    )

    assert supported_providers() == ["anthropic", "openai"]
    assert supported_models_for_provider("openai") == ["gpt-5-mini", "gpt-5-nano"]
    assert default_model_for_provider("anthropic") == "claude-3-7-sonnet"
    assert all_supported_models() == [
        "claude-3-5-haiku",
        "claude-3-7-sonnet",
        "gpt-5-mini",
        "gpt-5-nano",
    ]


def test_supported_models_for_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        supported_models_for_provider("missing")


def test_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        default_model_for_provider("deepseek")


def test_build_unknown_provider_has_clear_error() -> None:
    with pytest.raises(ValueError, match="unsupported provider"):
        build_llm_client("anthropic")


def test_normalize_openai_error_falls_back_to_generic_message() -> None:
    error = _normalize_openai_error(RuntimeError("boom"))

    assert isinstance(error, LLMProviderError)
    assert error.message == "OpenAI request failed: boom"


def test_normalize_openai_error_handles_authentication_error() -> None:
    from openai import AuthenticationError

    error = _normalize_openai_error(_status_error(AuthenticationError, 401))

    assert error.message == "OpenAI authentication failed. Check OPENAI_API_KEY and try again."


def test_normalize_openai_error_handles_rate_limit_error() -> None:
    from openai import RateLimitError

    error = _normalize_openai_error(_status_error(RateLimitError, 429))

    assert "quota or rate limit was exceeded" in error.message


def test_normalize_openai_error_handles_timeout_error() -> None:
    from openai import APITimeoutError

    request = Request("POST", "https://api.openai.com/v1/responses")
    error = _normalize_openai_error(APITimeoutError(request))

    assert error.message == "OpenAI timed out while generating a response. Try again."


def test_normalize_openai_error_handles_connection_error() -> None:
    from openai import APIConnectionError

    request = Request("POST", "https://api.openai.com/v1/responses")
    error = _normalize_openai_error(APIConnectionError(request=request))

    assert error.message == "Could not reach OpenAI. Check your network connection and try again."


def test_normalize_openai_error_handles_status_error() -> None:
    from openai import APIStatusError

    error = _normalize_openai_error(_status_error(APIStatusError, 500))

    assert error.message == "OpenAI returned an API error (status 500). Try again later."


def test_normalize_openai_error_includes_status_error_body_message() -> None:
    from openai import APIStatusError

    error = _normalize_openai_error(
        _status_error_with_body(APIStatusError, 400, {"error": {"message": "Bad tool result format"}})
    )

    assert error.message == (
        "OpenAI returned an API error (status 400). Try again later. Details: Bad tool result format"
    )


def test_get_output_text_prefers_output_text_attribute() -> None:
    class ResponseLike:
        output_text = "ready"

    assert _get_output_text(ResponseLike()) == "ready"


def test_get_output_text_falls_back_to_message_content() -> None:
    class Content:
        def __init__(self, type_, text):
            self.type = type_
            self.text = text

    class Item:
        def __init__(self, type_, content):
            self.type = type_
            self.content = content

    class ResponseLike:
        output_text = None
        output = [
            Item("message", [Content("output_text", "hello"), Content("text", "world")]),
            Item("reasoning", []),
        ]

    assert _get_output_text(ResponseLike()) == "hello\nworld"


def test_get_tool_calls_parses_valid_and_invalid_json() -> None:
    class Item:
        def __init__(self, type_, call_id=None, name=None, arguments=None):
            self.type = type_
            self.call_id = call_id
            self.name = name
            self.arguments = arguments

    class ResponseLike:
        output = [
            Item("function_call", "call_1", "read_file", '{"path": "README.md"}'),
            Item("function_call", "call_2", "edit_file", "{bad json"),
            Item("message"),
        ]

    calls = _get_tool_calls(ResponseLike())

    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "README.md"}
    assert calls[1].arguments["_invalid_json"] == "{bad json"
    assert "_error" in calls[1].arguments


def test_response_output_as_messages_keeps_model_dump_and_dict_items() -> None:
    class Dumpable:
        def model_dump(self):
            return {"type": "message", "content": "hi"}

    class ResponseLike:
        output = [Dumpable(), {"type": "function_call"}]

    assert _response_output_as_messages(ResponseLike()) == [
        {"type": "message", "content": "hi"},
        {"type": "function_call"},
    ]


def test_openai_tool_result_message_serializes_output() -> None:
    client = object.__new__(OpenAIClient)

    message = client.tool_result_message(
        ToolCallResult(call_id="call_1", name="read_file", output={"ok": True, "path": "README.md"})
    )

    assert message["type"] == "function_call_output"
    assert message["call_id"] == "call_1"
    assert '"ok": true' in message["output"]


def test_openai_complete_returns_normalized_turn() -> None:
    class Dumpable:
        def model_dump(self):
            return {"type": "message", "content": "raw"}

    class Content:
        def __init__(self, type_, text):
            self.type = type_
            self.text = text

    class MessageItem:
        def __init__(self):
            self.type = "message"
            self.content = [Content("output_text", "done")]

    class FunctionCallItem:
        def __init__(self):
            self.type = "function_call"
            self.call_id = "call_1"
            self.name = "read_file"
            self.arguments = '{"path": "README.md"}'

    class FakeResponses:
        def create(self, **kwargs):
            assert kwargs["previous_response_id"] is None
            return type(
                "ResponseLike",
                (),
                {
                    "id": "resp_1",
                    "output_text": None,
                    "output": [Dumpable(), MessageItem(), FunctionCallItem()],
                },
            )()

    client = object.__new__(OpenAIClient)
    client._client = type("FakeOpenAI", (), {"responses": FakeResponses()})()

    turn = client.complete(model="gpt-5-mini", messages=[], tools=[], instructions="hi")

    assert isinstance(turn, AssistantTurn)
    assert turn.response_id == "resp_1"
    assert turn.text == "done"
    assert turn.tool_calls[0].name == "read_file"
    assert turn.messages[0] == {"type": "message", "content": "raw"}


def test_openai_complete_normalizes_provider_exception() -> None:
    class FakeResponses:
        def create(self, **kwargs):
            raise RuntimeError("boom")

    client = object.__new__(OpenAIClient)
    client._client = type("FakeOpenAI", (), {"responses": FakeResponses()})()

    with pytest.raises(LLMProviderError, match="OpenAI request failed: boom"):
        client.complete(model="gpt-5-mini", messages=[], tools=[], instructions="hi")


def test_normalize_openai_error_handles_import_failure(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openai":
            raise ImportError("missing openai")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    error = _normalize_openai_error(RuntimeError("boom"))

    assert error.message == "OpenAI request failed: boom"
