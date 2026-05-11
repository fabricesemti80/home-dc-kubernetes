/* ============================================================
   Homepage — custom.js (OPTIONAL companion to custom.css)
   Drop into your homepage config dir as `custom.js`
   Docs: https://gethomepage.dev/configs/custom-css-js/

   What it does:
   • Tracks the cursor over service cards and sets CSS vars
     --mx / --my so the radial accent glow follows the pointer.
   • Re-binds on DOM mutations so it works as homepage swaps
     in widget data via SWR.
   ============================================================ */
(function () {
  const SEL = [
    '.service-card',
    '.service-card > a',
    '.service-card > div',
    '.service-card .service-container',
    'li.bookmark > a',
  ].join(',');

  function bind(card) {
    if (card.__hpBound) return;
    card.__hpBound = true;
    card.addEventListener('pointermove', (e) => {
      const r = card.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width)  * 100;
      const y = ((e.clientY - r.top)  / r.height) * 100;
      card.style.setProperty('--mx', x + '%');
      card.style.setProperty('--my', y + '%');
    });
    card.addEventListener('pointerleave', () => {
      card.style.setProperty('--mx', '50%');
      card.style.setProperty('--my', '0%');
    });
  }

  function scan() {
    document.querySelectorAll(SEL).forEach(bind);
  }

  // initial + re-scan on DOM updates
  const run = () => {
    scan();
    const mo = new MutationObserver(() => scan());
    mo.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }
})();
