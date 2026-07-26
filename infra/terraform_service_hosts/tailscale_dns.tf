resource "tailscale_dns_split_nameservers" "krapulax_home" {
  domain = "krapulax.home"
  nameservers = [
    var.tailscale_technitium_primary_dns_server,
    var.tailscale_technitium_secondary_dns_server,
  ]
}

resource "tailscale_dns_preferences" "this" {
  magic_dns = true
}

resource "tailscale_dns_search_paths" "this" {
  search_paths = [var.tailscale_tailnet]
}
