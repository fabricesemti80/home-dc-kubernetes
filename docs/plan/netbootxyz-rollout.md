# 🥾 netboot.xyz rollout

Design: [architecture/netbootxyz.md](../architecture/netbootxyz.md). Operator notes: [app README](../../kubernetes/apps/app-cluster/netboot/netbootxyz/README.md).

## Before merge

-   [ ] Confirm `10.0.40.108` is not in the UniFi DHCP range for VLAN 40 and not used elsewhere (`home-dc-terraform`, `home-dc-proxmox`).
-   [ ] Confirm the NAS export `10.0.40.2:/media` has room for ISOs (budget about 100–200 GB).

## After merge

-   [ ] Argo app `netbootxyz` is `Synced/Healthy`.
-   [ ] `kubectl -n netboot get svc netbootxyz-boot` shows `10.0.40.108`; both PVCs are `Bound`.
-   [ ] `curl -o /tmp/nbxyz.efi tftp://10.0.40.108/netboot.xyz.efi` works from VLAN 40.
-   [ ] `http://netboot.krapulax.home` opens.
-   [ ] UniFi → VLAN 40 network → Network Boot: server `10.0.40.108`, filename `netboot.xyz.efi`.
-   [ ] A test Proxmox VM (OVMF, network boot first) reaches the netboot.xyz menu.
-   [ ] Optional: pull local assets and set `live_endpoint` (README → "Mirror netboot.xyz assets locally").
-   [ ] Run the first backup: `kubectl create job --from=cronjob/protect-netbootxyz netbootxyz-first -n netboot`, then `task backups:run CLUSTER=app-cluster PLAN=app-netbootxyz`.

## If TFTP times out through the LB

Check `/config/tftpd.log` for the request first. If requests arrive but transfers stall, use the `hostNetwork` fallback in the design doc's Rollback section.
