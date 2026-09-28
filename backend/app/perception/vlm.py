"""Open-VLM perception: a two-stage pipeline that produces schema-validated
JSON findings for one aerial image.

Model (stage 1, vision): HuggingFaceTB/SmolVLM-256M-Instruct (Apache-2.0).
Chosen because it is small enough to run real inference on CPU within this
project's environment (no GPU available here — see docs/benchmarks.md).

Why two stages, not one (documented honestly, not hidden): a single-prompt
"look at the image and return this JSON schema" approach was tried first.
It worked for open-ended captioning (grounded, image-dependent output) but
FAILED for the structured-JSON version of the same prompt — the 256M model
reliably copied the few-shot example's content verbatim regardless of the
actual image, instead of describing what it saw. Manual verification (see
docs/benchmarks.md) showed this is a real capacity limit at this model
size, not a prompt bug: captioning stayed grounded on the same images
where JSON-constrained generation degenerated into copying. So perception
is now: stage 1 asks the VLM for a free-text caption (grounded, verified
working), stage 2 asks the local text LLM (already built for the agent
layer — app.llm.local_llm) to structure that caption into the JSON schema.
Structuring is a text-only task the small LLM is much better at than
combining vision grounding with strict formatting in one shot.
"""
from __future__ import annotations

import json
import re
import time

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

from app.config import settings
from app.llm.local_llm import LocalChatLLM
from app.perception.schemas import PerceptionResult, VLMFinding

CAPTION_PROMPT = "Describe what is visible in this image in one or two sentences."

STRUCTURING_SYSTEM_PROMPT = (
    "You convert a caption describing an aerial inspection photo into a single "
    "JSON object. Read the caption and produce ONLY this JSON object, no other "
    "text:\n"
    '{"finding_type": "<short snake_case label, e.g. vehicle_presence, '
    'personnel_presence, congestion_or_obstruction, no_finding>", '
    '"location_description": "<one sentence, based on the caption>", '
    '"severity": "<critical, major, minor, or informational>", '
    '"confidence": <your own decimal estimate between 0 and 1 of how clear-cut '
    'this reading is>, "notes": "<optional one sentence>"}\n'
    "IMPORTANT: only mention people (personnel_presence) if the caption "
    "explicitly mentions people/person/pedestrian, and only mention vehicles "
    "(vehicle_presence) if the caption explicitly mentions a car/van/truck/"
    "bus/vehicle. Never invent a finding type the caption does not support. "
    "Base every field on the caption you were given. If the caption describes "
    "nothing notable, use finding_type \"no_finding\" and severity "
    "\"informational\"."
)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict | None:
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_and_validate(raw_text: str) -> tuple[VLMFinding | None, bool]:
    """Pure parse+validate step, factored out of the model calls so it can
    be unit tested (JSON schema validation + retry logic) without loading
    any model.
    """
    data = extract_json(raw_text)
    if data is None:
        return None, True
    try:
        return VLMFinding.model_validate(data), False
    except Exception:
        return None, True


class VLMPerceptionService:
    def __init__(self, model_id: str | None = None, device: str | None = None,
                 structuring_llm: LocalChatLLM | None = None):
        self.model_id = model_id or settings.vlm_model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else settings.device)
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self.processor = AutoProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_id, torch_dtype=dtype,
        ).to(self.device)
        self.model.eval()
        self.structuring_llm = structuring_llm or LocalChatLLM(device=self.device)
        self.parse_failures = 0
        self.total_calls = 0

    @torch.inference_mode()
    def _caption(self, image: Image.Image, max_new_tokens: int = 80) -> str:
        messages = [{
            "role": "user",
            "content": [{"type": "image"}, {"type": "text", "text": CAPTION_PROMPT}],
        }]
        prompt = self.processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = self.processor(text=prompt, images=[image], return_tensors="pt").to(self.device)
        prompt_len = inputs["input_ids"].shape[1]
        # repetition_penalty mitigates a real, observed failure mode of this
        # small model under greedy decoding: looping the same short phrase
        # ("vehicles on the road, ... vehicles on the road, ...") instead of
        # finishing the caption.
        generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False, repetition_penalty=1.3)
        new_tokens = generated_ids[:, prompt_len:]
        return self.processor.batch_decode(new_tokens, skip_special_tokens=True)[0].strip()

    def _structure(self, caption: str, site_context: str, temperature: float) -> str:
        user_content = f"Caption: {caption}"
        if site_context:
            user_content += f"\n\nRelevant site guidance:\n{site_context}"
        messages = [
            {"role": "system", "content": STRUCTURING_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        return self.structuring_llm.chat(messages, max_new_tokens=150, temperature=temperature)

    def analyze(self, image: Image.Image, site_context: str = "", max_retries: int = 2) -> PerceptionResult:
        self.total_calls += 1
        start = time.perf_counter()
        caption = self._caption(image)

        raw_output = ""
        attempts = 0
        finding = None
        parse_failed = True

        for attempt in range(max_retries + 1):
            attempts = attempt + 1
            # do_sample=False on the first try (deterministic); light sampling
            # on retries so a retry isn't just an identical failing repeat.
            temperature = 0.0 if attempt == 0 else 0.4
            raw_output = self._structure(caption, site_context, temperature)
            finding, parse_failed = parse_and_validate(raw_output)
            if not parse_failed:
                break

        if parse_failed:
            self.parse_failures += 1

        latency_ms = (time.perf_counter() - start) * 1000
        return PerceptionResult(
            finding=finding, parse_failed=parse_failed, raw_output=f"[caption] {caption}\n[structured] {raw_output}",
            attempts=attempts, latency_ms=latency_ms,
        )

    def metrics(self) -> dict:
        rate = (self.parse_failures / self.total_calls) if self.total_calls else 0.0
        return {"total_calls": self.total_calls, "parse_failures": self.parse_failures, "parse_failure_rate": rate}
