"""Use cases behind the CLI commands, free of argument parsing and terminal output."""

from .workflows import (
    ServiceStatus,
    apply_site,
    build_ssh_exec_args,
    converge_existing,
    converge_service,
    create_service_scaffold,
    down_service,
    get_service_status,
    load_site_and_service,
    plan_service,
    prepare_service_workspace,
    resolve_deployed_addresses,
    up_service,
)

__all__ = [
    "ServiceStatus",
    "apply_site",
    "build_ssh_exec_args",
    "converge_existing",
    "converge_service",
    "create_service_scaffold",
    "down_service",
    "get_service_status",
    "load_site_and_service",
    "plan_service",
    "prepare_service_workspace",
    "resolve_deployed_addresses",
    "up_service",
]
