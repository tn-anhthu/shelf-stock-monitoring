"""Filter detect_gaps() geometry candidates through a VLM "does this really
look like empty shelf space" check before they reach scan_result — see
docs/superpowers/specs/2026-08-12-gap-detection-vlm-verify-design.md for the
full design and the real-model test data behind the model/config choices
below. detect_gaps() itself stays completely unchanged; this module is a
recall->precision filter layered on top of it, inserted by
src/pipeline/scan.py::run_scan() right after detect_gaps() runs.

Primary/fallback both go through the SAME OpenAI-compatible client pointed at
OpenRouter (base_url=OPENROUTER_BASE_URL) — only the model= string differs,
unlike src/pipeline/classify.py's Anthropic/Gemini split which needs two
separate SDKs.
"""
import base64
import io
import json
import os
import time
from typing import Dict, List, Optional, Tuple

import openai
from PIL import Image

from src.detection.benchmark.metrics import Box
from src.pipeline.crop import crop_box

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = os.environ.get("GAP_VERIFY_MODEL", "google/gemma-4-26b-a4b-it:free")
FALLBACK_MODEL = os.environ.get("GAP_VERIFY_FALLBACK_MODEL", "openai/gpt-5.6-luna")

# Small context margin around detect_gaps()'s real bbox, expressed as
# crop_box()'s padding_ratio (relative to the gap box's own width/height).
# Deliberately NOT reusing data/scan_viz/gap_crops/ -- confirmed out of scope
# with detect_gaps()'s real bboxes (spec S5). Exact number is an open tuning
# question (spec S8) -- 0.15 is a reasonable starting default, tune it while
# doing the manual test1-19 review (scripts/review_gap_verify.py).
CONTEXT_PADDING_RATIO = 0.15

# max_tokens=600: measured from real OpenRouter Playground test calls against
# these exact models (spec S10) -- all <500 tokens/call, peak 377, +generous
# headroom, not a guess.
MAX_TOKENS = 600
MAX_RETRIES_PER_MODEL = 2
RETRY_BACKOFF_BASE_SECONDS = 2.0

VALID_VERDICTS = ("gap", "not_gap", "uncertain")

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VALID_VERDICTS)},
        "reason": {"type": "string", "maxLength": 150},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}

# Describes the candidate by visual phenomenon only, never by internal
# function name (cluster_rows, merge_adjacent_fragments, ...) -- the model
# only sees the image, not this codebase (lesson learned fixing the test
# prompt in spec S10). Explicitly biases toward "uncertain" over a wrong
# guess, and explicitly excludes "Low stock" judgment -- a different,
# already-scoped-elsewhere issue type (spec S3) this module must not drift
# into answering.
_VERDICT_INSTRUCTION_TEXT = (
    "This is a cropped region from a retail shelf photo. An automated "
    "shelf-gap detector flagged this region as a candidate empty gap "
    "(missing/out-of-stock product) between two neighboring products on the "
    "same shelf row.\n\n"
    "Look at the actual image and decide whether this candidate is really an "
    "empty gap, or one of these known false-positive patterns instead:\n"
    "- the edge/frame of a cooler or fridge door, not shelf space\n"
    "- a shelf divider, price rail, or other fixture bar\n"
    "- the boundary between two separate shelves that got merged into one row\n"
    "- a single row of tightly-packed products that got visually split into "
    "two pieces by a detection box edge, even though the products are "
    "actually touching with no real gap between them\n\n"
    "Only judge whether shelf space here is truly empty. Do NOT judge whether "
    "a product is understocked, pushed back deep into the shelf, or otherwise "
    "low on stock elsewhere in the image -- that is a different question this "
    "check does not answer.\n\n"
    "Answering wrong is worse than saying you're not sure: if the region "
    "doesn't clearly match a true empty gap OR a known false-positive pattern "
    "above, answer \"uncertain\" rather than guessing.\n\n"
    "Respond with a verdict: \"gap\" (real empty shelf space), \"not_gap\" "
    "(one of the false-positive patterns above, or otherwise clearly not "
    "empty shelf space), or \"uncertain\" (not clearly either). Briefly "
    "explain what you see that supports your verdict."
)


def build_client(api_key: Optional[str] = None):
    """Returns an OpenAI-compatible client pointed at OpenRouter, or None if
    no API key is available. api_key defaults to reading OPENROUTER_API_KEY
    from the environment. Callers (ml-service/app.py, scripts/
    review_gap_verify.py) pass the None result straight through to
    run_scan()'s gap_verify_client -- fail-open at the whole-service level
    (spec S4): no key configured means gap_verify is skipped, not a crash."""
    key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    # timeout/max_retries are explicit here so _call_model's own retry loop
    # (below) is the sole retry authority: without these, the SDK's default
    # max_retries=2 would silently multiply each of _call_model's own
    # attempts into up to 3 HTTP requests, and its long default read timeout
    # could block the FastAPI event loop (this client is used synchronously
    # from within async def predict() in ml-service/app.py) far longer than
    # is reasonable for a single vision-model call.
    return openai.OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, timeout=60.0, max_retries=0)


def _image_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG")
    return buf.getvalue()


def _image_data_url(image: Image.Image) -> str:
    encoded = base64.standard_b64encode(_image_bytes(image)).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _call_model(
    client,
    model: str,
    image: Image.Image,
    reasoning_effort: Optional[str] = None,
    max_retries: int = MAX_RETRIES_PER_MODEL,
) -> Tuple[str, str, Dict[str, int]]:
    """One model's full attempt at verifying a single gap crop, with its own
    retry/backoff -- covers both transient call failures (rate limit, 5xx,
    timeout) and malformed/non-schema-conforming responses (structured
    output isn't guaranteed strict on every OpenRouter provider -- spec S5).
    Raises the last error if every attempt fails; the caller (verify_gap)
    decides what to do next -- this function only ever gives up on this one
    *model*, never on the candidate itself.

    NOTE before shipping for real: verify live against OpenRouter's
    /api/v1/models (filter by supported_parameters) that PRIMARY_MODEL and
    FALLBACK_MODEL actually support structured_outputs and
    provider.require_parameters before trusting this response_format/
    extra_body shape not to silently degrade on either model (spec S5) --
    don't assume it from this code alone.
    """
    content = [
        {"type": "text", "text": _VERDICT_INSTRUCTION_TEXT},
        {"type": "image_url", "image_url": {"url": _image_data_url(image)}},
    ]
    extra_body: Dict = {"provider": {"require_parameters": True}}
    if reasoning_effort is not None:
        extra_body["reasoning_effort"] = reasoning_effort

    usage = {"input_tokens": 0, "output_tokens": 0}
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": content}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "gap_verdict", "strict": True, "schema": _VERDICT_SCHEMA},
                },
                extra_body=extra_body,
            )
            if response.usage is not None:
                usage["input_tokens"] += response.usage.prompt_tokens
                usage["output_tokens"] += response.usage.completion_tokens
            parsed = json.loads(response.choices[0].message.content)
            verdict = parsed["verdict"]
            reason = parsed["reason"]
            if verdict not in VALID_VERDICTS:
                raise ValueError(f"model {model} returned unexpected verdict {verdict!r}")
            return verdict, reason, usage
        except openai.RateLimitError:
            # A rate-limit/quota error (e.g. OpenRouter's free-tier daily
            # cap) cannot resolve within this run -- retrying it just burns
            # attempts and sleeps on an error that will never succeed.
            # Raise straight through so verify_gap's fail-open logic moves
            # on to the next model tier immediately.
            raise
        except Exception:
            if attempt == max_retries:
                raise
            time.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt))


def verify_gap(
    client,
    image: Image.Image,
    box: Box,
    context_padding_ratio: float = CONTEXT_PADDING_RATIO,
) -> Dict:
    """Fail-open, 3-tier verification of a single detect_gaps() candidate
    (spec S6): try PRIMARY_MODEL, then FALLBACK_MODEL only if PRIMARY_MODEL's
    call itself raised (not merely because it answered "uncertain" -- that's
    a valid, final tier-1 answer). If both models fail, the candidate is kept
    as "uncertain" rather than dropped -- losing a real gap is worse than one
    unresolved review item."""
    cropped = crop_box(image, box, padding_ratio=context_padding_ratio)
    if cropped is None:
        return {
            "box": box,
            "verdict": "uncertain",
            "reason": "degenerate crop (outside image bounds)",
            "needs_review": True,
        }

    try:
        verdict, reason, _usage = _call_model(client, PRIMARY_MODEL, cropped)
        return {"box": box, "verdict": verdict, "reason": reason, "needs_review": verdict == "uncertain"}
    except Exception:
        pass

    try:
        verdict, reason, _usage = _call_model(client, FALLBACK_MODEL, cropped, reasoning_effort="low")
        return {"box": box, "verdict": verdict, "reason": reason, "needs_review": verdict == "uncertain"}
    except Exception:
        pass

    return {
        "box": box,
        "verdict": "uncertain",
        "reason": "gap_verify: both primary and fallback models failed, kept for human review",
        "needs_review": True,
    }


def verify_gaps(client, image: Image.Image, gaps: List[Box]) -> List[Dict]:
    """Runs verify_gap on every detect_gaps() candidate and drops the ones
    confirmed not_gap -- "gap" and "uncertain" both survive (spec S6)."""
    verified = [verify_gap(client, image, box) for box in gaps]
    return [g for g in verified if g["verdict"] != "not_gap"]
