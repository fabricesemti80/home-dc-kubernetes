output "kubernetes_internal_dns_records" {
  value = {
    kubernetes = {
      name   = unifi_dns_record.kubernetes_internal_gateway.name
      type   = unifi_dns_record.kubernetes_internal_gateway.type
      record = unifi_dns_record.kubernetes_internal_gateway.record
    }
    photos = {
      name   = unifi_dns_record.immich_internal.name
      type   = unifi_dns_record.immich_internal.type
      record = unifi_dns_record.immich_internal.record
    }
    jellyfin = {
      name   = unifi_dns_record.jellyfin_internal.name
      type   = unifi_dns_record.jellyfin_internal.type
      record = unifi_dns_record.jellyfin_internal.record
    }
    requests = {
      name   = unifi_dns_record.jellyseerr_internal.name
      type   = unifi_dns_record.jellyseerr_internal.type
      record = unifi_dns_record.jellyseerr_internal.record
    }
    prowlarr = {
      name   = unifi_dns_record.prowlarr_internal.name
      type   = unifi_dns_record.prowlarr_internal.type
      record = unifi_dns_record.prowlarr_internal.record
    }
    qbittorrent = {
      name   = unifi_dns_record.qbittorrent_internal.name
      type   = unifi_dns_record.qbittorrent_internal.type
      record = unifi_dns_record.qbittorrent_internal.record
    }
    radarr = {
      name   = unifi_dns_record.radarr_internal.name
      type   = unifi_dns_record.radarr_internal.type
      record = unifi_dns_record.radarr_internal.record
    }
    sabnzbd = {
      name   = unifi_dns_record.sabnzbd_internal.name
      type   = unifi_dns_record.sabnzbd_internal.type
      record = unifi_dns_record.sabnzbd_internal.record
    }
    sonarr = {
      name   = unifi_dns_record.sonarr_internal.name
      type   = unifi_dns_record.sonarr_internal.type
      record = unifi_dns_record.sonarr_internal.record
    }
    tdarr = {
      name   = unifi_dns_record.tdarr_internal.name
      type   = unifi_dns_record.tdarr_internal.type
      record = unifi_dns_record.tdarr_internal.record
    }
    termix = {
      name   = unifi_dns_record.termix_internal.name
      type   = unifi_dns_record.termix_internal.type
      record = unifi_dns_record.termix_internal.record
    }
    planka = {
      name   = unifi_dns_record.planka_internal.name
      type   = unifi_dns_record.planka_internal.type
      record = unifi_dns_record.planka_internal.record
    }
  }
}
