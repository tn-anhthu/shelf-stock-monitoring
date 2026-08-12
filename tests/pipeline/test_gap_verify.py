import base64
import io
import json
import time
from types import SimpleNamespace

import pytest
from PIL import Image

from src.pipeline import gap_verify


def test_build_client_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert gap_verify.build_client() is None


def test_build_client_returns_none_with_explicit_empty_api_key():
    assert gap_verify.build_client(api_key="") is None


def test_build_client_builds_openai_client_pointed_at_openrouter():
    client = gap_verify.build_client(api_key="sk-or-v1-test")
    assert client is not None
    assert str(client.base_url).rstrip("/") == gap_verify.OPENROUTER_BASE_URL
    assert client.api_key == "sk-or-v1-test"


def test_build_client_reads_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-from-env")
    client = gap_verify.build_client()
    assert client.api_key == "sk-or-v1-from-env"


class ScriptedCompletions:
    """Simulates client.chat.completions.create for gap_verify tests. `script`
    maps model name -> list of behaviors consumed one per call to that model:
    a dict (e.g. {"verdict": "gap", "reason": "..."}) to succeed with that
    JSON body, a raw string to simulate a malformed/non-JSON response, or an
    Exception instance to raise (simulating a transient network/rate-limit
    failure)."""

    def __init__(self, script):
        self.script = {model: list(behaviors) for model, behaviors in script.items()}
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        model = kwargs["model"]
        behavior = self.script[model].pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        text = behavior if isinstance(behavior, str) else json.dumps(behavior)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


def _scripted_client(script):
    return SimpleNamespace(chat=SimpleNamespace(completions=ScriptedCompletions(script)))


def test_call_model_sends_json_schema_response_format_and_max_tokens(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "empty shelf"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    call = client.chat.completions.calls[0]
    assert call["max_tokens"] == 600
    assert call["response_format"]["type"] == "json_schema"
    schema = call["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["verdict"]["enum"] == ["gap", "not_gap", "uncertain"]
    assert schema["properties"]["reason"]["maxLength"] == 150
    assert schema["required"] == ["verdict", "reason"]
    assert schema["additionalProperties"] is False


def test_call_model_omits_reasoning_effort_by_default(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "not_gap", "reason": "shelf divider"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    assert "reasoning_effort" not in client.chat.completions.calls[0]["extra_body"]


def test_call_model_sets_reasoning_effort_when_given(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "not_gap", "reason": "shelf divider"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image, reasoning_effort="low")

    assert client.chat.completions.calls[0]["extra_body"]["reasoning_effort"] == "low"


def test_call_model_requests_require_parameters_routing(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "empty"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    assert client.chat.completions.calls[0]["extra_body"]["provider"]["require_parameters"] is True


def test_call_model_returns_verdict_reason_and_usage(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "uncertain", "reason": "hard to tell"}]})
    image = Image.new("RGB", (20, 20))

    verdict, reason, usage = gap_verify._call_model(client, "m1", image)

    assert verdict == "uncertain"
    assert reason == "hard to tell"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_call_model_retries_on_malformed_json_then_succeeds(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": ["{not valid json", {"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    verdict, _reason, _usage = gap_verify._call_model(client, "m1", image)

    assert verdict == "gap"
    assert len(client.chat.completions.calls) == 2


def test_call_model_retries_on_raised_exception_then_succeeds(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [ConnectionError("rate limited"), {"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    verdict, _reason, _usage = gap_verify._call_model(client, "m1", image)

    assert verdict == "gap"
    assert len(client.chat.completions.calls) == 2


def test_call_model_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [ConnectionError("a"), ConnectionError("b"), ConnectionError("c")]})
    image = Image.new("RGB", (20, 20))

    with pytest.raises(ConnectionError):
        gap_verify._call_model(client, "m1", image, max_retries=2)

    assert len(client.chat.completions.calls) == 3  # 1 initial attempt + 2 retries


def test_call_model_backs_off_between_retries(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: sleeps.append(s))
    client = _scripted_client({"m1": [ConnectionError("a"), {"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    assert sleeps == [gap_verify.RETRY_BACKOFF_BASE_SECONDS]


def test_call_model_prompt_does_not_mention_internal_function_names(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    text = client.chat.completions.calls[0]["messages"][0]["content"][0]["text"].lower()
    for internal_name in [
        "cluster_rows", "merge_adjacent_fragments", "detect_gaps",
        "filter_contained_boxes", "filter_anomalous_boxes",
    ]:
        assert internal_name not in text


def test_call_model_prompt_biases_toward_uncertain_over_guessing(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    text = client.chat.completions.calls[0]["messages"][0]["content"][0]["text"].lower()
    assert "uncertain" in text
    assert "worse" in text


def test_call_model_prompt_excludes_low_stock_judgment(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    text = client.chat.completions.calls[0]["messages"][0]["content"][0]["text"].lower()
    assert "do not" in text
    assert "low on stock" in text or "pushed back" in text


def test_call_model_sends_image_as_data_url(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({"m1": [{"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (20, 20))

    gap_verify._call_model(client, "m1", image)

    content = client.chat.completions.calls[0]["messages"][0]["content"]
    image_block = next(c for c in content if c["type"] == "image_url")
    assert image_block["image_url"]["url"].startswith("data:image/jpeg;base64,")
