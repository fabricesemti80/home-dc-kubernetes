{
  description = "Development shell for home-dc-kubernetes";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = {nixpkgs, ...}: let
    systems = ["aarch64-darwin" "x86_64-linux"];
    forAllSystems = nixpkgs.lib.genAttrs systems;
  in {
    devShells = forAllSystems (system: let
      pkgs = import nixpkgs {inherit system;};
      makejinja = pkgs.writeShellApplication {
        name = "makejinja";
        runtimeInputs = [pkgs.uv];
        text = ''
          exec uvx --from makejinja==2.8.2 makejinja "$@"
        '';
      };
    in {
      default = pkgs.mkShell {
        packages = with pkgs; [
          age
          argocd
          cilium-cli
          cloudflared
          cue
          doppler
          gh
          gitleaks
          go-task
          helmfile
          jq
          kubeconform
          kubectl
          kubernetes-helm
          kustomize
          makejinja
          opentofu
          pre-commit
          prettier
          python3
          shellcheck
          shfmt
          sops
          talhelper
          talosctl
          tflint
          uv
          yamllint
          yq
        ];

        shellHook = ''
          export KUBECONFIG="$PWD/kubeconfig"
          export SOPS_AGE_KEY_FILE="$PWD/age.key"
          export TALOSCONFIG="$PWD/talos/clusterconfig/talosconfig"
        '';
      };
    });
  };
}
