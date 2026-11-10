#!/usr/bin/env bash
# Copy and verify an offline local-path PVC to an empty Longhorn PVC.
set -euo pipefail
fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}
[[ $# == 3 ]] || fail 'Usage: longhorn-copy-offline.sh <namespace> <source-pvc> <target-pvc>'
ns=$1 source=$2 target=$3
for value in "$ns" "$source" "$target"; do
  [[ $value =~ ^[a-z0-9]([-a-z0-9.]*[a-z0-9])?$ ]] || fail "Invalid Kubernetes name: $value"
done
[[ $source != "$target" ]] || fail 'Source and target must differ'
command -v kubectl >/dev/null || fail 'kubectl is required'
command -v jq >/dev/null || fail 'jq is required'
for pair in "$source:local-path" "$target:longhorn"; do
  name=${pair%%:*}
  expected=${pair#*:}
  data=$(kubectl -n "$ns" get pvc "$name" -o json) || fail "Cannot read PVC $ns/$name"
  [[ $(jq -r '.status.phase' <<<"$data") == Bound ]] || fail "$name is not Bound"
  [[ $(jq -r '.spec.storageClassName' <<<"$data") == "$expected" ]] || fail "$name is not on $expected"
done
# Terminal pods do not hold mounts. Every other pod must be stopped, including backup jobs.
users=$(kubectl -n "$ns" get pods -o json | jq -r --arg a "$source" --arg b "$target" '.items[] | select(.status.phase != "Succeeded" and .status.phase != "Failed") | select(any(.spec.volumes[]?; .persistentVolumeClaim.claimName == $a or .persistentVolumeClaim.claimName == $b)) | .metadata.name')
[[ -z $users ]] || fail "PVC still referenced by active pods: $users"
job="lh-copy-$(date +%s)-$RANDOM"
created=false
cleanup() { if $created; then kubectl -n "$ns" delete job "$job" --ignore-not-found >/dev/null || true; fi; }
trap cleanup EXIT
kubectl -n "$ns" create -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $job
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 7200
  template:
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: copy
          image: python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51
          command: [python3, -c]
          args:
            - |
              import filecmp, os, stat, subprocess, sys
              src, dst = '/source', '/target'
              if any(x != 'lost+found' for x in os.listdir(dst)):
                  sys.exit('Target is not empty; refusing to overwrite')
              if os.path.isdir(os.path.join(src, 'lost+found')) and os.listdir(os.path.join(src, 'lost+found')):
                  sys.exit('Source lost+found is not empty; inspect before migrating')
              subprocess.run(['cp', '-a', src + '/.', dst + '/'], check=True)
              def walk(root):
                  result = {}
                  for base, dirs, files in os.walk(root, followlinks=False):
                      if base == root and 'lost+found' in dirs:
                          dirs.remove('lost+found')
                      for name in dirs + files:
                          p = os.path.join(base, name)
                          rel = os.path.relpath(p, root)
                          s = os.lstat(p)
                          result[rel] = (stat.S_IFMT(s.st_mode), stat.S_IMODE(s.st_mode), s.st_uid, s.st_gid, os.readlink(p) if stat.S_ISLNK(s.st_mode) else None)
                  return result
              def root_metadata(root):
                  s = os.stat(root)
                  return stat.S_IMODE(s.st_mode), s.st_uid, s.st_gid
              if root_metadata(src) != root_metadata(dst):
                  sys.exit('Root permissions or ownership differ')
              a, b = walk(src), walk(dst)
              if a != b:
                  sys.exit('File names, types, modes, owners or symlink targets differ')
              for rel, meta in a.items():
                  if meta[0] == stat.S_IFREG and not filecmp.cmp(os.path.join(src, rel), os.path.join(dst, rel), shallow=False):
                      sys.exit('File content mismatch: ' + rel)
              print('Copy verified: file contents, names, types, permissions, ownership and symlinks match')
          securityContext:
            runAsUser: 0
            runAsGroup: 0
            allowPrivilegeEscalation: false
          volumeMounts:
            - {name: source, mountPath: /source, readOnly: true}
            - {name: target, mountPath: /target}
      volumes:
        - name: source
          persistentVolumeClaim: {claimName: $source, readOnly: true}
        - name: target
          persistentVolumeClaim: {claimName: $target}
EOF
created=true
deadline=$((SECONDS + 7200))
succeeded=false
while ((SECONDS < deadline)); do
  status=$(kubectl -n "$ns" get job "$job" -o json) || fail "Cannot read job $job; target may contain partial data"
  if [[ $(jq -r '.status.succeeded // 0' <<<"$status") -ge 1 ]]; then
    succeeded=true
    break
  fi
  if [[ $(jq -r '.status.failed // 0' <<<"$status") -ge 1 ]]; then
    kubectl -n "$ns" logs "job/$job" --all-containers --tail=30 >&2 || true
    fail 'Copy job failed; target may contain partial data and must not be used'
  fi
  sleep 3
done
if ! $succeeded; then
  kubectl -n "$ns" logs "job/$job" --all-containers --tail=30 >&2 || true
  fail 'Copy job timed out; target may contain partial data and must not be used'
fi
kubectl -n "$ns" logs "job/$job" --all-containers
