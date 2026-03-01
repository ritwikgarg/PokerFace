"""Modal vLLM inference — HuggingFace models on Modal GPUs.

Models are downloaded once to a persistent Modal Volume, so cold starts
only pay the download cost the first time. The LLM engine is loaded once
per container via @modal.enter(), then reused across all requests — warm
inference takes ~1-2s instead of ~30s.

Deploy:   cd backend && modal deploy app/services/inference_modal.py
Warmup:   cd backend && modal run app/services/inference_modal.py::download_models
Test:     cd backend && modal run app/services/inference_modal.py
"""

import modal

MINUTES = 60

app = modal.App("agent-poker-inference")

model_cache = modal.Volume.from_name("poker-model-cache", create_if_missing=True)
CACHE_DIR = "/model-cache"

MODELS = {
    "mistralai/Mistral-7B-Instruct-v0.3": "L4",
    "meta-llama/Llama-3.1-8B-Instruct": "L4",
    "Qwen/Qwen2.5-32B-Instruct": "A100-40GB",
    "Qwen/Qwen3.5-27B": "A100-40GB",
    "meta-llama/Llama-3.1-70B-Instruct": "A100-80GB",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": "H100",
    "mistralai/Devstral-Small-2-24B-Instruct-2512": "A100-40GB",
}

vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.6.0",
        "torch>=2.4.0",
        "transformers>=4.44.0",
        "huggingface-hub>=0.25.0",
    )
)


# ── Model download (run once per model) ──────────────────────────────────────

@app.function(
    image=vllm_image,
    volumes={CACHE_DIR: model_cache},
    timeout=30 * MINUTES,
    secrets=[modal.Secret.from_name("agent-poker-keys")],
)
def download_model(hf_repo_id: str):
    """Download a model to the persistent volume. Only needs to run once."""
    import os
    os.environ["HF_HOME"] = CACHE_DIR
    os.environ["HUGGINGFACE_HUB_CACHE"] = CACHE_DIR

    from huggingface_hub import snapshot_download
    print(f"Downloading {hf_repo_id} to {CACHE_DIR}...")
    snapshot_download(
        hf_repo_id,
        cache_dir=CACHE_DIR,
        token=os.environ.get("HF_TOKEN"),
    )
    model_cache.commit()
    print(f"Done: {hf_repo_id}")


# ── Shared inference logic ───────────────────────────────────────────────────

def _generate(llm, messages: list, temperature: float, max_tokens: int) -> dict:
    """Run vLLM generation on a pre-loaded LLM engine."""
    from vllm import SamplingParams

    tokenizer = llm.get_tokenizer()
    try:
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[INST] <<SYS>>\n{content}\n<</SYS>>\n")
            elif role == "user":
                parts.append(f"[INST] {content} [/INST]\n")
            elif role == "assistant":
                parts.append(f"{content}\n")
        prompt = "".join(parts)

    params = SamplingParams(
        temperature=max(temperature, 0.01),
        max_tokens=max_tokens,
        top_p=0.9,
        stop=["```\n", "\n\n\n"],
    )

    outputs = llm.generate([prompt], params)
    text = outputs[0].outputs[0].text.strip()

    return {
        "raw_response": text,
        "tokens_used": len(outputs[0].outputs[0].token_ids),
        "prompt_tokens": len(outputs[0].prompt_token_ids),
        "finish_reason": outputs[0].outputs[0].finish_reason,
    }


# ── GPU-tier inference classes ───────────────────────────────────────────────
# Each tier is a Modal Cls so @modal.enter() loads the model ONCE per
# container.  Subsequent requests reuse the warm engine (~1-2s).

_CLS_KWARGS = dict(
    image=vllm_image,
    volumes={CACHE_DIR: model_cache},
    timeout=5 * MINUTES,
    scaledown_window=10 * MINUTES,
    secrets=[modal.Secret.from_name("agent-poker-keys")],
)


def _load_llm(self):
    """Container startup hook — shared by all GPU tiers."""
    import os, threading
    os.environ["HF_HOME"] = CACHE_DIR
    os.environ["HUGGINGFACE_HUB_CACHE"] = CACHE_DIR
    os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")
    self._llm_cache = {}
    self._lock = threading.Lock()


def _infer(self, hf_repo_id: str, messages: list, temperature: float = 0.7,
           max_tokens: int = 512) -> dict:
    """Load model on first call (per repo), reuse on subsequent calls."""
    with self._lock:
        llm = self._llm_cache.get(hf_repo_id)
        if llm is None:
            from vllm import LLM
            gpu_mem = 0.95 if ("70b" in hf_repo_id.lower() or "Scout" in hf_repo_id) else 0.90
            llm = LLM(
                model=hf_repo_id,
                trust_remote_code=True,
                max_model_len=2048,
                gpu_memory_utilization=gpu_mem,
                enforce_eager=True,
                download_dir=CACHE_DIR,
            )
            self._llm_cache[hf_repo_id] = llm
    return _generate(llm, messages, temperature, max_tokens)


@app.cls(gpu="L4", **_CLS_KWARGS)
@modal.concurrent(max_inputs=16)
class InferL4:
    """7-8B models on L4 (24 GB VRAM)."""
    @modal.enter()
    def startup(self):
        _load_llm(self)

    @modal.method()
    def infer(self, hf_repo_id: str, messages: list, temperature: float = 0.7,
              max_tokens: int = 512) -> dict:
        return _infer(self, hf_repo_id, messages, temperature, max_tokens)


@app.cls(gpu="A100-40GB", **_CLS_KWARGS)
@modal.concurrent(max_inputs=32)
class InferA100:
    """24-32B models on A100-40GB."""
    @modal.enter()
    def startup(self):
        _load_llm(self)

    @modal.method()
    def infer(self, hf_repo_id: str, messages: list, temperature: float = 0.7,
              max_tokens: int = 512) -> dict:
        return _infer(self, hf_repo_id, messages, temperature, max_tokens)


@app.cls(gpu="A100-80GB", **_CLS_KWARGS)
@modal.concurrent(max_inputs=32)
class InferA100_80:
    """70B models on A100-80GB."""
    @modal.enter()
    def startup(self):
        _load_llm(self)

    @modal.method()
    def infer(self, hf_repo_id: str, messages: list, temperature: float = 0.7,
              max_tokens: int = 512) -> dict:
        return _infer(self, hf_repo_id, messages, temperature, max_tokens)


@app.cls(gpu="H100", **_CLS_KWARGS)
@modal.concurrent(max_inputs=32)
class InferH100:
    """MoE / largest models on H100."""
    @modal.enter()
    def startup(self):
        _load_llm(self)

    @modal.method()
    def infer(self, hf_repo_id: str, messages: list, temperature: float = 0.7,
              max_tokens: int = 512) -> dict:
        return _infer(self, hf_repo_id, messages, temperature, max_tokens)


# ── GPU → class name mapping (used by modal_workers.py) ──────────────────────

GPU_TO_CLS = {
    "T4": "InferL4",
    "L4": "InferL4",
    "A10G": "InferL4",
    "A100-40GB": "InferA100",
    "A100": "InferA100",
    "A100-80GB": "InferA100_80",
    "H100": "InferH100",
}


# ── Entrypoints ──────────────────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    """Smoke test: send a poker prompt to Mistral 7B on L4."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a poker agent. Respond with ONLY a JSON object: "
                '{"action": "fold|check|call|raise", "amount": <int or null>, '
                '"reasoning": "<brief>"}'
            ),
        },
        {
            "role": "user",
            "content": (
                "=== Pre-Flop ===\n"
                "Your cards: Ah Kd\n"
                "Board: (none yet)\n"
                "Position: Button (Dealer)\n"
                "Pot: 30  |  Current bet: 20  |  Your stack: 980\n"
                "Legal actions: fold | call | raise (min 40, max 980)\n\n"
                "Decide your action now."
            ),
        },
    ]

    print("Calling Mistral 7B on L4...")
    cls = modal.Cls.from_name("agent-poker-inference", "InferL4")
    result = cls().infer.remote(
        hf_repo_id="mistralai/Mistral-7B-Instruct-v0.3",
        messages=messages,
        temperature=0.7,
        max_tokens=256,
    )
    print(f"Response: {result['raw_response']}")
    print(f"Tokens: {result['tokens_used']}")
    print(f"Finish: {result['finish_reason']}")
