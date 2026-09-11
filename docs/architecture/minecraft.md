# Minecraft Server Design & Operations

## Architecture
- **Image**: `itzg/minecraft-server` (Vanilla)
- **Runtime**: Kubernetes Deployment (1 replica)
- **Resources**: 6Gi Heap / 8Gi Limit to prevent OOMKills from native overhead.
- **Storage**: 20Gi CephFS PVC (ReadWriteOnce) mounted at `/data`.
- **Network**: Exposed via TCP port 25565. Since Envoy Gateway is HTTP-centric, this server is reached via the ClusterIP service directly or a dedicated TCP listener.

## Security Assessment
- **Exposure**: Publicly exposed port 25565.
- **Risk**: Low (Standard Minecraft protocol).
- **Mitigation**: Server is isolated in the `gaming` namespace.

## Validation Procedure
1. Check pod logs for "Done (Xs)!".
2. Verify connectivity using a Minecraft client on port 25565.

## Rollback Plan
1. **Application Rollback**: Revert commit in `home-dc-kubernetes` and sync ArgoCD.
2. **Data Recovery**: The world data is persisted in CephFS; a snapshot of the PVC should be taken before major version upgrades. To restore, replace the PVC with the snapshot.
