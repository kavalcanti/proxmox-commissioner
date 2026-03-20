#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

SERVICE="${1:-}"
SERVICES_DIR="${CONFIG_DIR}/services"

if [[ -n "${SERVICE}" ]] && [[ ! -d "${SERVICES_DIR}/${SERVICE}" ]]; then
    echo "Error: No Configuration for service '${SERVICE}'" >&2
    echo "Expected: ${SERVICES_DIR}/${SERVICE}/" >&2
    exit 1
fi

echo "Updating Ansible inventory..."

if [[ -n "${SERVICE}" ]]; then
    services=("${SERVICE}")
else
    services=()
    for service_dir in "${SERVICES_DIR}"/*/; do
        [[ -d "${service_dir}" ]] || continue
        services+=("$(basename "${service_dir}")")
    done
fi

FOUND=0
for service_name in "${services[@]}"; do
    if "${SCRIPT_DIR}/inventory-generate.sh" "${service_name}"; then
        FOUND=$((FOUND + 1))
    else
        echo "  Warning: Could not generate inventory for '${service_name}' (no terraform state?)" >&2
    fi
done

if [[ ${FOUND} -eq 0 ]]; then
    echo "Error: No services with terraform state found." >&2
    exit 1
fi

echo ""
echo "Inventory updated for ${FOUND} service(s)"
