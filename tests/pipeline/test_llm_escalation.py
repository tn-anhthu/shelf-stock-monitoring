import json
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from src.pipeline.llm_escalation import escalate_to_llm


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
