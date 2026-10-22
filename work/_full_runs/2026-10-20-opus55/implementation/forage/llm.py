"""Provider-agnostic LLM client.

Model strings are of the form "<provider>:<model-id>", e.g.
"anthropic:claude-opus-5-5" or "openai:gpt-6-astra". Adapters live in this module;
add a new provider by adding one more dispatch branch in `complete`.

Callers pass a work_dir so every call gets appended to that book's
llm_calls.jsonl for reconstructibility.

Response replay cache: set FORAGE_REPLAY=1 to memoize responses to
work/.replay_cache/<hash>.json keyed by the full input tuple. Re-runs with
identical inputs skip the live call and return the saved response. Any
change to prompt text, model, system, or params busts the key (that's the
signal to make a fresh call). Useful for iterating on post-LLM code
(parsing, iterate-loop, rebudget, rendering) without re-spending.

Cache files also store a source_fingerprint metadata object for the relevant
pipeline stage. It is not part of the replay key; audits use it to flag cache
entries produced by older stage code while still allowing exact-response reuse.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .source_fingerprint import source_fingerprint_for_stage


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    duration_s: float
    stop_reason: Optional[str]
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None

    @property
    def is_truncated(self) -> bool:
        """Provider-neutral token-limit detection, including old replay entries."""
        return self.stop_reason in {"max_tokens", "length"}

    @property
    def is_complete(self) -> bool:
        """Only a nonempty, normally terminated response is complete."""
        return bool(self.text.strip()) and self.stop_reason in {
            "end_turn", "stop", "stop_sequence",
        }


def require_complete_response(response: LLMResponse, stage: str) -> None:
    if not response.is_complete:
        raise ValueError(f"incomplete {stage} response: {response.stop_reason}")


class LLMStreamTimeoutError(TimeoutError):
    """Raised when a streaming LLM call stays alive without yielding text."""


from .resources import workspace_root, workspace_dirs

ROOT = workspace_root()
REPLAY_DIR = workspace_dirs()[1] / ".replay_cache"
DEFAULT_ANTHROPIC_READ_TIMEOUT_S = 420.0


def _replay_enabled() -> bool:
    return os.environ.get("FORAGE_REPLAY", "") == "1"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be a number of seconds, got {raw!r}") from e
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {raw!r}")
    return value


from contextlib import contextmanager
from contextvars import ContextVar

_RUN_MODELS = ContextVar("forage_run_models", default=None)
_RUN_REPLAY = ContextVar("forage_run_replay", default=None)


@contextmanager
def production_context(models, replay_dir):
    token = _RUN_MODELS.set(models)
    cache_token = _RUN_REPLAY.set(replay_dir)
    try:
        yield
    finally:
        _RUN_REPLAY.reset(cache_token)
        _RUN_MODELS.reset(token)


def resolve_model_for_stage(model: str, stage: str) -> tuple[str, Optional[str]]:
    """Apply the same per-stage/global model override rules used by
    `complete`. Returns `(resolved_model, override_source)`, where
    `override_source` is None when no override was applied."""
    stage_base = stage.split(":")[0].upper().replace("-", "_")
    resolved = _RUN_MODELS.get()
    specific = "CRITIC_BOOK" if stage.startswith("critic:book:") else stage_base
    if resolved is not None and specific in resolved:
        return resolved[specific], "production configuration"
    stage_override = os.environ.get(f"FORAGE_{stage_base}_MODEL")
    if stage_override:
        return stage_override, f"FORAGE_{stage_base}_MODEL"
    global_override = os.environ.get("FORAGE_MODEL")
    if global_override:
        return global_override, "FORAGE_MODEL"
    return model, None


def replay_key_for_request(model: str, system: Optional[str],
                           cached_prompt: Optional[str], prompt: str,
                           max_tokens: int, temperature: Optional[float],
                           tools: Optional[list] = None,
                           thinking: Optional[str] = None) -> str:
    h = hashlib.sha256()
    h.update(f"model={model}\n".encode())
    h.update(f"system={system or ''}\n".encode())
    h.update(f"cached={cached_prompt or ''}\n".encode())
    h.update(f"prompt={prompt}\n".encode())
    h.update(f"max_tokens={max_tokens}\n".encode())
    h.update(f"temperature={'' if temperature is None else temperature}\n".encode())
    if tools:
        h.update(f"tools={json.dumps(tools, sort_keys=True)}\n".encode())
    if thinking:
        h.update(f"thinking={thinking}\n".encode())
    return h.hexdigest()[:32]


def replay_cache_root() -> Path:
    configured = any(os.environ.get(k) for k in ("FORAGE_WORKSPACE", "FORAGE_WORK_DIR"))
    return _RUN_REPLAY.get() or (workspace_dirs()[1] / ".replay_cache" if configured else REPLAY_DIR)


def replay_cache_path(key: str) -> Path:
    return replay_cache_root() / f"{key}.json"


def _replay_load(key: str) -> Optional[dict]:
    p = replay_cache_path(key)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _replay_save(key: str, model: str, resp: "LLMResponse", stage: str) -> None:
    replay_cache_path(key).parent.mkdir(parents=True, exist_ok=True)
    data = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "key": key,
        "model": model,
        "source_fingerprint": source_fingerprint_for_stage(stage),
        "response": {
            "text": resp.text,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cache_read_tokens": resp.cache_read_tokens,
            "cache_write_tokens": resp.cache_write_tokens,
            "duration_s": resp.duration_s,
            "stop_reason": resp.stop_reason,
        },
    }
    replay_cache_path(key).write_text(json.dumps(data, indent=2))


def complete(
    *,
    prompt: str,
    model: str,
    system: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: Optional[float] = None,
    cache: bool = False,
    cached_prompt: Optional[str] = None,
    tools: Optional[list[dict]] = None,
    thinking: Optional[str] = None,
    work_dir: Optional[Path] = None,
    stage: str = "unknown",
) -> LLMResponse:
    """Call an LLM.

    Caching shape (Anthropic only; OpenAI path ignores cache args):
      - `cached_prompt` (preferred): the stable book-scale prefix; goes first
        as a separate content block with cache_control. `prompt` is appended
        as the per-call tail (uncached). Enables cross-stage cache reuse.
      - `cache=True` (legacy): wrap the entire `prompt` in one cached block.
        Useful when there's no natural split.
    The two flags are independent; if both are set, `cached_prompt` wins.

    `thinking`: on supported Anthropic models, requests adaptive thinking
    and sets the effort level ("low" | "medium" | "high" | "xhigh" | "max").
    Thinking tokens count toward output billing and max_tokens. None leaves
    the provider default unchanged; Opus 5.5 always thinks and Sonnet 5.5
    enables adaptive thinking by default. The OpenAI adapter leaves reasoning
    effort at its provider default.
    """
    # Model overrides:
    #   FORAGE_{STAGE}_MODEL (e.g. FORAGE_CRITIC_MODEL) — per-stage, wins.
    #   FORAGE_MODEL — global fallback.
    # Applies to the cache key too, so each model's responses sit side-by-side.
    requested = model
    model, override_source = resolve_model_for_stage(model, stage)

    import sys as _sys
    if override_source and model != requested:
        print(f"[llm] stage={stage} model={model} "
              f"(caller requested {requested}, overridden by {override_source})",
              file=_sys.stderr, flush=True)
    else:
        print(f"[llm] stage={stage} model={model}",
              file=_sys.stderr, flush=True)

    provider, _, model_id = model.partition(":")
    if not model_id:
        raise ValueError(f"model must be '<provider>:<id>', got {model!r}")

    replay = _replay_enabled()
    if replay:
        # Tools and thinking influence the response; include in cache key.
        key = replay_key_for_request(model, system, cached_prompt, prompt,
                                     max_tokens, temperature, tools=tools,
                                     thinking=thinking)
        hit = _replay_load(key)
        if hit is not None:
            r = hit["response"]
            resp = LLMResponse(
                text=r["text"], model=model,
                input_tokens=r.get("input_tokens"),
                output_tokens=r.get("output_tokens"),
                cache_read_tokens=r.get("cache_read_tokens"),
                cache_write_tokens=r.get("cache_write_tokens"),
                duration_s=r.get("duration_s", 0.0),
                stop_reason=r.get("stop_reason"),
            )
            if _STREAM_SINK is not None:
                _STREAM_SINK(f"[REPLAY:{key[:8]}]\n{resp.text}")
            if work_dir is not None:
                _log_call(work_dir, stage=f"{stage}:replayed", prompt=prompt,
                          system=system, model=model, response=resp)
            return resp

    start = time.time()
    if provider == "anthropic":
        resp = _anthropic(prompt=prompt, model_id=model_id, system=system,
                          max_tokens=max_tokens, temperature=temperature,
                          cache=cache, cached_prompt=cached_prompt,
                          tools=tools, thinking=thinking)
    elif provider == "openai":
        # OpenAI has no equivalent of Anthropic's prompt-prefix caching, so
        # flatten cached_prompt + prompt into a single user message.
        flat = prompt if not cached_prompt else cached_prompt + prompt
        resp = _openai(prompt=flat, model_id=model_id, system=system,
                       max_tokens=max_tokens, temperature=temperature)
    else:
        raise ValueError(f"unknown provider {provider!r}")
    resp.duration_s = time.time() - start

    if replay:
        _replay_save(key, model, resp, stage)

    if work_dir is not None:
        _log_call(work_dir, stage=stage, prompt=prompt, system=system,
                  model=model, response=resp)
    return resp


_RETRY_EXCEPTIONS_CACHE = None


def _retryable_exceptions() -> tuple:
    """Network-layer exceptions worth retrying transparently."""
    global _RETRY_EXCEPTIONS_CACHE
    if _RETRY_EXCEPTIONS_CACHE is not None:
        return _RETRY_EXCEPTIONS_CACHE
    import httpx
    errs: list = [
        httpx.RemoteProtocolError,
        httpx.ReadTimeout,
        httpx.ConnectError,
        httpx.WriteTimeout,
        httpx.PoolTimeout,
        LLMStreamTimeoutError,
    ]
    try:
        import anthropic
        errs += [anthropic.APIConnectionError, anthropic.APITimeoutError]
    except ImportError:
        pass
    try:
        import openai
        errs += [openai.APIConnectionError, openai.APITimeoutError]
    except ImportError:
        pass
    _RETRY_EXCEPTIONS_CACHE = tuple(errs)
    return _RETRY_EXCEPTIONS_CACHE


def _with_retries(fn, *, attempts: int = 3,
                  backoff: tuple[int, ...] = (2, 5, 15)):
    """Call `fn` with transparent retries on transient network errors.

    Non-retryable exceptions (auth, quota, bad request) propagate immediately.
    """
    last: Optional[Exception] = None
    retryable = _retryable_exceptions()
    for i in range(attempts):
        try:
            return fn()
        except retryable as e:
            last = e
            if i == attempts - 1:
                break
            wait = backoff[min(i, len(backoff) - 1)]
            import sys
            print(f"[retry] {type(e).__name__} on attempt {i + 1}/{attempts}; "
                  f"sleeping {wait}s", file=sys.stderr, flush=True)
            time.sleep(wait)
    assert last is not None
    raise last


def _anthropic(*, prompt: str, model_id: str, system: Optional[str],
               max_tokens: int, temperature: Optional[float],
               cache: bool,
               cached_prompt: Optional[str] = None,
               tools: Optional[list[dict]] = None,
               thinking: Optional[str] = None) -> LLMResponse:
    import anthropic
    read_timeout = _env_float("FORAGE_ANTHROPIC_READ_TIMEOUT_S",
                              DEFAULT_ANTHROPIC_READ_TIMEOUT_S)
    text_timeout = _env_float("FORAGE_ANTHROPIC_TEXT_TIMEOUT_S", read_timeout)
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(
        default_headers={"anthropic-workspace-id": workspace} if workspace else {},
        timeout=anthropic.Timeout(connect=30.0, read=read_timeout,
                                  write=60.0, pool=30.0)
    )
    if cached_prompt is not None:
        # Two blocks: cached prefix + uncached tail. Prefix carries the
        # cache_control; the tail is plain text so it doesn't extend the
        # cached segment (only content up to and including a breakpoint is
        # cached, so putting cache_control on the tail would cache everything).
        content = [
            {"type": "text", "text": cached_prompt,
             "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": prompt},
        ]
    elif cache:
        content = [{"type": "text", "text": prompt,
                    "cache_control": {"type": "ephemeral"}}]
    else:
        content = prompt
    kwargs = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools
    if thinking:
        kwargs["thinking"] = {"type": "adaptive"}
        kwargs["output_config"] = {"effort": thinking}

    def _call() -> tuple[list[str], object]:
        import signal
        import threading

        chunks_inner: list[str] = []
        use_alarm = (
            threading.current_thread() is threading.main_thread()
            and hasattr(signal, "SIGALRM")
            and hasattr(signal, "ITIMER_REAL")
        )
        previous_handler = None

        def _raise_stream_timeout(signum, frame):
            raise LLMStreamTimeoutError(
                f"Anthropic stream yielded no text for {text_timeout:g}s"
            )

        if use_alarm:
            previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, _raise_stream_timeout)
            signal.setitimer(signal.ITIMER_REAL, text_timeout)
        try:
            with client.messages.stream(**kwargs) as stream:
                for chunk in stream.text_stream:
                    if use_alarm:
                        signal.setitimer(signal.ITIMER_REAL, text_timeout)
                    chunks_inner.append(chunk)
                    if _STREAM_SINK is not None:
                        _STREAM_SINK(chunk)
                final_inner = stream.get_final_message()
            return chunks_inner, final_inner
        finally:
            if use_alarm:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
                signal.signal(signal.SIGALRM, previous_handler)

    chunks, final = _with_retries(_call)
    text = "".join(chunks)
    usage = final.usage
    return LLMResponse(
        text=text,
        model=f"anthropic:{model_id}",
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
        duration_s=0.0,
        stop_reason=final.stop_reason,
    )


_STREAM_SINK = None  # set via set_stream_sink for live output


def set_stream_sink(sink) -> None:
    """Register a callable(chunk: str) -> None called for each streamed token."""
    global _STREAM_SINK
    _STREAM_SINK = sink


def _openai(*, prompt: str, model_id: str, system: Optional[str],
            max_tokens: int, temperature: Optional[float]) -> LLMResponse:
    import openai
    client = openai.OpenAI()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    # Newer OpenAI models (gpt-5, o-series) use max_completion_tokens and
    # reject the legacy max_tokens. Use the new name and let the API map
    # it for older models.
    kwargs = {
        "model": model_id,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    # Reasoning models (o1, o3, o4) often reject non-default temperature.
    # Only pass it if the caller explicitly set one.
    if temperature is not None:
        kwargs["temperature"] = temperature
    def _call():
        try:
            return client.chat.completions.create(**kwargs)
        except openai.BadRequestError as e:
            # Graceful fallback for legacy models that want max_tokens.
            if "max_completion_tokens" in str(e) or "max_tokens" in str(e):
                kwargs.pop("max_completion_tokens", None)
                kwargs["max_tokens"] = max_tokens
                return client.chat.completions.create(**kwargs)
            raise

    r = _with_retries(_call)
    choice = r.choices[0]
    return LLMResponse(
        text=choice.message.content or "",
        model=f"openai:{model_id}",
        input_tokens=getattr(r.usage, "prompt_tokens", None),
        output_tokens=getattr(r.usage, "completion_tokens", None),
        duration_s=0.0,
        stop_reason=choice.finish_reason,
    )


def _log_call(work_dir: Path, *, stage: str, prompt: str,
              system: Optional[str], model: str, response: LLMResponse) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    log_path = work_dir / "llm_calls.jsonl"
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stage": stage,
        "model": model,
        "prompt_hash": prompt_hash,
        "prompt_chars": len(prompt),
        "system_chars": len(system) if system else 0,
        "response_chars": len(response.text),
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cache_read_tokens": response.cache_read_tokens,
        "cache_write_tokens": response.cache_write_tokens,
        "duration_s": round(response.duration_s, 2),
        "stop_reason": response.stop_reason,
    }
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")
