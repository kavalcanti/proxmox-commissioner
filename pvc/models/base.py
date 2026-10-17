"""Shared base model and naming rules."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")
HOSTNAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
MIN_VM_ID = 100


class StrictModel(BaseModel):
    """Unknown keys are errors, so typos in YAML surface instead of being ignored."""

    model_config = ConfigDict(extra="forbid")
