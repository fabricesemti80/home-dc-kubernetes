# E — One combined gaming/server tower; reuse RTX 3080

Price snapshot: **2026-10-13**. GBP, displayed VAT-inclusive prices. These are example baskets, not orders or guarantees of future availability. Stock comes from retrieved UK supplier pages; some cached delivery dates were stale, so no delivery date is promised. Existing NAS, monitor, monitoring PCs and retained gaming hardware cost £0 in these budgets. Labour, paid OS licences, electricity and new independent backup storage are excluded. Delivery/accessory allowances include small cables and IEC-to-device leads, not quoted purchases. Contingency is 10% of product subtotal.

See [budget index](README.md), [product catalogue](products.md) and [architecture assessment](../hardware-replacement-options.md). Compatibility conditions below must be resolved before ordering.

## Example budget

| Product / UK link | Exact model / SKU | Supplier | Qty | Unit inc VAT | Line total | Retrieved availability |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [AMD Ryzen 9 9950X (16C/32T)](https://www.scan.co.uk/products/amd-ryzen-9-9950x-am5-zen-5-16-core-32-thread-43ghz-57ghz-turbo-64mb-cache-pcie-50-170w) | 100-100001277WOF / LN149410 | Scan | 1 | £499.99 | £499.99 | In stock |
| [MSI MAG B850M MORTAR WIFI](https://www.scan.co.uk/products/msi-mag-b850m-mortar-wifi-amd-b850-am5-ddr5-pcie-50-3x-m2-5g-wifi7-usb-32-aplusc-amd-expo-atx) | LN160846 | Scan | 1 | £169.99 | £169.99 | In stock |
| [Corsair Vengeance 128GB (2×64GB) DDR5-6000 CL40](https://www.scan.co.uk/products/128gb-2x64gb-corsair-ddr5-vengeance-black-pc5-48000-6000-non-ecc-unbuffered-cas-40-xmp-30-135v) | CMK128GX5M2D6000C40 / LN163479 | Scan | 1 | £2,522.48 | £2,522.48 | In stock |
| [Samsung 990 PRO 2TB NVMe](https://www.scan.co.uk/products/2tb-samsung-990-pro-m2-2280-pcie-40-x4-nvme-ssd-mlc-3d-v-nand-7450mb-s-read-6900mb-s-write-pc-ps5) | MZ-V9P2T0BW / LN130047 | Scan | 2 | £469.99 | £939.98 | In stock |
| [WD Black SN7100 1TB NVMe](https://www.scan.co.uk/products/1tb-wd-black-sn7100-m2-2280-pcie-40-x4-nvme-ssd-7250mb-s-read-6900mb-s-write-1000k-1400k-iops) | WDS100T4X0E-00CJA0 / LN154943 | Scan | 1 | £159.98 | £159.98 | In stock |
| [Noctua NH-U12S redux](https://www.scan.co.uk/products/noctua-nh-u12s-redux-cpu-cooler-intel-amd-120mm-fan-450-1700rpm-707cfm-airflow-251db-4-pin-pwm-grey) | NH-U12S-REDUX / LN123865 | Scan | 1 | £49.99 | £49.99 | In stock |
| [Fractal Meshify 2 Compact Black Solid (fans included)](https://www.scan.co.uk/products/fractal-meshify-2-compact-black-mid-tower-chassis-2x-140mm-1x-120mm-fans-usb-31-gen2-type-c-atx-matx) | FD-C-MES2C-01 / LN110396 | Scan | 1 | £79.99 | £79.99 | In stock |
| [Corsair RM850e 850W (UK)](https://www.scan.co.uk/products/850w-corsair-rm850e-fully-modular-cybenetics-gold-pcie-51-single-rail-708a-120mm-fan-atx-31-psu) | CP-9020296-UK / LN154144 | Scan | 1 | £89.99 | £89.99 | In stock |
| [TP-Link Omada SG3210X-M2 (8×2.5GbE + 2×SFP+)](https://ithardwaregroup.co.uk/tp-link-omada-8-port-2-5g-l2-managed-switch/) | SG3210X-M2 | IT Hardware Group | 1 | £216.84 | £216.84 | In stock |
| [APC BX1600MI 1600VA / 900W UPS (IEC outlets)](https://uk.rs-online.com/web/p/uninterruptible-power-supplies/2877237) | BX1600MI / RS 287-7237 | RS UK | 1 | £266.80 | £266.80 | 6 ready to ship; more stock also listed |

| Cost | Amount |
| --- | ---: |
| Product subtotal | **£4,996.03** |
| Delivery / small accessory allowance (estimate) | £75.00 |
| 10% contingency (estimate) | £499.60 |
| **Planning envelope** | **£5,570.63** |

## Result and fit

One **16-core/32-thread, 128GB** AM5 host with 2×2TB mirrored VM/application data and separate 1TB boot, reusing the RTX 3080 for a gaming VM. Existing NAS and monitoring remain outside the host.

This budget uses **2.5GbE onboard networking**, appropriate to a single-host/local-mirror design with a 2.5GbE NAS. It does not claim a separate 10GbE Ceph path. A 10G upgrade needs a checked PCIe layout, mechanical GPU clearance and extra NIC/cable cost.

## Compatibility and implementation

- Scan labels the board ATX in places; MSI identifies it as mATX and it fits the Meshify case.
- Check exact RTX 3080 length/thickness and power connectors. Meshify 2 Compact has finite clearance; do not extrapolate to an arbitrary future GPU.
- RM850e is selected for the RTX 3080-class build. Use the correct number of independent GPU power cables; never reuse modular PSU cables from another PSU model.
- NH-U12S redux is an example for the 9950X **with reduced power limits/Eco-mode**, not a promise of quiet unrestricted 170W operation. Validate sustained temperatures; change cooler/airflow and budget if full power is required.
- Require supplier/QVL confirmation for the exact 2×64GB kit; use supported JEDEC speeds and burn-in.
- Verify onboard Realtek 8126 support in the exact Proxmox kernel/Talos image before depending on it. A host NIC driver existing in Windows is insufficient.
- GPU uses PCI_E1; the board's secondary slot is electrically x4 and a large GPU may obscure it. Do not assume a second card will fit.
- Use local mirror + backups, not three Ceph VMs on this machine. GPU passthrough, reset behaviour and USB/input routing must be tested.

For the Dell monitor, use RTX DisplayPort/HDMI plus USB upstream for the hub; motherboard USB-C does not imply discrete-GPU video.

## Less expensive variants

| Change | Revised products | Revised envelope (£75 allowance + 10%) | Trade-off |
| --- | ---: | ---: | --- |
| 128GB retained; mirrored 1TB SN7100 data drives | £4,376.01 | £4,888.61 | About 1TB usable data mirror |
| Linked Kingston 64GB kit replaces 128GB kit | £3,273.54 | £3,675.89 | Much less VM/gaming headroom |

Keep 128GB if the app allocation, ZFS/hypervisor and gaming VM will run concurrently; the 64GB variant is a sizing experiment, not assumed adequate.

## Validation / rollback

Test game performance while media/background work runs, VM restart/GPU resets, memory stability and restore of a PVC/database. If combined maintenance is unacceptable, return to separate server/gaming roles. Keep the old desktop until passthrough and monitor access are validated.

## Next actions

- [ ] Recheck linked unit prices and required quantity at checkout.
- [ ] Resolve compatibility and stock qualifications above.
- [ ] Record any new quote in [price history](price-history.md).
- [ ] Verify backups/restores before retiring hardware.
