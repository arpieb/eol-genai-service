"""The single validator — the only gate between any query and EOL (Constitution Principle II)."""

from eol_genai_service.validator.core import Verdict, Violation, validate

__all__ = ["Verdict", "Violation", "validate"]
