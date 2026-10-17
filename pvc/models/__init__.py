"""Pure data: YAML schemas and resolved domain objects. No file or process I/O."""

from .base import HOSTNAME_PATTERN, MAC_PATTERN, MIN_VM_ID, NAME_PATTERN, StrictModel
from .service import HostSpec, ResolvedHost, ResolvedService, ServiceFile
from .site import (
    DEBIAN_13_URL,
    DEFAULT_ANSIBLE_VARS,
    HostDefaults,
    Image,
    Network,
    NetworkOverrides,
    Node,
    ProxmoxConnection,
    SiteConfig,
    Ssh,
    Storage,
    VmOptions,
)

__all__ = [
    "DEBIAN_13_URL",
    "DEFAULT_ANSIBLE_VARS",
    "HOSTNAME_PATTERN",
    "MAC_PATTERN",
    "MIN_VM_ID",
    "NAME_PATTERN",
    "HostDefaults",
    "HostSpec",
    "Image",
    "Network",
    "NetworkOverrides",
    "Node",
    "ProxmoxConnection",
    "ResolvedHost",
    "ResolvedService",
    "ServiceFile",
    "SiteConfig",
    "Ssh",
    "Storage",
    "StrictModel",
    "VmOptions",
]
