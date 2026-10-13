# B — One expandable server; retain gaming desktop

Price snapshot: **2026-10-13**. GBP, displayed VAT-inclusive prices. These are example baskets, not orders or guarantees of future availability. Stock comes from retrieved UK supplier pages; some cached delivery dates were stale, so no delivery date is promised. Existing NAS, monitor, monitoring PCs and retained gaming hardware cost £0 in these budgets. Labour, paid OS licences, electricity and new independent backup storage are excluded. Delivery/accessory allowances include small cables and IEC-to-device leads, not quoted purchases. Contingency is 10% of product subtotal.

See [budget index](README.md), [product catalogue](products.md) and [architecture assessment](../hardware-replacement-options.md). Compatibility conditions below must be resolved before ordering.

## Example budget

| Product / UK link | Exact model / SKU | Supplier | Qty | Unit inc VAT | Line total | Retrieved availability |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [AMD Ryzen 9 7900 (12C/24T)](https://www.scan.co.uk/products/amd-ryzen-9-7900-am5-zen-4-12-core-24-thread-37ghz-54ghz-turbo-64mb-cache-pcie-50-65w-cpu) | 100-100000590BOX / LN131630 | Scan | 1 | £296.99 | £296.99 | In stock |
| [MSI MAG B850M MORTAR WIFI](https://www.scan.co.uk/products/msi-mag-b850m-mortar-wifi-amd-b850-am5-ddr5-pcie-50-3x-m2-5g-wifi7-usb-32-aplusc-amd-expo-atx) | LN160846 | Scan | 1 | £169.99 | £169.99 | In stock |
| [Corsair Vengeance 128GB (2×64GB) DDR5-6000 CL40](https://www.scan.co.uk/products/128gb-2x64gb-corsair-ddr5-vengeance-black-pc5-48000-6000-non-ecc-unbuffered-cas-40-xmp-30-135v) | CMK128GX5M2D6000C40 / LN163479 | Scan | 1 | £2,522.48 | £2,522.48 | In stock |
| [Samsung 990 PRO 2TB NVMe](https://www.scan.co.uk/products/2tb-samsung-990-pro-m2-2280-pcie-40-x4-nvme-ssd-mlc-3d-v-nand-7450mb-s-read-6900mb-s-write-pc-ps5) | MZ-V9P2T0BW / LN130047 | Scan | 2 | £469.99 | £939.98 | In stock |
| [WD Black SN7100 1TB NVMe](https://www.scan.co.uk/products/1tb-wd-black-sn7100-m2-2280-pcie-40-x4-nvme-ssd-7250mb-s-read-6900mb-s-write-1000k-1400k-iops) | WDS100T4X0E-00CJA0 / LN154943 | Scan | 1 | £159.98 | £159.98 | In stock |
| [Noctua NH-U12S redux](https://www.scan.co.uk/products/noctua-nh-u12s-redux-cpu-cooler-intel-amd-120mm-fan-450-1700rpm-707cfm-airflow-251db-4-pin-pwm-grey) | NH-U12S-REDUX / LN123865 | Scan | 1 | £49.99 | £49.99 | In stock |
| [Fractal Pop Mini Silent Black Solid (fans included)](https://www.scan.co.uk/products/fractal-design-pop-mini-silent-black-solid) | FD-C-POS1M-01 / LN119150 | Scan | 1 | £79.99 | £79.99 | In stock |
| [Corsair RM650e 650W (UK)](https://www.scan.co.uk/products/650w-corsair-rme-series-rm650e-fully-modular-cybenetics-gold-pcie-51-single-rail-542a-120mm-fan-atx) | CP-9020302-UK / LN162482 | Scan | 1 | £79.99 | £79.99 | In stock |
| [Intel X710-DA2 dual-port 10GbE SFP+ PCIe](https://www.scan.co.uk/products/2-port-intel-x710-da2-10gbe-ethernet-plus-optical-converged-network-adapter-2x-sfpplus-pcie-30-x8-oe) | X710DA2BLK / LN64475 | Scan | 1 | £109.99 | £109.99 | In stock |
| [TP-Link Omada SG3210X-M2 (8×2.5GbE + 2×SFP+)](https://ithardwaregroup.co.uk/tp-link-omada-8-port-2-5g-l2-managed-switch/) | SG3210X-M2 | IT Hardware Group | 1 | £216.84 | £216.84 | In stock |
| [MikroTik XS+DA0003 3m DAC (run at 10GbE)](https://linitx.com/product/mikrotik-3m-sfp-sfp%2B-sfp28-direct-attach-cable---xs%2Bda0003/16614) | XS+DA0003 / LinITX 16614 | LinITX | 1 | £33.35 | £33.35 | 13 in stock |
| [APC BX1600MI 1600VA / 900W UPS (IEC outlets)](https://uk.rs-online.com/web/p/uninterruptible-power-supplies/2877237) | BX1600MI / RS 287-7237 | RS UK | 1 | £266.80 | £266.80 | 6 ready to ship; more stock also listed |

| Cost | Amount |
| --- | ---: |
| Product subtotal | **£4,926.37** |
| Delivery / small accessory allowance (estimate) | £75.00 |
| 10% contingency (estimate) | £492.64 |
| **Planning envelope** | **£5,494.01** |

## Result and fit

One 12-core/24-thread server with **128GB RAM, a 2×2TB ZFS mirror (about 2TB usable)** and separate 1TB boot disk. The 1TB boot disk is deliberately larger than needed because the linked example is available; a smaller compatible boot SSD can reduce cost. The existing gaming desktop stays separate.

## Compatibility checks

- MSI's [official specifications](https://www.msi.com/Motherboard/MAG-B850M-MORTAR-WIFI/Specification) identify this as micro-ATX despite Scan's URL/title saying ATX. It has three M.2 slots and supports Ryzen 7000/9000.
- Put mirrored data drives in M.2_1/_2 and boot in M.2_3 (PCIe 4.0 x2). This avoids buying an unbudgeted NVMe adapter.
- X710 uses the primary x16 slot with integrated CPU graphics for local setup. Verify firmware/DAC interoperability and Linux driver. One port is used; the second port is spare, not redundant switching.
- Board nominal capacity is not a QVL certification for this exact 2×64GB kit/CPU. Require supplier confirmation, current BIOS and memory burn-in; start at JEDEC, not XMP.
- Non-ECC RAM and consumer SSDs without enterprise PLP are explicit compromises. UPS and mirrors do not replace backups.
- Pop Mini Silent includes fans; NH-U12S redux fits the case's nominal cooler allowance. Check current AM5 mounting hardware.
- This single host should not run pretend-HA Ceph. Local mirror/NAS PVC migration must follow the architecture note.

## Less expensive variants

The linked 128GB kit at £2,522.48 is poor value; **this basket is a comparison, not a recommendation to buy that RAM at this price**.

| Change | Revised product subtotal | Revised envelope (same £75 allowance + 10%) | Trade-off |
| --- | ---: | ---: | --- |
| Use one linked Kingston 64GB kit instead | £3,203.88 | £3,599.27 | 64GB total; 48GB current app allocation leaves limited hypervisor/growth headroom |
| Keep 128GB; use 2× linked 1TB SN7100 for data mirror | £4,306.35 | £4,811.99 | About 1TB usable data space; separate 1TB boot still included |

Do not combine two unrelated dual-channel kits and assume equivalence to one certified 128GB configuration. A cheaper supported matched kit or prebuilt quote is preferable to paying the selected 128GB price.

## Validation / rollback

Burn in memory and disks, verify actual ECC status as non-ECC, test restore of one database/PVC and test UPS shutdown. Keep old hosts and data until the new storage architecture is proven.

## Next actions

- [ ] Recheck linked unit prices and required quantity at checkout.
- [ ] Resolve compatibility and stock qualifications above.
- [ ] Record any new quote in [price history](price-history.md).
- [ ] Verify backups/restores before retiring hardware.
