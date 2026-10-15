#!/bin/bash
# Deploy recipe for the service-template service.
# Playbook lists live in this service's deploy.conf; initial hardening is
# skipped automatically once the VM is hardened.
#
# Run from the project root. Options are passed through to service-deploy.sh:
#   --commission   provision the VM first
#   --post-deploy  also run post-deploy.sh on the VM
#   --dry-run      show what would run
set -e

bash ./scripts/service-deploy.sh service-template "$@"
