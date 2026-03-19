#!/bin/bash
# Shared library for lab-provisioning scripts
#
# This file is intentionally thin: it loads the smaller concern-specific modules.

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${LIB_DIR}/configs.sh"
source "${LIB_DIR}/terraform_ops.sh"
source "${LIB_DIR}/vm_ops.sh"
source "${LIB_DIR}/ansible_ops.sh"
