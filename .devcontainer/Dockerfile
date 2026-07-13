FROM mcr.microsoft.com/devcontainers/base:debian

ARG TASK_VERSION=3.52.0
ARG TOFU_VERSION=1.10.7
ARG KUBECTL_VERSION=1.36.2
ARG TALOSCTL_VERSION=1.13.6
ARG HELM_VERSION=4.2.3
ARG HELMFILE_VERSION=1.7.0
ARG KUSTOMIZE_VERSION=5.8.0
ARG SOPS_VERSION=3.13.2
ARG AGE_VERSION=1.3.1
ARG YQ_VERSION=4.53.3
ARG TFLINT_VERSION=0.59.1
ARG GITLEAKS_VERSION=8.28.0
ARG CILIUM_VERSION=0.19.5
ARG ARGOCD_VERSION=3.4.5
ARG CLOUDFLARED_VERSION=2026.7.1
ARG GH_VERSION=2.96.0
ARG KUBECONFORM_VERSION=0.8.0
ARG TALHELPER_VERSION=3.1.13
ARG UV_VERSION=0.11.28
ARG DOPPLER_VERSION=3.76.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash-completion \
    ca-certificates \
    curl \
    git \
    gnupg \
    jq \
    npm \
    openssh-client \
    pre-commit \
    python3 \
    python3-pip \
    python3-venv \
    shellcheck \
    shfmt \
    unzip \
    yamllint \
    zsh \
  && rm -rf /var/lib/apt/lists/*

RUN set -eu; \
  case "$(dpkg --print-architecture)" in \
    amd64) ARCH=amd64 ;; \
    arm64) ARCH=arm64 ;; \
    *) echo "unsupported arch $(dpkg --print-architecture)" >&2; exit 1 ;; \
  esac \
  && install -d /tmp/tools /usr/local/bin \
  && curl -fsSL "https://github.com/go-task/task/releases/download/v${TASK_VERSION}/task_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools task \
  && install /tmp/tools/task /usr/local/bin/task \
  && curl -fsSL "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_${ARCH}.zip" -o /tmp/tools/tofu.zip \
  && unzip -q /tmp/tools/tofu.zip -d /tmp/tools/tofu \
  && install /tmp/tools/tofu/tofu /usr/local/bin/tofu \
  && curl -fsSL "https://dl.k8s.io/release/v${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl" -o /usr/local/bin/kubectl \
  && chmod +x /usr/local/bin/kubectl \
  && curl -fsSL "https://github.com/siderolabs/talos/releases/download/v${TALOSCTL_VERSION}/talosctl-linux-${ARCH}" -o /usr/local/bin/talosctl \
  && chmod +x /usr/local/bin/talosctl \
  && curl -fsSL "https://get.helm.sh/helm-v${HELM_VERSION}-linux-${ARCH}.tar.gz" | tar -xz -C /tmp/tools \
  && install "/tmp/tools/linux-${ARCH}/helm" /usr/local/bin/helm \
  && curl -fsSL "https://github.com/helmfile/helmfile/releases/download/v${HELMFILE_VERSION}/helmfile_${HELMFILE_VERSION}_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools helmfile \
  && install /tmp/tools/helmfile /usr/local/bin/helmfile \
  && curl -fsSL "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v${KUSTOMIZE_VERSION}/kustomize_v${KUSTOMIZE_VERSION}_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools kustomize \
  && install /tmp/tools/kustomize /usr/local/bin/kustomize \
  && curl -fsSL "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${ARCH}" -o /usr/local/bin/sops \
  && chmod +x /usr/local/bin/sops \
  && curl -fsSL "https://github.com/FiloSottile/age/releases/download/v${AGE_VERSION}/age-v${AGE_VERSION}-linux-${ARCH}.tar.gz" | tar -xz -C /tmp/tools \
  && install "$(find /tmp/tools -type f -name age | head -n 1)" /usr/local/bin/age \
  && install "$(find /tmp/tools -type f -name age-keygen | head -n 1)" /usr/local/bin/age-keygen \
  && curl -fsSL "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_${ARCH}" -o /usr/local/bin/yq \
  && chmod +x /usr/local/bin/yq \
  && curl -fsSL "https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_${ARCH}.zip" -o /tmp/tools/tflint.zip \
  && unzip -q /tmp/tools/tflint.zip -d /tmp/tools/tflint \
  && install /tmp/tools/tflint/tflint /usr/local/bin/tflint \
  && curl -fsSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools gitleaks \
  && install /tmp/tools/gitleaks /usr/local/bin/gitleaks \
  && curl -fsSL "https://github.com/cilium/cilium-cli/releases/download/v${CILIUM_VERSION}/cilium-linux-${ARCH}.tar.gz" | tar -xz -C /tmp/tools cilium \
  && install /tmp/tools/cilium /usr/local/bin/cilium \
  && curl -fsSL "https://github.com/argoproj/argo-cd/releases/download/v${ARGOCD_VERSION}/argocd-linux-${ARCH}" -o /usr/local/bin/argocd \
  && chmod +x /usr/local/bin/argocd \
  && curl -fsSL "https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-${ARCH}" -o /usr/local/bin/cloudflared \
  && chmod +x /usr/local/bin/cloudflared \
  && curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools \
  && install "/tmp/tools/gh_${GH_VERSION}_linux_${ARCH}/bin/gh" /usr/local/bin/gh \
  && curl -fsSL "https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-linux-${ARCH}.tar.gz" | tar -xz -C /tmp/tools kubeconform \
  && install /tmp/tools/kubeconform /usr/local/bin/kubeconform \
  && curl -fsSL "https://github.com/budimanjojo/talhelper/releases/download/v${TALHELPER_VERSION}/talhelper_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools talhelper \
  && install /tmp/tools/talhelper /usr/local/bin/talhelper \
  && curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | env UV_INSTALL_DIR=/usr/local/bin sh \
  && curl -fsSL "https://github.com/DopplerHQ/cli/releases/download/${DOPPLER_VERSION}/doppler_${DOPPLER_VERSION}_linux_${ARCH}.tar.gz" | tar -xz -C /tmp/tools doppler \
  && install /tmp/tools/doppler /usr/local/bin/doppler \
  && npm install -g prettier @openai/codex \
  && python3 -m pip install --break-system-packages makejinja==2.8.2 \
  && rm -rf /tmp/tools

ENV PATH="/root/.local/bin:/home/vscode/.local/bin:${PATH}"
