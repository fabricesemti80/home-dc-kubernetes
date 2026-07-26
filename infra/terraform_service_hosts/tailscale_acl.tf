resource "tailscale_acl" "this" {
  overwrite_existing_content = true
  acl = jsonencode({
    autoApprovers = {
      services = {
        "tag:container" = ["tag:server"]
      }
    }

    grants = [
      {
        dst = ["*"]
        ip  = ["*"]
        src = ["*"]
      }
    ]

    ssh = [
      {
        action = "check"
        dst    = ["autogroup:self"]
        src    = ["autogroup:member"]
        users  = ["autogroup:nonroot", "root"]
      },
      {
        action = "accept"
        dst    = ["tag:server"]
        src    = ["autogroup:admin"]
        users  = ["autogroup:nonroot", "root"]
      }
    ]

    tagOwners = {
      "tag:container"    = ["tag:server"]
      "tag:k8s"          = ["tag:k8s-operator"]
      "tag:k8s-operator" = ["autogroup:admin"]
      "tag:server"       = ["autogroup:admin"]
    }
  })
}
