# Linkwarden Notes

Current intent:

-   deploy Linkwarden into the dedicated `productivity` namespace
-   serve it at `https://linkwarden.krapulax.dev`
-   keep user archive data on CephFS
-   keep the application PostgreSQL data on CephFS
-   source bootstrap secrets from Doppler

Storage layout:

-   `/data`
    -   CephFS PVC
    -   Linkwarden archive storage, screenshots, PDFs, and profile photos
-   PostgreSQL data
    -   CephFS PVC

Secrets:

-   `linkwarden-secrets` is managed by the Doppler operator
-   expected keys:
    -   `DATABASE_URL`
    -   `NEXTAUTH_URL`
    -   `NEXTAUTH_SECRET`
    -   `LINKWARDEN_DB_PASSWORD`

Route:

-   `https://linkwarden.krapulax.dev`

Operational note:

-   Linkwarden database migrations run from an init container before the web container starts
