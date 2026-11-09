# ☸️ Talos Clusters

Talos source is split by cluster:

-   `app/`: Proxmox VM app-cluster source managed by `talhelper`
-   `infra/`: physical infra-cluster source patches and notes

Generated machine configs, kubeconfigs, and private keys are local-only and must stay out of Git.

## Image Factory schematics

App-cluster nodes install from `factory.talos.dev/installer/<schematic-id>`. Schematics are public and non-secret; recreate or verify one with `curl -s -X POST --data-binary @schematic.yaml https://factory.talos.dev/schematics` (the ID is a hash of the content). The IDs are set per node in `talconfig.yaml` (rendered from the git-ignored `nodes.yaml` `schematic_id`).

| Nodes                        | Schematic ID                                                       | System extensions                                                                                                                        |
| ---------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `k8s-ctrl-01`                | `376567988ad370138ad8b2698212367b8edcb69b5fd68c80be1f2ec7d603b4ba` | none (empty schematic)                                                                                                                   |
| `k8s-wrkr-02`, `k8s-wrkr-03` | `613e1592b2da41ae5e265e8789429f22e121aab91cb4deb6bc3c0b6262961245` | `siderolabs/iscsi-tools`, `siderolabs/util-linux-tools`                                                                                  |
| `k8s-wrkr-01-gpu`            | `fb73a1920c434ba8ec579d24f15097f18ffb171342b1c61f68c063d1b2b601c2` | `siderolabs/iscsi-tools`, `siderolabs/nonfree-kmod-nvidia-lts`, `siderolabs/nvidia-container-toolkit-lts`, `siderolabs/util-linux-tools` |

```yaml
# workers 02/03
customization:
    systemExtensions:
        officialExtensions:
            - siderolabs/iscsi-tools
            - siderolabs/util-linux-tools
```

The GPU worker adds `siderolabs/nonfree-kmod-nvidia-lts` and `siderolabs/nvidia-container-toolkit-lts` (NVIDIA 580-series LTS, required by the P2000). Extensions only change on `talosctl upgrade --image …`, not on `apply-config`. The previous GPU schematic was `af8eb82417d3deaa94d2ef19c3b590b0dac1b2549d0b9b35b3da2bc325de75f7` and the previous worker schematic was the empty `3765…`.

## Worker data volumes

Each worker has three disks, told apart by **size** (device names are not stable): 55 GiB system, 100 GiB `local-path-provisioner` (`/var/mnt/local-path-provisioner`), ~465 GiB passed-through SSD `longhorn` (`/var/mnt/longhorn`, see [Longhorn](../docs/operations/longhorn.md)). The `worker.patches` entry `patches/worker/machine-longhorn.yaml` adds the kubelet bind mount Longhorn needs.
