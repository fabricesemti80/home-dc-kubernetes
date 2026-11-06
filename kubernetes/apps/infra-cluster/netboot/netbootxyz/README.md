# 🥾 netboot.xyz notes

PXE boot server on the **infra cluster** (`infra-wk-01`): iPXE menus over TFTP, ISOs over HTTP. Use `--context infra-cluster` (or your infra kubeconfig) for the `kubectl` commands below.
Design: [netbootxyz.md](../../../../../docs/architecture/netbootxyz.md).
Rollout checklist: [netbootxyz-rollout.md](../../../../../docs/plan/netbootxyz-rollout.md).

| What               | Where                                                     |
| ------------------ | --------------------------------------------------------- |
| Web UI             | `http://netboot.krapulax.home` (internal only, no login)  |
| TFTP / next-server | `10.0.40.108` udp/69                                      |
| Local assets       | `http://10.0.40.108:8080/`                                |
| Config             | `/config` on PVC `netbootxyz` (local-path, `infra-wk-01`) |
| Assets on NAS      | `10.0.40.2:/media/netboot/assets` → `/assets` in the pod  |

## 🌐 Point the network at it (UniFi)

UniFi Network → **Settings → Networks →** the network your PXE clients are on (VLAN 40 for Proxmox VMs and nodes) → **DHCP Service Management / Advanced** →

-   **Network Boot**: on
    -   Server: `10.0.40.108`
    -   Filename: `netboot.xyz.efi` (UEFI). Use `netboot.xyz.kpxe` only if every client on that network is legacy BIOS.
-   Leave **TFTP Server (option 66)** empty or set it to `10.0.40.108` too; some firmware reads 66 instead of next-server.

UniFi sends one filename per network, so mixed BIOS/UEFI clients need either a separate network/VLAN, or a manual pick at the client. For VMs, use OVMF (UEFI).

Clients on **other VLANs** (e.g. VLAN 30) also need a firewall rule allowing `udp/69` and `tcp/8080` to `10.0.40.108`, plus the Network Boot settings on that network.

The bootloader files on TFTP:

| File                        | Use                                     |
| --------------------------- | --------------------------------------- |
| `netboot.xyz.efi`           | UEFI x86_64 (default)                   |
| `netboot.xyz-snp.efi`       | UEFI, if the NIC is not detected        |
| `netboot.xyz.kpxe`          | Legacy BIOS                             |
| `netboot.xyz-undionly.kpxe` | Legacy BIOS, if the NIC is not detected |
| `netboot.xyz-arm64.efi`     | ARM64 UEFI                              |

Quick test from a Linux/macOS workstation on VLAN 40:

```bash
curl -o /tmp/nbxyz.efi tftp://10.0.40.108/netboot.xyz.efi && ls -l /tmp/nbxyz.efi
```

## 💿 Mirror netboot.xyz assets locally (faster boots)

By default the menus pull kernels/ISOs from GitHub over the internet. To serve them from the NAS:

1. Web UI → **Local Assets** → tick the distros you use (e.g. Ubuntu, Debian, Rocky, SystemRescue) → **Pull Selected**. Files land in `/assets` (the NAS).
2. Web UI → **Menus** → `boot.cfg` → change the line

    ```ipxe
    set live_endpoint https://github.com/netbootxyz
    ```

    to

    ```ipxe
    set live_endpoint http://10.0.40.108:8080
    ```

    and save. Anything not mirrored then fails to load locally, so pull everything you use first (or set `live_endpoint` per menu file instead of globally).

## ➕ Add your own ISOs or kernels

1. **Copy the file to the NAS** under `/media/netboot/assets/` (SMB/NFS from your workstation is easiest), e.g. `/media/netboot/assets/custom/talos/vmlinuz-amd64`. Or from a workstation:

    ```bash
    kubectl -n netboot cp ./my.iso "$(kubectl -n netboot get pod -l app.kubernetes.io/name=netbootxyz -o name | cut -d/ -f2)":/assets/custom/my.iso
    ```

    It is then served at `http://10.0.40.108:8080/custom/...`.

2. **Enable the custom menu**: Web UI → Menus → `boot.cfg` → add `set menu custom-user`.
3. **Create `custom.ipxe`** in Web UI → Menus (new file), e.g.:

    ```ipxe
    #!ipxe
    :custom_menu
    menu Homelab
    item --gap -- Installers
    item talos   Talos Linux (metal, maintenance mode)
    item myiso   My ISO (sanboot)
    item --gap -- Return
    item back    Back to main menu
    choose sel || goto back
    goto ${sel}

    :talos
    set base http://10.0.40.108:8080/custom/talos
    kernel ${base}/vmlinuz-amd64 talos.platform=metal console=tty0 init_on_alloc=1 slab_nomerge pti=on
    initrd ${base}/initramfs-amd64.xz
    boot || goto custom_menu

    :myiso
    sanboot http://10.0.40.108:8080/custom/my.iso || goto custom_menu

    :back
    exit 0
    ```

    Get the Talos kernel/initramfs for your schematic from `https://factory.talos.dev` (PXE boot assets).

4. If the main menu still does not show the entry, open `menu.ipxe` in the UI and change `chain custom/custom.ipxe` to `chain custom.ipxe` ([upstream docs](https://netboot.xyz/docs/docker/custom-menus)).

Notes:

-   **Prefer kernel + initrd over `sanboot`** for ISOs. `sanboot` loads the whole ISO into RAM and only works for hybrid/small ISOs, and poorly on UEFI.
-   `custom.ipxe` survives menu upgrades. Edits to stock files (`boot.cfg`, `menu.ipxe`) can be overwritten when you upgrade menus from the UI; re-check them after an upgrade.
-   `/config` is backed up nightly (Backrest plan `app-netbootxyz`). `/assets` is not; it is re-downloadable.

## 🛠️ Useful commands

```bash
kubectl -n netboot logs deploy/netbootxyz -f
kubectl -n netboot exec deploy/netbootxyz -- tail -f /config/tftpd.log   # TFTP requests
kubectl -n netboot get svc netbootxyz-boot                              # EXTERNAL-IP 10.0.40.108
```
