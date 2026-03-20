#!/bin/bash
set -e

# Create a new service by copying 00-service-template and renaming placeholders.
# Usage: ./scripts/new-service-from-template.sh <service-name>

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
    cat <<EOF
Usage: $(basename "$0") <service-name>

Create a new service directory from the service template.

Arguments:
  service-name  New service identifier (pattern: [a-z0-9][a-z0-9-]*)

Options:
  -h, --help Show this help message and exit

Example:
  $(basename "$0") my-media-server
EOF
}

case "${1:-}" in
    -h|--help)
        print_help
        exit 0
        ;;
    -*)
        echo "Error: Unknown option '${1}'" >&2
        print_help >&2
        exit 1
        ;;
esac

# ------------------------------------------------------------------------------
# Arguments
# ------------------------------------------------------------------------------
if [[ -z "${1:-}" ]]; then
    print_help >&2
    exit 1
fi

SERVICE="${1}"

# ------------------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------------------
# Reject empty or whitespace-only

if [[ ! "${SERVICE}" =~ [^[:space:]] ]]; then
    echo "Error: Service name must not be empty or whitespace-only." >&2
    print_help >&2
    exit 1
fi

# Reject path traversal and unsafe characters
if [[ "${SERVICE}" == */* || "${SERVICE}" == *..* || "${SERVICE}" == .* || "${SERVICE}" == *. ]]; then
    echo "Error: Service name must not contain '/', '..', or lead/end with '.'." >&2
    print_help >&2
    exit 1
fi

# Optional: restrict to hostname-friendly pattern [a-z0-9][a-z0-9-]*
if [[ ! "${SERVICE}" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "Error: Service name must match [a-z0-9][a-z0-9-]* (e.g. my-service)." >&2
    print_help >&2
    exit 1
fi

TEMPLATE_DIR="${CONFIG_DIR}/defaults/services/service-template"
TARGET_DIR="${SERVICES_DIR}/${SERVICE}"

if [[ ! -d "${TEMPLATE_DIR}" ]]; then
    echo "Error: Template not found at ${TEMPLATE_DIR}" >&2
    print_help >&2
    exit 1
fi

if [[ -d "${TARGET_DIR}" ]]; then
    echo "Error: Service '${SERVICE}' already exists at ${TARGET_DIR}" >&2
    echo "Choose a different name or remove the existing directory." >&2
    print_help >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# Copy
# ------------------------------------------------------------------------------
mkdir -p "$(dirname "${TARGET_DIR}")"
cp -r "${TEMPLATE_DIR}" "${TARGET_DIR}"

# ------------------------------------------------------------------------------
# Rename and substitute
# ------------------------------------------------------------------------------
if [[ -f "${TARGET_DIR}/service-template.infrastructure.env" ]]; then
    mv "${TARGET_DIR}/service-template.infrastructure.env" "${TARGET_DIR}/${SERVICE}.infrastructure.env"
else
    mv "${TARGET_DIR}/service-template.infrastructure.env.example" "${TARGET_DIR}/${SERVICE}.infrastructure.env"
fi
rm "${TARGET_DIR}/ansible/.gitkeep"
rm "${TARGET_DIR}/filetree/.gitkeep"

# Resolve Terraform module source relative to service terraform root.
module_dir="${TERRAFORM_DIR}/modules/proxmox-vm"
if [[ ! -d "${module_dir}" ]]; then
    echo "Error: Terraform module not found at ${module_dir}" >&2
    exit 1
fi
module_source="${module_dir}"

# Replace template placeholders with concrete values in the new service directory only
for f in "${TARGET_DIR}/${SERVICE}.infrastructure.env" "${TARGET_DIR}/deploy-service.sh"; do
    if [[ -f "${f}" ]]; then
        sed -i "s/service-template/${SERVICE}/g" "${f}"
    fi
done

if [[ -f "${TARGET_DIR}/terraform/main.tf" ]]; then
    sed -i "s#__PROXMOX_VM_MODULE_SOURCE__#${module_source}#g" "${TARGET_DIR}/terraform/main.tf"
fi

# ------------------------------------------------------------------------------
# Output
# ------------------------------------------------------------------------------
echo "Created service '${SERVICE}' at ${TARGET_DIR}/"
echo "  - Edit ${TARGET_DIR}/${SERVICE}.infrastructure.env (VM id, IP, etc.)"
echo "  - Then run steps in ${TARGET_DIR}/deploy-service.sh"
