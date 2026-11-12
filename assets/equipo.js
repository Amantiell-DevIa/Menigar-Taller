'use strict';
// Zona del equipo: imprimir, copiar datos, buscar con «/» y avisar de cambios sin guardar.
// Todo funciona también sin este archivo; solo añade comodidad.
(() => {
  const live = document.querySelector('[data-live]');
  const say = message => { if (live) { live.textContent = ''; setTimeout(() => { live.textContent = message; }, 30); } };

  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => {
    button.closest('details')?.removeAttribute('open');
    window.print();
  }));

  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const what = (button.getAttribute('aria-label') || 'Copiar').replace(/^Copiar /, '');
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.classList.add('is-done');
      say('Copiado ' + what + '.');
      setTimeout(() => button.classList.remove('is-done'), 1600);
    } catch (_) {
      say('No se ha podido copiar ' + what + '.');
    }
  }));

  // «/» puts the cursor in the search box, as in most mail and project tools.
  const search = document.querySelector('[data-search]');
  if (search) {
    document.addEventListener('keydown', event => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
      if (event.key === '/' && !typing && !event.metaKey && !event.ctrlKey) { event.preventDefault(); search.focus(); search.select(); }
    });
  }

  // Close the «Más» menu when clicking elsewhere or pressing Escape.
  document.querySelectorAll('details.eq-menu').forEach(menu => {
    document.addEventListener('click', event => { if (!menu.contains(event.target)) menu.removeAttribute('open'); });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { menu.removeAttribute('open'); menu.querySelector('summary')?.focus(); } });
  });

  // A piece form with changes asks before leaving the page.
  let dirty = null;
  document.querySelectorAll('form[data-unsaved]').forEach(form => {
    const mark = () => { dirty = form; form.classList.add('is-dirty'); };
    form.addEventListener('input', mark);
    form.addEventListener('change', mark);
    form.addEventListener('submit', () => { dirty = null; });
  });
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
})();
