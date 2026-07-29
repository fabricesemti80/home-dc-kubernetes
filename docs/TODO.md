# TODO

This document captures architectural and automation work that is intentionally deferred. Items should be converted into implementation pull requests when time permits.

## Create GitHub Actions for Taskfile tasks that do not need to be manual

Review the repository Taskfile targets and identify deterministic tasks that should run automatically in GitHub Actions rather than relying on a developer to remember them.

Candidate categories include:

-   generated configuration and documentation;
-   formatting and linting;
-   Kubernetes manifest validation;
-   Helm and Kustomize rendering checks;
-   drift detection;
-   repository consistency checks.

### Completion criteria

-   classify relevant Taskfile targets as manual, local helper, validation, or automation;
-   create focused GitHub Actions for tasks that are safe and useful to automate;
-   avoid duplicating task logic inside workflow YAML where the workflow can invoke the existing Taskfile target;
-   document any tasks that must remain manual and why.

## Separate app-cluster and infra-cluster folder structure

Refactor the Kubernetes repository layout so that resources targeting the application cluster and infrastructure cluster are clearly separated.

The structure should make cluster ownership obvious from the path and reduce the need to inspect Argo CD destination configuration before understanding where a workload runs.

A possible direction is:

```text
kubernetes/
  app-cluster/
    apps/
    platform/
    networking/
    storage/
  infra-cluster/
    apps/
    platform/
    networking/
    storage/
```

The final structure should follow the actual responsibilities of each cluster rather than this example mechanically.

### Completion criteria

-   verify both clusters reconcile successfully after the full migration;
-   add validation that prevents new app manifests from using the legacy mixed folders.

## Separate app-cluster and infra-cluster DNS validation

Complete validation and ownership checks for DNS records split between the application and infrastructure clusters.

Public services use canonical cluster endpoints:

```text
external-apps.krapulax.dev  -> application-cluster Cloudflare Tunnel
external-infra.krapulax.dev -> infrastructure-cluster Cloudflare Tunnel
```

Service records should continue pointing to the appropriate cluster endpoint rather than directly referencing tunnel UUIDs or ambiguous legacy aliases.

The design should also define ownership of internal DNS records and which cluster or controller is authoritative for each DNS zone.

### Completion criteria

-   document internal DNS ownership boundaries;
-   add validation that prevents new records from bypassing the canonical endpoints.

## Separate app-cluster and infra-cluster Doppler configs

Split shared Doppler configuration into independent config boundaries for the application and infrastructure clusters.

This should reduce secret exposure, clarify ownership, and allow credentials and service tokens to be rotated independently.

The chosen naming model is:

```text
home-dc-kubernetes/apps
home-dc-kubernetes/infra
```

Canary and full migration PRs should move DopplerSecret manifests and local Doppler CLI tasks to these configs.

### Completion criteria

-   inventory existing secrets and classify them by cluster and workload;
-   create separate Doppler projects or configurations with least-privilege access;
-   issue independent operator or service tokens for each cluster;
-   migrate `DopplerSecret` resources without exposing secret values in Git;
-   remove obsolete shared access after successful migration;
-   document secret ownership, rotation, and recovery procedures.
