#!/usr/bin/env bash
set -euo pipefail
# Copy an app's protected export into a NEW, empty Longhorn PVC
# (step 3 of docs/operations/local-path-to-longhorn.md).
#
# Source is the app-protect export on the NAS (SQLite already captured with the online backup API),
# not the live volume: the app keeps running, the database copy is consistent, and neither the app nor
# its old volume is touched. A fresh export is taken first unless --no-fresh-export is given.
#
# Safety: refuses if the target PVC is not Bound on the `longhorn` class, is used by any pod, or already
# holds files (unless --force). Afterwards every SQLite file is checked with PRAGMA integrity_check.
#
# usage: longhorn-migrate-copy.sh <namespace> <app> <new-pvc> <uid> <gid> [--no-fresh-export] [--force]
#   uid/gid: the user the app runs as; the copied files are chowned to it.
# Uses the KUBECONFIG from the environment (the Taskfile exports it).

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}
ok() { printf 'ok:   %s\n' "$*"; }

# Wait until a Job succeeds or fails. `kubectl wait --for=condition=complete` only watches one
# condition, so a Job that fails would block until the timeout.
wait_job() {
  local name=$1 limit=$2 waited=0 succeeded failed
  while ((waited < limit)); do
    succeeded=$(kubectl -n "$ns" get job "$name" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)
    failed=$(kubectl -n "$ns" get job "$name" -o jsonpath='{.status.failed}' 2>/dev/null || true)
    [[ ${succeeded:-0} -ge 1 ]] && return 0
    [[ ${failed:-0} -ge 1 ]] && return 1
    sleep 3
    waited=$((waited + 3))
  done
  return 1
}

[[ $# -ge 5 ]] || fail "usage: $0 <namespace> <app> <new-pvc> <uid> <gid> [--no-fresh-export] [--force]"
ns=$1 app=$2 pvc=$3 uid=$4 gid=$5
shift 5
fresh=true
force=0
for arg in "$@"; do
  case $arg in
  --no-fresh-export) fresh=false ;;
  --force) force=1 ;;
  *) fail "unknown option $arg" ;;
  esac
done
[[ $uid =~ ^[0-9]+$ && $gid =~ ^[0-9]+$ ]] || fail "uid and gid must be numbers"

cronjob="protect-$app"
kubectl -n "$ns" get cronjob "$cronjob" >/dev/null 2>&1 || fail "no CronJob $ns/$cronjob: the app is not protected by app-protect, so there is no export to copy from"

# Target volume: bound, on Longhorn, unused.
class=$(kubectl -n "$ns" get pvc "$pvc" -o jsonpath='{.spec.storageClassName}' 2>/dev/null) || fail "PVC $ns/$pvc does not exist"
phase=$(kubectl -n "$ns" get pvc "$pvc" -o jsonpath='{.status.phase}')
[[ $class == longhorn ]] || fail "PVC $pvc uses storage class '$class', expected 'longhorn'"
[[ $phase == Bound ]] || fail "PVC $pvc is $phase, expected Bound"
users=$(kubectl -n "$ns" get pods -o json | jq -r --arg c "$pvc" '.items[] | select(any(.spec.volumes[]?; .persistentVolumeClaim.claimName == $c)) | .metadata.name')
[[ -z $users ]] || fail "PVC $pvc is in use by: $users"
ok "target $ns/$pvc is Bound on longhorn and unused"

# Everything about the export location comes from the app's own CronJob, so nothing is duplicated here.
template='.spec.jobTemplate.spec.template.spec'
image=$(kubectl -n "$ns" get cronjob "$cronjob" -o jsonpath="{$template.containers[0].image}")
cluster=$(kubectl -n "$ns" get cronjob "$cronjob" -o json | jq -r "$template.containers[0].env[] | select(.name == \"CLUSTER_NAME\") | .value")
nas_server=$(kubectl -n "$ns" get cronjob "$cronjob" -o json | jq -r "$template.volumes[] | select(.name == \"backups\") | .nfs.server")
nas_path=$(kubectl -n "$ns" get cronjob "$cronjob" -o json | jq -r "$template.volumes[] | select(.name == \"backups\") | .nfs.path")
[[ -n $image && -n $cluster && -n $nas_server && -n $nas_path ]] || fail "could not read the export settings from CronJob $cronjob"

if $fresh; then
  export_job="$app-migrate-export-$(date -u +%H%M%S)"
  kubectl -n "$ns" create job --from="cronjob/$cronjob" "$export_job" >/dev/null
  if ! wait_job "$export_job" 600; then
    kubectl -n "$ns" logs "job/$export_job" --all-containers --tail=30 >&2 || true
    fail "the fresh export job $export_job failed or timed out; it is left in place for inspection"
  fi
  kubectl -n "$ns" delete job "$export_job" >/dev/null
  ok "fresh export taken"
else
  ok "using the existing export (--no-fresh-export)"
fi

copy_job="$app-migrate-copy"
kubectl -n "$ns" delete job "$copy_job" --ignore-not-found >/dev/null
kubectl -n "$ns" apply -f - >/dev/null <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $copy_job
  namespace: $ns
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 900
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        seccompProfile:
          type: RuntimeDefault
      initContainers:
        # Reads the 0700 export as the NAS writer (UID 1004) into a scratch volume.
        - name: read-export
          image: $image
          command:
            - sh
            - -c
            - |
              src=/backups/$cluster/exports/$app/current
              test -f \$src/.captured-at || { echo "no export at \$src"; exit 1; }
              echo "export captured at \$(cat \$src/.captured-at)"
              cp -R \$src/. /stage/
          securityContext:
            runAsUser: 1004
            runAsGroup: 65534
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
          volumeMounts:
            - {name: backups, mountPath: /backups, readOnly: true}
            - {name: stage, mountPath: /stage}
      containers:
        # Writes into the new volume as root so ownership can be set to the app's user.
        - name: write-volume
          image: $image
          env:
            - {name: APP_UID, value: "$uid"}
            - {name: APP_GID, value: "$gid"}
            - {name: FORCE, value: "$force"}
          command:
            - python3
            - -c
            - |
              import os, shutil, sqlite3, sys
              SRC, DST = "/stage", "/dest"
              existing = [n for n in os.listdir(DST) if n != "lost+found"]
              if existing and os.environ["FORCE"] != "1":
                  sys.exit("destination is not empty: %s (use --force to overwrite)" % existing[:5])
              for name in os.listdir(SRC):
                  if name == ".captured-at":
                      continue
                  s, d = os.path.join(SRC, name), os.path.join(DST, name)
                  if os.path.isdir(s) and not os.path.islink(s):
                      shutil.copytree(s, d, symlinks=True, dirs_exist_ok=True)
                  else:
                      shutil.copy2(s, d, follow_symlinks=False)
              uid, gid = int(os.environ["APP_UID"]), int(os.environ["APP_GID"])
              os.chown(DST, uid, gid)
              for root, dirs, files in os.walk(DST):
                  for n in dirs + files:
                      os.lchown(os.path.join(root, n), uid, gid)
              checked = 0
              for root, dirs, files in os.walk(DST):
                  for n in files:
                      p = os.path.join(root, n)
                      if os.path.islink(p):
                          continue
                      with open(p, "rb") as fh:
                          head = fh.read(16)
                      if head == b"SQLite format 3\x00":
                          c = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
                          res = c.execute("pragma integrity_check").fetchone()[0]
                          c.close()
                          print("sqlite %s: integrity_check=%s" % (os.path.relpath(p, DST), res))
                          checked += 1
                          if res != "ok":
                              sys.exit(1)
              print("databases checked: %d" % checked)
              for root, dirs, files in sorted(os.walk(DST)):
                  for n in sorted(files):
                      p = os.path.join(root, n)
                      st = os.lstat(p)
                      print("%8d %d:%d %s" % (st.st_size, st.st_uid, st.st_gid, os.path.relpath(p, DST)))
          securityContext:
            runAsUser: 0
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: [ALL]
              add: [CHOWN, DAC_OVERRIDE, FOWNER]
          volumeMounts:
            - {name: stage, mountPath: /stage, readOnly: true}
            - {name: dest, mountPath: /dest}
      volumes:
        - name: backups
          nfs:
            server: $nas_server
            path: $nas_path
        - name: stage
          emptyDir:
            sizeLimit: 4Gi
        - name: dest
          persistentVolumeClaim:
            claimName: $pvc
EOF

if ! wait_job "$copy_job" 900; then
  echo '--- copy job logs:' >&2
  kubectl -n "$ns" logs "job/$copy_job" --all-containers --tail=40 >&2 || true
  fail "the copy job failed or timed out; it is left in place for inspection (kubectl -n $ns describe job/$copy_job)"
fi
echo "--- what was copied:"
kubectl -n "$ns" logs "job/$copy_job" --all-containers
kubectl -n "$ns" delete job "$copy_job" >/dev/null
ok "copied into $ns/$pvc; the volume is detached again and ready for the cutover"
