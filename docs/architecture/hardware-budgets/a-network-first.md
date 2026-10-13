# A — Network-first refresh

Price snapshot: **2026-10-13**. GBP, displayed VAT-inclusive prices. These are example baskets, not orders or guarantees of future availability. Stock comes from retrieved UK supplier pages; some cached delivery dates were stale, so no delivery date is promised. Existing NAS, monitor, monitoring PCs and retained gaming hardware cost £0 in these budgets. Labour, paid OS licences, electricity and new independent backup storage are excluded. Delivery/accessory allowances include small cables and IEC-to-device leads, not quoted purchases. Contingency is 10% of product subtotal.

See [budget index](README.md), [product catalogue](products.md) and [architecture assessment](../hardware-replacement-options.md). Compatibility conditions below must be resolved before ordering.

## Example budget

| Product / UK link | Exact model / SKU | Supplier | Qty | Unit inc VAT | Line total | Retrieved availability |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [TP-Link Omada SG3210X-M2 (8×2.5GbE + 2×SFP+)](https://ithardwaregroup.co.uk/tp-link-omada-8-port-2-5g-l2-managed-switch/) | SG3210X-M2 | IT Hardware Group | 1 | £216.84 | £216.84 | In stock |
| [Belkin USB-C to 2.5Gb Ethernet](https://www.apple.com/uk/shop/product/hrg32zm/a/belkin-usb-c-to-25gb-ethernet-adapter) | Apple HRG32ZM/A / EAN 745883889006 | Apple UK | 3 | £29.95 | £89.85 | Orderable; delivery date not exposed |
| [APC BX1600MI 1600VA / 900W UPS (IEC outlets)](https://uk.rs-online.com/web/p/uninterruptible-power-supplies/2877237) | BX1600MI / RS 287-7237 | RS UK | 1 | £266.80 | £266.80 | 6 ready to ship; more stock also listed |

| Cost | Amount |
| --- | ---: |
| Product subtotal | **£573.49** |
| Delivery / small accessory allowance (estimate) | £50.00 |
| 10% contingency (estimate) | £57.35 |
| **Planning envelope** | **£680.84** |

## Result and fit

Retains all existing compute and adds managed 2.5GbE access plus power protection. This is **a 2.5GbE refresh**, not a promise of 10GbE Ceph on UN1265 machines that lack standard PCIe expansion.

Three USB adapters are a conditional allowance. Buy/test one first; omit any where the built-in NIC already supports 2.5GbE. Apple lists this adapter for its devices; exact chipset and Proxmox/Talos driver behaviour are not validated. If USB networking is unsuitable, keep management on the original NIC and defer the host upgrade rather than force an unreliable storage path.

## Connections

NAS and three hosts connect to 2.5GbE copper ports; remaining ports serve management/uplink devices as needed. Existing copper patch cables are reused subject to testing. Heavy storage transfers must not hairpin through a 1GbE routed uplink.

## Validation / rollback

- Check host native link speeds first: three adapters may be unnecessary.
- Validate USB resets, sustained bidirectional traffic, reboots and driver support on one host.
- SG3210X-M2 is substituted for the out-of-stock CRS310; verify hardware revision, cooling/noise and VLAN configuration.
- Measure wall power/runtime before putting all hosts/NAS/switch on the UPS. Test stepped-wave PSU compatibility and coordinated shutdown.
- Retain old switch/NIC configuration for rollback.

## Alternatives

Without USB adapters, subtract £89.85 from products (and £8.99 from rounded contingency). No new independent backup disk is included.

## Next actions

- [ ] Recheck linked unit prices and required quantity at checkout.
- [ ] Resolve compatibility and stock qualifications above.
- [ ] Record any new quote in [price history](price-history.md).
- [ ] Verify backups/restores before retiring hardware.
