# UK hardware example budgets

Price snapshot: **2026-10-13**. Companion to [hardware replacement options](../hardware-replacement-options.md).

These are five separately documented UK product baskets. Prices are displayed VAT-inclusive amounts from supplier pages, not claimed market minima. Availability labels distinguish in-stock from orderable/quantity-unverified. No out-of-stock item is in the core baskets. D's exact two-unit stock remains to be confirmed; A's adapter is UK-orderable with host-driver checks outstanding.

## Comparison

| Option | Product subtotal | Delivery / accessories allowance | 10% contingency | Planning envelope |
| --- | ---: | ---: | ---: | ---: |
| [A — Network-first refresh](a-network-first.md) | £573.49 | £50.00 | £57.35 | **£680.84** |
| [B — One expandable server; retain gaming desktop](b-single-server.md) | £4,926.37 | £75.00 | £492.64 | **£5,494.01** |
| [C — Three expandable servers with Ceph](c-three-servers.md) | £7,088.23 | £100.00 | £708.82 | **£7,897.05** |
| [D — Two refurbished workstation towers](d-refurbished-workstations.md) | £3,410.32 | £100.00 | £341.03 | **£3,851.35** |
| [E — One combined gaming/server tower; reuse RTX 3080](e-combined-gaming-server.md) | £4,996.03 | £75.00 | £499.60 | **£5,570.63** |

## What the priced examples change

The earlier architecture ranges were preliminary allowances. These examples supersede them **for the linked baskets only**. B/E with 128GB and 2TB usable mirrors are around £5.5k including contingency; their 1TB usable variants fit under £5k. C's fully new 64GB-per-host Ceph example is around £7.9k, not the earlier £3.3–£4.8k allowance. D remains within the budget, conditional on the exact two-unit supplier quote.

The selected 128GB kit alone is £2,522.48 and the selected 64GB kit £799.99. Those are verified listing prices, **not sensible target buy prices or proof that every UK supplier charges the same**. These examples make the memory cost visible rather than assuming outdated prices. Reprice matched RAM kits or prebuilt systems before selecting a layout. B can start at 64GB for £3,599.27, but current app VM reservations already total 48GB; measure headroom first.

## Tracking and sourcing

- [Product catalogue](products.md): reusable model numbers, UK links, prices and stock.
- [Price history](price-history.md): append observations without overwriting the baseline.
- [Gaming and AI extras](gaming-ai-extras.md): alternatives excluded from the five core totals.
- [Machine-readable snapshot](price-snapshot.json): quantities, exact prices and totals for later comparison.

Each file links exact product pages, not generic search results. No prices refresh automatically and no scheduled monitoring has been configured. Scan product pages offer price/availability notifications that you can enable yourself; no email subscriptions were created.

All calculations use decimal GBP and line quantity × unit price. The contingency is 10% of products, not delivery. Delivery allowances are estimates covering multiple suppliers and small leads. Products reused from current equipment are £0, with no speculative resale credits. Independent backup storage is excluded because requirements/free existing backup capacity have not been established; NAS free space alone is not an independent backup.

## Rejected stock examples

CRS310 at NetXL/LinITX was out of stock; Scan B650M GAMING PLUS and 2TB SN7100 were end-of-life; 128GB Vengeance 6400 kits showed unavailable. They were replaced rather than included as purchasable. The Scan APC BX1600MI listing was preorder, so the in-stock RS UK listing is used despite its higher price.

## Next actions

- [ ] Choose an architecture and desired usable SSD capacity.
- [ ] Reprice exact RAM and get a supplier compatibility confirmation.
- [ ] Confirm two units for D before relying on its total.
- [ ] Check all quantities, VAT, delivery and returns before purchase.
