import json
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from src.pipeline.llm_escalation import (
    escalate_to_llm,
    escalate_to_llm_gemini,
    escalate_to_llm_openrouter,
    verify_same_object,
    verify_same_object_gemini,
)


FAKE_USAGE = SimpleNamespace(input_tokens=100, output_tokens=20)


class FakeMessages:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.answer = answer
        self.reasoning = reasoning
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"reasoning": self.reasoning, "answer": self.answer})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=FAKE_USAGE)


class FakeLLMClient:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.messages = FakeMessages(answer, reasoning)


class FlakyMessages:
    """Returns malformed JSON for the first `fail_times` calls, then valid JSON —
    mimics the rare structured-output glitch observed from the real API."""

    def __init__(self, fail_times, answer):
        self.fail_times = fail_times
        self.answer = answer
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            text = "{answer: " + self.answer  # malformed: unquoted key, unterminated
        else:
            text = json.dumps({"reasoning": "ok", "answer": self.answer})
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=FAKE_USAGE)


class FlakyLLMClient:
    def __init__(self, fail_times, answer):
        self.messages = FlakyMessages(fail_times, answer)


class FakeGeminiUsage:
    def __init__(self, prompt_token_count=100, candidates_token_count=20):
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count


class FakeGeminiResponse:
    def __init__(self, text, prompt_token_count=100, candidates_token_count=20):
        self.text = text
        self.usage_metadata = FakeGeminiUsage(prompt_token_count, candidates_token_count)


class FakeGeminiModels:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.answer = answer
        self.reasoning = reasoning
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"reasoning": self.reasoning, "answer": self.answer})
        return FakeGeminiResponse(text)


class FakeGeminiClient:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.models = FakeGeminiModels(answer, reasoning)


class FlakyGeminiModels:
    """Mirrors FlakyMessages but for the google-genai response shape."""

    def __init__(self, fail_times, answer):
        self.fail_times = fail_times
        self.answer = answer
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            text = "{answer: " + self.answer  # malformed: unquoted key, unterminated
        else:
            text = json.dumps({"reasoning": "ok", "answer": self.answer})
        return FakeGeminiResponse(text)


class FlakyGeminiClient:
    def __init__(self, fail_times, answer):
        self.models = FlakyGeminiModels(fail_times, answer)


class FakeOpenRouterCompletions:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.answer = answer
        self.reasoning = reasoning
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = json.dumps({"reasoning": self.reasoning, "answer": self.answer})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


class FakeOpenRouterClient:
    def __init__(self, answer, reasoning="Bao bì khớp với candidate này"):
        self.chat = SimpleNamespace(completions=FakeOpenRouterCompletions(answer, reasoning))


class FlakyOpenRouterCompletions:
    """Mirrors FlakyMessages/FlakyGeminiModels but for the OpenAI-compatible
    chat.completions response shape used by OpenRouter."""

    def __init__(self, fail_times, answer):
        self.fail_times = fail_times
        self.answer = answer
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            text = "{answer: " + self.answer  # malformed: unquoted key, unterminated
        else:
            text = json.dumps({"reasoning": "ok", "answer": self.answer})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )


class FlakyOpenRouterClient:
    def __init__(self, fail_times, answer):
        self.chat = SimpleNamespace(completions=FlakyOpenRouterCompletions(fail_times, answer))


def _make_reference_image(images_dir, sku_id):
    sku_dir = os.path.join(images_dir, sku_id)
    os.makedirs(sku_dir, exist_ok=True)
    Image.new("RGB", (5, 5)).save(os.path.join(sku_dir, "1.jpg"))


def test_escalate_to_llm_returns_answer_and_reasoning_from_response(tmp_path):
    client = FakeLLMClient(answer="choco_pie_orion", reasoning="Logo và màu bao bì khớp hoàn toàn")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, reasoning, usage = escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "Logo và màu bao bì khớp hoàn toàn"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_escalate_to_llm_returns_unknown_when_model_says_so(tmp_path):
    client = FakeLLMClient(answer="unknown", reasoning="Không có candidate nào khớp thương hiệu")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, _usage = escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "unknown"
    assert reasoning == "Không có candidate nào khớp thương hiệu"


def test_escalate_to_llm_schema_enum_is_sku_ids_plus_unknown(tmp_path):
    client = FakeLLMClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    schema = client.messages.calls[0]["output_config"]["format"]["schema"]
    assert schema["properties"]["answer"]["enum"] == ["choco_pie_orion", "coke_330", "unknown"]


def test_escalate_to_llm_schema_declares_reasoning_before_answer(tmp_path):
    client = FakeLLMClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    schema = client.messages.calls[0]["output_config"]["format"]["schema"]
    assert list(schema["properties"].keys()) == ["reasoning", "answer"]
    assert schema["required"] == ["reasoning", "answer"]
    assert schema["properties"]["reasoning"]["type"] == "string"


def test_escalate_to_llm_uses_a_large_enough_max_tokens_for_reasoning_plus_answer(tmp_path):
    # Root-caused via real API replay: with reasoning required before answer
    # and up to 5 candidates, 256 max_tokens routinely truncates mid-JSON
    # ("Unterminated string...") before the answer field is reached — 54/60
    # boxes failed this way in one real run. 512 was verified against the
    # real API to fit a full comparative reasoning + answer for 5 candidates.
    client = FakeLLMClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    assert client.messages.calls[0]["max_tokens"] >= 512


def test_escalate_to_llm_prompt_insists_on_unknown_over_wrong_guess(tmp_path):
    client = FakeLLMClient(answer="unknown")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    content = client.messages.calls[0]["messages"][0]["content"]
    final_text = content[-1]["text"]
    assert 'you MUST answer "unknown"' in final_text
    assert "much worse than answering unknown" in final_text


def test_escalate_to_llm_includes_reference_image_when_it_exists(tmp_path):
    _make_reference_image(tmp_path, "choco_pie_orion")
    client = FakeLLMClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    content = client.messages.calls[0]["messages"][0]["content"]
    # crop image first, immediately followed by its own label
    assert content[0]["type"] == "image"
    assert content[1] == {"type": "text", "text": "Đây là ảnh sản phẩm cần nhận diện:"}
    # candidate: its text line immediately followed by its reference image
    assert content[2] == {"type": "text", "text": "- choco_pie_orion: Chocopie"}
    assert content[3]["type"] == "image"
    # final instruction/question block, after every candidate
    assert content[-1]["type"] == "text"
    assert "unknown" in content[-1]["text"]


def test_escalate_to_llm_falls_back_to_text_only_when_reference_image_missing(tmp_path):
    # tmp_path has no sku subfolder at all -> reference image genuinely missing
    client = FakeLLMClient(answer="unknown")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, _reasoning, _usage = escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    content = client.messages.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    text_blocks = [c["text"] for c in content if c["type"] == "text"]
    # only the crop image itself -> no reference image found for either candidate,
    # and neither candidate got dropped from the prompt
    assert len(image_blocks) == 1
    assert "- choco_pie_orion: Chocopie" in text_blocks
    assert "- coke_330: Coke" in text_blocks
    assert answer == "unknown"


def test_escalate_to_llm_mixed_some_candidates_have_reference_images_some_dont(tmp_path):
    _make_reference_image(tmp_path, "choco_pie_orion")
    # coke_330 deliberately has no reference image directory
    client = FakeLLMClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    content = client.messages.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    # crop image + 1 reference image (choco_pie_orion only)
    assert len(image_blocks) == 2


def test_escalate_to_llm_retries_once_on_malformed_json_then_succeeds(tmp_path):
    client = FlakyLLMClient(fail_times=1, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, usage = escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "ok"
    assert client.messages.calls == 2
    # both the failed attempt and the succeeding one burned real tokens
    assert usage == {"input_tokens": 200, "output_tokens": 40}


def test_escalate_to_llm_raises_after_exhausting_retries_on_persistent_malformed_json(tmp_path):
    client = FlakyLLMClient(fail_times=99, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    with pytest.raises(json.JSONDecodeError):
        escalate_to_llm(client, image, candidates, images_dir=str(tmp_path))

    assert client.messages.calls == 3  # 1 initial attempt + 2 retries (default max_retries=2)


def test_escalate_to_llm_gemini_returns_answer_and_reasoning_from_response(tmp_path):
    client = FakeGeminiClient(answer="choco_pie_orion", reasoning="Logo và màu bao bì khớp hoàn toàn")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, reasoning, usage = escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "Logo và màu bao bì khớp hoàn toàn"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_escalate_to_llm_gemini_returns_unknown_when_model_says_so(tmp_path):
    client = FakeGeminiClient(answer="unknown", reasoning="Không có candidate nào khớp thương hiệu")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, _usage = escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "unknown"
    assert reasoning == "Không có candidate nào khớp thương hiệu"


def test_escalate_to_llm_gemini_schema_enum_is_sku_ids_plus_unknown(tmp_path):
    client = FakeGeminiClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    config = client.models.calls[0]["config"]
    assert config.response_json_schema["properties"]["answer"]["enum"] == ["choco_pie_orion", "coke_330", "unknown"]


def test_escalate_to_llm_gemini_minimizes_thinking_to_avoid_output_truncation(tmp_path):
    # Regression test: a real call against gemini-3.6-flash spent
    # thoughts_token_count=460 of the 512 max_output_tokens budget on internal
    # "thinking" before writing any visible JSON, truncating the response
    # mid-string (finish_reason=MAX_TOKENS) and exhausting all retries.
    # thinking_budget=0 was tried first and rejected outright (400
    # INVALID_ARGUMENT) -- this model wants thinking_level=MINIMAL instead.
    from google.genai import types

    client = FakeGeminiClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    config = client.models.calls[0]["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL


def test_escalate_to_llm_gemini_uses_the_same_prompt_text_as_claude(tmp_path):
    client = FakeGeminiClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    parts = client.models.calls[0]["contents"][0].parts
    final_text = parts[-1].text
    assert 'you MUST answer "unknown"' in final_text
    assert "much worse than answering unknown" in final_text


def test_escalate_to_llm_gemini_includes_reference_image_when_it_exists(tmp_path):
    _make_reference_image(tmp_path, "choco_pie_orion")
    client = FakeGeminiClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    parts = client.models.calls[0]["contents"][0].parts
    # crop image + intro text + candidate label + reference image + final instruction
    assert len(parts) == 5


def test_escalate_to_llm_gemini_falls_back_to_text_only_when_reference_image_missing(tmp_path):
    client = FakeGeminiClient(answer="unknown")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, _reasoning, _usage = escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    parts = client.models.calls[0]["contents"][0].parts
    # crop image + intro text + 2 candidate labels + final instruction, no reference images
    assert len(parts) == 5
    assert answer == "unknown"


def test_escalate_to_llm_gemini_retries_once_on_malformed_json_then_succeeds(tmp_path):
    client = FlakyGeminiClient(fail_times=1, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, usage = escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "ok"
    assert client.models.calls == 2
    assert usage == {"input_tokens": 200, "output_tokens": 40}


def test_escalate_to_llm_gemini_raises_after_exhausting_retries_on_persistent_malformed_json(tmp_path):
    client = FlakyGeminiClient(fail_times=99, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    with pytest.raises(json.JSONDecodeError):
        escalate_to_llm_gemini(client, image, candidates, images_dir=str(tmp_path))

    assert client.models.calls == 3


# --- escalate_to_llm_openrouter: 2026-08-17, OpenRouter fallback for
# escalate_to_llm_gemini when the primary Gemini call itself errors
# (503/rate-limit/timeout) -- same OpenAI-compatible client shape as
# src/pipeline/gap_verify.py::build_client(), classify's own
# (answer, reasoning, usage) signature/schema. ---


def test_escalate_to_llm_openrouter_returns_answer_and_reasoning_from_response(tmp_path):
    client = FakeOpenRouterClient(answer="choco_pie_orion", reasoning="Logo và màu bao bì khớp hoàn toàn")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, reasoning, usage = escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "Logo và màu bao bì khớp hoàn toàn"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_escalate_to_llm_openrouter_returns_unknown_when_model_says_so(tmp_path):
    client = FakeOpenRouterClient(answer="unknown", reasoning="Không có candidate nào khớp thương hiệu")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, _usage = escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "unknown"
    assert reasoning == "Không có candidate nào khớp thương hiệu"


def test_escalate_to_llm_openrouter_schema_enum_is_sku_ids_plus_unknown(tmp_path):
    client = FakeOpenRouterClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    call = client.chat.completions.calls[0]
    schema = call["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["answer"]["enum"] == ["choco_pie_orion", "coke_330", "unknown"]
    assert schema["required"] == ["reasoning", "answer"]
    assert schema["additionalProperties"] is False
    assert call["response_format"]["type"] == "json_schema"


def test_escalate_to_llm_openrouter_uses_classify_fallback_model_by_default(tmp_path):
    from src.pipeline.llm_escalation import CLASSIFY_FALLBACK_MODEL

    client = FakeOpenRouterClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    assert client.chat.completions.calls[0]["model"] == CLASSIFY_FALLBACK_MODEL


def test_escalate_to_llm_openrouter_sends_crop_image_as_data_url(tmp_path):
    client = FakeOpenRouterClient(answer="unknown")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    content = client.chat.completions.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image_url"]
    assert len(image_blocks) == 1
    assert image_blocks[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_escalate_to_llm_openrouter_includes_reference_image_when_it_exists(tmp_path):
    _make_reference_image(tmp_path, "choco_pie_orion")
    client = FakeOpenRouterClient(answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    content = client.chat.completions.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image_url"]
    assert len(image_blocks) == 2  # crop image + choco_pie_orion's reference image


def test_escalate_to_llm_openrouter_falls_back_to_text_only_when_reference_image_missing(tmp_path):
    client = FakeOpenRouterClient(answer="unknown")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie"), ("coke_330", "Coke")]

    answer, _reasoning, _usage = escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    content = client.chat.completions.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image_url"]
    text_blocks = [c["text"] for c in content if c["type"] == "text"]
    assert len(image_blocks) == 1  # only the crop image -> no reference image found for either candidate
    assert "- choco_pie_orion: Chocopie" in text_blocks
    assert "- coke_330: Coke" in text_blocks
    assert answer == "unknown"


def test_escalate_to_llm_openrouter_retries_once_on_malformed_json_then_succeeds(tmp_path):
    client = FlakyOpenRouterClient(fail_times=1, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    answer, reasoning, usage = escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    assert answer == "choco_pie_orion"
    assert reasoning == "ok"
    assert client.chat.completions.calls == 2
    assert usage == {"input_tokens": 200, "output_tokens": 40}


def test_escalate_to_llm_openrouter_raises_after_exhausting_retries_on_persistent_malformed_json(tmp_path):
    client = FlakyOpenRouterClient(fail_times=99, answer="choco_pie_orion")
    image = Image.new("RGB", (10, 10))
    candidates = [("choco_pie_orion", "Chocopie")]

    with pytest.raises(json.JSONDecodeError):
        escalate_to_llm_openrouter(client, image, candidates, images_dir=str(tmp_path))

    assert client.chat.completions.calls == 3  # 1 initial attempt + 2 retries (default max_retries=2)


# --- verify_same_object: 2026-07-28, IoU-duplicate case (see
# docs/log-figures/2026-07-28-nms-iou-duplicate-detection.md) -- given 2 crops
# from a high-IoU/high-containment box pair, ask the LLM whether they show the
# SAME physical product (merge) or 2 DIFFERENT physical units (keep both). ---


def test_verify_same_object_returns_answer_and_reasoning(tmp_path):
    client = FakeLLMClient(answer="same_object", reasoning="Cùng 1 hộp, box dưới chỉ chụp thiếu phần trên")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 12))

    answer, reasoning, usage = verify_same_object(client, crop_a, crop_b)

    assert answer == "same_object"
    assert reasoning == "Cùng 1 hộp, box dưới chỉ chụp thiếu phần trên"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_verify_same_object_returns_different_objects(tmp_path):
    client = FakeLLMClient(answer="different_objects", reasoning="2 lốc Yakult xếp chồng, mỗi box lệch nửa lốc")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 12))

    answer, reasoning, _usage = verify_same_object(client, crop_a, crop_b)

    assert answer == "different_objects"
    assert reasoning == "2 lốc Yakult xếp chồng, mỗi box lệch nửa lốc"


def test_verify_same_object_schema_enum_is_same_or_different(tmp_path):
    client = FakeLLMClient(answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    verify_same_object(client, crop_a, crop_b)

    schema = client.messages.calls[0]["output_config"]["format"]["schema"]
    assert schema["properties"]["answer"]["enum"] == ["same_object", "different_objects"]
    assert list(schema["properties"].keys()) == ["reasoning", "answer"]


def test_verify_same_object_sends_both_crops_as_images():
    client = FakeLLMClient(answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    verify_same_object(client, crop_a, crop_b)

    content = client.messages.calls[0]["messages"][0]["content"]
    image_blocks = [c for c in content if c["type"] == "image"]
    assert len(image_blocks) == 2  # crop_a + crop_b, nothing else (no candidate reference images here)


def test_verify_same_object_retries_once_on_malformed_json_then_succeeds():
    client = FlakyLLMClient(fail_times=1, answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    answer, _reasoning, usage = verify_same_object(client, crop_a, crop_b)

    assert answer == "same_object"
    assert client.messages.calls == 2
    assert usage == {"input_tokens": 200, "output_tokens": 40}


def test_verify_same_object_raises_after_exhausting_retries():
    client = FlakyLLMClient(fail_times=99, answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    with pytest.raises(json.JSONDecodeError):
        verify_same_object(client, crop_a, crop_b)

    assert client.messages.calls == 3


def test_verify_same_object_gemini_returns_answer_and_reasoning():
    client = FakeGeminiClient(answer="different_objects", reasoning="2 chai riêng biệt")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    answer, reasoning, usage = verify_same_object_gemini(client, crop_a, crop_b)

    assert answer == "different_objects"
    assert reasoning == "2 chai riêng biệt"
    assert usage == {"input_tokens": 100, "output_tokens": 20}


def test_verify_same_object_gemini_schema_enum_is_same_or_different():
    client = FakeGeminiClient(answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    verify_same_object_gemini(client, crop_a, crop_b)

    config = client.models.calls[0]["config"]
    assert config.response_json_schema["properties"]["answer"]["enum"] == ["same_object", "different_objects"]


def test_verify_same_object_gemini_minimizes_thinking_to_avoid_output_truncation():
    from google.genai import types

    client = FakeGeminiClient(answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    verify_same_object_gemini(client, crop_a, crop_b)

    config = client.models.calls[0]["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL


def test_verify_same_object_gemini_retries_once_on_malformed_json_then_succeeds():
    client = FlakyGeminiClient(fail_times=1, answer="same_object")
    crop_a = Image.new("RGB", (10, 10))
    crop_b = Image.new("RGB", (10, 10))

    answer, _reasoning, usage = verify_same_object_gemini(client, crop_a, crop_b)

    assert answer == "same_object"
    assert client.models.calls == 2
    assert usage == {"input_tokens": 200, "output_tokens": 40}
