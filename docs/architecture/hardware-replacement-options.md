# Hardware replacement options

Date: 2026-10-13
Status: options assessment; no hardware purchase or infrastructure change approved.
Scope: app-cluster compute, storage networking, gaming and optional local AI.
This revisits the earlier single high-end PC idea; it does not supersede deployed architecture.

## Context and constraints

Keep the existing NAS: approximately 11 TB usable RAID storage, about 4 TB free, approximately one year old. Keep Viglen/Dell OptiPlex equipment for a low-budget, physically separate monitoring/infra stack. Target £4,000–£5,000 maximum; spending less is desirable. An £8,000–£10,000 AI-focused budget is conditional on demonstrated usefulness, not GPU marketing.

Kubernetes remains the preferred application platform. A single Docker host is a fallback, not the default recommendation. Avoid full-size 19-inch servers because of space and noise. Prefer replaceable RAM, drives, NICs, PSU and cooling over another fleet of tightly integrated mini PCs.

Current user-supplied allocation:

| Cluster | Nodes | CPUs reported | RAM |
| --- | --- | ---: | ---: |
| App | k8s-ctrl-01/02/03 | 10 each; 30 total | 16 GB each; 48 GB total |
| Infra | infra-cp-01 | 6 | 16 GB |
| Infra | infra-wk-01 | 4 | 8 GB |
| Total | 5 | 40 | 72 GB |

The repository identifies app nodes as Talos VMs on Proxmox and infra nodes as physical Talos. Therefore **40 reported CPUs is not 40 physical cores required in a new host**. If infra hardware remains, the starting app allocation is 48 GB, not 72 GB. Measure demand before selecting CPUs.

Existing storage is CephFS from Ceph on three Proxmox hosts, plus NAS NFS for media. See [storage overview](../storage/overview.md) and [media NFS](../storage/media-nfs.md). The distinction matters: removing Proxmox hosts also removes Ceph storage failure domains.

Earlier context identifies three Minisforum UN1265 machines, an RTX 3080 desktop, a QNAP TS-462 and Dell U4025QW monitor. Treat NAS and monitor model identity as historical context to check against actual devices before ordering model-specific upgrades. This note does not invent missing desktop CPU, PSU or drive details.

## Dated UK example budgets

See the [separate UK budget files](hardware-budgets/README.md) for each option, exact product links, VAT-inclusive unit prices, quantities, stock qualifications and price history. The 2026-10-13 linked examples supersede the preliminary cost allowances below for those specific baskets: A £680.84; B £5,494.01; C £7,897.05; D £3,851.35; E £5,570.63, including stated delivery/accessory allowances and 10% contingency. B/E with 1TB usable mirrors instead of 2TB fit under £5,000. D's exact two-unit availability remains a supplier check. Current linked DDR5 prices materially change the cost comparison; the earlier ranges should not be used as purchase quotes.

## Recommendation

**Separate gaming from always-on servers. Choose between one expandable server and three modest expandable servers according to the required outage tolerance.**

The most economical starting point is to retain the RTX 3080 gaming PC and improve storage networking first. The gaming PC can be off when unused. Its present CPU, health and performance must be assessed before spending money replacing it.

- For acceptable maintenance outages: one quiet 12–16-core AM5 tower, 128 GB RAM, mirrored NVMe and 10GbE, retaining the separate monitoring stack and NAS.
- For host maintenance without taking down the application cluster: three quiet micro-ATX towers, initially 64 GB RAM each, 6–8 modern cores each and 10GbE. Place one app control-plane VM on each physical host.
- Buy a handheld only if portable play is valuable. For strategy gaming mainly at a desk, an existing desktop GPU is generally a better fit.
- Evaluate local AI separately before allocating the doubled budget.

### Architecture comparison and cost allowances

These are **planning allowances in GBP intended to include VAT**, not verified baskets or supplier quotes. Upper ends include room for quality parts; used-hardware prices and exact configurations vary. Existing NAS, monitor, retained monitoring hardware and existing gaming PC/GPU are counted as sunk cost. No resale income assumed.

| Option | Compute allowance | Network allowance | UPS / backup / contingency | Total new spend | Main trade-off |
| --- | ---: | ---: | ---: | ---: | --- |
| A. Keep current compute; diagnose storage, upgrade network where supported | £0–£400 | £300–£800 | £250–£500 | £550–£1,700 | Cheapest; does not fix limited chassis expansion |
| B. One AM5 server; retain gaming desktop | £1,500–£2,200 | £350–£650 | £300–£500 | £2,150–£3,350 | Best simple replacement; app outage on host failure/reboot |
| C. Three expandable AM5 micro-ATX servers; retain gaming desktop | £2,400–£3,300 | £500–£850 | £350–£600 | £3,250–£4,750 | Best physical failure separation within budget |
| D. Two refurbished workstation towers; retain gaming desktop | £1,200–£2,000 | £400–£700 | £400–£650 | £2,000–£3,350 | Cheap ECC/PCIe; older hardware and two-host quorum complications |
| E. One combined AM5 gaming/server tower using RTX 3080 | £1,600–£2,400 | £350–£650 | £300–£500 | £2,250–£3,550 | Fewest boxes; gaming and service maintenance coupled |

Replacing gaming with a handheld adds about £900–£1,200 as an allowance for device/cable/accessories; the verified ASUS UK page displayed £859 for the ROG Xbox Ally X when researched. Adding that to C can exceed £5,000. Do not add a handheld simply because it is smaller.

## Option details

### A. Network-first refresh

Establish whether the current problems come from 1GbE saturation, Ceph disk latency, recovery, or workload configuration. Upgrade only endpoints that can use faster links. Do not assume an external USB NIC is equivalent to a supported PCIe server NIC: validate drivers, resets, sustained throughput and Talos support.

This is a useful first phase even when replacement is inevitable. If compute has adequate headroom, it avoids buying CPUs to address a storage problem.

### B. Dedicated quiet server plus existing gaming PC

Suggested class:
- Ryzen 9 7900/9900X/9950X-class, 12–16 cores, selected for actual pricing and load rather than flagship status.
- 128 GB RAM in a motherboard-supported configuration at conservative supported speed. Prefer two DIMMs where capacity/QVL permits; four large DDR5 DIMMs may require lower clocks.
- Two 2 TB TLC NVMe drives mirrored for VM/application storage: approximately 2 TB usable before overhead, not 4 TB.
- A separate boot device where practical; adequate PCIe slots/lanes for NIC and any future transcoding GPU.
- Standard micro-ATX/ATX case, quality PSU, large low-speed fans and air cooling.
- 10GbE PCIe NIC; validate exact chipset, driver and firmware with Proxmox/Talos.

Use Proxmox with Talos VMs if VM flexibility is useful; direct Talos is also possible if the machine will serve only Kubernetes. One control-plane VM is honest about single-host availability. Three control-plane VMs on the same machine may support experimentation but do not protect against physical failure.

**Do not recreate three Ceph storage nodes as VMs on this one host and describe it as resilient.** For this option, prefer local mirrored storage and explicit backups. Kubernetes local PVs require node affinity and a restore/relocation plan. For shared file PVCs, evaluate NAS NFS; databases need application-supported storage and tested fsync/locking/latency. This is a proposed exception to the repo's existing CephFS default, requiring a separate migration design.

### C. Three modest expandable servers

Target per host: 6–8 modern cores, 64 GB RAM, replaceable PSU/fans, at least two NVMe slots plus a usable PCIe NIC slot, and 10GbE. This gives 192 GB installed RAM across three hosts and room for Ceph/Proxmox overhead and workload growth.

Two practical storage variants:
1. Keep Ceph with dedicated SSD OSD devices separate from boot/VM drives, host-based replica placement and 10GbE. Add OSD drive costs if the selected host allowance does not cover them. Check SSD endurance and sustained synchronous write behaviour; power-loss-protected enterprise SSDs may justify paying more.
2. Remove distributed block storage; use local mirrored VM disks plus NAS file storage and application backups. This is simpler but local disks do not automatically follow a VM or pod onto another host.

Three hosts permit quorum placement; they do not automatically ensure service HA. With one host down, the other two must have enough CPU/RAM, access to data, and suitable scheduling. Audit actual reservations rather than relying on aggregate capacity. Ceph itself consumes memory and CPU.

Use micro-ATX rather than tiny mini-ITX unless space is decisive: expansion and cooling are more valuable here than the smallest possible enclosure.

### D. Refurbished workstation towers

Examples to investigate: Lenovo ThinkStation P520, Dell Precision 5820 or HP Z4-class towers. These are candidate families, not purchase-ready configurations.

Look for 128 GB ECC, documented CPU model, usable PCIe slots, suitable PSU and replaceable storage. RAM type differs between platforms; ECC RDIMM cannot simply be moved into ordinary AM5 UDIMM boards.

Benefits: inexpensive high memory capacity and PCIe expansion. Risks: older single-core performance, idle consumption, aging fans/PSUs, proprietary cabling, restricted firmware support and variable seller warranty. A workstation badge is not proof that a particular used machine is healthier than a new consumer build.

Two Proxmox hosts need an independent qdevice for cluster quorum; a qdevice is not a third compute/storage replica. Three etcd members distributed 2+1 across only two hosts cannot survive losing either host. Two-host Ceph is not the preferred replacement. For strong failure symmetry buy three hosts, or accept documented outages.

### E. Single combined gaming and server tower

Technically viable using GPU passthrough to a Windows/Linux gaming VM. Budget RAM for the app VMs, hypervisor/ZFS, gaming VM and headroom; do not simply allocate every byte of 128 GB.

Validate IOMMU grouping, GPU reset/restart behaviour, USB controller passthrough, game compatibility and local display access. A GPU passed through to gaming cannot simultaneously be used by host/Kubernetes CUDA workloads without a separate sharing solution. The host needs usable independent graphics/management if the discrete GPU is assigned away.

This is attractive for reducing boxes but weaker for maintenance independence. Gaming failures alone need not crash the host, but host firmware updates and failures affect both roles.

## Reliability and expansion

AM5 does **not inherently mean no ECC**. Some CPU/motherboard combinations support ECC UDIMM. ASRock Rack B650D4U is an example with ECC/non-ECC UDIMM and IPMI; verify its CPU support list, memory QVL and actual ECC reporting for the selected combination. Server boards cost more and may offer older platform I/O or fewer convenient desktop ports.

Priorities:
1. Supported RAM configuration, sensible power limits and no speculative overclock.
2. Good PSU/cooling, SSD health/endurance and firmware compatibility.
3. Tested backups, spare parts availability and documented rebuilds.
4. ECC/IPMI when their cost fits the chosen layout.

Protect the NAS, storage switch and always-on servers with appropriately sized UPS capacity. A small server UPS allowance is not a promise that it will support a 5090 workstation at full load. RAID/mirroring protects against some drive failures; it is not a backup. An independent backup destination or off-site copy remains necessary.

## Gaming and Dell monitor docking

The referenced Dell U4025QW is 5120×2160 at up to 120 Hz with a Thunderbolt upstream connection, up to 140 W power delivery and 2.5GbE in its hub. The video/charging upstream port must be used; its separate USB-C data-only upstream port cannot carry display output.

The ASUS ROG Xbox Ally X has USB4 with DisplayPort and USB PD; it is a plausible one-cable monitor connection for video, peripherals and charging. Verify the exact unit/cable, display mode, USB devices, Ethernet, wake behaviour and negotiated charging before purchase. Connecting a display is not evidence that demanding games run well at its native resolution.

For Total War-class gaming:
- Prefer keyboard/mouse and a desktop GPU if most play is docked.
- Start handheld testing at 1920×1080 or a suitable lower ultrawide resolution, not native 5K2K.
- Test a large battle and late-campaign simulation, not just a title screen.
- Do not promise performance for Dawn of War 4 without released requirements and appropriate benchmarks.

A compact gaming desktop reusing the RTX 3080 is another alternative if the current PC needs replacement. Most desktop USB-C ports do not route the discrete GPU's video: plan DisplayPort/HDMI to the monitor plus USB upstream for peripherals, or verify a specific Thunderbolt/DP-input arrangement if a single cable is mandatory.

## Storage networking

Theoretical line-rate payload ceilings before protocol overhead:

| Link | MB/s decimal |
| --- | ---: |
| 1GbE | 125 |
| 2.5GbE | 312.5 |
| 10GbE | 1,250 |

Ceph carries client I/O, replication and recovery; faster links can reduce contention and recovery time, but cannot fix slow synchronous SSD writes, unhealthy OSDs or insufficient memory. NFS media reads and Ceph application configuration writes are different paths and should be measured separately.

### Two switch layouts

| Layout | Candidate | Fit and limits |
| --- | --- | --- |
| One server + NAS / desktop | MikroTik CRS310-8G+2S+IN | Eight 2.5GbE ports, two 10GbE SFP+ ports; compact, but has a fan. Only two 10G endpoints without another switch. |
| Three 10GbE server hosts | MikroTik CRS309-1G-8S+IN plus suitable 2.5GbE access switch | Eight SFP+ ports, passive chassis cooling. Provides host expansion; additional switch/uplink costs needed for copper 2.5GbE NAS/monitor. |

These are specification-verified examples, not a supplier shortlist. Confirm managed VLAN features, noise in the room, hardware-offloaded switching configuration and NIC/module interoperability.

Prefer SFP+ DAC between nearby servers and switch where compatible. 10GBASE-T modules can be hot and power-hungry; check vendor thermal limits. A VLAN isolates traffic but does not create more bandwidth on a shared saturated link. LACP generally does not double a single TCP flow.

If the NAS is indeed TS-462, its built-in 2.5GbE should be used before buying a 10GbE upgrade. Its PCIe expansion has compatibility and lane limitations; do not assume arbitrary NIC support or 10GbE file throughput from its HDD array. Upgrading only the switch leaves 1GbE endpoint NICs at 1GbE.

Keep heavy storage traffic on the fast switched path where possible. If it crosses VLANs, account for the router's actual forwarding capacity and firewall policy; avoid introducing a 1GbE routed bottleneck. Keep BMC/IPMI access restricted to management networks. Start at MTU 1500; jumbo frames are optional after end-to-end validation.

## Local AI: decision gate before doubling spend

RTX 5090 has 32 GB GDDR7; NVIDIA specifies 575 W graphics power and 1,000 W minimum system PSU for its reference configuration. Exact board size/power varies. It is capable local inference hardware, **not a demonstrated replacement for premium hosted reasoning models**.

Weight-only arithmetic: a 32-billion-parameter dense model at 4 bits is about 16 GB; a 70-billion-parameter model is about 35 GB. Quantization metadata, runtime buffers and KV cache add memory. Thus a typical 70B 4-bit model does not fit fully into 32 GB VRAM. CPU offload can make execution possible with a speed cost. MoE models require evaluation of total stored weights as well as active parameters.

Model quality, context length, tool reliability and task completion matter more than nominal FLOPS. Use the existing M4 Max MacBook and RTX 3080 to establish a baseline. Mac Studio high-memory configurations or DGX Spark (128 GB coherent unified memory) are alternative AI appliances for larger models; neither should be assumed to replace expandable x86 homelab servers or Windows strategy gaming. Capacity and speed are different questions.

Do not assign pricing, release dates or performance to a future RTX 6090. No purchase recommendation depends on it.

Acceptance test before an £8k–£10k build:
- Use 20–30 representative Ansible, Terraform, PowerShell, Kubernetes and documentation tasks with held-out expected outcomes.
- Record correctness, retries, human correction time, context length, latency and power consumption.
- Compare against the specific paid service and workflow it would replace, with equivalent tools and context.
- Benchmark the intended model/quantization on the exact prospective hardware through a demo or borrowed system.
- Retain a hybrid hosted/local option if complex tasks still require hosted models.

Financial examples, not current subscription quotes: £4,000 additional capital breaks even after 40 months at £100/month genuinely avoided, or 20 months at £200/month, before energy, depreciation and residual hosted spend. At an assumed £0.25/kWh, every extra 50 W running continuously costs about £109.50/year. Use actual tariff and measured wall power.

## Validation and migration

Before sizing, capture one to two weeks of CPU peaks, memory working set, disk latency, Ceph utilisation/recovery and NIC throughput, including downloads, scans, backups and transcoding.

Read-only starting checks (use the intended kubeconfig and Proxmox host):
```bash
kubectl top nodes
kubectl top pods -A
kubectl get pvc -A
kubectl get pv
kubectl get storageclass
ceph status
ceph health detail
ceph osd perf
ceph df
ceph osd pool ls detail
```
Metrics Server is required for kubectl top; use existing Prometheus history for sustained/peak evidence. Use iperf3 on test endpoints to isolate network performance and a disposable test dataset for disk tests, not active Ceph block devices.

Migration outline:
1. Inventory PVCs, databases, NAS shares and VM dependencies; verify app-aware backup and restore.
2. Build new networking alongside current setup; retain existing VLAN configuration and a management access route.
3. Burn in RAM, CPU, disks and network; test power recovery and cooling/noise.
4. Deploy target Proxmox/Talos layout and storage. Preserve the independent infra/monitoring stack.
5. Restore a representative workload, validate data and backup, then migrate incrementally.
6. For databases, stop/quiesce writes and use supported backup/restore. Do not blindly copy live database directories.
7. Keep old hosts and original data until successful restores and a stable observation period.

Rollback: retain old storage and manifests; switch back only after reconciling writes made after cutover. Never mount one writable database volume concurrently from old and new stacks. Restore the latest verified backup when data formats or storage layout prevent safe reversal. Ceph snapshots and VM backups do not automatically prove separately mounted CephFS application data is backed up.

## Open questions

- Confirm current desktop CPU/RAM/PSU, GPU model/VRAM, drive health and which parts can be reused.
- Confirm NAS model, NIC/link speed, disk arrangement and measured NFS performance.
- Confirm switch models, VLAN routing path and existing host NIC expansion options.
- Define acceptable app downtime: planned reboot outages, hours to restore, or surviving one physical host failure?
- Measure Jellyfin transcode demand and select a dedicated supported accelerator if needed; the small Ryzen display GPU is not assumed equivalent to Intel Quick Sync.
- Check monitor identity and whether portable gaming is valuable enough to justify a handheld.

## Next actions

- [ ] Measure current bottlenecks before buying compute.
- [ ] Choose B for simplicity/cost or C for physical host availability; retain A as the first phase.
- [ ] Make a price-verified compatible parts list within £5,000 including network and UPS.
- [ ] Test storage backups/restores and agree PVC migration architecture.
- [ ] Validate docking and actual strategy-game performance if buying a handheld.
- [ ] Run the AI acceptance test before allocating extra GPU budget.

## Sources

Specifications checked 2026-10-13; cost allowances are our estimates rather than quotations.

- [AMD Ryzen 9000 CPU specifications](https://www.amd.com/en/partner/articles/ryzen-9000-series-processors.html)
- [ASRock Rack B650D4U](https://www.asrockrack.com/general/productdetail.asp?Model=B650D4U)
- [Lenovo ThinkStation P520 platform specifications](https://psref.lenovo.com/syspool/Sys/PDF/ThinkStation/ThinkStation_P520/ThinkStation_P520_Spec.html)
- [Dell U4025QW datasheet](https://www.delltechnologies.com/asset/en-gb/products/electronics-and-accessories/technical-support/dell-ultrasharp-40-curved-thunderbolt-hub-monitor-u4025qw-datasheet.pdf)
- [ASUS ROG Xbox Ally X UK specifications and displayed price](https://rog.asus.com/uk/gaming-handhelds/rog-ally/rog-xbox-ally-x-2025/spec/)
- [QNAP TS-462](https://www.qnap.com/en-us/product/ts-462)
- [MikroTik CRS310](https://mikrotik.com/product/crs310_8g_2s_in)
- [MikroTik CRS309](https://mikrotik.com/product/crs309_1g_8s_in)
- [Ceph hardware recommendations](https://docs.ceph.com/en/latest/start/hardware-recommendations/) (development-version guidance; check installed-version docs during implementation)
- [NVIDIA RTX 5090 specifications](https://www.nvidia.com/en-gb/geforce/graphics-cards/50-series/rtx-5090/)
- [NVIDIA DGX Spark specifications](https://www.nvidia.com/en-gb/support/dgx-spark/)
- [Apple Mac Studio specifications](https://www.apple.com/uk/mac-studio/specs/)
