"""Pure data: YAML schemas and resolved domain objects. No file or process I/O."""

from .base import HOSTNAME_PATTERN, MAC_PATTERN, MIN_VM_ID, NAME_PATTERN, StrictModel
from .service import HostSpec, ResolvedHost, ResolvedService, ServiceFile
from .site import (
    DEBIAN_13_URL,
    DEFAULT_ANSIBLE_VARS,
    ExporterOptions,
    HostConfig,
    HostDefaults,
    Image,
    Network,
    NetworkOverrides,
    Node,
    ProxmoxConnection,
    SiteConfig,
    SmartctlExporterOptions,
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
    "ExporterOptions",
    "HostConfig",
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
    "SmartctlExporterOptions",
    "Ssh",
    "Storage",
    "StrictModel",
    "VmOptions",
]
