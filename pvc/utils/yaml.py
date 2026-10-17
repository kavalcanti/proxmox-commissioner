"""YAML reading and writing with errors reported as `PvcError`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..errors import PvcError


def parse_yaml(text: str, source: Path | str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise PvcError(f"{source} is not valid YAML: {error}") from error


def read_yaml(path: Path) -> Any:
    return parse_yaml(path.read_text(), path)


def parse_yaml_mapping(text: str, source: Path | str) -> dict[str, Any]:
    """Like `parse_yaml`, but the document must be a mapping."""
    data = parse_yaml(text, source)
    if not isinstance(data, dict):
        raise PvcError(f"{source} must be a YAML mapping.")
    return data


def dump_yaml(data: Any, header: str = "") -> str:
    return header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
