# Homepage Rollout

## Scope

-   [ ] Deploy Homepage into the `web` namespace
-   [ ] Expose Homepage at `https://homepage.krapulax.dev`
-   [ ] Enable in-cluster Kubernetes discovery with Gateway API support
-   [ ] Add Homepage discovery annotations to externally exposed `HTTPRoute` objects
-   [ ] Keep the initial rollout free of committed widget credentials

## Assumptions

-   Gateway API `HTTPRoute` resources remain the primary public routing layer for the cluster
-   Homepage service discovery will rely on `gethomepage.dev/*` annotations on those routes
-   Homepage will run behind the existing external gateway and TLS path
-   API-backed Homepage widgets can be added later once any required credentials exist in Doppler

## Validation

-   [ ] `kubectl get application -n argo-system homepage`
-   [ ] `kubectl rollout status deploy/homepage -n web`
-   [ ] `kubectl get httproute -n web homepage`
-   [ ] `kubectl get httproute -A -o yaml | rg 'gethomepage.dev/'`
-   [ ] Open `https://homepage.krapulax.dev`
-   [ ] Confirm discovered services appear from annotated routes

## Rollback

-   [ ] Remove the Homepage Argo application
-   [ ] Remove Homepage route annotations from services that should not be auto-discovered
-   [ ] Remove any Homepage-specific Doppler secrets if API-backed widgets are later rolled back
