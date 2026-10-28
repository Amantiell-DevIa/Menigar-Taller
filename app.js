/* MENIGAR — Navigation, guided discovery and catalogue search.
 * Search finds documented information; it never determines a diagnosis or a price.
 * No third-party tracking, fake form submission or destructive source transformation.
 */
(() => {
  'use strict';
  // The services page loads the catalogue only when someone searches (useCatalogue below).
  let all = Array.isArray(window.MENIGAR_CATALOG) ? window.MENIGAR_CATALOG : [];
  let families = Array.isArray(window.MENIGAR_FAMILIES) ? window.MENIGAR_FAMILIES : [];
  const collator = new Intl.Collator('es', { numeric: true, sensitivity: 'base' });
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const compact = value => normalize(value).replace(/\s/g, '');
  const escape = value => String(value || '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const unique = values => [...new Set(values.filter(Boolean))].sort(collator.compare);
  let familyByKey = new Map(families.map(family => [family.key, family]));
  let recordsById = new Map(all.map(record => [record.uid, record]));
  const genericBrand = value => /^(otras?|otros?|varios?|multimarca|general|todas? las marcas|sin marca)$/i.test(String(value || '').trim());
  let brands = unique(all.map(record => record.brand).filter(value => !genericBrand(value)));
  const findBrand = value => brands.find(brand => normalize(brand) === normalize(value)) || '';
  const validFamily = value => familyByKey.has(value) ? value : '';
  const safeLocal = value => /^\/reparaciones\/[a-z0-9_-]+\/$/i.test(value || '') ? value : '/servicios.html';
  const icon = name => {
    const paths = {
      cuadro:'<path d="M3 17a9 9 0 1 1 18 0M5 17h14M12 12l4-4M6 9l1 1M12 5v2M18 9l-1 1"/>',
      abs:'<circle cx="12" cy="12" r="7"/><path d="M3 8c-2 2-2 6 0 8M21 8c2 2 2 6 0 8M10 9v6M14 9v6M10 12h4"/>',
      display:'<rect x="3" y="5" width="18" height="13" rx="2"/><path d="M7 9h4M7 13h9M7 21h10"/>',
      multimedia:'<rect x="3" y="4" width="18" height="15" rx="2"/><path d="M8 8h8v5H8zM8 16h8M11 22h2"/>',
      cambio:'<circle cx="7" cy="6" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="17" cy="18" r="2"/><path d="M7 8v8h10M17 8v8M12 6v10"/>',
      palanca:'<rect x="9" y="3" width="6" height="6" rx="2"/><path d="M12 9v9M8 18h8l3 3H5l3-3Z"/>',
      bluetooth:'<path d="m8 7 9 10-5 4V3l5 4L8 17M4 10c-1 1-1 3 0 4M21 8c2 2 2 6 0 8"/>',
      ecu:'<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
      clima:'<path d="M12 3v18M4 7l16 10M4 17 20 7M9 5l3 3 3-3M9 19l3-3 3 3M5 10l4-1-1-4M16 19l-1-4 4-1M5 14l4 1-1 4M16 5l-1 4 4 1"/>',
      bsi:'<rect x="5" y="4" width="14" height="16" rx="2"/><path d="m13 7-4 6h4l-2 4 5-7h-4l1-3Z"/>',
      inmo:'<circle cx="8" cy="9" r="4"/><path d="m11 12 8 8M16 17l3-3M14 15l2-2"/>'
    };
    return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (paths[name] || paths.ecu) + '</svg>';
  };
  const modelGroupsFor = record => (record.modelGroups || []).filter(group => group.vehicleModel !== false);
  // Editorial pilot, reviewed against sourceSections/modelGroups on 17-10-2026.
  // These relations organise documented sections. They do NOT assert that a part,
  // symptom, reference or generation is compatible with another generation.
  // Names and original anchors must both still exist or the relation is ignored.
  const MODEL_FAMILIES = Object.freeze([
    { brand: 'Mazda', model: '3', records: {
      'main-2942': [
        { model: '3 BK', anchor: 'detalle-6' },
        { model: '3 BM', anchor: 'detalle-17' }
      ],
      'main-712': [
        { model: '3 BK-BL', anchor: 'detalle-27' },
        { model: '3 BM', anchor: 'detalle-29' },
        { model: '3 BP', anchor: 'detalle-31' }
      ]
    }, source: 'modelGroups and sourceSections of main-2942 and main-712', reviewed: '2026-10-17' }
  ]);
  const modelFamilyFor = (record, model) => MODEL_FAMILIES.find(family => normalize(record.brand) === normalize(family.brand) && normalize(model) === normalize(family.model) && family.records[record.uid]);
  const familyGroupsFor = (record, model) => {
    const family = modelFamilyFor(record, model);
    if (!family) return [];
    return family.records[record.uid].map(reviewed => modelGroupsFor(record).find(group => normalize(group.model) === normalize(reviewed.model) && group.anchor === reviewed.anchor)).filter(Boolean);
  };
  const documentedModels = record => {
    const labels = new Map();
    [record.model, ...(record.coveredModels || []), ...modelGroupsFor(record).flatMap(group => [group.model, ...(group.modelAliases || [])])].filter(Boolean).forEach(model => {
      if (!labels.has(normalize(model))) labels.set(normalize(model), model);
    });
    return [...labels.values()];
  };
  const modelsFor = brand => {
    const labels = new Map();
    const records = all.filter(record => !brand || normalize(record.brand) === normalize(brand));
    // Keep the combined heading as evidence and as an existing URL value, while
    // letting a person choose each explicitly named vehicle individually.
    const combinedHeadings = new Set(records.flatMap(record => modelGroupsFor(record).filter(group => new Set((group.modelAliases || []).map(normalize)).size > 1).map(group => normalize(group.model))));
    records.forEach(record => {
      documentedModels(record).filter(model => !combinedHeadings.has(normalize(model))).forEach(model => {
        if (!labels.has(normalize(model))) labels.set(normalize(model), model);
      });
    });
    return [...labels.values()].sort(collator.compare);
  };
  const literalPhrase = (text, phrase) => (' ' + normalize(text) + ' ').includes(' ' + normalize(phrase) + ' ');
  const titleModelCache = new Map();
  const titleModelsFor = record => {
    if (!titleModelCache.has(record.uid)) titleModelCache.set(record.uid, modelsFor(record.brand).filter(model => literalPhrase(record.title, model)));
    return titleModelCache.get(record.uid);
  };
  const vehicleMatch = (record, brand, model) => {
    if (brand && normalize(record.brand) !== normalize(brand)) return 'none';
    if (!model) return 'unfiltered';
    if (familyGroupsFor(record, model).length) return 'model-family';
    const known = documentedModels(record);
    if (known.some(value => normalize(value) === normalize(model))) return 'documented';
    if (record.model) return 'none';
    // Some legacy records lack model metadata although their title names a car.
    // Literal title evidence can exclude another model; it never certifies a fit.
    const titleModels = titleModelsFor(record);
    if (titleModels.length && !titleModels.some(value => normalize(value) === normalize(model))) return 'none';
    // A general page can help a person review variants, without confirming their car.
    if (record.isAggregator && modelGroupsFor(record).length) return 'brand-only';
    if (known.length) return 'none';
    return 'brand-only';
  };
  const withVehicle = (record, brand, model) => ['unfiltered', 'documented', 'model-family'].includes(vehicleMatch(record, brand, model));
  const modelGroupFor = (record, model) => model ? modelGroupsFor(record).find(group => [group.model, ...(group.modelAliases || [])].some(value => normalize(value) === normalize(model))) : null;
  const modelAnchor = group => {
    const anchor = group?.anchor || (group?.model ? 'modelo-' + normalize(group.model).replace(/ /g, '-') : '');
    return /^[a-z0-9][a-z0-9_-]*$/i.test(anchor) ? '#' + anchor : '';
  };
  const selectableSymptoms = (record, group) => {
    const candidates = group ? (group.symptoms || []).concat(...(group.blocks || []).map(block => block.symptoms || [])) : (record.symptoms || []);
    return [...new Set(candidates.filter(value => {
      const text = normalize(value);
      if (!text || text === normalize(record.title) || /:\s*$/.test(value)) return false;
      if (/^(reparacion|reparaciones|reparamos|servicio|servicios|especialistas|somos capaces|en menigar|menigar|ponemos a tu alcance|contamos con|nuestro equipo|los codigos de error|los fallos mas frecuentes|las averias mas frecuentes)\b/.test(text)) return false;
      if (/\b(equipo de profesionales|profesionales y expertos|ponemos a tu alcance|consultanos|solicita un presupuesto|ofrecemos|anos de experiencia|capaces de reparar|reparaciones frecuentes)\b/.test(text)) return false;
      return /\b(fallos?|fallas?|error(?:es)?|averias?|averiad[oa]s?|defectuos[oa]s?|intermitentes?|apagad[oa]s?|parpade[ao]s?|parpadea|vibracion|vibra|borros[oa]s?|ilegibles?|rayas?|lineas?|pixel(?:es)?|burbujas?|presion|bloquead[oa]s?|congelad[oa]s?|ruidos?|sin comunicacion|sin iluminacion|en blanco|pantalla negra)\b/.test(text) || /\bno\b.{0,35}\b(funciona|enciende|arranca|responde|comunica|apaga|muestra|hay|frenan|frena|acumula|reduce|detecta|lee|se ve|se escucha)\b/.test(text);
    }))];
  };
  const options = (select, entries, placeholder, selected = '') => {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ''));
    entries.forEach(entry => {
      const value = typeof entry === 'string' ? entry : entry.value;
      const label = typeof entry === 'string' ? entry : entry.label;
      select.add(new Option(label, value, false, value === selected));
    });
    if (![...select.options].some(option => option.value === selected)) select.value = '';
  };
  const familyOptions = records => {
    const keys = new Set(records.map(record => record.componentKey));
    return families.filter(family => keys.has(family.key)).map(family => ({ value: family.key, label: family.name }));
  };
  const familiesForBrand = brand => familyOptions(findBrand(brand) ? all.filter(record => normalize(record.brand) === normalize(brand)) : all);
  const newSearchParams = state => {
    const params = new URLSearchParams();
    if (state.q) params.set('q', state.q);
    if (state.brand) params.set('marca', state.brand);
    if (state.model) params.set('modelo', state.model);
    if (state.component) params.set('pieza', state.component);
    if (state.page > 1) params.set('pagina', String(state.page));
    return params;
  };
  const copyQueryContext = (params, state, uid, ranking) => {
    if (!state.q) return;
    // Keep the visitor's words even when they are not a complete identifier.
    params.set('consulta', state.q);
    // Only a complete match in this particular record can populate a typed field.
    // The value remains the visitor's declaration, not a technical confirmation.
    if (ranking?.record?.uid !== uid) return;
    if (ranking.matchKind === 'reference-exact') params.set('referencia', state.q);
    if (ranking.matchKind === 'dtc-exact') params.set('codigo', state.q);
  };
  const consultUrl = (state = {}, uid = '', symptom = '', ranking = null) => {
    const params = new URLSearchParams({ tipo: 'consulta' });
    if (uid) params.set('pieza', uid);
    if (state.brand) params.set('marca', state.brand);
    if (state.model) params.set('modelo', state.model);
    if (state.component) params.set('familia', state.component);
    copyQueryContext(params, state, uid, ranking);
    if (symptom) params.set('sintoma', symptom);
    return '/solicitud.html?' + params.toString();
  };

  function setupNavigation() {
    const toggle = document.querySelector('.menu-toggle');
    const nav = document.getElementById('site-nav');
    if (toggle && nav) {
      const toggleLabel = toggle.querySelector('span') || toggle;
      const close = returnFocus => {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
        toggleLabel.textContent = 'Menú';
        if (returnFocus) toggle.focus();
      };
      toggle.addEventListener('click', () => {
        const opening = toggle.getAttribute('aria-expanded') !== 'true';
        toggle.setAttribute('aria-expanded', String(opening));
        toggleLabel.textContent = opening ? 'Cerrar' : 'Menú';
        nav.classList.toggle('is-open', opening);
      });
      nav.addEventListener('click', event => { if (event.target.closest('a')) close(false); });
      document.addEventListener('keydown', event => { if (event.key === 'Escape' && nav.classList.contains('is-open')) close(true); });
      document.addEventListener('click', event => { if (nav.classList.contains('is-open') && !event.target.closest('.site-header')) close(false); });
      window.addEventListener('resize', () => { if (window.innerWidth > 860) close(false); });
    }
    document.querySelectorAll('[data-current-year]').forEach(element => { element.textContent = String(new Date().getFullYear()); });
    if (['localhost', '127.0.0.1', '::1'].includes(location.hostname) && !document.querySelector('.local-preview-note')) {
      const note = document.createElement('div');
      note.className = 'local-preview-note';
      note.textContent = 'Versión de revisión · No publicada';
      document.querySelector('.site-header')?.after(note);
    }
  }

  function setupFamilies() {
    document.querySelectorAll('[data-family-grid]').forEach(grid => {
      // The home page ships its complete family cards in HTML, avoiding a layout
      // shift and keeping the links available before scripts run.
      if (grid.querySelector?.('.family-featured')) return;
      const featuredKeys = ['cuadro', 'abs', 'display', 'multimedia'];
      const media = window.MENIGAR_FAMILY_MEDIA || {};
      const featured = featuredKeys.map(key => familyByKey.get(key)).filter(Boolean);
      const other = families.filter(family => !featuredKeys.includes(family.key));
      const featuredHtml = featured.map(family => {
        const photo = media[family.key];
        const validPhoto = photo && /^\/assets\/[a-z0-9_./-]+$/i.test(photo.src || '') && String(photo.source || '').trim();
        const visual = validPhoto ? '<figure class="family-media"><img src="' + escape(photo.src) + '" alt="' + escape(photo.alt || ('Ejemplo de ' + family.name + ', fotografía de ' + photo.source)) + '" width="640" height="480" loading="lazy" decoding="async"><figcaption>' + escape(photo.caption || 'Ejemplo de pieza') + '</figcaption></figure>' : '<span class="family-icon">' + icon(family.key) + '</span>';
        return '<a class="family-card family-card--featured" href="/servicios.html?pieza=' + encodeURIComponent(family.key) + '" aria-label="Ver reparaciones de ' + escape(family.name) + '">' + visual + '<span class="family-arrow" aria-hidden="true">↗</span><h3>' + escape(family.name) + '</h3><p>' + escape(family.description) + '</p></a>';
      }).join('');
      const moreHtml = other.length ? '<div class="family-more"><h3>También reparamos otras piezas</h3><div class="family-more-list">' + other.map(family => '<a class="family-more-link" href="/servicios.html?pieza=' + encodeURIComponent(family.key) + '"><span>' + escape(family.name) + '</span><span aria-hidden="true">↗</span></a>').join('') + '</div></div>' : '';
      grid.innerHTML = featuredHtml ? '<div class="family-featured">' + featuredHtml + '</div>' + moreHtml : '<div class="notice">Puedes <a href="/solicitud.html?tipo=consulta">consultar tu pieza con el equipo</a>.</div>';
    });
  }

  function setupGuidedSearch() {
    const form = document.getElementById('guided-search-form');
    if (!form) return;
    const brand = document.getElementById('guide-brand');
    const model = document.getElementById('guide-model');
    const component = document.getElementById('guide-component');
    const stageElements = [...form.querySelectorAll('[data-guide-stage]')];
    const indicators = [...document.querySelectorAll('[data-guide-indicator]')];
    const summary = document.getElementById('guide-summary');
    const back = form.querySelector('[data-guide-back]');
    const skip = form.querySelector('[data-guide-skip]');
    const next = form.querySelector('[data-guide-next]');
    const submit = form.querySelector('[data-guide-submit]');
    let currentStep = 0;
    options(brand, brands, 'Selecciona una marca');
    const refreshModels = () => options(model, modelsFor(brand.value), 'Selecciona un modelo', model.value);
    const refreshComponents = () => options(component, familiesForBrand(brand.value), 'Selecciona una pieza', component.value);
    refreshModels();
    refreshComponents();
    const fields = [brand, model, component];
    const lastStep = Math.min(fields.length, stageElements.length) - 1;
    const render = (focus = false) => {
      stageElements.forEach((stage, index) => { stage.hidden = index !== currentStep; });
      indicators.forEach((indicator, index) => {
        indicator.classList.toggle('is-complete', index < currentStep);
        if (index === currentStep) indicator.setAttribute('aria-current', 'step');
        else indicator.removeAttribute('aria-current');
      });
      back.hidden = currentStep === 0;
      next.hidden = currentStep === lastStep;
      skip.hidden = false;
      submit.hidden = currentStep !== lastStep;
      skip.textContent = currentStep === lastStep ? 'No sé qué pieza es' : currentStep === 1 ? 'No aparece, continuar' : 'No lo sé, continuar';
      const selected = [brand.value, model.value, familyByKey.get(component.value)?.name].filter(Boolean);
      summary.innerHTML = selected.map(value => '<span>' + escape(value) + '</span>').join('');
      document.querySelectorAll('[data-guide-help]').forEach(link => { link.href = consultUrl({brand:brand.value, model:model.value, component:component.value}); });
      if (focus) fields[currentStep].focus();
    };
    const openResults = () => location.assign('/servicios.html?' + newSearchParams({q:'', brand:brand.value, model:model.value, component:component.value, page:1}) + '#resultados');
    const advance = () => { currentStep = Math.min(lastStep, currentStep + 1); render(true); };
    next.addEventListener('click', advance);
    skip.addEventListener('click', () => {
      fields[currentStep].value = '';
      if (currentStep === lastStep) { render(); openResults(); return; }
      if (currentStep === 0) { model.value = ''; component.value = ''; refreshModels(); refreshComponents(); }
      if (currentStep === 1) { component.value = ''; refreshComponents(); }
      advance();
    });
    back.addEventListener('click', () => { currentStep = Math.max(0, currentStep - 1); render(true); });
    brand.addEventListener('change', () => { model.value = ''; component.value = ''; refreshModels(); refreshComponents(); render(); });
    model.addEventListener('change', () => { component.value = ''; refreshComponents(); render(); });
    component.addEventListener('change', () => render());
    form.addEventListener('submit', event => {
      event.preventDefault();
      if (currentStep !== lastStep) { advance(); return; }
      openResults();
    });
    const tabs = [...document.querySelectorAll('[data-search-tab]')];
    function activateTab(tab, focus = false) {
      tabs.forEach(item => { item.setAttribute('aria-selected', String(item === tab)); item.tabIndex = item === tab ? 0 : -1; });
      document.querySelectorAll('[data-search-panel]').forEach(panel => { panel.hidden = panel.dataset.searchPanel !== tab.dataset.searchTab; });
      if (focus) tab.focus();
    }
    tabs.forEach(tab => {
      tab.addEventListener('click', () => activateTab(tab));
      tab.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = tabs.indexOf(tab);
        const target = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs[tabs.length - 1] : tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
        activateTab(target, true);
      });
    });
    render();
  }

  // Build once; preserve the complete source values and rank before pagination.
  let prepared = null;
  const useCatalogue = () => {
    all = Array.isArray(window.MENIGAR_CATALOG) ? window.MENIGAR_CATALOG : [];
    families = Array.isArray(window.MENIGAR_FAMILIES) ? window.MENIGAR_FAMILIES : [];
    familyByKey = new Map(families.map(family => [family.key, family]));
    recordsById = new Map(all.map(record => [record.uid, record]));
    brands = unique(all.map(record => record.brand).filter(value => !genericBrand(value)));
    prepared = null;
    titleModelCache.clear();
  };
  const prepare = () => prepared ||= all.map(record => {
    const references = (record.references || []).map(value => ({ raw: value, normalized: compact(value) }));
    const codes = (record.dtcCodes || []).map(value => ({ raw: value, normalized: compact(value) }));
    const title = normalize([record.title, record.brand, record.model, record.variant].join(' '));
    const symptoms = normalize((record.symptoms || []).join(' '));
    const text = normalize([record.componentName, record.description, record.title, record.brand, record.model, record.variant, ...documentedModels(record), ...(record.symptoms || [])].join(' '));
    return { record, references, codes, title, symptoms, text };
  });
  const STOPWORDS = new Set(['de', 'la', 'el', 'los', 'las', 'del', 'en', 'un', 'una', 'mi', 'me', 'se', 'que', 'con', 'por', 'para', 'y']);
  function rankRecord(entry, query) {
    if (!query) return { score: entry.record.isAggregator ? 8 : 10, match: '', matchValue: '' };
    const normalized = normalize(query);
    const collapsed = compact(query);
    if (!normalized || !collapsed) return null;
    const exactReference = entry.references.find(reference => reference.normalized === collapsed);
    if (exactReference) return { score: 10000, match: 'Referencia coincidente', matchValue: exactReference.raw, matchKind: 'reference-exact' };
    const exactCode = entry.codes.find(code => code.normalized === collapsed);
    if (exactCode) return { score: 9000, match: 'Código de avería documentado', matchValue: exactCode.raw, matchKind: 'dtc-exact' };
    const partialReference = collapsed.length >= 4 ? entry.references.find(reference => reference.normalized.includes(collapsed)) : null;
    if (partialReference) return { score: 5000, match: 'Coincidencia parcial de referencia', matchValue: partialReference.raw };
    const partialCode = collapsed.length >= 4 ? entry.codes.find(code => code.normalized.includes(collapsed)) : null;
    if (partialCode) return { score: 4000, match: 'Coincidencia parcial de código', matchValue: partialCode.raw };
    const tokens = normalized.split(' ').filter(token => !STOPWORDS.has(token));
    if (!tokens.length) return null;
    const equivalents = { apagado: ['apagado', 'apaga', 'apagada', 'enciende'], apagada: ['apagada', 'apaga', 'apagado', 'enciende'], burbuja: ['burbuja', 'burbujas'], burbujas: ['burbuja', 'burbujas'], pantalla: ['pantalla', 'display'], centralita: ['centralita', 'ecu'], kilometros: ['kilometros', 'cuentakilometros', 'odometro'] };
    const tokenMatches = tokens.every(token => (equivalents[token] || [token]).some(term => entry.text.includes(term)));
    if (!tokenMatches) return null;
    let score = tokens.reduce((total, token) => total + (entry.title.includes(token) ? 80 : entry.symptoms.includes(token) ? 55 : 25), 0);
    if (entry.title.includes(normalized)) score += 500;
    if (entry.symptoms.includes(normalized)) score += 250;
    if (entry.record.isAggregator) score -= 15;
    return { score, match: 'Servicio relacionado', matchValue: '' };
  }
  const rankedResults = (query, filters, matchVehicle) => prepare().filter(entry => matchVehicle(entry.record, filters.brand || '', filters.model || '') && (!filters.component || entry.record.componentKey === filters.component)).map(entry => {
    const ranking = rankRecord(entry, query);
    return ranking ? { ...ranking, record: entry.record, vehicleMatch: vehicleMatch(entry.record, filters.brand || '', filters.model || '') } : null;
  }).filter(Boolean).sort((a, b) => b.score - a.score || collator.compare(a.record.title, b.record.title) || collator.compare(a.record.uid, b.record.uid));
  // Exposed for meaningful integration verification without duplicating the algorithm.
  window.MENIGAR_SEARCH = {
    normalize,
    modelsFor,
    vehicleMatch,
    familyGroupsFor,
    search: (query, filters = {}) => rankedResults(query, filters, withVehicle),
    brandOptions: (query, filters = {}) => filters.model && filters.brand ? rankedResults(query, filters, (record, brand, model) => vehicleMatch(record, brand, model) === 'brand-only') : [],
    getById: uid => recordsById.get(uid)
  };

  // The services page opens with its specialties and featured services, which need no data. The
  // catalogue (3.45 MB) loads when the visitor arrives with a search, uses the search or the selector,
  // or scrolls near it; whatever was chosen in the meantime is kept.
  function setupCatalogue() {
    const form = document.getElementById('catalog-filter-form');
    if (!form) return;
    const source = form.dataset?.catalogSrc;
    if (all.length || !source) { startCatalogue(form); return; }
    const fields = ['catalog-query', 'catalog-brand', 'catalog-model', 'catalog-component'].map(id => document.getElementById(id)).filter(Boolean);
    let loading = null;
    let pending = null;
    const intended = () => {
      const params = new URLSearchParams();
      [['q', 'catalog-query'], ['marca', 'catalog-brand'], ['modelo', 'catalog-model'], ['pieza', 'catalog-component']].forEach(([key, id]) => {
        const value = (document.getElementById(id)?.value || '').trim();
        if (value) params.set(key, value);
      });
      return params;
    };
    const load = () => loading ||= new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = source;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    }).then(() => {
      useCatalogue();
      if (pending) history.replaceState(null, '', location.pathname + (pending.toString() ? '?' + pending : '') + '#resultados');
      startCatalogue(form);
    }).catch(() => {
      const count = document.getElementById('results-count');
      const area = document.getElementById('resultados');
      if (area) area.hidden = false;
      if (count) count.textContent = 'No se ha podido cargar el catálogo. Vuelve a intentarlo o consúltanos directamente.';
    });
    // While the catalogue arrives, the visitor already sees where the results will be.
    const showLoading = () => {
      const area = document.getElementById('resultados');
      const showcase = document.getElementById('catalog-showcase');
      if (!area) return;
      area.hidden = false;
      if (showcase) showcase.hidden = true;
      document.getElementById('results-count').textContent = 'Cargando catálogo…';
      area.scrollIntoView({block:'start', behavior:'instant'});
    };
    const params = new URLSearchParams(location.search);
    if (['q', 'marca', 'modelo', 'pieza', 'pagina'].some(key => params.get(key))) { showLoading(); load(); return; }
    // A specialty opens its results in place, without reloading the page.
    document.addEventListener('click', event => {
      const link = event.target.closest('a[data-catalog-link]');
      if (!link || all.length || event.metaKey || event.ctrlKey || event.shiftKey) return;
      event.preventDefault();
      history.pushState(null, '', link.pathname + link.search + '#resultados');
      pending = null;
      showLoading();
      load();
    });
    const act = event => {
      if (all.length) return;
      if (event.type === 'submit') event.preventDefault();
      if (event.type !== 'focusin' && event.type !== 'pointerdown') pending = intended();
      const area = document.getElementById('resultados');
      if (pending?.toString() && area) showLoading();
      load();
    };
    form.addEventListener('submit', act);
    fields.forEach(field => ['focusin', 'pointerdown', 'change'].forEach(type => field.addEventListener(type, act)));
    if (/^#(catalogo|paso-a-paso|resultados)$/.test(location.hash)) load();
    else if ('IntersectionObserver' in window) {
      const near = new IntersectionObserver(entries => { if (entries.some(entry => entry.isIntersecting)) { near.disconnect(); load(); } }, { rootMargin: '600px 0px' });
      near.observe(document.getElementById('catalogo') || form);
    }
  }

  function startCatalogue(form) {
    const query = document.getElementById('catalog-query');
    const advanced = document.getElementById('catalog-advanced');
    const brand = document.getElementById('catalog-brand');
    const model = document.getElementById('catalog-model');
    const component = document.getElementById('catalog-component');
    const resultList = document.getElementById('catalog-results');
    const relatedBrand = document.getElementById('catalog-related-brand');
    const resultCount = document.getElementById('results-count');
    const pagination = document.getElementById('results-pagination');
    const activeFilters = document.getElementById('active-filters');
    const resultGuidance = document.getElementById('results-guidance');
    const filterPanel = document.getElementById('catalog-filter-panel');
    const selection = document.getElementById('catalog-selection');
    const selectionText = document.getElementById('catalog-selection-text');
    const editSelection = document.querySelector('[data-catalog-edit]');
    const showcase = document.getElementById('catalog-showcase');
    const familyBrands = document.getElementById('family-brands');
    const pageSize = 18;
    let state;
    let filtersExpanded = false;
    const mobileFilters = () => matchMedia('(max-width: 760px)').matches;
    const renderFilterSummary = () => {
      if (!filterPanel || !selection || !selectionText || !editSelection) return;
      const values = [state.brand, state.model, familyByKey.get(state.component)?.name, state.q && 'Tu búsqueda: ' + state.q].filter(Boolean);
      const collapsed = mobileFilters() && values.length > 0 && !filtersExpanded;
      selectionText.textContent = values.join(' · ');
      selection.hidden = !collapsed;
      filterPanel.hidden = collapsed;
      editSelection.setAttribute('aria-expanded', String(!collapsed));
    };
    const parseLocation = () => {
      const params = new URLSearchParams(location.search);
      const givenBrand = (params.get('marca') || '').slice(0, 120).trim();
      const givenModel = (params.get('modelo') || '').slice(0, 120).trim();
      const next = { q: (params.get('q') || '').slice(0, 180).trim(), brand: findBrand(givenBrand) || givenBrand, model: givenModel, component: validFamily(params.get('pieza')), page: Math.max(1, parseInt(params.get('pagina'), 10) || 1) };
      // Keep an unknown vehicle in the URL and consultation; do not broaden it silently.
      next.model = modelsFor(next.brand).find(value => normalize(value) === normalize(givenModel)) || givenModel;
      return next;
    };
    const selectedOptions = (entries, value) => value && !entries.some(entry => normalize(entry) === normalize(value)) ? [...entries, value] : entries;
    const populate = () => {
      query.value = state.q;
      if (advanced && state.q) advanced.open = true;
      options(brand, selectedOptions(brands, state.brand), 'Todas las marcas', state.brand);
      options(model, selectedOptions(modelsFor(state.brand), state.model), 'Todos los modelos', state.model);
      const componentEntries = familiesForBrand(state.brand);
      if (state.component && !componentEntries.some(entry => entry.value === state.component)) componentEntries.push({value:state.component, label:familyByKey.get(state.component).name + ' · consultar'});
      options(component, componentEntries, 'Todas las piezas', state.component);
    };
    const updateUrl = (replace = false) => {
      const params = newSearchParams(state).toString();
      history[replace ? 'replaceState' : 'pushState'](null, '', location.pathname + (params ? '?' + params : ''));
    };
    const resultHtml = (item, isGeneric = false) => {
      const record = item.record;
      const family = record.componentName || familyByKey.get(record.componentKey)?.name || 'Reparación electrónica';
      const publicTitle = record.publicTitle || record.title;
      const group = modelGroupFor(record, state.model);
      const selectedModel = ['documented', 'model-family'].includes(item.vehicleMatch) ? state.model : record.model;
      const familyGroups = item.vehicleMatch === 'model-family' ? familyGroupsFor(record, state.model) : [];
      const vehicle = [record.brand, selectedModel].filter(Boolean).join(' · ');
      const detailUrl = safeLocal(record.localPath) + (familyGroups.length ? '?' + new URLSearchParams({marca:record.brand, modelo:state.model}).toString() : '') + modelAnchor(group);
      const matchText = isGeneric ? 'Consulta si sirve para tu modelo' : item.match || (item.vehicleMatch === 'model-family' ? 'Versiones documentadas de este modelo' : item.vehicleMatch === 'documented' ? 'Información para este modelo' : '');
      const match = matchText ? '<div class="result-match"><strong>' + escape(matchText) + '</strong>' + (item.matchValue ? '<br>' + escape(item.matchValue) : '') + '</div>' : '';
      // The list is taken from this service or the selected model group, never another model.
      const distinctSymptoms = familyGroups.length ? [] : selectableSymptoms(record, group);
      const symptomHtml = distinctSymptoms.length ? '<div class="result-symptoms"><strong>¿Te ocurre alguno de estos fallos?</strong><p>Elige uno para explicárnoslo.</p><ul>' + distinctSymptoms.slice(0, 3).map(symptom => '<li><a class="result-symptom-link" href="' + escape(consultUrl(state, record.uid, symptom, item)) + '"><span>' + escape(symptom) + '</span><span aria-hidden="true">→</span></a></li>').join('') + '</ul>' + (distinctSymptoms.length > 3 ? '<a class="result-all-faults" href="' + detailUrl + '">Ver todos los fallos de esta ficha →</a>' : '') + '</div>' : '';
      const groupImages = group ? (group.blocks || []).flatMap(block => block.images || []) : state.model && modelGroupsFor(record).length ? [] : (record.gallery || []);
      const photo = groupImages.find(image => /^\/assets\/[a-z0-9_./-]+$/i.test(image.src || ''));
      const imageHtml = photo ? '<a class="result-image" href="' + detailUrl + '"><img src="' + escape(photo.src) + '" alt="' + escape(photo.alt || 'Fotografía publicada en esta ficha de reparación') + '" width="640" height="480" loading="lazy" decoding="async"></a>' : '';
      const groups = !familyGroups.length && (!state.model || isGeneric) ? modelGroupsFor(record) : [];
      const modelLinks = groups.slice(0, 4).map(value => '<a href="' + safeLocal(record.localPath) + modelAnchor(value) + '">' + escape(value.model) + '</a>').join('');
      const modelsHtml = modelLinks ? '<div class="result-models"><strong>Elige tu modelo</strong><div>' + modelLinks + '</div>' + (groups.length > 4 ? '<a href="' + safeLocal(record.localPath) + '">Ver todos los modelos →</a>' : '') + '</div>' : '';
      const familyVariants = familyGroups.length ? '<div class="result-variants">' + familyGroups.map(variant => {
        const variantParams = new URLSearchParams({marca:record.brand, modelo:variant.model});
        const variantUrl = safeLocal(record.localPath) + '?' + variantParams.toString() + modelAnchor(variant);
        const image = (variant.blocks || []).flatMap(block => block.images || []).find(value => /^\/assets\/[a-z0-9_./-]+$/i.test(value.src || ''));
        const imageHtml = image ? '<a class="result-variant-media" href="' + variantUrl + '"><img src="' + escape(image.src) + '" alt="' + escape(image.alt || ('Pieza publicada para ' + record.brand + ' ' + variant.model)) + '" width="640" height="480" loading="lazy" decoding="async"></a>' : '';
        return '<section class="result-variant">' + imageHtml + '<div class="result-variant-body"><h4>' + escape(record.brand + ' ' + variant.model) + '</h4><div class="result-variant-actions"><a class="result-detail-link" href="' + variantUrl + '">Ver esta versión →</a><a class="result-consult-link" href="' + escape(consultUrl({...state, model:variant.model}, record.uid, '', item)) + '">Consultar mi ' + escape(record.brand + ' ' + variant.model) + ' →</a></div></div></section>';
      }).join('') + '</div>' : '';
      const references = !isGeneric && !familyGroups.length ? (record.referenceGroups?.length ? record.referenceGroups.map(value => value.display) : (record.references || [])) : [];
      const refs = references.length ? '<details class="result-references"><summary>Ver referencias de la pieza</summary><div>' + references.slice(0, 3).map(reference => '<span>' + escape(reference) + '</span>').join('') + '</div>' + (references.length > 3 ? '<a href="' + detailUrl + '">Ver todas las referencias →</a>' : '') + '</details>' : '';
      const requestParams = new URLSearchParams({ tipo: 'consulta', pieza: record.uid });
      if (isGeneric) requestParams.set('tipo', 'consulta');
      if (state.brand) requestParams.set('marca', state.brand);
      if (state.model) requestParams.set('modelo', state.model);
      if (state.component) requestParams.set('familia', state.component);
      copyQueryContext(requestParams, state, record.uid, item);
      const description = familyGroups.length ? '' : isGeneric ? 'Consulta las variantes de este servicio para saber si corresponde a tu pieza.' : !distinctSymptoms.length ? 'Revisa esta ficha y compárala con tu pieza.' : '';
      return '<article class="result-card' + (familyGroups.length ? ' result-card--variants' : '') + (isGeneric ? ' result-card--generic' : '') + '">' + imageHtml + '<div class="result-meta">' + (vehicle ? '<span class="result-vehicle">' + escape(vehicle) + '</span>' : '') + '<span class="result-family">' + escape(family) + '</span></div><h3><a href="' + detailUrl + '">' + escape(publicTitle) + '</a></h3>' + match + (description ? '<p>' + escape(description) + '</p>' : '') + symptomHtml + familyVariants + modelsHtml + refs + '<div class="result-actions"><a class="result-detail-link" href="' + detailUrl + '">Ver pieza y todos los detalles <span aria-hidden="true">↗</span></a><a class="result-consult-link" href="/solicitud.html?' + requestParams.toString() + '">' + (isGeneric ? 'Consultar mi pieza' : 'Consultar esta pieza') + ' →</a></div></article>';
    };
    const render = () => {
      // Without a search or a filter the page shows its specialties and featured services, not
      // the whole catalogue page by page.
      const browsing = !state.q && !state.brand && !state.model && !state.component;
      if (showcase) {
        showcase.hidden = !browsing;
        document.getElementById('resultados').hidden = browsing;
        if (browsing) {
          renderFilterSummary();
          document.querySelectorAll('[data-context-consult]').forEach(link => { link.href = consultUrl(state); });
          pagination.innerHTML = '';
          if (familyBrands) familyBrands.hidden = true;
          return;
        }
      }
      const items = window.MENIGAR_SEARCH.search(state.q, state);
      const generic = window.MENIGAR_SEARCH.brandOptions(state.q, state);
      const genericOnly = !items.length && generic.length > 0;
      const visibleItems = genericOnly ? generic : items;
      const totalPages = Math.max(1, Math.ceil(visibleItems.length / pageSize));
      const requestedPage = state.page;
      state.page = Math.min(state.page, totalPages);
      if (state.page !== requestedPage) updateUrl(true);
      const start = (state.page - 1) * pageSize;
      resultCount.textContent = visibleItems.length ? visibleItems.length.toLocaleString('es-ES') + (genericOnly ? (visibleItems.length === 1 ? ' servicio para consultar' : ' servicios para consultar') : (visibleItems.length === 1 ? ' opción' : ' opciones')) + ' · Mostrando ' + (start + 1) + '–' + Math.min(start + pageSize, visibleItems.length) : state.q ? 'No encontramos coincidencias con tu búsqueda y los filtros elegidos.' : 'No tenemos una ficha para esta combinación de vehículo y pieza.';
      const title = document.getElementById('results-title');
      title.textContent = genericOnly ? 'Servicios de ' + state.brand + ' para consultar' : state.q ? 'Resultados de tu búsqueda' : [familyByKey.get(state.component)?.name, state.brand, state.model].filter(Boolean).join(' · ') || 'Piezas que reparamos';
      if (resultGuidance) resultGuidance.textContent = items.some(item => item.vehicleMatch === 'model-family') ? 'Tenemos información para estas versiones del ' + [state.brand, state.model].filter(Boolean).join(' ') + '. Revisa la información de cada versión o envíanos una imagen de tu pieza si no sabes cuál es.' : genericOnly ? 'No hay una ficha específica para ' + state.model + '. Puedes revisar la información de la marca y preguntarnos por tu pieza; estas opciones no confirman que corresponda a tu modelo.' : items.length ? 'Compara los fallos, las fotos y los modelos de cada opción. No necesitas saber el nombre técnico de la avería.' : 'Podemos ayudarte aunque tu pieza no aparezca aquí. Cuéntanos qué ocurre y adjunta una foto.';
      const chips = [['q', state.q ? 'Tu búsqueda: ' + state.q : ''], ['brand', state.brand], ['model', state.model], ['component', familyByKey.get(state.component)?.name]];
      activeFilters.innerHTML = chips.filter(([,value]) => value).map(([key, value]) => '<button class="filter-chip" type="button" data-remove-filter="' + key + '" aria-label="Quitar filtro ' + escape(value) + '">' + escape(value) + '<span aria-hidden="true">×</span></button>').join('');
      renderFilterSummary();
      document.querySelectorAll('[data-context-consult]').forEach(link => { link.href = consultUrl(state); });
      if (!visibleItems.length) {
        const malformed = state.q && !normalize(state.q);
        resultList.innerHTML = '<div class="empty-results"><span class="empty-icon">' + icon('ecu') + '</span><h3>' + (malformed ? 'Revisa el texto de tu búsqueda.' : '¿No ves tu pieza? Consúltanos.') + '</h3><p>' + (malformed ? 'Escribe un modelo, las letras y números de una referencia o describe brevemente qué ocurre.' : 'Que no aparezca en esta lista no significa que no podamos repararla. Envíanos una foto y dinos qué ocurre.') + '</p><a class="button button-primary" href="' + consultUrl(state) + '">Consultar mi pieza ↗</a><br>' + (state.q ? '<button class="text-button" type="button" data-remove-filter="q">Ver opciones sin este texto</button><br>' : '') + (state.model && state.brand ? '<a class="text-link" href="/servicios.html?' + newSearchParams({...state, model:'', page:1}).toString() + '">Ver piezas de ' + escape(state.brand) + ' sin elegir modelo →</a><br>' : '') + (state.q && (state.brand || state.model || state.component) ? '<button class="text-button" type="button" data-search-without-filters>Buscar este texto sin filtros de vehículo ni pieza</button><br>' : '') + '<button class="text-button" type="button" data-reset-filters>Volver a ver todas las piezas</button></div>';
      } else resultList.innerHTML = visibleItems.slice(start, start + pageSize).map(item => resultHtml(item, genericOnly)).join('');
      if (familyBrands) {
        // A whole specialty is long: its brands, by number of fichas, narrow it in one step.
        const counts = new Map();
        if (state.component && !state.brand && !state.q) items.forEach(item => { const value = item.record.brand; if (value && !genericBrand(value)) counts.set(value, (counts.get(value) || 0) + 1); });
        const top = [...counts].sort((a, b) => b[1] - a[1] || collator.compare(a[0], b[0])).slice(0, 14);
        familyBrands.hidden = top.length < 2;
        familyBrands.innerHTML = top.length < 2 ? '' : '<p>Elige tu marca para ver menos opciones</p><ul>' + top.map(([value, count]) => '<li><a href="/servicios.html?' + newSearchParams({...state, brand:value, model:'', page:1}).toString() + '#resultados" data-brand-shortcut="' + escape(value) + '">' + escape(value) + ' <span>' + count + '</span></a></li>').join('') + '</ul>';
      }
      if (relatedBrand) {
        relatedBrand.hidden = !items.length || !generic.length;
        relatedBrand.innerHTML = items.length && generic.length ? '<h3>Otros servicios de ' + escape(state.brand) + '</h3><p>Revisa otras opciones de la marca. Si tu variante no aparece, te ayudamos a identificarla.</p><div class="results-grid">' + generic.slice(0, 3).map(item => resultHtml(item, true)).join('') + '</div>' + (generic.length > 3 ? '<a class="text-link" href="/servicios.html?' + newSearchParams({...state, model:'', page:1}).toString() + '">Ver todos los servicios de la marca →</a>' : '') : '';
      }
      const pageLink = (page, text, current = false, label = '') => '<a href="/servicios.html?' + newSearchParams({ ...state, page }).toString() + '#resultados" data-result-page="' + page + '"' + (current ? ' aria-current="page"' : '') + (label ? ' aria-label="' + label + '"' : '') + '>' + text + '</a>';
      if (totalPages <= 1) { pagination.innerHTML = ''; return; }
      const pageNumbers = unique([1, state.page - 1, state.page, state.page + 1, totalPages].filter(page => page > 0 && page <= totalPages)).map(Number).sort((a,b) => a-b);
      let previous = 0;
      let html = state.page > 1 ? pageLink(state.page - 1, '←', false, 'Página anterior') : '';
      pageNumbers.forEach(page => { if (previous && page > previous + 1) html += '<span class="pagination-dots" aria-hidden="true">…</span>'; html += pageLink(page, page, page === state.page, 'Página ' + page); previous = page; });
      if (state.page < totalPages) html += pageLink(state.page + 1, '→', false, 'Página siguiente');
      pagination.innerHTML = html;
    };
    const commit = () => { state = { q: query.value.trim().slice(0, 180), brand: brand.value, model: model.value, component: component.value, page: 1 }; updateUrl(); render(); };
    form.addEventListener('submit', event => { event.preventDefault(); filtersExpanded = false; commit(); if (mobileFilters()) { resultCount.focus(); document.getElementById('resultados').scrollIntoView({block:'start', behavior:'instant'}); } });
    brand.addEventListener('change', () => { filtersExpanded = true; model.value = ''; component.value = ''; options(model, modelsFor(brand.value), 'Todos los modelos'); options(component, familiesForBrand(brand.value), 'Todas las piezas'); commit(); });
    model.addEventListener('change', () => { filtersExpanded = true; component.value = ''; options(component, familiesForBrand(brand.value), 'Todas las piezas'); commit(); });
    component.addEventListener('change', () => { filtersExpanded = true; commit(); });
    editSelection?.addEventListener('click', () => { filtersExpanded = true; renderFilterSummary(); brand.focus(); });
    document.addEventListener('click', event => {
      const widen = event.target.closest('[data-search-without-filters]');
      if (widen) { filtersExpanded = true; state = {...state, brand:'', model:'', component:'', page:1}; populate(); updateUrl(); render(); resultCount.focus(); return; }
      const reset = event.target.closest('[data-reset-filters]');
      if (reset) { filtersExpanded = true; state = {q:'', brand:'', model:'', component:'', page:1}; populate(); updateUrl(); render(); brand.focus(); return; }
      const chip = event.target.closest('[data-remove-filter]');
      if (chip) { state[chip.dataset.removeFilter] = ''; if (chip.dataset.removeFilter === 'brand') { state.model = ''; state.component = ''; } if (chip.dataset.removeFilter === 'model') state.component = ''; state.page = 1; populate(); updateUrl(); render(); resultCount.focus(); return; }
      const catalogLink = event.target.closest('a[data-catalog-link]');
      if (catalogLink && !event.metaKey && !event.ctrlKey && !event.shiftKey) {
        event.preventDefault();
        const linked = new URLSearchParams(catalogLink.search);
        filtersExpanded = false;
        state = {q:(linked.get('q') || '').slice(0, 180), brand:findBrand(linked.get('marca') || ''), model:'', component:validFamily(linked.get('pieza')), page:1};
        populate(); updateUrl(); render();
        document.getElementById('resultados').scrollIntoView({block:'start', behavior:'instant'});
        return;
      }
      const back = event.target.closest('[data-show-showcase]');
      if (back) {
        event.preventDefault();
        filtersExpanded = false;
        state = {q:'', brand:'', model:'', component:'', page:1};
        populate(); updateUrl(); render();
        (showcase || document.getElementById('catalogo')).scrollIntoView({block:'start', behavior:'instant'});
        return;
      }
      const shortcut = event.target.closest('[data-brand-shortcut]');
      if (shortcut) { event.preventDefault(); filtersExpanded = false; state = {...state, brand:shortcut.dataset.brandShortcut, model:'', page:1}; populate(); updateUrl(); render(); resultCount.focus(); document.getElementById('results-title').scrollIntoView({block:'start'}); return; }
      const page = event.target.closest('[data-result-page]');
      if (page) { event.preventDefault(); state.page = Number(page.dataset.resultPage); updateUrl(); render(); resultCount.focus(); document.getElementById('results-title').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block:'start'}); }
    });
    window.addEventListener('popstate', () => { filtersExpanded = false; state = parseLocation(); populate(); render(); });
    window.addEventListener('resize', renderFilterSummary);
    state = parseLocation();
    populate();
    render();
    if (location.hash === '#resultados' && showcase && !document.getElementById('resultados').hidden) document.getElementById('resultados').scrollIntoView({block:'start'});
  }

  function setupDetailContext() {
    const source = document.querySelector('.repair-source[data-repair-uid]');
    const status = document.getElementById('repair-model-context');
    if (!source || !status) return;
    const sections = [...source.querySelectorAll('.repair-variant[data-model-group][data-model-anchor]')];
    if (!sections.length) return;
    const params = new URLSearchParams(location.search);
    const brand = String(source.dataset.repairBrand || '').trim();
    // An index link selects its own documented variant. A fragment alone would
    // retain the previous ?modelo= value and leave the highlight and general
    // consultation attached to a different vehicle after the visitor changes it.
    // Prepare these destinations even on an initial visit with no query string.
    const indexLinks = [...source.querySelectorAll('a[data-model-group][data-model-anchor]')];
    indexLinks.forEach(link => {
      const group = String(link.dataset.modelGroup || '').trim();
      const anchor = String(link.dataset.modelAnchor || '');
      if (!group || !/^[a-z0-9][a-z0-9_-]*$/i.test(anchor) || !sections.some(section => section.dataset.modelAnchor === anchor && normalize(section.dataset.modelGroup) === normalize(group))) return;
      const url = new URL(link.getAttribute('href') || '#' + anchor, (location.origin || 'https://local.invalid') + location.pathname + location.search);
      if (brand) url.searchParams.set('marca', brand);
      url.searchParams.set('modelo', group);
      url.hash = anchor;
      link.href = url.pathname + '?' + url.searchParams.toString() + url.hash;
    });
    const requestedBrand = (params.get('marca') || '').slice(0, 120).trim();
    const model = (params.get('modelo') || '').slice(0, 120).trim();
    if (!model || (requestedBrand && normalize(requestedBrand) !== normalize(brand))) return;
    const family = MODEL_FAMILIES.find(value => normalize(value.brand) === normalize(brand) && normalize(value.model) === normalize(model) && value.records[source.dataset.repairUid]);
    const reviewed = family?.records[source.dataset.repairUid] || [];
    const matches = sections.filter(section => {
      const aliases = [section.dataset.modelGroup];
      try { if (section.dataset.modelAliases) { const values = JSON.parse(section.dataset.modelAliases); if (Array.isArray(values)) aliases.push(...values.filter(value => typeof value === 'string')); } } catch (_) { /* A damaged optional alias cannot create a match. */ }
      if (aliases.some(value => normalize(value) === normalize(model))) return true;
      return reviewed.some(value => normalize(value.model) === normalize(section.dataset.modelGroup) && value.anchor === section.dataset.modelAnchor);
    });
    if (!matches.length) return;
    sections.forEach(section => {
      section.classList.toggle('is-context-match', matches.includes(section));
      section.classList.toggle('is-context-other', !matches.includes(section));
    });
    indexLinks.forEach(link => {
      link.classList.toggle('is-context-match', matches.some(section => section.dataset.modelAnchor === link.dataset.modelAnchor));
    });
    const label = [brand, model].filter(Boolean).join(' ');
    status.hidden = false;
    status.textContent = family ? 'Tu búsqueda: ' + label + '. Hemos destacado sus versiones documentadas. Compara la información de cada una o consulta si no reconoces tu pieza.' : 'Tu selección: ' + label + '. Hemos destacado su apartado. Puedes revisar también las demás versiones de esta ficha.';
    // Keep a general consultation tied to the visitor's selection. Per-variant
    // links already contain their own model and must remain independent.
    document.querySelectorAll('.contact-card a[href^="/solicitud.html"], .repair-unlisted a[href^="/solicitud.html"]').forEach(link => {
      const url = new URL(link.getAttribute('href'), location.origin || 'https://local.invalid');
      url.searchParams.set('tipo', 'consulta');
      if (brand) url.searchParams.set('marca', brand);
      url.searchParams.set('modelo', model);
      link.href = url.pathname + '?' + url.searchParams.toString();
    });
  }

  // Third-party players load only when the visitor asks for them: until that
  // click no request reaches YouTube or Google Maps. Without JavaScript the
  // video links open YouTube and the map link opens Google Maps.
  function setupEmbeds() {
    const sources = {
      youtube: id => /^[\w-]{11}$/.test(id) ? 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0&playsinline=1' : '',
      map: url => /^https:\/\/www\.google\.com\/maps\/embed\?pb=[\w!%.-]+$/.test(url) ? url : ''
    };
    document.querySelectorAll('[data-embed]').forEach(frame => {
      const trigger = frame.querySelector('[data-embed-load]');
      const kind = frame.getAttribute('data-embed');
      const source = (sources[kind] || (() => ''))(frame.getAttribute('data-embed-src') || '');
      if (!trigger || !source) return;
      trigger.hidden = false;
      trigger.addEventListener('click', event => {
        if (event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        const player = document.createElement('iframe');
        player.src = source;
        player.title = frame.getAttribute('data-embed-title') || '';
        player.setAttribute('allow', (kind === 'youtube' ? 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; ' : '') + 'fullscreen');
        // The site sends no referrer; both players need the page origin to load.
        player.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
        frame.classList.add('is-loaded');
        frame.replaceChildren(player);
        player.focus();
      });
    });
  }

  setupNavigation();
  setupEmbeds();
  setupFamilies();
  setupGuidedSearch();
  setupCatalogue();
  setupDetailContext();
})();
