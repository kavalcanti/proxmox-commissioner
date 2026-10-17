"""Loading site.yml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import paths
from ..errors import ConfigError, PvcError, format_validation_error
from ..models import SiteConfig
from ..utils import read_yaml


def parse_site(raw: Any, source: str = "site.yml") -> SiteConfig:
    if not isinstance(raw, dict):
        raise ConfigError(source, ["file must be a YAML mapping"])
    try:
        return SiteConfig.model_validate(raw)
    except ValidationError as error:
        raise ConfigError(source, format_validation_error(error)) from error


def load_site(path: Path | None = None) -> SiteConfig:
    path = path or paths.SITE_FILE
    if not path.is_file():
        raise PvcError(f"{path} not found. Run `pvc init` to create it from site.example.yml.")
    return parse_site(read_yaml(path), str(path))
