# Decommission Unused Apps

## Scope

-   Remove `hometube` and `copyparty` from `media`.
-   Remove `n8n`, `mkdocs`, and `convertx` from `productivity`.
-   Remove matching public/internal route, monitor, Cloudflare Access, and local DNS definitions managed in this repo.

## Assumptions

-   The apps are no longer needed by users.
-   `hometube` data remains under the shared `media-library-pvc` NFS subpaths.
-   `copyparty`, `n8n`, `mkdocs`, and `convertx` have chart-created CephFS PVCs.
-   Doppler project secrets can be cleaned manually after the cluster no longer references them.

## Data Handling

-   Before cascading Application deletion, record the PVC and PV bindings:

    ```sh
    kubectl get pvc -n media -l app.kubernetes.io/instance=copyparty -o wide
    kubectl get pvc -n productivity -l 'app.kubernetes.io/instance in (n8n,mkdocs,convertx)' -o wide
    ```

-   If rollback must preserve old CephFS data, either keep those PVCs out of the cascade or clear/rebind the retained PVs before re-syncing the apps.
-   Do not delete `media-library-pvc` or `downloads/hometube/` unless the downloaded files are intentionally being removed.

## Validation

-   `pre-commit run --files <changed files>`
-   `tofu -chdir=infra/terraform_cloudflare plan`
-   `tofu -chdir=infra/terraform_localdns plan`
-   After merge: add the Argo resource finalizer, then delete the five live child Applications because the root `apps` Application uses `Prune=false`:

    ```sh
    for app in hometube copyparty n8n mkdocs convertx; do
      kubectl patch application -n argo-system "$app" --type merge \
        -p '{"metadata":{"finalizers":["resources-finalizer.argocd.argoproj.io"]}}'
      kubectl delete application -n argo-system "$app"
    done
    ```

-   Confirm `kubectl get applications -n argo-system` no longer lists them.
-   Confirm the app pods/routes are gone:

    ```sh
    kubectl get pods,httproutes -n media -l 'app.kubernetes.io/instance in (hometube,copyparty)'
    kubectl get pods,httproutes -n productivity -l 'app.kubernetes.io/instance in (n8n,mkdocs,convertx)'
    ```

## Rollback

-   Revert this PR.
-   Re-sync the `apps` Argo Application.
-   Recreate or rebind retained CephFS PVC/PVs for `copyparty`, `n8n`, `mkdocs`, and `convertx` if their previous data is needed.
-   Re-apply Cloudflare and local DNS Terraform if the hostname records are needed again.
