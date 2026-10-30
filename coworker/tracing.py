"""Optional Langfuse tracing for agent turns, model calls, and tools."""

from __future__ import annotations

import atexit
import contextlib
import json
import logging
import os
import re
from typing import Any, Iterator, Optional

logger = logging.getLogger("coworker.tracing")

_client: Any = None
_propagate_attributes: Any = None
_client_ready: Optional[bool] = None
_atexit_registered = False

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|password|authorization|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"\b(?:sk|pk|ghp|gho|xox[abp]|ya29|AIza)[A-Za-z0-9_\-]{12,}\b"
)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)


def _tracing_enabled() -> bool:
    flag = os.environ.get("LANGFUSE_TRACING_ENABLED", "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    has_keys = bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    )
    has_host = bool(
        os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
    )
    return has_keys and has_host


def _get_client() -> Any:
    global _atexit_registered, _client, _client_ready, _propagate_attributes
    if _client_ready is False:
        return None
    if not _tracing_enabled():
        _client_ready = False
        return None
    if _client is None:
        try:
            from langfuse import get_client, propagate_attributes

            _client = get_client()
            _propagate_attributes = propagate_attributes
            _client_ready = True
        except Exception as exc:  # pragma: no cover - depends on optional env/package
            logger.debug("Langfuse tracing disabled: %s", exc)
            _client_ready = False
            return None
    if not _atexit_registered:
        atexit.register(flush)
        _atexit_registered = True
    return _client


def flush() -> None:
    client = _client
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        logger.debug("Langfuse flush failed", exc_info=True)


class NoopObservation:
    enabled = False

    def update(self, **_kwargs: Any) -> "NoopObservation":
        return self

    def end(self) -> None:
        return None


class Observation:
    enabled = True

    def __init__(self, observation: Any):
        self._observation = observation
        self._ended = False

    def update(self, **kwargs: Any) -> "Observation":
        if self._ended:
            return self
        safe = {
            key: sanitize(value) if key in {"input", "output", "metadata"} else value
            for key, value in kwargs.items()
        }
        try:
            self._observation.update(**safe)
        except Exception:
            logger.debug("Langfuse observation update failed", exc_info=True)
        return self

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        try:
            self._observation.end()
        except Exception:
            logger.debug("Langfuse observation end failed", exc_info=True)


class TurnTrace:
    enabled = True

    def __init__(self, root: Any):
        self._root = root

    def update(self, **kwargs: Any) -> None:
        safe = {
            key: sanitize(value) if key in {"input", "output", "metadata"} else value
            for key, value in kwargs.items()
        }
        try:
            self._root.update(**safe)
        except Exception:
            logger.debug("Langfuse turn update failed", exc_info=True)

    def start_generation(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        metadata: dict[str, Any],
    ) -> Observation:
        try:
            return Observation(
                self._root.start_observation(
                    as_type="generation",
                    name="generate-assistant-turn",
                    input=sanitize_messages(messages),
                    model=model,
                    metadata={
                        **metadata,
                        "tool_count": len(tools or []),
                    },
                )
            )
        except Exception:
            logger.debug("Langfuse generation start failed", exc_info=True)
            return NoopObservation()

    def start_tool(self, tool_name: str, arguments: dict[str, Any]) -> Observation:
        try:
            return Observation(
                self._root.start_observation(
                    as_type="tool",
                    name="execute-tool",
                    input={"name": tool_name, "arguments": sanitize(arguments)},
                    metadata={"tool_name": tool_name},
                )
            )
        except Exception:
            logger.debug("Langfuse tool start failed", exc_info=True)
            return NoopObservation()


class NoopTurnTrace:
    enabled = False

    def update(self, **_kwargs: Any) -> None:
        return None

    def start_generation(self, **_kwargs: Any) -> NoopObservation:
        return NoopObservation()

    def start_tool(self, *_args: Any, **_kwargs: Any) -> NoopObservation:
        return NoopObservation()


@contextlib.contextmanager
def start_turn_trace(
    *,
    operation: str,
    user_input: Any,
    session_id: str,
    agent: str,
    workspace: str,
    model: str,
    mode: str,
    source: Optional[dict[str, Any]] = None,
) -> Iterator[TurnTrace | NoopTurnTrace]:
    client = _get_client()
    if client is None:
        yield NoopTurnTrace()
        return

    metadata = {
        "operation": operation,
        "agent": agent,
        "workspace": workspace,
        "model": model,
        "mode": mode,
        "source": source_type(source),
    }
    tags = ["openworker", f"agent:{agent}", f"turn:{operation}"]
    try:
        trace_cm = client.start_as_current_observation(
            as_type="agent",
            name="run-agent-turn",
            input=sanitize(user_input),
            metadata=metadata,
        )
    except Exception:
        logger.debug("Langfuse turn start failed", exc_info=True)
        yield NoopTurnTrace()
        return

    with trace_cm as root:
        propagate = _propagate_attributes
        if propagate is None:
            yield TurnTrace(root)
        else:
            with propagate(
                session_id=session_id or None,
                tags=tags,
                trace_name="run-agent-turn",
            ):
                yield TurnTrace(root)


def source_type(source: Optional[dict[str, Any]]) -> str:
    if not source:
        return "direct"
    return str(source.get("connector") or source.get("kind") or source.get("type") or "external")[
        :80
    ]


def sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_message(message) for message in messages]


def sanitize_message(message: dict[str, Any]) -> dict[str, Any]:
    out = {
        k: v
        for k, v in message.items()
        if k not in {"source", "_display", "ts", "reasoning"}
        and not str(k).startswith("_")
    }
    if "content" in out:
        out["content"] = sanitize_content(out["content"])
    if "tool_calls" in out:
        out["tool_calls"] = sanitize(out["tool_calls"])
    return out


def sanitize_content(value: Any) -> Any:
    if isinstance(value, list):
        cleaned = []
        for part in value:
            if not isinstance(part, dict):
                cleaned.append(sanitize(part))
                continue
            kind = part.get("type")
            if kind == "image_url":
                cleaned.append({"type": "image_url", "image_url": "[image redacted]"})
            elif kind == "file":
                filename = ((part.get("file") or {}).get("filename") or "file")[:120]
                cleaned.append({"type": "file", "file": {"filename": filename}})
            else:
                cleaned.append(sanitize(part))
        return cleaned
    return sanitize(value)


def sanitize(value: Any, *, max_chars: int = 8000) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                out[key_text] = "[redacted]"
            else:
                out[key_text] = sanitize(item, max_chars=max_chars)
        return out
    if isinstance(value, list):
        return [sanitize(item, max_chars=max_chars) for item in value[:50]]
    if isinstance(value, tuple):
        return [sanitize(item, max_chars=max_chars) for item in value[:50]]
    if isinstance(value, str):
        text = _BEARER_RE.sub("Bearer [redacted]", value)
        text = _SECRET_VALUE_RE.sub("[redacted]", text)
        if len(text) > max_chars:
            return text[: max_chars - 15] + "...[truncated]"
        return text
    try:
        json.dumps(value)
        return value
    except TypeError:
        return sanitize(str(value), max_chars=max_chars)
