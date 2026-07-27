"""Verify a classify_crop candidate shortlist against the real crop image via
Claude Haiku, since SigLIP2 cosine similarity alone can't reliably separate
near-identical packaging (same-brand flavor variants, cross-brand same-can
shape) — see scripts/llm_escalation_experiment.py for the experiment that
established this.

Each candidate's own catalog reference photo (data/catalog/images/<sku_id>/1.jpg)
is sent alongside its name, not just the text name alone. Ground-truth review
on the first real scan (data/scan_viz/test1_llm/, tracked in
data/scan_viz/review.xlsx) caught a case this fixes: a BOSS Cà Phê can — not a
catalog SKU at all — got matched to caphelon_hl_235 by name-only reasoning,
because the model had no real image of caphelon_hl_235 to compare against and
had to guess from the name alone. A candidate missing its reference image
(catalog coverage is 100/100 SKUs today, but this isn't assumed to stay true)
falls back to text-only for that candidate rather than failing the whole
request or dropping the candidate from the list.

max_retries handles a rare (~1/60 observed) malformed-JSON response from the
real API despite the json_schema output_config forcing structured output.
Root-caused by replaying the exact 60 real crops/candidates from that failing
run through the real API again right after: 0/60 failures — the same prompt
structure that failed once succeeds essentially every other time, which rules
out a deterministic prompt-building bug and points to an occasional glitch on
the API side. Retrying is cheap (immediate re-call, no backoff needed — this
isn't rate-limiting) and avoids losing an entire 60-box scan to one hiccup.

Ground-truth review across 3 real runs (data/scan_viz/test1_llm(_2|_3)/,
tracked in data/scan_viz/review.xlsx) found reference images didn't reduce
the "real product isn't a catalog SKU at all, but the LLM forces a match
anyway" failure mode — it stayed flat at 9/44 reviewed cases, just changing
WHICH case failed rather than the count. The old prompt only said "match or
say unknown if unsure", with no concrete bar for what counts as a match, so
the model defaulted to "same general product type" instead of demanding an
(almost) exact brand/name/packaging match. The prompt below is explicit about
that bar and explicitly says guessing wrong is worse than saying unknown.
The schema's reasoning field (required, declared before answer) exists so a
human can read back WHY the model picked what it picked when auditing a scan
in review.xlsx. Whether declaring it first actually forces the model to
reason before committing to an answer (vs. just being documentation) was
checked empirically, not assumed: 3 real API calls with this exact schema all
returned reasoning before answer in the raw JSON text's key order — confirmed
generation order, not just a schema-declaration nicety.

max_tokens is 512, not 256: requiring reasoning before every answer means
responses got a lot longer (a full comparative paragraph, not just one
word), and 256 wasn't enough — replaying a real failing box with its actual
5 real candidates reproduced a truncated "Unterminated string" JSON error
on every attempt at 256, confirmed fixed at 512. This was root-caused after
a first real run under the new prompt/schema came back 59/60 "unknown": the
raw failure counts (54/60 were JSON truncation errors falling back through
max_retries, only 5/60 were the model genuinely reasoning to "unknown", 1/60
matched) showed it was a token-budget bug, not the stricter prompt being
miscalibrated.
"""
import base64
import io
import json
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image

MODEL_ID = "claude-haiku-4-5"
GEMINI_MODEL_ID = os.environ.get("GEMINI_ESCALATION_MODEL", "gemini-2.5-flash")

_INTRO_TEXT = "Đây là ảnh sản phẩm cần nhận diện:"
_MATCH_INSTRUCTION_TEXT = (
    "This is a crop of a single product from a retail shelf, along with reference "
    "images of each candidate below. Compare the crop image against each reference "
    "image carefully: only choose a sku_id if the brand, product name, and "
    "packaging design match almost exactly — not just similar product category or "
    "color tone. If the crop shows any clear difference (different brand name, "
    "different text, different design) from ALL candidates, or you are not "
    "confident enough, you MUST answer \"unknown\" — choosing the wrong SKU is much "
    "worse than answering unknown.\n\n"
    "Write your reasoning in English: briefly compare the crop against the "
    "reference images, focusing on the candidates that are genuinely plausible "
    "(same product category/color) rather than restating every candidate. State "
    "clearly what specific feature (brand, text, design) confirms or rules out "
    "your final answer. You may quote short Vietnamese text visible on the "
    "packaging if relevant (e.g. brand names, flavor labels), but the reasoning "
    "itself should be written in English."
)
_REASONING_SCHEMA_DESCRIPTION = (
    "Reasoning in English: brief comparison against the "
    "genuinely plausible candidates, stating the specific "
    "feature that confirms or rules out the final answer"
)


def _image_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


def _encode_image(image: Image.Image) -> str:
    return base64.standard_b64encode(_image_bytes(image)).decode("utf-8")


def _image_block(image: Image.Image) -> Dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": _encode_image(image),
        },
    }


def _load_reference_image(sku_id: str, images_dir: str) -> Optional[Image.Image]:
    path = os.path.join(images_dir, sku_id, "1.jpg")
    if not os.path.exists(path):
        return None
    return Image.open(path)


def escalate_to_llm(
    client,
    image: Image.Image,
    candidates: List[Tuple[str, str]],
    images_dir: str = "data/catalog/images",
    max_retries: int = 2,
) -> Tuple[str, str, Dict[str, int]]:
    """Returns (answer, reasoning, usage) — reasoning is for human review/debugging
    only (see data/scan_viz/review.xlsx's llm_reasoning column), never
    persisted to the production DB. usage is {"input_tokens", "output_tokens"}
    summed across every attempt (including malformed-JSON retries, which still
    burn real tokens), for cost tracking in scripts/visualize_scan_e2e.py."""
    sku_ids = [sku_id for sku_id, _ in candidates]

    content: List[Dict] = [
        _image_block(image),
        {"type": "text", "text": _INTRO_TEXT},
    ]
    for sku_id, name in candidates:
        content.append({"type": "text", "text": f"- {sku_id}: {name}"})
        reference_image = _load_reference_image(sku_id, images_dir)
        if reference_image is not None:
            content.append(_image_block(reference_image))
    content.append({"type": "text", "text": _MATCH_INSTRUCTION_TEXT})

    usage = {"input_tokens": 0, "output_tokens": 0}
    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=512,
            messages=[{"role": "user", "content": content}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "reasoning": {
                                "type": "string",
                                "description": _REASONING_SCHEMA_DESCRIPTION,
                            },
                            "answer": {"type": "string", "enum": sku_ids + ["unknown"]},
                        },
                        "required": ["reasoning", "answer"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens
        text = next(b.text for b in response.content if b.type == "text")
        try:
            parsed = json.loads(text)
            return parsed["answer"], parsed.get("reasoning", ""), usage
        except json.JSONDecodeError:
            if attempt == max_retries:
                raise


def escalate_to_llm_gemini(
    client,
    image: Image.Image,
    candidates: List[Tuple[str, str]],
    images_dir: str = "data/catalog/images",
    max_retries: int = 2,
) -> Tuple[str, str, Dict[str, int]]:
    """Gemini 2.5 Flash counterpart to escalate_to_llm -- same interface
    (answer, reasoning, usage) and the exact same prompt/schema, via the
    shared _INTRO_TEXT/_MATCH_INSTRUCTION_TEXT/_REASONING_SCHEMA_DESCRIPTION
    constants above, so scripts/pilot_gemini_vs_claude.py can compare a fresh
    Gemini answer against Claude's already-recorded answer on an identical
    crop + candidate list. See escalate_to_llm's docstring for why the
    prompt/schema look the way they do -- this function inherits that
    reasoning unchanged, just on a different provider's SDK/types.

    client is a google.genai.Client (or anything exposing the same
    client.models.generate_content(...) shape) -- constructing it is the
    caller's job, same division of responsibility as escalate_to_llm's
    anthropic.Anthropic client."""
    from google.genai import types  # deferred: google-genai is an optional dependency, only needed by this provider

    sku_ids = [sku_id for sku_id, _ in candidates]

    parts: List["types.Part"] = [
        types.Part.from_bytes(data=_image_bytes(image), mime_type="image/jpeg"),
        types.Part.from_text(text=_INTRO_TEXT),
    ]
    for sku_id, name in candidates:
        parts.append(types.Part.from_text(text=f"- {sku_id}: {name}"))
        reference_image = _load_reference_image(sku_id, images_dir)
        if reference_image is not None:
            parts.append(types.Part.from_bytes(data=_image_bytes(reference_image), mime_type="image/jpeg"))
    parts.append(types.Part.from_text(text=_MATCH_INSTRUCTION_TEXT))

    schema = {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string", "description": _REASONING_SCHEMA_DESCRIPTION},
            "answer": {"type": "string", "enum": sku_ids + ["unknown"]},
        },
        "required": ["reasoning", "answer"],
        "additionalProperties": False,
    }

    usage = {"input_tokens": 0, "output_tokens": 0}
    for attempt in range(max_retries + 1):
        response = client.models.generate_content(
            model=GEMINI_MODEL_ID,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=512,
            ),
        )
        usage["input_tokens"] += response.usage_metadata.prompt_token_count
        usage["output_tokens"] += response.usage_metadata.candidates_token_count
        try:
            parsed = json.loads(response.text)
            return parsed["answer"], parsed.get("reasoning", ""), usage
        except json.JSONDecodeError:
            if attempt == max_retries:
                raise
