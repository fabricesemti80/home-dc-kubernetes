# MkDocs Multi-Repository Setup

This mkdocs deployment is configured to pull documentation from multiple Git repositories and display them in a unified interface.

## Current Setup

### Data Sources

**Primary Repository:**
- Source: `https://github.com/fabricesemti80/home-dc-kubernetes.git` (branch: `main`)
- Content: All documentation from `/docs` folder
- Sync: Automatic on pod restart (via Stakater Reloader)

### How It Works

1. **Initialization** (`init-docs.sh`):
   - Runs when the mkdocs pod starts
   - Clones the repository with shallow clone (`--depth=1`) for efficiency
   - Copies documentation files from the repo's `/docs` folder
   - Copies mkdocs configuration from ConfigMap
   - Creates the directory structure for mkdocs

2. **Storage**:
   - Documentation is stored in a `cephfs` PVC (`/docs`)
   - Persists across pod restarts
   - Survives pod updates

3. **Auto-Update**:
   - Enabled via `reloader.stakater.com/auto: "true"` annotation
   - Pod restarts when ConfigMaps change
   - Re-runs initialization script to sync latest content

## Adding External Repository Sources

### Option 1: Add to Existing Init Script (Recommended)

Edit `kubernetes/apps/app-cluster/productivity/mkdocs/config/init-scripts/configmap.yaml` and add clone commands in the `init-docs.sh` script:

```bash
# Clone additional repository
echo "📦 Cloning external repo..."
git clone --depth=1 --branch=main "https://github.com/username/external-repo.git" /tmp/external-repo

# Copy documentation
if [ -d "/tmp/external-repo/docs" ]; then
  cp -r /tmp/external-repo/docs/* "$DOCS_DIR/docs/external/" 2>/dev/null || true
  echo "   ✓ Copied external documentation"
fi
```

### Option 2: Use Environment Variables (For Secrets/Dynamic Repos)

Modify the init script to accept environment variables:

```bash
# In init-docs.sh, add:
EXTERNAL_REPOS="${EXTERNAL_REPOS:-}"

# Then for each repo:
for repo_url in $(echo "$EXTERNAL_REPOS" | tr ',' '\n'); do
  # Clone and process
done
```

Then add to `values.yaml`:

```yaml
controllers:
  mkdocs:
    containers:
      app:
        env:
          - name: EXTERNAL_REPOS
            value: "https://github.com/user/repo1.git,https://github.com/user/repo2.git"
```

### Option 3: Using Kustomize Overlays

Create environment-specific overlays:

```
kubernetes/apps/app-cluster/productivity/mkdocs/
├── base/
│   ├── values.yaml
│   └── kustomization.yaml
└── overlays/
    └── with-external-repos/
        ├── kustomization.yaml
        └── init-scripts-patch.yaml
```

## Customizing Navigation

The documentation structure is defined in the mkdocs.yml ConfigMap (`kubernetes/apps/app-cluster/productivity/mkdocs/config/docs-seed/configmap.yaml`).

### Update Navigation Structure

Edit the `nav:` section in the ConfigMap to add new sections:

```yaml
nav:
  - Home: index.md
  - New Section:
    - Page 1: path/to/page1.md
    - Page 2: path/to/page2.md
```

### Important Considerations

1. **File Paths**: Use relative paths from the `/docs` directory root
2. **External Repos**: If cloning to subdirectories, adjust navigation paths accordingly
3. **Naming Conflicts**: Ensure doc file names don't conflict between repositories

## Repository Cloning Examples

### Clone a Specific Folder from a Repo

```bash
# Clone only a specific directory using sparse checkout
git clone --filter=blob:none --sparse "https://github.com/user/repo.git" /tmp/partial-repo
cd /tmp/partial-repo
git sparse-checkout set docs/specific-folder
```

### Clone Multiple Branches

```bash
# Clone different branches from the same repo
git clone --branch=branch-name --single-branch "https://github.com/user/repo.git" /tmp/repo-branch

# Copy and organize by branch
cp -r /tmp/repo-branch/docs "$DOCS_DIR/docs/branch-name/"
```

## Environment Variables

Configure these in `values.yaml` under `initContainers.seed-docs.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DOCS_DIR` | `/docs` | Root directory for documentation |
| `REPO_URL` | `https://github.com/fabricesemti80/home-dc-kubernetes.git` | Primary repository URL |
| `REPO_BRANCH` | `main` | Repository branch to clone |
| `GIT_DEPTH` | `1` | Shallow clone depth (lower = faster) |

## Troubleshooting

### Check Pod Logs

```bash
kubectl logs -n productivity deployment/mkdocs -c seed-docs
```

### Verify Documentation Files

```bash
# Connect to pod
kubectl exec -it -n productivity deployment/mkdocs -- sh

# Check documentation structure
ls -la /docs/docs/
find /docs/docs -name "*.md" | head -20
```

### Force Sync

```bash
# Restart the pod to trigger re-initialization
kubectl rollout restart deployment/mkdocs -n productivity
```

## Performance Tips

1. **Use Shallow Clones**: Set `GIT_DEPTH=1` for faster cloning
2. **Cache Efficiently**: PVC persists docs, reducing re-clone time
3. **Limit Repository Size**: Clone only necessary branches and folders
4. **Monitor Pod Startup**: Check init container logs for bottlenecks

## Security Considerations

- **Credentials**: Use SSH keys or GitHub tokens via Kubernetes secrets if needed
- **Private Repos**: Mount SSH key or configure git credentials in init container
- **Network Access**: Pod requires outbound HTTPS access to GitHub (or your Git server)

### Using Private Repositories

```yaml
# In values.yaml, add Git SSH config
persistence:
  ssh-config:
    type: secret
    name: git-ssh-credentials
    globalMounts:
      - path: /root/.ssh
        readOnly: true
```

Then update init script to use SSH:
```bash
export GIT_SSH_COMMAND="ssh -i /root/.ssh/id_rsa -o StrictHostKeyChecking=no"
git clone git@github.com:user/private-repo.git
```

## Next Steps

1. **Test Current Setup**: Deploy and verify documentation loads correctly
2. **Add External Repos**: Modify init script to include other documentation sources
3. **Customize Navigation**: Update mkdocs.yml to match your doc structure
4. **Monitor Sync**: Watch pod logs to ensure automatic updates work
