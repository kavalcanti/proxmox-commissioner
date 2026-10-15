"""Shared exception types."""

from __future__ import annotations

from pydantic import ValidationError


class PvcError(Exception):
    """A user-facing error. The CLI prints the message and exits non-zero."""


class ConfigError(PvcError):
    """Invalid site.yml or service.yml. Carries every problem found, not just the first."""

    def __init__(self, source: str, problems: list[str]):
        self.source = source
        self.problems = problems
        lines = "\n".join(f"  - {problem}" for problem in problems)
        super().__init__(f"{source} is invalid:\n{lines}")


def format_validation_error(error: ValidationError) -> list[str]:
    """Flatten a pydantic error into 'path: message' strings."""
    problems = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        message = item["msg"]
        problems.append(f"{location}: {message}" if location else message)
    return problems
