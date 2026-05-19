"""Content redaction helpers for memory learning pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class RedactionResult:
    """Redaction output containing sanitized text and metadata."""

    content: str
    applied: bool


class MemoryRedactor:
    """Apply basic secret/sensitive data masking patterns."""

    _EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
    _TOKEN_RE = re.compile(r"\b(?:sk|rk|pk|ghp|gho|ghu|bearer)[-_a-zA-Z0-9]{8,}\b", re.IGNORECASE)
    _LONG_NUMBER_RE = re.compile(r"\b\d{12,}\b")

    def redact(self, content: str) -> RedactionResult:
        sanitized = self._EMAIL_RE.sub("[redacted_email]", content)
        sanitized = self._TOKEN_RE.sub("[redacted_token]", sanitized)
        sanitized = self._LONG_NUMBER_RE.sub("[redacted_number]", sanitized)
        return RedactionResult(content=sanitized, applied=sanitized != content)
