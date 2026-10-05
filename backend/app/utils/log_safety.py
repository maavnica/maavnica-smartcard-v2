"""Sanitation centralisée des diagnostics avant stockage ou journalisation."""

from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL_RE = re.compile(
    r"(?i)(?<![A-Z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9.-]+"
    r"(?![A-Z0-9.-])"
)
_NAMED_SECRET_RE = re.compile(
    r"(?i)(api[-_]?key|x-key|smtp_pass(?:word)?|password|token|secret)"
    r"\s*[:=]\s*\S+"
)


def sanitize_log_text(
    value: object,
    *,
    secrets: Iterable[str] = (),
    limit: int = 500,
) -> str:
    """Masque toute adresse e-mail et toute valeur secrète connue."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = _EMAIL_RE.sub("***@***", text)
    text = _NAMED_SECRET_RE.sub(r"\1=***", text)
    for secret in secrets:
        cleaned = str(secret or "").strip()
        if cleaned:
            text = text.replace(cleaned, "***")
    return " ".join(text.split())[:limit]
