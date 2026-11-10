# 📺 Sonarr Notes

Use the web UI at `https://sonarr.krapulax.dev`.

Recommended first settings:

-   Root folder:
    -   `/media/tv`
-   Download client:
    -   type: `SABnzbd`
    -   host: `sabnzbd.media.svc.cluster.local`
    -   port: `8080`
    -   SSL: `off`
    -   URL base: empty
    -   category: `tv`
    -   API key: copy from the SABnzbd UI
-   Media Management:
    -   keep completed download handling enabled

The pod mounts:

-   `/config` on a Longhorn ReadWriteOnce PVC (`sonarr-longhorn`, declared in `config/pvc-config-longhorn.yaml`; the old local-path claim `sonarr` is retained until the migration is signed off, see docs/architecture/longhorn.md)
-   `/media` on the shared NFS library
-   `/downloads` on the shared NFS completed-downloads path

Runtime note:

-   `PATH` includes `/app/sonarr/bin` so Sonarr can run its bundled `ffprobe` when checking whether completed-download files are samples.
