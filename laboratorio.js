/* MENIGAR · Laboratorio de portada, 22 Oct 2026. Review tool only, loaded by laboratorio.html,
 * a copy of the homepage kept apart from the official one. It brings the hero compositions of
 * opciones-hero.html into that page and swaps the design (A–D) and the background (four
 * palettes) in place, with the rest of the page working underneath. The choice stays in the
 * address and is remembered in this browser for the next visit. */
(() => {
  'use strict';
  const designs = ['a', 'b', 'c', 'd'];
  const palettes = ['laguna', 'profundo', 'turquesa', 'cian', 'cobalto', 'violeta', 'noche'];
  const designNames = { a: 'Encendido', b: 'Cabina', c: 'Bento', d: 'Escaparate' };
  const paletteNames = { laguna: 'Laguna', profundo: 'Cian profundo', turquesa: 'Turquesa', cobalto: 'Cobalto', cian: 'Cian original', violeta: 'Violeta', noche: 'Noche' };
  const storageKey = 'menigar-laboratorio';
  const original = document.querySelector('main > .p-hero');
  if (!original || document.querySelector('.lab-panel')) return;

  const pick = (value, list, fallback) => list.includes(value) ? value : fallback;
  const saved = (() => { try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (error) { return {}; } })();
  const params = new URLSearchParams(location.search);
  const state = {
    design: pick(params.get('diseno'), designs, pick(saved.design, designs, 'a')),
    palette: pick(params.get('fondo'), palettes, pick(saved.palette, palettes, 'laguna'))
  };
  const heroes = { a: original };
  let current = original;

  document.body.classList.add('o-page', 'lab-on');
  document.body.insertAdjacentHTML('beforeend', '<aside class="lab-panel" aria-label="Laboratorio de la portada"><div class="lab-row">'
    + '<p class="lab-brand">Laboratorio</p>'
    + '<fieldset class="lab-designs"><legend class="p-visually-hidden">Diseño del hero</legend>'
    + designs.map(key => '<label class="lab-design"><input type="radio" name="lab-diseno" value="' + key + '"><b>' + key.toUpperCase() + '</b><span>' + designNames[key] + '</span></label>').join('')
    + '</fieldset><fieldset class="o-swatches"><legend class="p-visually-hidden">Fondo del hero</legend>'
    + palettes.map(key => '<label class="o-swatch"><input type="radio" name="paleta" id="paleta-' + key + '" value="' + key + '"><span class="o-dot o-dot--' + key + '" aria-hidden="true"></span><span class="lab-swatch-name">' + paletteNames[key] + '</span></label>').join('')
    + '</fieldset><div class="lab-actions">'
    + '<button class="lab-button" type="button" data-lab-hide>Ocultar</button>'
    + '<a class="lab-button" href="/">Salir</a></div></div>'
    + '<p class="lab-error" role="alert" hidden></p><p class="p-visually-hidden" aria-live="polite" data-lab-status></p></aside>'
    + '<button class="lab-reopen" type="button" data-lab-show hidden>Laboratorio</button>');

  const panel = document.querySelector('.lab-panel');
  const reopen = document.querySelector('[data-lab-show]');
  const status = panel.querySelector('[data-lab-status]');
  const error = panel.querySelector('.lab-error');

  const sync = () => {
    panel.querySelectorAll('input[name="lab-diseno"]').forEach(input => { input.checked = input.value === state.design; });
    panel.querySelectorAll('input[name="paleta"]').forEach(input => { input.checked = input.value === state.palette; });
    history.replaceState(null, '', location.pathname + '?diseno=' + state.design + '&fondo=' + state.palette + location.hash);
    try { localStorage.setItem(storageKey, JSON.stringify(state)); } catch (error) { /* Private mode: the address still keeps the choice. */ }
  };
  const describe = () => 'Diseño ' + state.design.toUpperCase() + ', ' + designNames[state.design] + ', con fondo ' + paletteNames[state.palette].toLowerCase() + '.';
  const chooseDesign = (key, announce = true) => {
    if (!designs.includes(key)) return;
    state.design = key;
    const hero = heroes[key];
    if (hero && hero !== current) { current.replaceWith(hero); current = hero; }
    sync();
    if (announce) status.textContent = hero ? describe() : 'Cargando el diseño ' + key.toUpperCase() + '…';
  };
  const choosePalette = (key, announce = true) => {
    if (!palettes.includes(key)) return;
    state.palette = key;
    sync();
    if (announce) status.textContent = describe();
  };
  const setHidden = hidden => {
    panel.hidden = hidden;
    reopen.hidden = !hidden;
    document.body.classList.toggle('lab-hidden', hidden);
    (hidden ? reopen : panel.querySelector('input:checked'))?.focus();
  };

  panel.addEventListener('change', event => {
    if (event.target.name === 'lab-diseno') chooseDesign(event.target.value);
    if (event.target.name === 'paleta') choosePalette(event.target.value);
  });
  panel.querySelector('[data-lab-hide]').addEventListener('click', () => setHidden(true));
  reopen.addEventListener('click', () => setHidden(false));
  // Keyboard shortcuts for quick comparisons: A–D design, 1–4 background, H hides the panel.
  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const field = event.target.closest?.('input, textarea, select, [contenteditable="true"]');
    if (field && field.type !== 'radio') return;
    const key = event.key.toLowerCase();
    if (designs.includes(key)) { event.preventDefault(); chooseDesign(key); }
    else if (/^[1-7]$/.test(key)) { event.preventDefault(); choosePalette(palettes[Number(key) - 1]); }
    else if (key === 'h') { event.preventDefault(); setHidden(!panel.hidden); }
  });

  // The compositions come from the review page, so the lab and that page stay in step.
  const adopt = source => {
    const hero = document.createElement('section');
    hero.className = source.className;
    hero.setAttribute('aria-labelledby', 'p-hero-title');
    hero.append(...document.importNode(source, true).childNodes);
    const title = hero.querySelector('.p-display');
    if (title) {
      const heading = document.createElement('h1');
      heading.className = title.className;
      heading.id = 'p-hero-title';
      heading.append(...title.childNodes);
      title.replaceWith(heading);
    }
    // The step-by-step search left the homepage for servicios.html (owner, 22 Oct 2026).
    hero.querySelectorAll('a[href="/index.html#buscar"]').forEach(link => link.setAttribute('href', '/servicios.html#catalogo'));
    hero.querySelectorAll('a[href^="/index.html#"]').forEach(link => link.setAttribute('href', link.getAttribute('href').slice('/index.html'.length)));
    return hero;
  };

  sync();
  fetch('/opciones-hero.html', { credentials: 'same-origin' })
    .then(response => { if (!response.ok) throw new Error('HTTP ' + response.status); return response.text(); })
    .then(html => {
      const page = new DOMParser().parseFromString(html, 'text/html');
      designs.forEach(key => {
        const source = page.querySelector('#opcion-' + key + ' .p-hero');
        if (key !== 'a' && source) heroes[key] = adopt(source);
      });
      chooseDesign(state.design, false);
    })
    .catch(() => {
      error.hidden = false;
      error.textContent = 'No se han podido cargar los diseños B, C y D. Recarga la página para volver a intentarlo.';
    });
})();
