# Paperclip Operator Integration

## Scope

-   [x] Add a new `ai` namespace through Argo CD.
-   [x] Install the upstream `paperclip-operator` Helm chart.
-   [x] Create a Paperclip `Instance` custom resource.
-   [x] Source auth and provider API keys from Doppler.
-   [x] Use CephFS-backed persistence for managed PostgreSQL.
-   [x] Keep Paperclip app storage ephemeral for the initial deployment because the upstream operator's SELinux relabel init container is not compatible with CephFS.
-   [x] Keep the first deployment private until auth, storage, and secret handling are validated.

## Proposed Shape

-   Namespace: `ai`
-   Operator chart: `oci://ghcr.io/paperclipinc/charts/paperclip-operator`
-   Candidate chart version: `0.12.1`
-   Instance app path: `kubernetes/apps/ai/paperclip/`
-   Argo apps:
    -   `kubernetes/argo/apps/ai/paperclip-operator.yaml`
    -   `kubernetes/argo/apps/ai/paperclip.yaml`
-   Instance API: `paperclip.inc/v1alpha1`
-   Paperclip image: `ghcr.io/paperclipai/paperclip@sha256:33d6183ba25698f9d61759fc348f964fa235af61a479d12cf73b02828e1a0d79`
-   Deployment mode: `authenticated`
-   Exposure: `private`
-   Service: `ClusterIP` on port `3100`
-   Database: managed PostgreSQL with CephFS storage
-   App persistence: disabled for the initial deployment

## Secrets

Use Doppler as the source of truth and render Kubernetes secrets in `ai`.

Initial secret keys:

-   `PAPERCLIP_BETTER_AUTH_SECRET`
-   `PAPERCLIP_MASTER_KEY`
-   `OPENAI_API_KEY`
-   `ANTHROPIC_API_KEY`

Optional later keys:

-   `PAPERCLIP_OAUTH_CREDENTIALS`
-   `PAPERCLIP_DATABASE_URL`
-   `PAPERCLIP_S3_ACCESS_KEY_ID`
-   `PAPERCLIP_S3_SECRET_ACCESS_KEY`

## Security Impact

-   Paperclip runs agent orchestration workloads and may receive LLM provider API keys, so the namespace should be treated as high-trust.
-   Start with private exposure to keep the control plane off public DNS while validating authentication.
-   Enable the operator and instance network policies where they do not block required cluster access.
-   Do not store provider API keys in `Instance` specs; use Secret references so credentials are not persisted directly in custom resources.
-   Pin image tags for the operator and Paperclip app; avoid `latest`.

## Assumptions

-   Kubernetes `v1.36.1` remains the active Talos target and satisfies the operator chart requirement of Kubernetes `>=1.28.0`.
-   CephFS is acceptable for the initial managed PostgreSQL PVC.
-   Paperclip app storage persistence requires either an upstream operator switch to disable SELinux relabeling or a storage class that supports the injected `chcon` init container.
-   A single Paperclip replica and managed PostgreSQL are acceptable for first validation.
-   Public access can be added later through Gateway API HTTPRoute after the private deployment is healthy.

## Validation

-   [ ] `helm template paperclip-operator oci://ghcr.io/paperclipinc/charts/paperclip-operator --version 0.12.1 --namespace ai --include-crds`
-   [ ] `kubectl get crd | rg paperclip`
-   [ ] `kubectl get application -n argo-system paperclip-operator paperclip`
-   [ ] `kubectl get instances -n ai`
-   [ ] `kubectl get pods,pvc,svc -n ai`
-   [ ] `kubectl port-forward -n ai svc/paperclip 3100:3100`

## Rollback

-   [ ] Remove the Paperclip `Instance` manifest first.
-   [ ] Confirm operator-managed workloads and services are gone.
-   [ ] Keep PVCs until Paperclip data export or deletion is confirmed.
-   [ ] Remove the Paperclip operator Argo CD application.
-   [ ] Remove Doppler Paperclip secrets only after rollback/export is no longer required.
