provider "unifi" {
  username       = var.unifi_username
  password       = var.unifi_password
  api_url        = var.unifi_api_url
  allow_insecure = var.unifi_allow_insecure
}

resource "unifi_dns_record" "kubernetes_internal_gateway" {
  name   = "kubernetes.${local.internal_domain}"
  type   = "A"
  record = local.kubernetes_internal_gateway_ip
}

resource "unifi_dns_record" "immich_internal" {
  name   = "photos.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "jellyfin_internal" {
  name   = "jellyfin.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "jellyseerr_internal" {
  name   = "requests.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "prowlarr_internal" {
  name   = "prowlarr.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "qbittorrent_internal" {
  name   = "qbittorrent.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "radarr_internal" {
  name   = "radarr.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "sabnzbd_internal" {
  name   = "sabnzbd.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "sonarr_internal" {
  name   = "sonarr.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "tdarr_internal" {
  name   = "tdarr.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "termix_internal" {
  name   = "termix.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}

resource "unifi_dns_record" "n8n_internal" {
  name   = "n8n.${local.internal_domain}"
  type   = "CNAME"
  record = unifi_dns_record.kubernetes_internal_gateway.name
}
