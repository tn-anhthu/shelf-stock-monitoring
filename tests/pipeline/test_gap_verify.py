import base64
import io
import json
import time
from types import SimpleNamespace

import httpx
import openai
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


def test_build_client_sets_bounded_timeout_and_disables_sdk_retries():
    # _call_model implements its own retry/backoff loop -- the SDK's own
    # default retry behavior (max_retries=2) and long default read timeout
    # must be disabled/bounded here so _call_model's retry constant is the
    # sole retry authority and a hung call can't block the event loop
    # indefinitely (this client is called synchronously from inside
    # ml-service/app.py's async def predict()).
    client = gap_verify.build_client(api_key="sk-or-v1-test")

    assert client.max_retries == 0
    assert client.timeout == 60.0


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


def _rate_limit_error(message="rate limited"):
    """Builds a real openai.RateLimitError, matching the installed SDK's
    actual constructor (message, *, response: httpx.Response, body)."""
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )
    return openai.RateLimitError(message, response=response, body=None)


def test_call_model_fast_fails_on_rate_limit_without_retry_or_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: sleeps.append(s))
    client = _scripted_client({"m1": [_rate_limit_error()]})
    image = Image.new("RGB", (20, 20))

    with pytest.raises(openai.RateLimitError):
        gap_verify._call_model(client, "m1", image, max_retries=2)

    assert len(client.chat.completions.calls) == 1  # no retry attempts consumed
    assert sleeps == []  # never slept -- raised straight through


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


def test_verify_gap_returns_gap_verdict_from_primary_model(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({gap_verify.PRIMARY_MODEL: [{"verdict": "gap", "reason": "empty shelf space"}]})
    image = Image.new("RGB", (400, 400))
    box = (100.0, 100.0, 200.0, 200.0)

    result = gap_verify.verify_gap(client, image, box)

    assert result == {"box": box, "verdict": "gap", "reason": "empty shelf space", "needs_review": False}
    assert len(client.chat.completions.calls) == 1  # primary succeeded, fallback never called


def test_verify_gap_does_not_escalate_to_fallback_on_uncertain_verdict(monkeypatch):
    # Spec S6: "uncertain" from the primary model is a final answer, not a
    # trigger to also call the fallback -- fallback is only for
    # *infrastructure* failure (the primary call itself erroring).
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({gap_verify.PRIMARY_MODEL: [{"verdict": "uncertain", "reason": "hard to tell"}]})
    image = Image.new("RGB", (400, 400))
    box = (100.0, 100.0, 200.0, 200.0)

    result = gap_verify.verify_gap(client, image, box)

    assert result["verdict"] == "uncertain"
    assert result["needs_review"] is True
    assert len(client.chat.completions.calls) == 1


def test_verify_gap_falls_back_to_luna_when_primary_errors(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({
        gap_verify.PRIMARY_MODEL: [ConnectionError("a"), ConnectionError("b"), ConnectionError("c")],
        gap_verify.FALLBACK_MODEL: [{"verdict": "not_gap", "reason": "shelf divider"}],
    })
    image = Image.new("RGB", (400, 400))
    box = (100.0, 100.0, 200.0, 200.0)

    result = gap_verify.verify_gap(client, image, box)

    assert result["verdict"] == "not_gap"
    assert result["needs_review"] is False
    calls = client.chat.completions.calls
    primary_calls = [c for c in calls if c["model"] == gap_verify.PRIMARY_MODEL]
    fallback_calls = [c for c in calls if c["model"] == gap_verify.FALLBACK_MODEL]
    assert len(primary_calls) == 3  # exhausted its own retries first
    assert len(fallback_calls) == 1
    assert fallback_calls[0]["extra_body"]["reasoning_effort"] == "low"


def test_verify_gap_kept_as_uncertain_when_both_models_fail(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({
        gap_verify.PRIMARY_MODEL: [ConnectionError("a")] * 3,
        gap_verify.FALLBACK_MODEL: [ConnectionError("b")] * 3,
    })
    image = Image.new("RGB", (400, 400))
    box = (100.0, 100.0, 200.0, 200.0)

    result = gap_verify.verify_gap(client, image, box)

    # never silently dropped -- the box is still present, just marked uncertain
    assert result["box"] == box
    assert result["verdict"] == "uncertain"
    assert result["needs_review"] is True


def test_verify_gap_degenerate_crop_kept_as_uncertain_without_calling_client():
    client = _scripted_client({})
    image = Image.new("RGB", (400, 400))
    box = (500.0, 500.0, 500.0, 500.0)  # zero-area, entirely outside the image

    result = gap_verify.verify_gap(client, image, box)

    assert result["verdict"] == "uncertain"
    assert result["needs_review"] is True
    assert client.chat.completions.calls == []


def test_verify_gap_crop_includes_context_margin_beyond_raw_box(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({gap_verify.PRIMARY_MODEL: [{"verdict": "gap", "reason": "ok"}]})
    image = Image.new("RGB", (400, 400))
    box = (100.0, 100.0, 200.0, 200.0)  # 100x100 raw box

    gap_verify.verify_gap(client, image, box)

    content = client.chat.completions.calls[0]["messages"][0]["content"]
    image_block = next(c for c in content if c["type"] == "image_url")
    data_url = image_block["image_url"]["url"]
    raw = base64.b64decode(data_url.split(",", 1)[1])
    sent_image = Image.open(io.BytesIO(raw))
    # cropped with context_padding_ratio > 0 -> strictly larger than the raw 100x100 box,
    # proof this crops fresh from the real bbox + margin, not a pre-existing fixed-size file
    assert sent_image.width > 100
    assert sent_image.height > 100


def test_verify_gaps_drops_not_gap_and_keeps_gap_and_uncertain(monkeypatch):
    monkeypatch.setattr(gap_verify.time, "sleep", lambda s: None)
    client = _scripted_client({
        gap_verify.PRIMARY_MODEL: [
            {"verdict": "gap", "reason": "empty"},
            {"verdict": "not_gap", "reason": "shelf divider"},
            {"verdict": "uncertain", "reason": "hard to tell"},
        ],
    })
    image = Image.new("RGB", (400, 400))
    gaps = [(0.0, 0.0, 50.0, 50.0), (60.0, 0.0, 110.0, 50.0), (120.0, 0.0, 170.0, 50.0)]

    result = gap_verify.verify_gaps(client, image, gaps)

    assert [r["verdict"] for r in result] == ["gap", "uncertain"]
    assert [r["box"] for r in result] == [gaps[0], gaps[2]]


def test_verify_gaps_empty_input_returns_empty_list():
    client = _scripted_client({})
    image = Image.new("RGB", (400, 400))

    assert gap_verify.verify_gaps(client, image, []) == []
