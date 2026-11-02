# Kubernetes version policy

Talos 1.13.8 supports Kubernetes 1.31.0 through 1.36.99. Keep the app cluster and its generation template on Kubernetes 1.36.x; the reviewed patch target is 1.36.6. Renovate caps `ghcr.io/siderolabs/kubelet` below 1.37.0 to prevent incompatible independent minor upgrades.

Source: [Talos 1.13.8 compatibility constants](https://github.com/siderolabs/talos/blob/v1.13.8/pkg/machinery/compatibility/talos113/talos113.go).

Assumption: Talos remains on the 1.13 minor. Review the Renovate cap against upstream compatibility whenever upgrading the Talos minor, and update both `talos/app/talenv.yaml` and `templates/config/talos/talenv.yaml.j2` together.

Validation: run the CI lint and manifest workflows, including `talhelper validate talconfig talconfig.yaml` from `talos/app`. Passing configuration validation does not perform or verify a live cluster upgrade. Before deploying, verify running node versions and follow the Talos Kubernetes upgrade procedure.

Rollback before deployment: revert the fix commit and restore both version files to the main-branch baseline (1.36.3); retain or restore the compatibility cap. After deployment, do not treat a Git revert as a Kubernetes downgrade; use the supported recovery procedure and backups.
