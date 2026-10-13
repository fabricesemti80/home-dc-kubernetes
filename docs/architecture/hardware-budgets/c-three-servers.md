# C — Three expandable servers with Ceph

Price snapshot: **2026-10-13**. GBP, displayed VAT-inclusive prices. These are example baskets, not orders or guarantees of future availability. Stock comes from retrieved UK supplier pages; some cached delivery dates were stale, so no delivery date is promised. Existing NAS, monitor, monitoring PCs and retained gaming hardware cost £0 in these budgets. Labour, paid OS licences, electricity and new independent backup storage are excluded. Delivery/accessory allowances include small cables and IEC-to-device leads, not quoted purchases. Contingency is 10% of product subtotal.

See [budget index](README.md), [product catalogue](products.md) and [architecture assessment](../hardware-replacement-options.md). Compatibility conditions below must be resolved before ordering.

## Example budget

| Product / UK link | Exact model / SKU | Supplier | Qty | Unit inc VAT | Line total | Retrieved availability |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [AMD Ryzen 5 7600 (6C/12T)](https://www.scan.co.uk/products/amd-ryzen-5-7600-am5-zen-4-6-core-12-thread-38ghz-51ghz-turbo-32mb-cache-pcie-50-65w-cpu) | 100-100001015BOX / LN131632 | Scan | 3 | £169.99 | £509.97 | In stock |
| [MSI MAG B850M MORTAR WIFI](https://www.scan.co.uk/products/msi-mag-b850m-mortar-wifi-amd-b850-am5-ddr5-pcie-50-3x-m2-5g-wifi7-usb-32-aplusc-amd-expo-atx) | LN160846 | Scan | 3 | £169.99 | £509.97 | In stock |
| [Kingston FURY Beast 64GB (2×32GB) DDR5-5600](https://www.overclockers.co.uk/kingston-fury-beast-64gb-2x32gb-ddr5-pc5-44800c40-5600mhz-dual-channel-kit-kf556c40bbk2-64/MY-29W-KS.html) | KF556C40BBK2-64 / MY-29W-KS | Overclockers UK | 3 | £799.99 | £2,399.97 | In stock |
| [WD Black SN7100 1TB NVMe](https://www.scan.co.uk/products/1tb-wd-black-sn7100-m2-2280-pcie-40-x4-nvme-ssd-7250mb-s-read-6900mb-s-write-1000k-1400k-iops) | WDS100T4X0E-00CJA0 / LN154943 | Scan | 3 | £159.98 | £479.94 | In stock |
| [Samsung 990 PRO 2TB NVMe](https://www.scan.co.uk/products/2tb-samsung-990-pro-m2-2280-pcie-40-x4-nvme-ssd-mlc-3d-v-nand-7450mb-s-read-6900mb-s-write-pc-ps5) | MZ-V9P2T0BW / LN130047 | Scan | 3 | £469.99 | £1,409.97 | In stock |
| [Noctua NH-U12S redux](https://www.scan.co.uk/products/noctua-nh-u12s-redux-cpu-cooler-intel-amd-120mm-fan-450-1700rpm-707cfm-airflow-251db-4-pin-pwm-grey) | NH-U12S-REDUX / LN123865 | Scan | 3 | £49.99 | £149.97 | In stock |
| [Fractal Pop Mini Silent Black Solid (fans included)](https://www.scan.co.uk/products/fractal-design-pop-mini-silent-black-solid) | FD-C-POS1M-01 / LN119150 | Scan | 3 | £79.99 | £239.97 | In stock |
| [Corsair RM650e 650W (UK)](https://www.scan.co.uk/products/650w-corsair-rme-series-rm650e-fully-modular-cybenetics-gold-pcie-51-single-rail-542a-120mm-fan-atx) | CP-9020302-UK / LN162482 | Scan | 3 | £79.99 | £239.97 | In stock |
| [Intel X710-DA2 dual-port 10GbE SFP+ PCIe](https://www.scan.co.uk/products/2-port-intel-x710-da2-10gbe-ethernet-plus-optical-converged-network-adapter-2x-sfpplus-pcie-30-x8-oe) | X710DA2BLK / LN64475 | Scan | 3 | £109.99 | £329.97 | In stock |
| [TP-Link Omada SG3210X-M2 (8×2.5GbE + 2×SFP+)](https://ithardwaregroup.co.uk/tp-link-omada-8-port-2-5g-l2-managed-switch/) | SG3210X-M2 | IT Hardware Group | 1 | £216.84 | £216.84 | In stock |
| [MikroTik CRS309-1G-8S+IN (8×SFP+)](https://www.netxl.com/network-switches/mikrotik-crs309-1g-8s-in-sfp-cloud-router-switch/) | CRS309-1G-8S+IN | NetXL | 1 | £201.49 | £201.49 | 1 in stock |
| [MikroTik XS+DA0003 3m DAC (run at 10GbE)](https://linitx.com/product/mikrotik-3m-sfp-sfp%2B-sfp28-direct-attach-cable---xs%2Bda0003/16614) | XS+DA0003 / LinITX 16614 | LinITX | 4 | £33.35 | £133.40 | 13 in stock |
| [APC BX1600MI 1600VA / 900W UPS (IEC outlets)](https://uk.rs-online.com/web/p/uninterruptible-power-supplies/2877237) | BX1600MI / RS 287-7237 | RS UK | 1 | £266.80 | £266.80 | 6 ready to ship; more stock also listed |

| Cost | Amount |
| --- | ---: |
| Product subtotal | **£7,088.23** |
| Delivery / small accessory allowance (estimate) | £100.00 |
| 10% contingency (estimate) | £708.82 |
| **Planning envelope** | **£7,897.05** |

## Result and fit

Three hosts, each **6 cores/12 threads, 64GB RAM, one 1TB boot/VM disk and one dedicated 2TB Ceph OSD**. Aggregate: 18 physical cores, 192GB RAM, 6TB raw OSD capacity. At replication size 3, nominal data capacity is around 2TB before metadata and safety headroom. Boot/VM disks are single devices: no mirrored boot is claimed.

The current example exceeds £5,000 substantially. It corrects the earlier architecture allowance rather than hiding RAM/SSD costs.

## Connections and storage

Three X710 NICs connect over one DAC each to CRS309. A fourth DAC connects CRS309 to SG3210X-M2; NAS/monitor access uses 2.5GbE copper. The small switches sit on a shelf, without installing a full-size rack. Storage traffic must remain on the fast switched path.

Use one control-plane VM per physical host. Ceph placement is by host; current application data must be backed up and migrated. VM disks can move onto the new Ceph cluster after it is healthy. A 3-host cluster retaining size 3 writes may operate degraded after losing a host, but cannot recreate three host-separated replicas until that host returns or another is added.

## Reliability limits

- Consumer 990 PRO drives lack enterprise power-loss protection. This is the purchasable consumer-SSD example, **not the preferred PLP Ceph BOM**. Compare actual fsync latency/endurance against enterprise SSD quotes before buying; no unverified enterprise price is included.
- A single boot disk failure requires rebuilding/restoring that host; Ceph replication covers OSD data, not its local boot disk.
- X710 occupies the primary x16 slot; CPU integrated graphics handles setup. Check cable/firmware.
- Exact RAM QVL, BIOS and boot testing are required. Run JEDEC rather than assume 5600 XMP is stable.
- Budget includes one switch of each model; switch failure is still a shared failure point. A dual-port NIC alone does not fix this.
- Measure worst-case wall power; UPS runtime/stepped-wave compatibility and shutdown must be tested.

## Cost-reduction direction

Reducing each OSD from the linked 2TB 990 PRO to a linked 1TB SN7100 saves £930.03 in products; revised envelope is **£6,874.02**, with only around 1TB nominal replicated storage before headroom. This still does not fit £5,000.

Reusing suitable existing OSDs or RAM could reduce spend, but no savings are counted until exact reusable hardware is identified. Do not buy three expensive new DDR5 kits merely to preserve a three-host layout; the refurb option deserves serious consideration.

## Validation / rollback

Test host loss, memory/CPU headroom on the other two, Ceph recovery under real load and restore of application data. Keep the old Ceph cluster until cutover and data verification are complete.

## Next actions

- [ ] Recheck linked unit prices and required quantity at checkout.
- [ ] Resolve compatibility and stock qualifications above.
- [ ] Record any new quote in [price history](price-history.md).
- [ ] Verify backups/restores before retiring hardware.
