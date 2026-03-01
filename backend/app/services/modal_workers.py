from __future__ import annotations

"""
Modal worker lifecycle management.

Manages model workers on Modal GPUs. Workers are tracked locally,
and inference calls are dispatched directly to the GPU-tier class
(InferL4, InferA100, etc.) — no intermediate router hop.

Each worker serves a specific model and can handle multiple agent requests.
Workers are kept warm for the duration of a match to minimize cold-start latency.
"""

import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

_MODAL_AVAILABLE = False
try:
    import modal
    _MODAL_AVAILABLE = True
    logger.info("[MODAL] modal package imported successfully, version=%s", getattr(modal, '__version__', '?'))
except ImportError as e:
    logger.warning("[MODAL] modal package NOT available: %s", e)

FALLBACK_ACTION = '{"action": "call", "amount": null, "reasoning": "Inference unavailable, defaulting to call."}'

GPU_TO_CLS = {
    "T4": "InferL4",
    "L4": "InferL4",
    "A10G": "InferL4",
    "A100-40GB": "InferA100",
    "A100": "InferA100",
    "A100-80GB": "InferA100_80",
    "H100": "InferH100",
}


class WorkerStatus(Enum):
    PENDING = "pending"
    STARTING = "starting"
    WARM = "warm"
    BUSY = "busy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class ModelWorker:
    def __init__(self, model_key: str, hf_repo_id: str, gpu: str, table_id: str):
        self.id = str(uuid.uuid4())
        self.model_key = model_key
        self.hf_repo_id = hf_repo_id
        self.gpu = gpu
        self.table_id = table_id
        self.status = WorkerStatus.PENDING
        self.requests_served = 0
        self.last_request_at: str | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model_key": self.model_key,
            "hf_repo_id": self.hf_repo_id,
            "gpu": self.gpu,
            "table_id": self.table_id,
            "status": self.status.value,
            "requests_served": self.requests_served,
            "last_request_at": self.last_request_at,
            "created_at": self.created_at,
            "error_message": self.error_message,
        }


_workers: dict[str, ModelWorker] = {}


def spin_up(model_key: str, hf_repo_id: str, gpu: str, table_id: str) -> ModelWorker:
    """Register a new model worker. The actual GPU container is managed by Modal."""
    worker = ModelWorker(model_key, hf_repo_id, gpu, table_id)
    worker.status = WorkerStatus.WARM
    _workers[worker.id] = worker
    return worker


def get_worker(worker_id: str) -> ModelWorker | None:
    return _workers.get(worker_id)


def get_worker_for_table(table_id: str, model_key: str) -> ModelWorker | None:
    """Find a warm worker for a specific table and model."""
    for w in _workers.values():
        if w.table_id == table_id and w.model_key == model_key and w.status == WorkerStatus.WARM:
            return w
    return None


def get_or_create_worker(model_key: str, hf_repo_id: str, gpu: str, table_id: str) -> ModelWorker:
    existing = get_worker_for_table(table_id, model_key)
    if existing:
        return existing
    return spin_up(model_key, hf_repo_id, gpu, table_id)


def call_inference(worker: ModelWorker, messages: list[dict], temperature: float,
                   max_tokens: int = 512) -> dict:
    """
    Send an inference request to Modal.

    Calls the deployed GPU-tier class (InferL4, InferA100, etc.) which
    loads the model via vLLM on a GPU container and returns the raw response.

    Falls back to a safe default action if Modal is unavailable or errors.

    Returns: {"raw_response": str, "latency_ms": float, "tokens_used": int}
    """
    worker.status = WorkerStatus.BUSY
    worker.requests_served += 1
    worker.last_request_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "[MODAL] ── call_inference START ──────────────────────────────────────"
    )
    logger.info(
        "[MODAL]   worker_id=%s  model=%s  hf_repo=%s  gpu=%s",
        worker.id[:8], worker.model_key, worker.hf_repo_id, worker.gpu,
    )
    logger.info(
        "[MODAL]   temperature=%.2f  max_tokens=%d  num_messages=%d",
        temperature, max_tokens, len(messages),
    )
    # Log the actual messages being sent (truncate long content)
    for i, msg in enumerate(messages):
        content_preview = str(msg.get('content', ''))[:300]
        logger.info(
            "[MODAL]   message[%d] role=%s content=%.300s...",
            i, msg.get('role', '?'), content_preview,
        )
    logger.info("[MODAL]   modal_available=%s", _MODAL_AVAILABLE)
    sys.stdout.flush()

    if not _MODAL_AVAILABLE:
        worker.status = WorkerStatus.WARM
        worker.error_message = "modal package not installed"
        logger.error(
            "[MODAL]   SKIPPED — modal package not installed. Returning fallback."
        )
        sys.stdout.flush()
        return {
            "raw_response": FALLBACK_ACTION,
            "latency_ms": 0,
            "tokens_used": 0,
            "stub": True,
            "error": "modal package not installed",
        }

    try:
        t0 = time.perf_counter()

        cls_name = GPU_TO_CLS.get(worker.gpu, "InferL4")
        logger.info(
            "[MODAL]   Resolving Modal class: app='agent-poker-inference' cls='%s'",
            cls_name,
        )
        sys.stdout.flush()

        cls = modal.Cls.from_name("agent-poker-inference", cls_name)
        logger.info("[MODAL]   Modal class resolved. Calling .infer.remote()...")
        sys.stdout.flush()

        result = cls().infer.remote(
            hf_repo_id=worker.hf_repo_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        latency_ms = (time.perf_counter() - t0) * 1000
        worker.status = WorkerStatus.WARM
        worker.error_message = None

        raw_resp = result.get("raw_response", FALLBACK_ACTION)
        logger.info("[MODAL]   ✓ SUCCESS in %.0fms", latency_ms)
        logger.info(
            "[MODAL]   raw_response=%.500s",
            raw_resp,
        )
        logger.info(
            "[MODAL]   tokens_used=%s  prompt_tokens=%s  finish_reason=%s",
            result.get("tokens_used"), result.get("prompt_tokens"),
            result.get("finish_reason"),
        )
        sys.stdout.flush()

        return {
            "raw_response": raw_resp,
            "latency_ms": round(latency_ms, 1),
            "tokens_used": result.get("tokens_used", 0),
            "prompt_tokens": result.get("prompt_tokens", 0),
            "finish_reason": result.get("finish_reason", ""),
            "stub": False,
        }

    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000 if 't0' in dir() else 0
        worker.status = WorkerStatus.ERROR
        worker.error_message = f"{type(e).__name__}: {str(e)[:500]}"

        logger.error("[MODAL]   ✗ FAILED after %.0fms", latency_ms)
        logger.error("[MODAL]   error_type=%s", type(e).__name__)
        logger.error("[MODAL]   error_message=%s", str(e)[:1000])
        logger.error("[MODAL]   Returning fallback action.", exc_info=True)
        sys.stdout.flush()

        return {
            "raw_response": FALLBACK_ACTION,
            "latency_ms": 0,
            "tokens_used": 0,
            "stub": True,
            "error": worker.error_message,
        }


def stop_worker(worker_id: str) -> bool:
    worker = _workers.get(worker_id)
    if not worker:
        return False
    worker.status = WorkerStatus.STOPPED
    return True


def stop_table_workers(table_id: str) -> int:
    """Stop all workers for a table (called when match ends)."""
    count = 0
    for w in _workers.values():
        if w.table_id == table_id and w.status in (WorkerStatus.WARM, WorkerStatus.BUSY):
            w.status = WorkerStatus.STOPPED
            count += 1
    return count


def list_workers(table_id: str | None = None) -> list[ModelWorker]:
    if table_id:
        return [w for w in _workers.values() if w.table_id == table_id]
    return list(_workers.values())


def health_check() -> dict:
    total = len(_workers)
    warm = sum(1 for w in _workers.values() if w.status == WorkerStatus.WARM)
    busy = sum(1 for w in _workers.values() if w.status == WorkerStatus.BUSY)
    errors = sum(1 for w in _workers.values() if w.status == WorkerStatus.ERROR)
    return {
        "total": total,
        "warm": warm,
        "busy": busy,
        "errors": errors,
        "modal_available": _MODAL_AVAILABLE,
    }
