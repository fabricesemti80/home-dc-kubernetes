#!/usr/bin/env bash

###############################################################################
# Code Server Kubernetes Kubeconfig
#
# Purpose
# -------
# Creates a temporary kubeconfig from the ServiceAccount mounted inside the
# code-server pod.
#
# This enables tools such as:
#   - kubectl
#   - argocd --core
#   - helm
#
# which expect a normal kubeconfig instead of in-cluster authentication.
#
# Usage
# -----
# Source this script:
#
#   source hack/codeserver-kubeconfig.sh
#
# or
#
#   . hack/codeserver-kubeconfig.sh
#
# The script exports KUBECONFIG for the current shell.
#
# The generated kubeconfig contains the current ServiceAccount token and is
# written to /tmp, so it should not be committed to Git.
###############################################################################

set -euo pipefail

export KUBECONFIG="/tmp/code-server-kubeconfig"

SA_DIR="/var/run/secrets/kubernetes.io/serviceaccount"
API_SERVER="https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT_HTTPS:-443}"

echo "Generating temporary kubeconfig..."

kubectl config set-cluster kubernetes \
    --server="${API_SERVER}" \
    --certificate-authority="${SA_DIR}/ca.crt" \
    --embed-certs=true \
    >/dev/null

kubectl config set-credentials code-server \
    --token="$(<"${SA_DIR}/token")" \
    >/dev/null

kubectl config set-context code-server \
    --cluster=kubernetes \
    --user=code-server \
    --namespace=argo-system \
    >/dev/null

kubectl config use-context code-server >/dev/null

chmod 600 "${KUBECONFIG}"

echo
echo "✓ KUBECONFIG configured"
echo
echo "Current context:"
kubectl config current-context

echo
echo "Current namespace:"
kubectl config view --minify --output 'jsonpath={..namespace}'
echo

echo
echo "Example commands:"
echo "  kubectl get nodes"
echo "  kubectl get pods -n argo-system"
echo "  argocd login --core"
echo "  argocd app list --core"
echo