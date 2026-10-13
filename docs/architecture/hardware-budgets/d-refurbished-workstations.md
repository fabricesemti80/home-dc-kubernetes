# D — Two refurbished workstation towers

Price snapshot: **2026-10-13**. GBP, displayed VAT-inclusive prices. These are example baskets, not orders or guarantees of future availability. Stock comes from retrieved UK supplier pages; some cached delivery dates were stale, so no delivery date is promised. Existing NAS, monitor, monitoring PCs and retained gaming hardware cost £0 in these budgets. Labour, paid OS licences, electricity and new independent backup storage are excluded. Delivery/accessory allowances include small cables and IEC-to-device leads, not quoted purchases. Contingency is 10% of product subtotal.

See [budget index](README.md), [product catalogue](products.md) and [architecture assessment](../hardware-replacement-options.md). Compatibility conditions below must be resolved before ordering.

## Example budget

| Product / UK link | Exact model / SKU | Supplier | Qty | Unit inc VAT | Line total | Retrieved availability |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [Refurbished Lenovo P520, W-2155 10-core, 128GB DDR4, 2×1TB NVMe](https://www.ebay.co.uk/itm/126714071518) | eBay item 126714071518 | Bargain Hardware UK via eBay | 2 | £1,320.00 | £2,640.00 | UK listing active; exact quantity not exposed |
| [Intel X710-DA2 dual-port 10GbE SFP+ PCIe](https://www.scan.co.uk/products/2-port-intel-x710-da2-10gbe-ethernet-plus-optical-converged-network-adapter-2x-sfpplus-pcie-30-x8-oe) | X710DA2BLK / LN64475 | Scan | 2 | £109.99 | £219.98 | In stock |
| [TP-Link Omada SG3210X-M2 (8×2.5GbE + 2×SFP+)](https://ithardwaregroup.co.uk/tp-link-omada-8-port-2-5g-l2-managed-switch/) | SG3210X-M2 | IT Hardware Group | 1 | £216.84 | £216.84 | In stock |
| [MikroTik XS+DA0003 3m DAC (run at 10GbE)](https://linitx.com/product/mikrotik-3m-sfp-sfp%2B-sfp28-direct-attach-cable---xs%2Bda0003/16614) | XS+DA0003 / LinITX 16614 | LinITX | 2 | £33.35 | £66.70 | 13 in stock |
| [APC BX1600MI 1600VA / 900W UPS (IEC outlets)](https://uk.rs-online.com/web/p/uninterruptible-power-supplies/2877237) | BX1600MI / RS 287-7237 | RS UK | 1 | £266.80 | £266.80 | 6 ready to ship; more stock also listed |

| Cost | Amount |
| --- | ---: |
| Product subtotal | **£3,410.32** |
| Delivery / small accessory allowance (estimate) | £100.00 |
| 10% contingency (estimate) | £341.03 |
| **Planning envelope** | **£3,851.35** |

## Result and fit

Two Lenovo P520 towers, each with **Xeon W-2155 (10 cores/20 threads), 128GB DDR4 and 2×1TB NVMe** according to the exact UK seller listing. Treat each pair as a roughly 1TB usable software mirror after confirming drive identities/health. Combined: 20 physical cores and 256GB RAM. Existing RTX 3080 desktop remains separate.

The £1,320 unit price is the visible listing price, not the £168 bare chassis price from the seller's configurator. Do not substitute a different configuration without repricing.

## Stock qualification

The UK eBay listing is active with a price and advertised 3-year warranty, but the retrieved purchase widget did not expose available quantity. [Bargain Hardware's direct P520 configurator](https://www.bargainhardware.co.uk/lenovo-thinkstation-p520-workstation-configure-to-order) explicitly says in stock and supports this platform. **Confirm two units of the exact CPU/RAM/SSD specification and VAT treatment with the supplier before relying on the total.** This is a UK-sourceable example with an exact-quantity stock check outstanding, not a claim that two reserved units exist.

## Connections / compatibility

Each X710 attaches to one of the SG3210X-M2's two SFP+ ports with a DAC. NAS attaches to 2.5GbE copper. Both SFP+ ports are then occupied; a future third 10G host needs another switch. No CRS309 is needed for this two-host example.

Confirm DDR4 is ECC RDIMM, not just a generic 128GB description; request DIMM layout, PSU model, full-height NIC bracket, NVMe arrangement, included GPU for setup, UK mains lead and SMART/endurance data. P520 has proprietary PSU/case elements: it is expandable, but not as interchangeable as a standard AM5 tower.

## Availability limitations

- Put an independent Proxmox qdevice on retained hardware if running a 2-host Proxmox cluster. A qdevice is not a data replica.
- Do not implement two-host Ceph as though it gives symmetric host-failure resilience.
- Local mirror/NAS data and manual restore are the baseline here. Three etcd members split 2+1 cannot tolerate loss of either host.
- UPS size is conditional on measured load: old workstation idle and peak power may be higher than new AM5 nodes.
- Advertised warranty and refurbished condition are seller claims, not measured health.

## Validation / rollback

Verify burn-in, SSD health, ECC reporting, temperatures and fan noise during the return window. Confirm app-aware restore and power shutdown. Keep existing machines until the used hardware passes testing.

## Next actions

- [ ] Recheck linked unit prices and required quantity at checkout.
- [ ] Resolve compatibility and stock qualifications above.
- [ ] Record any new quote in [price history](price-history.md).
- [ ] Verify backups/restores before retiring hardware.
