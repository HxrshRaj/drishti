"""A small local instruction-tuned text LLM, used to power agent reasoning
(LangGraph nodes, the AutoGen verifier, the CrewAI crew) with zero API keys.

Model: Qwen/Qwen2.5-0.5B-Instruct (Apache-2.0) — chosen for the same reason
as the perception VLM: small enough for real CPU inference in an
environment with no GPU. If ANTHROPIC_API_KEY or OPENAI_API_KEY is set,
callers should prefer that provider instead (see app.llm.provider) for
higher-quality agent reasoning — this local model exists so the whole
system runs end-to-end with no credentials at all.
"""
from __future__ import annotations

import threading

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.config import settings


class LocalChatLLM:
    def __init__(self, model_id: str | None = None, device: str | None = None):
        self.model_id = model_id or settings.local_llm_model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else settings.device)
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_id, torch_dtype=dtype).to(self.device)
        self.model.eval()
        self._lock = threading.Lock()  # transformers generate() isn't safely reentrant per-instance

    @torch.inference_mode()
    def chat(self, messages: list[dict], max_new_tokens: int = 300, temperature: float = 0.2) -> str:
        """messages: [{"role": "system"|"user"|"assistant", "content": str}, ...]"""
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with self._lock:
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=temperature > 0,
                temperature=max(temperature, 1e-4),
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


_instance: LocalChatLLM | None = None
_instance_lock = threading.Lock()


def get_local_llm() -> LocalChatLLM:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LocalChatLLM()
    return _instance
