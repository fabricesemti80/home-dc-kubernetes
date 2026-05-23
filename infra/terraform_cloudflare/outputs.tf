output "kubernetes_tunnel_id" {
  value     = local.kubernetes_tunnel_id
  sensitive = true
}

output "kubernetes_account_tag" {
  value     = local.kubernetes_account_tag
  sensitive = true
}

output "trinity_tunnel_id" {
  value = cloudflare_zero_trust_tunnel_cloudflared.trinity[0].id
}
