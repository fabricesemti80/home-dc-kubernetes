# 🎬 HomeTube Notes

Use the web UI at `https://hometube.krapulax.dev` (or `http://hometube.krapulax.home` on the LAN).

HomeTube is a universal video downloader (YouTube, Vimeo, Reddit, etc.) that
organizes downloads into a media-server-friendly structure.

## Storage

The app runs as UID 1000 (`streamlit`) and mounts the shared NFS media library:

-   `/data/videos` → `downloads/hometube/videos` on the NFS
-   `/data/tmp` → `downloads/hometube/tmp` on the NFS (staging area)

An init container creates and chowns those subdirectories to UID 1000 on first
start, so the non-root app can write into them.

Point HomeTube's destination folder at `/data/videos` — it will create
organised subfolders (e.g. `Tech/Python/Advanced`) there.

## First-run notes

-   Cookies: if YouTube downloads hit signature errors, add `youtube_cookies.txt`
    under `/config` (currently not mounted; mount a small CephFS PVC if needed).
-   ffmpeg is bundled in the image (`jauderho/yt-dlp` base), so clip/subtitle
    processing works out of the box.
