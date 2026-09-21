# Pi-hole DNS Migration Plan

- [ ] Review and merge the Pi-hole cutover PR.
- [ ] Confirm `10.0.40.53` answers both local and public names.
- [ ] Update the router only if it is not already using `10.0.40.53`.
- [ ] Remove retained Technitium PVCs only after an agreed recovery window.
