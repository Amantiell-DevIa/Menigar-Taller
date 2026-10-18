'use strict';
/* Ejecutar desde cualquier carpeta: node /ruta/al/proyecto/tests/test_busqueda.cjs.
 * Regresiones funcionales detectadas en la auditoría del prototipo.
 * Se ejecuta el catálogo y el motor reales, sin duplicar su algoritmo.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const context = {
  window: {},
  document: {
    querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById() { return null; }
  },
  location: { hostname: 'tests.example' },
  console, Intl, URLSearchParams, Map, Set, Date,
  Option: function Option() {}
};
vm.createContext(context);
for (const file of ['data/catalogo-v2.js', 'app.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, { filename: file });
}
const { MENIGAR_CATALOG: catalog, MENIGAR_SEARCH: engine } = context.window;
assert.ok(Array.isArray(catalog) && catalog.length > 0, 'Debe cargarse el catálogo real.');
assert.equal(typeof engine?.search, 'function', 'Debe cargarse el motor real.');
let passed = 0;
function test(name, run) {
  run();
  passed += 1;
  console.log('✓ ' + name);
}
function ids(results) { return Array.from(results, item => item.record.uid); }

test('Las claves son únicas y recuperan exactamente la misma ficha.', () => {
  assert.equal(new Set(catalog.map(record => record.uid)).size, catalog.length);
  for (const record of catalog) {
    assert.strictEqual(engine.getById(record.uid), record);
    assert.match(record.localPath, /^\/reparaciones\/[a-z0-9_-]+\/$/i);
  }
});

test('La ficha Jaguar con guion bajo conserva su ruta local completa.', () => {
  const record = engine.getById('abs-1786');
  assert.ok(record);
  assert.equal(record.localPath, '/reparaciones/abs-1786-x-type-2001-2009-bosch_57/');
  assert.match(record.localPath, /^\/reparaciones\/[a-z0-9_-]+\/$/i);
});

test('Referencia exacta: espacios y guiones conservan resultados y orden.', () => {
  const expected = engine.search('94003-07010');
  assert.ok(expected.length > 0);
  for (const query of ['94003 07010', '9400307010', '94003.07010']) {
    assert.deepEqual(ids(engine.search(query)), ids(expected));
  }
  assert.equal(expected[0].record.uid, 'main-13285');
  assert.equal(expected[0].match, 'Referencia coincidente');
});

test('07010 es una referencia parcial; nunca un código de avería diagnosticado.', () => {
  const results = engine.search('07010');
  assert.ok(results.length > 0);
  assert.ok(results.every(item => !/código de avería|diagn[oó]stic|reparable|garantiz/i.test(item.match)));
  assert.equal(results[0].match, 'Coincidencia parcial de referencia');
  assert.equal(results[0].record.uid, 'main-13285');
});

test('Honda → Civic → ABS conserva la ficha Civic 2016–2022, sin mostrar Mini.', () => {
  const results = engine.search('', { brand: 'Honda', model: 'Civic', component: 'abs' });
  assert.ok(results.length > 0);
  assert.ok(results.some(item => item.record.uid === 'abs-3198'));
  assert.ok(results.every(item => item.record.brand === 'Honda' && item.record.componentKey === 'abs'));
  assert.ok(results.every(item => !/mini|display/i.test(item.record.title)));
  const selected = engine.getById('abs-3198');
  assert.match(selected.title, /Civic 2016-2022/i);
  assert.match(selected.localPath, /civic/);
  assert.equal(selected.brand, 'Honda');
});

test('Una consulta formada solo por símbolos no muestra resultados arbitrarios.', () => {
  for (const query of ['%%%', '---', '?!', '...']) {
    assert.equal(engine.search(query).length, 0);
  }
});

test('Burbujas muestra opciones relacionadas y conserva su ficha individual.', () => {
  const results = engine.search('burbujas');
  assert.ok(results.length > 1, 'Un síntoma genérico debe permitir comparar alternativas.');
  assert.ok(results.every(item => item.match === 'Servicio relacionado'));
  assert.ok(results.every(item => engine.getById(item.record.uid) === item.record));
  assert.equal(context.location.href, undefined, 'El motor no debe seleccionar ni abrir una ficha por sí solo.');
});

test('Cuadro apagado muestra alternativas, sin diagnosticar ni seleccionar Ford Puma.', () => {
  const results = engine.search('cuadro apagado');
  assert.ok(results.length > 1);
  assert.ok(results.every(item => item.match === 'Servicio relacionado'));
  assert.ok(results.every(item => !/confirmad|garantiz|diagnosticad/i.test(item.match)));
  assert.equal(context.location.href, undefined);
});

test('Una referencia exacta se ordena antes de coincidencias parciales y texto.', () => {
  let verified = false;
  for (const record of catalog) {
    if (verified) break;
    for (const reference of record.references || []) {
      if (String(reference).length < 6) continue;
      const results = engine.search(reference);
      const hasExact = results.some(item => item.match === 'Referencia coincidente');
      const hasOther = results.some(item => item.match !== 'Referencia coincidente');
      if (!hasExact || !hasOther) continue;
      assert.equal(results[0].match, 'Referencia coincidente');
      let otherSeen = false;
      for (const item of results) {
        if (item.match !== 'Referencia coincidente') otherSeen = true;
        else assert.equal(otherSeen, false, 'Ninguna referencia exacta debe quedar tras otra coincidencia.');
      }
      verified = true;
      break;
    }
  }
  assert.ok(verified, 'Debe comprobarse una referencia del catálogo que tenga coincidencias exactas y parciales.');
});

test('Hyundai i30 display encuentra el listado que documenta ese modelo.', () => {
  const results = engine.search('i30 display', {brand:'Hyundai',model:'i30',component:'display'});
  assert.ok(results.some(item => item.record.uid === 'main-3915'));
  assert.ok(results.every(item => item.record.componentKey === 'display'));
  assert.equal(results.find(item => item.record.uid === 'main-3915').match, 'Servicio relacionado');
  assert.equal(engine.getById('main-1604').componentKey, 'cuadro');
});

test('Las referencias del cuadro i30 conservan ambas escrituras y el servicio específico.', () => {
  const filters = {brand:'Hyundai',model:'i30',component:'cuadro'};
  const original = engine.search('94003-2L410', filters);
  assert.equal(original[0].record.uid,'main-1604');
  assert.deepEqual(ids(original),ids(engine.search('940032L410', filters)));
  assert.ok(original.every(item=>item.record.uid!=='main-3915'));
});



// Exercise the production controllers with minimal DOM elements, not a copied state machine.
function controllerFixture(mode, search = '', viewport = 1280, familyMedia = {}) {
  class Element {
    constructor() { this.value = ''; this.options = []; this.events = new Map(); this.hidden = false; this.innerHTML = ''; this.textContent = ''; this.attributes = {}; this.focused = false; this.open = false; this.dataset = {}; this.classList = { toggle() {} }; }
    addEventListener(name, action) { this.events.set(name, action); }
    emit(name, target = this) { this.events.get(name)?.({ preventDefault() {}, target }); }
    replaceChildren(...values) { this.options = values; this.value = values[0]?.value || ''; }
    add(option) { this.options.push(option); if (option.selected) this.value = option.value; }
    focus() { this.focused = true; }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    scrollIntoView() {}
  }
  const nodes = new Map();
  const element = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  const form = element(mode === 'guided' ? 'guided-search-form' : 'catalog-filter-form');
  const stages = [new Element(), new Element(), new Element()];
  const indicators = [new Element(), new Element(), new Element()];
  const buttons = Object.fromEntries(['back', 'skip', 'next', 'submit'].map(key => [key, new Element()]));
  form.querySelectorAll = selector => selector === '[data-guide-stage]' ? stages : [];
  form.querySelector = selector => buttons[selector.match(/data-guide-(\w+)/)?.[1]] || null;
  const idsForMode = mode === 'guided' ? ['guided-search-form','guide-brand','guide-model','guide-component','guide-summary'] : ['catalog-filter-form','catalog-query','catalog-advanced','catalog-brand','catalog-model','catalog-component','catalog-results','catalog-related-brand','results-count','results-pagination','active-filters','results-title','results-guidance','catalog-filter-panel','catalog-selection','catalog-selection-text','resultados'];
  idsForMode.forEach(element);
  const document = { events: new Map(), querySelector(selector) { return selector === '[data-catalog-edit]' && mode === 'catalogue' ? element('catalog-edit') : null; }, querySelectorAll(selector) { return selector === '[data-guide-indicator]' ? indicators : selector === '[data-guide-help]' && mode === 'guided' ? [element('guide-help')] : selector === '[data-family-grid]' ? [element('family-grid')] : []; }, getElementById(id) { return nodes.get(id) || null; }, addEventListener(name, fn) { this.events.set(name, fn); } };
  const location = { hostname: 'tests.example', pathname:'/servicios.html', search, assigned:'', assign(url) { this.assigned = url; } };
  const fixtureContext = { window: { MENIGAR_FAMILY_MEDIA:familyMedia, events: new Map(), addEventListener(name, fn) { this.events.set(name, fn); } }, document, location, history:{ pushState(_a,_b,url) { location.search = url.includes('?') ? '?' + url.split('?')[1] : ''; }, replaceState(_a,_b,url) { location.search = url.includes('?') ? '?' + url.split('?')[1] : ''; } }, console, Intl, URLSearchParams, Map, Set, Date, matchMedia(query) { return {matches:query.includes('max-width') ? viewport <= 760 : true}; }, Option: function(label,value,_default,selected) { this.label = label; this.value = value; this.selected = selected; } };
  vm.createContext(fixtureContext);
  for (const file of ['data/catalogo-v2.js','app.js']) vm.runInContext(fs.readFileSync(path.join(root,file),'utf8'),fixtureContext,{filename:file});
  return { element, buttons, stages, indicators, location, document, window:fixtureContext.window };
}

test('Marca → modelo → pieza llega a resultados sin paso de síntoma ni texto obligatorio.', () => {
  const view = controllerFixture('guided');
  const brand = view.element('guide-brand'); brand.value = 'Hyundai'; brand.emit('change');
  view.buttons.next.emit('click');
  const model = view.element('guide-model'); model.value = 'i30'; model.emit('change');
  view.buttons.next.emit('click');
  const component = view.element('guide-component'); component.value = 'display'; component.emit('change');
  assert.equal(view.stages[2].hidden,false);
  assert.equal(view.buttons.submit.hidden,false);
  assert.equal(view.buttons.next.hidden,true);
  assert.equal(view.buttons.skip.hidden,false);
  assert.equal(view.buttons.skip.textContent,'No sé qué pieza es');
  view.element('guided-search-form').emit('submit');
  const url = new URL(view.location.assigned,'https://tests.example');
  assert.equal(url.pathname,'/servicios.html');
  assert.equal(url.hash,'#resultados');
  assert.equal(url.searchParams.get('marca'),'Hyundai');
  assert.equal(url.searchParams.get('modelo'),'i30');
  assert.equal(url.searchParams.get('pieza'),'display');
  assert.equal(url.searchParams.has('q'),false);
});

test('Cambiar marca en el recorrido guiado borra el modelo y la pieza anteriores.', () => {
  const view = controllerFixture('guided');
  view.element('guide-brand').value = 'Hyundai'; view.element('guide-brand').emit('change');
  view.element('guide-model').value = 'i30'; view.element('guide-component').value = 'display';
  view.element('guide-brand').value = 'Honda'; view.element('guide-brand').emit('change');
  assert.equal(view.element('guide-model').value,'');
  assert.equal(view.element('guide-component').value,'');
  assert.ok(view.element('guide-model').options.some(option => option.value === 'Civic'));
  assert.equal(view.element('guide-model').options.some(option => /i30/i.test(option.value)),false);
});

test('Continuar sin modelo permite buscar por marca y pieza sin inventar un modelo.', () => {
  const view = controllerFixture('guided');
  view.element('guide-brand').value = 'Hyundai'; view.element('guide-brand').emit('change');
  view.buttons.next.emit('click'); view.buttons.skip.emit('click');
  view.element('guide-component').value = 'display'; view.element('guided-search-form').emit('submit');
  const url = new URL(view.location.assigned,'https://tests.example');
  assert.equal(url.searchParams.has('modelo'),false);
  assert.equal(url.searchParams.get('marca'),'Hyundai');
  assert.equal(url.searchParams.get('pieza'),'display');
});

test('La ficha Hyundai i30 se reconoce por sus fallos sin escribir una avería.', () => {
  const view = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro');
  const html = view.element('catalog-results').innerHTML;
  assert.match(html,/main-1604-i30/);
  assert.match(html,/¿Te ocurre alguno de estos fallos\?/);
  assert.match(html,/Fallo del display del cuadro de instrumentos/);
  assert.match(html,/Fallo de vibración y parpadeos/);
  assert.match(html,/Fallo en las agujas/);
  assert.match(html,/modelo=i30/);
  assert.match(html,/familia=cuadro/);
  assert.equal(view.element('catalog-advanced').open,false);
});

test('Seleccionar un fallo conserva su texto exacto y el contexto en una consulta editable.', () => {
  const view = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro');
  const html = view.element('catalog-results').innerHTML;
  const href = html.match(/<a class="result-symptom-link" href="([^"]+)"><span>Fallo del display[^<]+<\/span>/)?.[1];
  assert.ok(href,'Cada síntoma visible permite consultar ese fallo.');
  assert.equal(html.includes('Consultar este fallo'),false,'El texto del fallo es el enlace completo.');
  const url = new URL(href.replace(/&amp;/g,'&'),'https://tests.example');
  assert.equal(url.pathname,'/solicitud.html');
  assert.equal(url.searchParams.get('tipo'),'consulta');
  assert.equal(url.searchParams.get('pieza'),'main-1604');
  assert.equal(url.searchParams.get('marca'),'Hyundai');
  assert.equal(url.searchParams.get('modelo'),'i30');
  assert.equal(url.searchParams.get('familia'),'cuadro');
  assert.equal(url.searchParams.get('sintoma'),engine.getById('main-1604').symptoms[0]);
});

test('La tarjeta prioriza vehículo, pieza y fallo; mantiene referencias consultables.', () => {
  const html = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro').element('catalog-results').innerHTML;
  assert.ok(html.indexOf('class="result-image"') < html.indexOf('class="result-vehicle"'));
  assert.ok(html.indexOf('class="result-vehicle"') < html.indexOf('<h3>'));
  assert.ok(html.indexOf('<h3>') < html.indexOf('class="result-symptoms"'));
  assert.ok(html.indexOf('class="result-symptoms"') < html.indexOf('class="result-actions"'));
  assert.equal((html.match(/class="result-symptom-link"/g) || []).length,3);
  assert.match(html,/<details class="result-references"><summary>Ver referencias de la pieza<\/summary>/);
  assert.match(html,/Ver todas las referencias/);
});

test('En móvil se resume la búsqueda y Cambiar recupera los filtros; en escritorio quedan visibles.', () => {
  const search = '?marca=Hyundai&modelo=i30&pieza=cuadro';
  const mobile = controllerFixture('catalogue',search,390);
  assert.equal(mobile.element('catalog-filter-panel').hidden,true);
  assert.equal(mobile.element('catalog-selection').hidden,false);
  assert.equal(mobile.element('catalog-selection-text').textContent,'Hyundai · i30 · Cuadros de instrumentos');
  mobile.element('catalog-edit').emit('click');
  assert.equal(mobile.element('catalog-filter-panel').hidden,false);
  assert.equal(mobile.element('catalog-selection').hidden,true);
  assert.equal(mobile.element('catalog-brand').focused,true);
  mobile.element('catalog-filter-form').emit('submit');
  assert.equal(mobile.element('catalog-filter-panel').hidden,true);
  assert.equal(mobile.element('catalog-selection').hidden,false);
  assert.equal(mobile.element('results-count').focused,true);
  const desktop = controllerFixture('catalogue',search,1280);
  assert.equal(desktop.element('catalog-filter-panel').hidden,false);
  assert.equal(desktop.element('catalog-selection').hidden,true);
});

test('Cuatro familias muestran fotos como ejemplos y las otras siete siguen accesibles.', () => {
  const media = {cuadro:{src:'/assets/hyundai/ejemplo.jpg',source:'Hyundai i30'},abs:{src:'https://externo.example/foto.jpg',source:'ABS de prueba'}};
  const html = controllerFixture('catalogue','',1280,media).element('family-grid').innerHTML;
  assert.equal((html.match(/family-card--featured/g) || []).length,4);
  assert.equal((html.match(/family-more-link/g) || []).length,7);
  assert.match(html,/alt="Ejemplo de Cuadros de instrumentos, fotografía de Hyundai i30"/);
  assert.match(html,/Ejemplo de pieza/);
  assert.equal(html.includes('https://externo.example/foto.jpg'),false);
});

test('Los servicios genéricos no se cuentan como coincidencias del modelo.', () => {
  const filters = {brand:'BMW', model:'Modelo no documentado', component:'display'};
  assert.equal(engine.search('',filters).length,0);
  const generic = engine.brandOptions('',filters);
  assert.ok(generic.every(item => item.vehicleMatch === 'brand-only' && !item.record.model));
  const view = controllerFixture('catalogue','?marca=BMW&modelo=Modelo%20no%20documentado&pieza=display');
  if (!generic.length) { assert.match(view.element('results-count').textContent,/No tenemos una ficha/); assert.match(view.element('catalog-results').innerHTML,/¿No ves tu pieza/); }
  else { assert.match(view.element('results-guidance').textContent,/No hay una ficha específica/); }
  assert.equal(view.element('catalog-model').value,'Modelo no documentado','La consulta conserva el modelo del cliente.');
  assert.match(view.element('catalog-results').innerHTML,/modelo=Modelo\+no\+documentado/);
  if (generic.length) {
    assert.match(view.element('catalog-results').innerHTML,/Consulta las variantes de este servicio/);
    assert.match(view.element('catalog-results').innerHTML,/tipo=consulta/);
  }
});

test('Una página general permite consultar variantes sin afirmar una coincidencia de modelo.', () => {
  const record = engine.getById('main-3915');
  assert.equal(engine.vehicleMatch(record,'Hyundai','i30'),'documented');
  assert.equal(engine.vehicleMatch(record,'Hyundai','Otro modelo'),'brand-only');
  assert.equal(engine.search('',{brand:'Hyundai',model:'Otro modelo',component:'display'}).some(item=>item.record.uid==='main-3915'),false);
  assert.equal(engine.brandOptions('',{brand:'Hyundai',model:'Otro modelo',component:'display'}).some(item=>item.record.uid==='main-3915'),true);
});

test('Una referencia opcional abre su filtro y se puede retirar sin perder el vehículo.', () => {
  const view = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro&q=94003-2L410');
  assert.equal(view.element('catalog-advanced').open,true);
  assert.match(view.element('catalog-results').innerHTML,/Referencia coincidente/);
  const chip = { dataset:{ removeFilter:'q' } };
  view.document.events.get('click')({target:{closest(selector) { return selector === '[data-remove-filter]' ? chip : null; }}});
  const params = new URLSearchParams(view.location.search);
  assert.equal(params.has('q'),false); assert.equal(params.get('modelo'),'i30'); assert.equal(params.get('pieza'),'cuadro');
  assert.match(view.element('catalog-results').innerHTML,/Fallo en las agujas/);
});

test('El historial y la paginación conservan filtros y la página visible.', () => {
  const view = controllerFixture('catalogue','?marca=BMW&pieza=cuadro');
  assert.match(view.element('results-pagination').innerHTML,/pagina=2/);
  const page = {dataset:{resultPage:'2'}};
  view.document.events.get('click')({preventDefault(){},target:{closest(selector) { return selector === '[data-result-page]' ? page : null; }}});
  let params = new URLSearchParams(view.location.search);
  assert.equal(params.get('pagina'),'2'); assert.equal(params.get('marca'),'BMW'); assert.equal(params.get('pieza'),'cuadro');
  assert.match(view.element('results-count').textContent,/Mostrando 19/);
  view.location.search = '?marca=Hyundai&modelo=i30&pieza=display';
  view.window.events.get('popstate')();
  assert.equal(view.element('catalog-model').value,'i30');
  assert.match(view.element('catalog-results').innerHTML,/main-3915-reparacion-display-hyundai\/#modelo-i30/);
});

test('Audi sin ficha específica muestra una consulta como alternativa principal y conserva el modelo.', () => {
  const filters = {brand:'Audi',model:'Mi modelo',component:'display'};
  assert.equal(engine.search('',filters).length,0);
  assert.ok(engine.brandOptions('',filters).some(item=>item.record.uid==='main-2303'));
  const view = controllerFixture('catalogue','?marca=Audi&modelo=Mi%20modelo&pieza=display');
  assert.match(view.element('results-title').textContent,/Servicios de Audi para consultar/);
  assert.match(view.element('results-guidance').textContent,/No hay una ficha específica para Mi modelo/);
  assert.equal(view.element('catalog-related-brand').hidden,true);
  const related = view.element('catalog-results').innerHTML;
  assert.match(related,/main-2303/);
  assert.match(related,/Consulta las variantes de este servicio/);
  assert.match(related,/tipo=consulta/);
  assert.match(related,/modelo=Mi\+modelo/);
  assert.match(related,/familia=display/);
});

test('BMW permite elegir aliases documentados y excluye componentes que no son modelos.', () => {
  const models = Array.from(engine.modelsFor('BMW'));
  for (const expected of ['Serie 1 E81/E87','X1 E84','Serie 5 E60','Serie 6 E63']) assert.ok(models.includes(expected),expected);
  assert.equal(models.includes('BMW Live Cockpit'),false);
  assert.equal(models.includes('BMW pantalla reposacabezas'),false);
  assert.equal(engine.vehicleMatch(engine.getById('main-2321'),'BMW','Serie 1'),'brand-only','El listado de displays permite consultar variantes sin afirmar toda una serie.');
  const filters = {brand:'BMW',model:'X1 E84',component:'display'};
  assert.ok(engine.search('',filters).some(item=>item.record.uid==='main-2321' && item.vehicleMatch==='documented'));
  assert.equal(engine.brandOptions('',filters).some(item=>item.record.uid==='main-2321'),false);
});

test('El alias BMW abre su grupo original y conserva el modelo elegido en la consulta.', () => {
  const view = controllerFixture('catalogue','?marca=BMW&modelo=X1%20E84&pieza=display');
  const html = view.element('catalog-results').innerHTML;
  assert.match(html,/main-2321-reparacion-display-bmw\/#modelo-serie-1-e81-e87-y-x1-e84/);
  assert.match(html,/modelo=X1\+E84/);
  assert.match(html,/familia=display/);
  assert.match(html,/Información para este modelo/);
});

test('Los fallos generales BMW no se atribuyen a un grupo que no los documenta.', () => {
  const record = engine.getById('main-2321');
  assert.ok(record.symptoms.length > 0,'La ficha general sí contiene fallos publicados.');
  const selected = controllerFixture('catalogue','?marca=BMW&modelo=X1%20E84&pieza=display').element('catalog-results').innerHTML;
  const card = selected.match(/<article[^>]*>[\s\S]*?main-2321[\s\S]*?<\/article>/)?.[0];
  assert.ok(card);
  assert.equal(card.includes('result-symptoms'),false);
  for (const symptom of record.symptoms) assert.equal(card.includes(symptom),false,symptom);
  const general = controllerFixture('catalogue','?marca=BMW&pieza=display').element('catalog-results').innerHTML;
  assert.match(general,/¿Te ocurre alguno de estos fallos\?/);
  assert.match(general,/sintoma=Fallos/);
});

test('Las piezas del asistente corresponden a la marca, sin limitarse al modelo elegido.', () => {
  const view = controllerFixture('guided');
  const brand = view.element('guide-brand'); brand.value = 'BMW'; brand.emit('change');
  const model = view.element('guide-model'); model.value = 'X1 E84'; model.emit('change');
  let pieces = view.element('guide-component').options.map(option=>option.value).filter(Boolean);
  assert.deepEqual(pieces,['cuadro','abs','display','multimedia','cambio']);
  assert.equal(pieces.includes('bluetooth'),false);
  assert.ok(pieces.includes('display'),'Se incluyen las fichas generales de BMW, no solo una coincidencia estricta del modelo.');
  brand.value = 'Fiat'; brand.emit('change');
  pieces = view.element('guide-component').options.map(option=>option.value).filter(Boolean);
  assert.ok(pieces.includes('bluetooth'));
  brand.value = ''; brand.emit('change');
  assert.equal(view.element('guide-component').options.length - 1,context.window.MENIGAR_FAMILIES.length);
});

test('El catálogo limita piezas por marca y conserva una pieza válida recibida en el enlace.', () => {
  const view = controllerFixture('catalogue','?marca=BMW&modelo=X1%20E84&pieza=display');
  assert.equal(view.element('catalog-component').value,'display');
  assert.equal(view.element('catalog-component').options.some(option=>option.value==='bluetooth'),false);
  const brand = view.element('catalog-brand'); brand.value = 'Fiat'; brand.emit('change');
  assert.equal(view.element('catalog-component').value,'');
  assert.ok(view.element('catalog-component').options.some(option=>option.value==='bluetooth'));
  const unknown = controllerFixture('catalogue','?marca=Marca%20desconocida&pieza=display');
  assert.equal(unknown.element('catalog-component').value,'display');
  assert.equal(unknown.element('catalog-component').options.length - 1,context.window.MENIGAR_FAMILIES.length);
});

test('Los modelos combinados BMW se sustituyen por sus aliases al elegir, pero sus enlaces antiguos funcionan.', () => {
  const models = Array.from(engine.modelsFor('BMW'));
  const combined = 'Serie 1 E81/E87 y X1 E84';
  assert.equal(models.includes(combined),false);
  assert.ok(models.includes('Serie 1 E81/E87')); assert.ok(models.includes('X1 E84'));
  assert.equal(engine.vehicleMatch(engine.getById('main-2321'),'BMW',combined),'documented');
  const view = controllerFixture('catalogue','?marca=BMW&modelo=' + encodeURIComponent(combined) + '&pieza=display');
  assert.equal(view.element('catalog-model').value,combined);
  assert.match(view.element('catalog-results').innerHTML,/main-2321-reparacion-display-bmw\/#modelo-serie-1-e81-e87-y-x1-e84/);
  assert.match(view.element('catalog-results').innerHTML,/modelo=Serie\+1\+E81%2FE87\+y\+X1\+E84/);
});

test('El título BMW Serie 5 impide ofrecer esa ficha como consulta general para X1.', () => {
  const record = engine.getById('main-2819');
  assert.equal(record.model,'','La regresión cubre el dato de modelo ausente en la extracción.');
  assert.equal(engine.vehicleMatch(record,'BMW','X1 E84'),'none');
  assert.equal(engine.brandOptions('',{brand:'BMW',model:'X1 E84',component:'display'}).some(item=>item.record.uid==='main-2819'),false);
  assert.equal(engine.vehicleMatch(record,'BMW','Serie 5'),'brand-only','El título permite consultar, sin declarar una coincidencia de compatibilidad.');
  assert.equal(engine.search('',{brand:'BMW',model:'Serie 5',component:'display'}).some(item=>item.record.uid==='main-2819'),false);
  const view = controllerFixture('catalogue','?marca=BMW&modelo=X1%20E84&pieza=display');
  assert.equal(view.element('catalog-related-brand').innerHTML.includes('main-2819'),false);
});

test('La evidencia del título exige palabras completas, sin confundir X10 con X1 ni Serie 50 con Serie 5.', () => {
  const base = {brand:'BMW',model:'',coveredModels:[],modelGroups:[],isAggregator:true};
  assert.equal(engine.vehicleMatch({...base,uid:'test-x10-title',title:'Reparación de display BMW X10'},'BMW','Modelo desconocido'),'brand-only');
  assert.equal(engine.vehicleMatch({...base,uid:'test-serie50-title',title:'Reparación BMW Serie 50'},'BMW','Modelo desconocido'),'brand-only');
  assert.equal(engine.vehicleMatch({...base,uid:'test-serie5-title',title:'Reparación BMW Serie 5'},'BMW','Modelo desconocido'),'none');
});

test('La página general BMW se ofrece para revisar variantes de Serie 1 sin confirmar ese modelo.', () => {
  const filters = {brand:'BMW',model:'Serie 1',component:'display'};
  assert.equal(engine.search('',filters).some(item=>item.record.uid==='main-2321'),false);
  const generic = engine.brandOptions('',filters);
  assert.ok(generic.some(item=>item.record.uid==='main-2321' && item.vehicleMatch==='brand-only'));
  assert.equal(generic.some(item=>item.record.uid==='main-2819'),false);
  const view = controllerFixture('catalogue','?marca=BMW&modelo=Serie%201&pieza=display');
  assert.match(view.element('results-title').textContent,/Servicios de BMW para consultar/);
  assert.match(view.element('results-guidance').textContent,/No hay una ficha específica para Serie 1/);
  const html = view.element('catalog-results').innerHTML;
  assert.match(html,/main-2321/); assert.match(html,/Consulta si sirve para tu modelo/);
  assert.match(html,/modelo=Serie\+1/);
  assert.match(html,/result-models/,'La página general permite revisar sus variantes.');
  assert.equal(html.includes('result-image'),false,'No se usa la foto de otro grupo como si fuera Serie 1.');
});

test('La presentación no convierte un título ni un párrafo de marketing en fallos seleccionables.', () => {
  const record = engine.getById('main-2819');
  assert.equal(record.symptoms.length,2,'Se conserva íntegra la extracción original.');
  assert.match(record.symptoms[1],/En Menigar ponemos a tu alcance/);
  const view = controllerFixture('catalogue','?marca=BMW&pieza=display');
  const cards = view.element('catalog-results').innerHTML.match(/<article\b[^>]*>[\s\S]*?<\/article>/g) || [];
  const card = cards.find(value=>value.includes('/main-2819-'));
  assert.ok(card,'La ficha sigue visible en el listado de su marca.');
  assert.equal(card.includes('result-symptoms'),false);
  assert.equal(card.includes('Consultar este fallo'),false);
  assert.equal(card.includes('En Menigar ponemos a tu alcance'),false);
  const documented = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro').element('catalog-results').innerHTML;
  assert.match(documented,/Fallo en las agujas de los indicadores analógicos/);
  assert.match(documented,/result-symptom-link/);
});

test('No sé qué pieza es muestra opciones de mi vehículo sin inventar una familia.', () => {
  const view = controllerFixture('guided');
  view.element('guide-brand').value = 'BMW'; view.element('guide-brand').emit('change');
  view.buttons.next.emit('click');
  view.element('guide-model').value = 'X1 E84'; view.element('guide-model').emit('change');
  view.buttons.next.emit('click');
  view.element('guide-component').value = 'display'; view.element('guide-component').emit('change');
  assert.equal(view.buttons.skip.textContent,'No sé qué pieza es');
  view.buttons.skip.emit('click');
  const url = new URL(view.location.assigned,'https://tests.example');
  assert.equal(url.searchParams.get('marca'),'BMW');
  assert.equal(url.searchParams.get('modelo'),'X1 E84');
  assert.equal(url.searchParams.has('pieza'),false);
  assert.equal(url.searchParams.has('q'),false);
  assert.equal(url.hash,'#resultados');
});

test('La ayuda del asistente conserva marca y modelo y se actualiza al cambiar de vehículo.', () => {
  const view = controllerFixture('guided');
  view.element('guide-brand').value = 'Hyundai'; view.element('guide-brand').emit('change');
  view.element('guide-model').value = 'i30'; view.element('guide-model').emit('change');
  let url = new URL(view.element('guide-help').href,'https://tests.example');
  assert.equal(url.searchParams.get('tipo'),'consulta');
  assert.equal(url.searchParams.get('marca'),'Hyundai');
  assert.equal(url.searchParams.get('modelo'),'i30');
  assert.equal(url.searchParams.has('familia'),false);
  view.element('guide-brand').value = 'BMW'; view.element('guide-brand').emit('change');
  url = new URL(view.element('guide-help').href,'https://tests.example');
  assert.equal(url.searchParams.get('marca'),'BMW');
  assert.equal(url.searchParams.has('modelo'),false);
});

test('Una página fuera del rango se corrige también en la URL sin perder los filtros.', () => {
  const view = controllerFixture('catalogue','?marca=Hyundai&modelo=i30&pieza=cuadro&pagina=999');
  const params = new URLSearchParams(view.location.search);
  assert.equal(params.has('pagina'),false);
  assert.equal(params.get('modelo'),'i30');
  assert.match(view.element('results-count').textContent,/Mostrando 1/);
});

function firstConsultation(query, className = 'result-consult-link') {
  const html = controllerFixture('catalogue','?q='+encodeURIComponent(query)).element('catalog-results').innerHTML;
  const href = html.match(new RegExp('class="'+className+'" href="([^"]+)"'))?.[1];
  assert.ok(href, 'Debe existir una consulta para '+query);
  return new URL(href.replace(/&amp;/g,'&'),'https://tests.example');
}

test('Una referencia exacta se traslada al formulario sin perder el texto del visitante.', () => {
  for (const query of ['94003-07010','94003 07010','9400307010']) {
    const url = firstConsultation(query);
    assert.equal(url.searchParams.get('pieza'),'main-13285');
    assert.equal(url.searchParams.get('referencia'),query);
    assert.equal(url.searchParams.get('consulta'),query);
    assert.equal(url.searchParams.has('codigo'),false);
  }
});

test('Un código de avería exacto se copia al campo de diagnosis, nunca al de referencia.', () => {
  const url = firstConsultation('C2200');
  assert.equal(url.searchParams.get('pieza'),'abs-3543');
  assert.equal(url.searchParams.get('codigo'),'C2200');
  assert.equal(url.searchParams.get('consulta'),'C2200');
  assert.equal(url.searchParams.has('referencia'),false);
});

test('Una referencia parcial conserva contexto sin inventar un identificador completo.', () => {
  const url = firstConsultation('07010');
  assert.equal(url.searchParams.get('consulta'),'07010');
  assert.equal(url.searchParams.has('referencia'),false);
  assert.equal(url.searchParams.has('codigo'),false);
});

test('Un código parcial y una descripción libre no rellenan campos técnicos.', () => {
  for (const query of ['C220','burbujas']) {
    const url = firstConsultation(query);
    assert.equal(url.searchParams.get('consulta'),query);
    assert.equal(url.searchParams.has('referencia'),false);
    assert.equal(url.searchParams.has('codigo'),false);
  }
});

test('Elegir un síntoma también mantiene la referencia exacta y su contexto.', () => {
  const url = firstConsultation('94003-07010','result-symptom-link');
  assert.equal(url.searchParams.get('referencia'),'94003-07010');
  assert.equal(url.searchParams.get('consulta'),'94003-07010');
  assert.ok(url.searchParams.get('sintoma'));
});

test('Mazda 3 muestra sus variantes documentadas de display sin ofrecer Mazda 5 ni 6 como equivalentes.', () => {
  const results = engine.search('', {brand:'Mazda', model:'3', component:'display'});
  const match = results.find(item => item.record.uid === 'main-2942');
  assert.ok(match, 'El nombre común llega a la documentación ya existente.');
  assert.equal(match.vehicleMatch,'model-family','Una familia documentada no es una coincidencia exacta de pieza.');
  const groups = Array.from(engine.familyGroupsFor(match.record,'3'));
  assert.deepEqual(groups.map(group => group.model),['3 BK','3 BM']);
  assert.equal(engine.brandOptions('',{brand:'Mazda',model:'3',component:'display'}).some(item => item.record.uid === 'main-2942'),false);
  const view = controllerFixture('catalogue','?marca=Mazda&modelo=3&pieza=display');
  const html = view.element('catalog-results').innerHTML;
  assert.match(view.element('results-guidance').textContent,/Tenemos información para estas versiones del Mazda 3/);
  assert.equal(view.element('results-guidance').textContent.includes('No hay una ficha'),false);
  assert.match(html,/result-card--variants/);
  assert.equal((html.match(/class="result-variant"/g) || []).length,2);
  assert.match(html,/<h4>Mazda 3 BK<\/h4>/);
  assert.match(html,/<h4>Mazda 3 BM<\/h4>/);
  assert.equal(html.includes('Mazda 5'),false);
  assert.equal(html.includes('Mazda 6'),false);
  for (const group of groups) {
    const image = group.blocks.flatMap(block => block.images || [])[0];
    assert.ok(html.includes(image.src),'La foto corresponde al grupo '+group.model);
    const url = new URL('/reparaciones/main-2942-reparacion-display-mazda/?marca=Mazda&modelo='+encodeURIComponent(group.model)+'#'+group.anchor,'https://tests.example');
    assert.ok(html.includes(url.searchParams.toString()+'#'+group.anchor));
  }
});

test('La relación piloto conserva los identificadores y apartados de la extracción, sin generar parentescos por nombre.', () => {
  const full = JSON.parse(fs.readFileSync(path.join(root,'data/catalogo-v2.json'),'utf8'));
  for (const uid of ['main-2942','main-712']) {
    const record = engine.getById(uid);
    const original = full.find(value => value.uid === uid);
    const groups = engine.familyGroupsFor(record,'3');
    assert.ok(groups.length > 0);
    for (const group of groups) {
      const section = original.sourceSections.find(value => value.anchor === group.anchor);
      assert.ok(section,'El ancla tiene un apartado de origen en '+uid);
      assert.equal(section.vehicleModel,group.model,'Se conserva la asociación modelo-apartado.');
      for (const image of group.blocks.flatMap(block => block.images || [])) {
        assert.ok(section.blocks.some(block => block.kind === 'image' && block.src === image.src),'La foto procede del mismo apartado.');
      }
    }
  }
  assert.equal(engine.familyGroupsFor(engine.getById('main-2942'),'30').length,0);
  assert.equal(engine.familyGroupsFor(engine.getById('main-2321'),'Serie 1').length,0,'No se extiende el piloto a relaciones sin revisar.');
  const stale = {...engine.getById('main-2942'),modelGroups:[{model:'3 BK',anchor:'otro-apartado'}]};
  assert.equal(engine.familyGroupsFor(stale,'3').length,0,'Un apartado cambiado exige revisar el mapa; no se adivina.');
});

test('Elegir una variante Mazda conserva la versión elegida y permite consultar con contexto.', () => {
  const html = controllerFixture('catalogue','?marca=Mazda&modelo=3&pieza=display').element('catalog-results').innerHTML;
  const href = html.match(/class="result-consult-link" href="([^"]+)">Consultar mi Mazda 3 BM/)?.[1];
  assert.ok(href);
  const url = new URL(href.replace(/&amp;/g,'&'),'https://tests.example');
  assert.equal(url.searchParams.get('tipo'),'consulta');
  assert.equal(url.searchParams.get('pieza'),'main-2942');
  assert.equal(url.searchParams.get('modelo'),'3 BM');
  assert.equal(url.searchParams.get('familia'),'display');
});

test('Cambiar marca, modelo o pieza conserva el texto escrito y no amplía la búsqueda silenciosamente.', () => {
  for (const [field,value] of [['catalog-brand','Honda'],['catalog-model','i20'],['catalog-component','abs']]) {
    const view = controllerFixture('catalogue','?q=94003-2L410&marca=Hyundai&modelo=i30&pieza=cuadro');
    const control = view.element(field); control.value = value; control.emit('change');
    const params = new URLSearchParams(view.location.search);
    assert.equal(params.get('q'),'94003-2L410',field);
    assert.equal(view.element('catalog-query').value,'94003-2L410',field);
    assert.match(view.element('catalog-results').innerHTML,/data-search-without-filters/);
  }
});

test('Sin coincidencias se puede buscar el mismo texto sin filtros mediante una acción explícita.', () => {
  const view = controllerFixture('catalogue','?q=94003-2L410&marca=Honda&modelo=Civic&pieza=abs');
  assert.match(view.element('catalog-results').innerHTML,/Buscar este texto sin filtros de vehículo ni pieza/);
  assert.match(view.element('results-count').textContent,/tu búsqueda/);
  const widen = {};
  view.document.events.get('click')({target:{closest(selector) {return selector === '[data-search-without-filters]' ? widen : null;}}});
  const params = new URLSearchParams(view.location.search);
  assert.equal(params.get('q'),'94003-2L410');
  assert.equal(params.has('marca'),false); assert.equal(params.has('modelo'),false); assert.equal(params.has('pieza'),false);
  assert.match(view.element('catalog-results').innerHTML,/main-1604-i30/);
  assert.match(view.element('catalog-results').innerHTML,/Referencia coincidente/);
});

test('Un DTC o texto libre se presenta como búsqueda y no se etiqueta como referencia de pieza.', () => {
  for (const query of ['C2200','burbujas']) {
    const view = controllerFixture('catalogue','?q='+encodeURIComponent(query),390);
    assert.match(view.element('results-title').textContent,/Resultados de tu búsqueda/);
    assert.equal(view.element('catalog-selection-text').textContent,'Tu búsqueda: '+query);
    assert.match(view.element('active-filters').innerHTML,/Tu búsqueda:/);
    assert.equal(view.element('active-filters').innerHTML.includes('Referencia:'),false);
  }
});

function detailFixture(uid, search) {
  const record = engine.getById(uid);
  class DetailNode {
    constructor(dataset = {}) {this.dataset = dataset; this.hidden = false; this.textContent = ''; this.classes = new Set(); this.classList = {toggle:(key,on) => on ? this.classes.add(key) : this.classes.delete(key)};}
    getAttribute(name) {return name === 'href' ? this.href || '#' + this.dataset.modelAnchor : null;}
  }
  // Use the generated HTML's real hooks, including legacy model anchors which
  // do not exist in the small browser catalogue's modelGroups projection.
  const html = fs.readFileSync(path.join(root,record.localPath,'index.html'),'utf8');
  const decode = value => value.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
  const attr = (tag,name) => decode(tag.match(new RegExp('\\b'+name+'="([^\"]*)"'))?.[1] || '');
  const fromTag = tag => {const node = new DetailNode({modelGroup:attr(tag,'data-model-group'),modelAnchor:attr(tag,'data-model-anchor'),modelAliases:attr(tag,'data-model-aliases')}); node.href = attr(tag,'href'); return node;};
  const sections = (html.match(/<article\b[^>]*class="[^"]*\brepair-variant\b[^"]*"[^>]*>/g) || []).map(fromTag);
  const nav = (html.match(/<nav\b[^>]*>[\s\S]*?<\/nav>/g) || []).join('');
  const index = (nav.match(/<a\b[^>]*data-model-anchor="[^"]+"[^>]*>/g) || []).map(fromTag);
  const source = new DetailNode({repairUid:uid,repairBrand:record.brand});
  source.querySelectorAll = selector => selector.startsWith('.repair-variant') ? sections : index;
  const status = new DetailNode(); status.hidden = true;
  const consultation = {getAttribute() {return '/solicitud.html?pieza='+uid;}};
  const document = {querySelector(selector) {return selector === '.repair-source[data-repair-uid]' ? source : null;},querySelectorAll(selector) {return selector.startsWith('.contact-card') ? [consultation] : [];},getElementById(id) {return id === 'repair-model-context' ? status : null;}};
  // Deliberately load no catalogue: real detail pages only load app.js.
  const detailContext = {window:{},document,location:{hostname:'tests.example',pathname:record.localPath,search,origin:'https://tests.example'},console,Intl,URL,URLSearchParams,Map,Set,Date};
  vm.createContext(detailContext);
  vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8'),detailContext,{filename:'app.js'});
  return {sections,index,status,consultation};
}

test('La ficha destaca las variantes del Mazda 3 sin ocultar Mazda 5 y 6 ni necesitar cargar todo el catálogo.', () => {
  const view = detailFixture('main-2942','?marca=Mazda&modelo=3');
  assert.equal(view.status.hidden,false);
  assert.match(view.status.textContent,/Tu búsqueda: Mazda 3/);
  const selected = view.sections.filter(section => section.classes.has('is-context-match'));
  assert.deepEqual(selected.map(section => section.dataset.modelGroup),['3 BK','3 BM']);
  assert.ok(view.sections.every(section => !section.hidden),'El resto de contenido sigue disponible.');
  assert.equal(view.sections.filter(section => section.classes.has('is-context-other')).length,2);
  const url = new URL(view.consultation.href,'https://tests.example');
  assert.equal(url.searchParams.get('modelo'),'3');
  assert.equal(url.searchParams.get('marca'),'Mazda');
  assert.equal(url.searchParams.get('tipo'),'consulta');
});

test('La selección precisa destaca solo su variante y una marca ajena no crea contexto falso.', () => {
  const view = detailFixture('main-2942','?marca=Mazda&modelo=3%20BM');
  assert.deepEqual(view.sections.filter(section => section.classes.has('is-context-match')).map(section => section.dataset.modelGroup),['3 BM']);
  assert.match(view.status.textContent,/Tu selección: Mazda 3 BM/);
  const wrong = detailFixture('main-2942','?marca=BMW&modelo=3');
  assert.equal(wrong.status.hidden,true);
  assert.ok(wrong.sections.every(section => !section.classes.has('is-context-match')));
});

test('Cambiar de variante desde el índice sustituye el contexto anterior, también en BMW e Hyundai.', () => {
  for (const [uid,initialModel,targetModel] of [
    ['main-2942','3 BM','3 BK'],
    ['main-2321','Serie 5 E60 y Serie 6 E63','Serie 1 E81/E87 y X1 E84'],
    ['main-3915','i30','Getz']
  ]) {
    const record = engine.getById(uid);
    const initial = detailFixture(uid,'?marca='+encodeURIComponent(record.brand)+'&modelo='+encodeURIComponent(initialModel));
    const link = initial.index.find(value => value.dataset.modelGroup === targetModel);
    assert.ok(link,'El índice contiene '+targetModel);
    const url = new URL(link.href,'https://tests.example');
    assert.equal(url.pathname,record.localPath);
    assert.equal(url.searchParams.get('marca'),record.brand);
    assert.equal(url.searchParams.get('modelo'),targetModel);
    assert.equal(url.hash,'#'+link.dataset.modelAnchor);
    const next = detailFixture(uid,url.search);
    assert.equal(next.sections.filter(section => section.classes.has('is-context-match')).length,1);
    assert.equal(next.sections.find(section => section.classes.has('is-context-match')).dataset.modelGroup,targetModel);
    assert.equal(new URL(next.consultation.href,'https://tests.example').searchParams.get('modelo'),targetModel);
    assert.ok(next.sections.every(section => !section.hidden),'Cambiar selección conserva las demás secciones legibles.');
  }
});

test('El índice genera un destino coherente para cada variante aunque se entre sin parámetros.', () => {
  const view = detailFixture('main-2942','');
  assert.equal(view.status.hidden,true,'Sin selección no se inventa un contexto inicial.');
  const link = view.index.find(value => value.dataset.modelGroup === '3 BK');
  const url = new URL(link.href,'https://tests.example');
  assert.equal(url.searchParams.get('marca'),'Mazda');
  assert.equal(url.searchParams.get('modelo'),'3 BK');
  assert.equal(url.hash,'#detalle-6');
  const next = detailFixture('main-2942',url.search);
  assert.match(next.status.textContent,/Tu selección: Mazda 3 BK/);
  assert.equal(next.sections.find(section => section.classes.has('is-context-match')).dataset.modelGroup,'3 BK');
});

console.log('\n' + passed + ' pruebas de búsqueda y recorrido superadas · ' + catalog.length + ' fichas reales.');
