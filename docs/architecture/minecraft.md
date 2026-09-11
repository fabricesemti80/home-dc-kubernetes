# Minecraft Server Design & Operations

## Architecture
- **Image**: `itzg/minecraft-server` (Vanilla)
- **Runtime**: Kubernetes Deployment (1 replica)
- **Resources**: 6Gi Heap / 8Gi Limit to prevent OOMKills from native overhead.
- **Storage**: 20Gi CephFS PVC (ReadWriteOnce) mounted at `/data`.
- **Network**: Exposed on TCP port 25565 through a Cilium `LoadBalancer` Service. Cilium assigns a LAN IP from its pool; Envoy Gateway is not used because Minecraft is not HTTP.

## Security Assessment
- **Exposure**: Available only on the assigned LAN LoadBalancer IP and port 25565. No WAN port forward is configured.
- **Risk**: Low (Standard Minecraft protocol).
- **Mitigation**: Server is isolated in the `gaming` namespace.

## Validation Procedure
1. Check pod logs for "Done (Xs)!".
2. Verify the Service has an `EXTERNAL-IP`: `kubectl -n gaming get service minecraft-server-service`.
3. Connect a Minecraft client to `<EXTERNAL-IP>:25565`.

## Rollback Plan
1. **Application Rollback**: Revert the Service to `NodePort` in `home-dc-kubernetes` and sync ArgoCD.
2. **Data Recovery**: The world data is persisted in CephFS; a snapshot of the PVC should be taken before major version upgrades. To restore, replace the PVC with the snapshot.
