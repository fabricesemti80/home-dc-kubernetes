# Terraform guests

This directory owns standalone service guests.

## PBS CPU from root PAM polling

`proxmox-pbs-0` is the PBS LXC at `10.0.40.16`.

On 2026-07-15, the container reported near-100% CPU. The hot process was
`unix_chkpwd root nullok`, spawned by `proxmox-backup-api`.

Cause: Proxmox storage `pbs-proxmox-backup` was configured as `root@pam`, so
regular PVE storage polling repeatedly hit PBS PAM authentication.

Fix applied:

-   created PBS API token `root@pam!pve-storage`
-   granted it `DatastoreAdmin` on `/datastore/proxmox-pbs-datastore`
-   changed PVE storage `pbs-proxmox-backup` username to `root@pam!pve-storage`
-   kept the existing Proxmox storage password file as the token secret
-   changed existing PBS backup group owners to `root@pam!pve-storage`

Validation:

-   `pvesm status` showed `pbs-proxmox-backup` active from `pve-0`, `pve-1`, and `pve-2`
-   PBS CPU dropped back to normal; no hot `unix_chkpwd` process remained

If this regresses, check `/etc/pve/storage.cfg` before tuning PBS resources.

If backups fail with `backup owner check failed`, check group ownership with:

```sh
PBS_PASSWORD_FILE=/etc/pve/priv/storage/pbs-proxmox-backup.pw \
PBS_FINGERPRINT=<storage fingerprint> \
proxmox-backup-client list \
  --repository root@pam!pve-storage@10.0.40.16:proxmox-pbs-datastore
```
