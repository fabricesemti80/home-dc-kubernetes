# n8n Deployment

Deploys [n8n](https://n8n.io/) — a workflow automation platform — to the Talos Kubernetes cluster.

## Architecture

- **Namespace:** `productivity`
- **Chart:** `bjw-s-labs/app-template` (v5.0.1)
- **Image:** `docker.io/n8nio/n8n:2.25.5`
- **Database:** SQLite (embedded, stored on CephFS PVC)
- **Replicas:** 1 (stateful — SQLite doesn't support multi-replica)

## Networking

| Route | Hostname | Purpose |
|-------|----------|---------|
| External | `n8n.krapulax.dev` | Public access via Cloudflare Tunnel |
| Internal | `n8n.krapulax.home` | LAN access via Envoy internal gateway |

- **Authentication:** Cloudflare Access (email-based, 24h session, auto-redirect)
- **Webhook bypass:** Two Cloudflare Access Applications bypass auth for `/webhook` and `/webhook-test` paths so external services can trigger workflows.

## Storage

- **5Gi CephFS PVC** at `/home/node/.n8n` — holds SQLite DB, execution data, and n8n config.
- Ephemeral storage limit of 2Gi for temp data.

## Secrets

- `N8N_ENCRYPTION_KEY` synced from Doppler (`project-homelab/dev_homelab`) via `DopplerSecret` CRD.

## Scalability & Limitations

- Single-replica only (SQLite backend). Scaling to HA requires migrating to PostgreSQL.
- Execution data pruned after 168h (7 days) to keep PVC usage bounded.

## Rollback

1. `gh pr revert <pr-number>` or `git revert <commit-hash>`
2. Remove `n8n` from `dns_apps` and `zero_trust_apps` in `infra/terraform_cloudflare/variables.tf`
3. Remove n8n webhook bypass applications from `infra/terraform_cloudflare/main.tf`
4. Remove `unifi_dns_record.n8n_internal` from `infra/terraform_localdns/main.tf`
5. Run `terraform apply` on both Cloudflare and localdns dirs
6. Delete the `n8n` Application from ArgoCD (Argo will clean up the namespace resources)

## Validation

1. Verify pod is `Running` and ready: `kubectl -n productivity get pods -l app.kubernetes.io/name=n8n`
2. Check HTTPRoute is accepted: `kubectl -n productivity get httproutes n8n`
3. Hit `https://n8n.krapulax.dev` — should show Cloudflare Access login, then n8n editor
4. Check internal: `curl -H "Host: n8n.krapulax.home" http://10.0.40.102:80` should reach n8n
5. Trigger a test webhook to verify bypass works
