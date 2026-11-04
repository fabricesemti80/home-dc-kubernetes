# Usenet downloads failing in a loop, 2026-11-04

## Symptom

Dark Matter (and partly Lioness) episodes kept failing in SABnzbd and were re-grabbed over and over.

## Diagnosis

-   SABnzbd connected to its only provider (`news.eweka.nl`, TLS 1.3, 50 connections) without problems, but the log said `Article ... unavailable on all servers, discarding`: the articles of these releases are not on that provider. With `fail_hopeless_jobs` enabled, SABnzbd aborts such a job within seconds ("Aborted, cannot be completed").
-   Sonarr treated every abort as a failed download, blocklisted the release and grabbed the next one immediately. Sonarr history since 2026-10-30: Dark Matter 101 Usenet grabs, 99 failures, 3 imports; Lioness 33 grabs, 27 failures, 6 imports. The releases came from several groups, which points at removed or incomplete articles on that provider (the exact cause was not verified).
-   Not the cause: NZBgeek (no indexer backed off in Prowlarr, 0 failed queries, a live search returned results, no throttling in the log), the network, or SABnzbd itself. Radarr was unaffected (10 events, 0 failures).
-   Torrents worked but the swarms for these releases are small (several stalled with no seeds).

## What was changed (Sonarr, live, not in Git)

Sonarr's configuration lives in its database, so this is recorded here. Settings > Profiles > Delay Profiles:

-   New tag `torrent-first`.
-   New delay profile (order 1, tag `torrent-first`): preferred protocol **torrent**, Usenet delay **240 minutes**, torrent delay 0, "bypass if highest quality" **off**.
-   The tag was added to the series that fail most: Dark Matter (2024) and Lioness. Series without the tag still use the default profile (Usenet preferred, no delay).

Effect: for tagged series Sonarr takes a torrent release immediately if one exists and only falls back to Usenet after four hours, which stops the instant retry loop against missing articles.

To revert: remove the tag from the series (Series > Edit), then delete the delay profile and the tag.

## What would actually fix it

-   A second Usenet provider on a **different backbone** from the first one, so SABnzbd can fetch the missing articles there (needs a paid account; none at the moment). Check the backbone before buying.
-   More or better torrent indexers in Prowlarr to get better-seeded releases (currently only The Pirate Bay).

## Related: a Deployment cannot move from RollingUpdate to Recreate through Argo's server-side apply

During the Seerr rollout (`docs/operations/2026-11-04-media-stack-update.md`) the Jellyseerr Application showed `Synced` but never rolled out: Argo's comparison failed with `spec.strategy.rollingUpdate: Forbidden: may not be specified when strategy type is 'Recreate'`, because the live Deployment kept its defaulted `rollingUpdate` parameters. Fix, once, on the live object (it only matches the strategy Git already declares and does not touch the pod template):

```bash
kubectl -n media patch deployment <name> --type=merge -p '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}'
```

Check `kubectl -n argo-system get application <name> -o jsonpath='{.status.conditions}'` after any such change; `Synced` on the parent list does not prove the rollout happened.
