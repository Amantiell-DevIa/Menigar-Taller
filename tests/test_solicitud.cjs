'use strict';
/* Run the actual request controller with a small DOM fixture and in-memory
 * sessionStorage/fetch. No browser, server, external requests or real data.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const requestSource = fs.readFileSync(path.join(root, 'solicitud.js'), 'utf8');
const receiptSource = fs.readFileSync(path.join(root, 'receipt.js'), 'utf8');
const catalogueSource = fs.readFileSync(path.join(root, 'data/catalogo-v2.js'), 'utf8');
const decode = value => String(value || '').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
const draftKey = search => 'menigar-request-v2:' + new URLSearchParams(search).toString();

function fixture(search = '', storage = new Map()) {
  const nodes = new Map(), posted = [];
  let active = null, counter = 0;
  class Element {
    constructor(id = '') {
      this.id=id; this.value=''; this.checked=false; this.required=false;
      this.disabled=false; this.hidden=false; this.type='text'; this.files=[];
      this.dataset={}; this.attributes={}; this.events=new Map(); this.descendants=[];
      this._html=''; this.textContent=''; this.validity={valid:true};
    }
    addEventListener(name, callback) {
      if (!this.events.has(name)) this.events.set(name, []);
      this.events.get(name).push(callback);
    }
    async emit(name) {
      for (const callback of this.events.get(name) || []) await callback({target:this,preventDefault(){}});
    }
    focus() { active=this.id; }
    setAttribute(name,value) { this.attributes[name]=value; }
    removeAttribute(name) { delete this.attributes[name]; }
    getClientRects() { return this.hidden ? [] : [{}]; }
    closest(selector) { return selector === '.unit-card' ? this.card : null; }
    querySelectorAll(selector) {
      if (selector === 'a') return this.descendants.filter(item => item.tag === 'a');
      const name = selector.match(/^\[data-([a-z-]+)\]$/)?.[1]?.replace(/-([a-z])/g,(_m,c)=>c.toUpperCase());
      return name ? this.descendants.filter(item => Object.hasOwn(item.dataset,name)) : [];
    }
    querySelector(selector) {
      const match = selector.match(/^\[data-unit-field="([^"]+)"\]$/);
      return match ? this.descendants.find(item => item.dataset.unitField === match[1]) : null;
    }
    set innerHTML(html) {
      this._html=html; this.descendants=parse(html);
      for (const card of html.matchAll(/<article class="unit-card" id="([^"]+)">([\s\S]*?)<\/article>/g)) {
        const article=element(card[1]);
        article.descendants=this.descendants.filter(item => item.offset > card.index && item.offset < card.index+card[0].length);
        article.descendants.forEach(item => item.card=article);
        this.descendants.push(article);
      }
    }
    get innerHTML() { return this._html; }
  }
  const element = id => {
    if (!nodes.has(id)) nodes.set(id,new Element(id));
    return nodes.get(id);
  };
  function parse(html) {
    const found=[];
    for (const match of html.matchAll(/<(input|select|textarea|button|div|h[123]|a|section)\b([^>]*)>/g)) {
      const attrs={};
      for (const attr of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) attrs[attr[1]]=decode(attr[2] ?? '');
      const item=attrs.id ? new Element(attrs.id) : new Element();
      if (item.id) nodes.set(item.id,item);
      item.tag=match[1]; item.offset=match.index; item.type=attrs.type || 'text'; item.value=attrs.value || '';
      item.checked=Object.hasOwn(attrs,'checked'); item.required=Object.hasOwn(attrs,'required');
      item.disabled=Object.hasOwn(attrs,'disabled'); item.hidden=Object.hasOwn(attrs,'hidden');
      for (const [key,value] of Object.entries(attrs)) {
        if (key.startsWith('data-')) item.dataset[key.slice(5).replace(/-([a-z])/g,(_m,c)=>c.toUpperCase())]=value;
      }
      if (['select','textarea'].includes(item.tag)) {
        const content=html.slice(match.index+match[0].length).split('</'+item.tag+'>')[0];
        if (item.tag === 'textarea') item.value=decode(content);
        else {
          const options=[...content.matchAll(/<option\b([^>]*)>/g)];
          const selected=options.find(option => /\bselected\b/.test(option[1])) || options[0];
          item.value=decode(selected?.[1].match(/value="([^"]*)"/)?.[1] || '');
        }
      }
      if (attrs.href) { item.href=attrs.href; item.hash=attrs.href.startsWith('#') ? attrs.href : ''; }
      found.push(item);
    }
    return found;
  }
  const form=element('requestForm');
  form.elements={intent:{value:'consultation'}};
  form.reset=()=>{};
  const next=[new Element(),new Element()], back=[new Element(),new Element()];
  const contactIds=['customerName','customerContact','customerEmail','customerPhone','vehicleBrand','vehicleModel','taxId','address','city','postalCode','country','returnAddress','returnCity','returnPostalCode','returnCountry'];
  ['customerName','customerEmail','customerPhone','vehicleBrand','vehicleModel'].forEach(id=>element(id).required=true);
  element('customerEmail').type='email';
  form.querySelectorAll=selector => selector === '[data-next]' ? next : selector === '[data-back]' ? back : selector === '[data-step="0"] input' ? contactIds.map(element) : [];
  form.querySelector=selector => {
    const step=selector.match(/data-step="(\d+)"/);
    return step ? element(['contactTitle','piecesTitle','reviewTitle'][Number(step[1])]) : null;
  };
  const sections=[0,1,2].map(step => Object.assign(new Element(),{dataset:{step:String(step)}}));
  const progress=[0,1,2].map(step => Object.assign(new Element(),{dataset:{stepLabel:String(step)}}));
  const document={
    getElementById:element,
    querySelectorAll(selector) { return selector === '.request-step' ? sections : selector === '[data-step-label]' ? progress : []; }
  };
  const context={window:{},document,location:{search},URLSearchParams,Map,Set,Uint8Array,console,
    crypto:{randomUUID:()=>`test-unit-${++counter}-0123456789`},
    sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)},
    fetch:async (url,options) => {
      if (url === '/api/config') return {ok:true,json:async()=>({mode:'review',submissions:true,transport:'json'})};
      assert.equal(url,'/api/solicitudes'); posted.push(JSON.parse(options.body));
      return {ok:true,status:201,json:async()=>({reference:'SOL-20261017-FAKE0001',mode:'review',summaryUrl:'/resumen.html#'+'a'.repeat(43),downloadUrl:'/resumen.html#'+'a'.repeat(43)+'&descargar=datos'})};
    }
  };
  vm.createContext(context);
  vm.runInContext(catalogueSource,context,{filename:'data/catalogo-v2.js'});
  vm.runInContext(requestSource,context,{filename:'solicitud.js'});
  return {element,nodes,storage,posted,next,back,form,sections,active:()=>active,
    draft:()=>JSON.parse(storage.get(draftKey(search))),
    // Promise callbacks from the mocked configuration endpoint, never a timer.
    ready:async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();}
  };
}

function savedDraft(names = ['etiqueta.jpg','diagnosis.pdf']) {
  return {key:'test-request-0123456789',step:2,contextQuery:'La pantalla no enciende',values:{
    clientType:'particular',customerName:'Persona de prueba',customerEmail:'prueba@example.invalid',customerPhone:'600000000',
    vehicleBrand:'Honda',vehicleModel:'Civic',intent:'consultation'
  },units:[{id:'pieza-prueba',catalogUid:'',componentKey:'abs',componentName:'ABS y ESP',manufacturer:'',reference:'',unknownReference:true,dtc:'',symptoms:'No funciona el componente',accessories:'',vehicleBrand:'',vehicleModel:'',files:[],missingFiles:names}]};
}
function withDraft(draft = savedDraft()) { return new Map([[draftKey(''),JSON.stringify(draft)]]); }
async function receiptMarkup(data) {
  const node={innerHTML:'',addEventListener(){},querySelectorAll(){return [];}};
  const context={document:{getElementById:()=>node},location:{hash:'#'+'a'.repeat(43)},
    fetch:async()=>({ok:true,json:async()=>data}),window:{},console};
  vm.createContext(context);vm.runInContext(receiptSource,context,{filename:'receipt.js'});
  for(let turn=0;turn<5;turn++)await Promise.resolve();
  return node.innerHTML;
}
let passed=0;
async function test(name, run) { await run();passed++;console.log('✓ '+name); }

(async()=>{
  await test('Varias recargas y guardados conservan los nombres de todos los archivos pendientes.', async()=>{
    const storage=withDraft();
    for(let reload=0;reload<3;reload++) {
      const view=fixture('',storage); await view.ready();
      assert.deepEqual(view.draft().units[0].missingFiles,['etiqueta.jpg','diagnosis.pdf']);
      assert.equal(view.sections[2].hidden,false);
      assert.match(view.element('reviewContent').innerHTML,/Faltan archivos de la pieza 1/);
      assert.match(view.element('reviewContent').innerHTML,/etiqueta\.jpg/);
      assert.match(view.element('reviewContent').innerHTML,/diagnosis\.pdf/);
      await view.form.emit('input'); await view.form.emit('change');
      assert.deepEqual(view.draft().units[0].missingFiles,['etiqueta.jpg','diagnosis.pdf']);
      assert.equal(view.draft().values.customerName,'Persona de prueba');
    }
  });

  await test('Enviar desde Revisión no pierde los adjuntos sin una decisión explícita.', async()=>{
    const view=fixture('',withDraft()); await view.ready();
    view.element('privacyRead').checked=true; view.element('conditionsRead').checked=true;
    await view.form.emit('submit');
    assert.equal(view.posted.length,0);
    assert.match(view.element('formErrors').innerHTML,/archivos pendientes/);
    assert.equal(view.element('review-missing-pieza-prueba').attributes['aria-invalid'],'true');
  });

  await test('Reponer un archivo no descarta los demás y una nueva recarga conserva ambos.', async()=>{
    const view=fixture('',withDraft()); await view.ready();
    const input=view.element('files-pieza-prueba');
    input.files=[{name:'etiqueta.jpg',type:'image/jpeg',size:150}]; await input.emit('change');
    const pendingHtml=view.element('unitsContainer').innerHTML.split('class="missing-files-notice"')[1];
    assert.ok(pendingHtml); assert.match(pendingHtml,/diagnosis\.pdf/);
    assert.equal(pendingHtml.includes('<li>etiqueta.jpg</li>'),false);
    assert.deepEqual(view.draft().units[0].missingFiles,['diagnosis.pdf','etiqueta.jpg']);
    const reloaded=fixture('',view.storage); await reloaded.ready();
    assert.deepEqual(reloaded.draft().units[0].missingFiles,['diagnosis.pdf','etiqueta.jpg']);
  });

  await test('Los archivos nuevos también se recuerdan como pendientes al recargar.', async()=>{
    const view=fixture('',withDraft(savedDraft([]))); await view.ready();
    const input=view.element('files-pieza-prueba');
    input.files=[{name:'pieza-nueva.jpg',type:'image/jpeg',size:200}]; await input.emit('change');
    assert.match(view.element('unitsContainer').innerHTML,/pieza-nueva\.jpg/);
    const reloaded=fixture('',view.storage); await reloaded.ready();
    assert.deepEqual(reloaded.draft().units[0].missingFiles,['pieza-nueva.jpg']);
    assert.match(reloaded.element('reviewContent').innerHTML,/Faltan archivos de la pieza 1/);
  });

  await test('Un archivo rechazado no se considera una reposición de un adjunto perdido.', async()=>{
    const view=fixture('',withDraft()); await view.ready();
    const input=view.element('files-pieza-prueba');
    input.files=[{name:'etiqueta.jpg',type:'image/jpeg',size:6*1024*1024}]; await input.emit('change');
    assert.deepEqual(view.draft().units[0].missingFiles,['etiqueta.jpg','diagnosis.pdf']);
    assert.match(view.element('formErrors').innerHTML,/cada archivo/);
  });

  await test('Descartar expresamente los pendientes permite enviar y no inventa adjuntos.', async()=>{
    const view=fixture('',withDraft()); await view.ready();
    const discard=view.element('reviewContent').querySelectorAll('[data-discard-missing]')[0];
    assert.ok(discard); await discard.emit('click');
    assert.deepEqual(view.draft().units[0].missingFiles,[]);
    assert.equal(view.element('reviewContent').innerHTML.includes('missing-files-notice'),false);
    view.element('privacyRead').checked=true; view.element('conditionsRead').checked=true;
    await view.form.emit('submit');
    assert.equal(view.posted.length,1);
    assert.deepEqual(view.posted[0].units[0].attachments,[]);
    assert.equal(view.posted[0].contextQuery,'La pantalla no enciende');
  });

  await test('Volver a adjuntar desde Revisión lleva al selector de la pieza correcta.', async()=>{
    const view=fixture('',withDraft()); await view.ready();
    const replace=view.element('reviewContent').querySelectorAll('[data-replace-missing]')[0];
    await replace.emit('click');
    assert.equal(view.sections[1].hidden,false);
    assert.equal(view.active(),'files-pieza-prueba');
  });

  await test('Los nombres se muestran como texto, sin insertar etiquetas HTML.', async()=>{
    const view=fixture('',withDraft(savedDraft(['<img src=x onerror=alert(1)>.jpg']))); await view.ready();
    assert.match(view.element('reviewContent').innerHTML,/&lt;img src=x onerror=alert\(1\)&gt;\.jpg/);
    assert.equal(view.element('reviewContent').innerHTML.includes('<img src=x'),false);
  });

  await test('La referencia de búsqueda se precarga editable y conserva su contexto para revisión.', async()=>{
    const query='?pieza=main-13285&consulta=94003-07010&referencia=94003-07010';
    const view=fixture(query); await view.ready();
    const draft=view.draft(),id=draft.units[0].id;
    assert.equal(draft.units[0].reference,'94003-07010');
    assert.equal(view.element('reference-'+id).disabled,false);
    assert.equal(draft.contextQuery,'94003-07010');
    view.element('reference-'+id).value='94003-07011';
    await view.element('reference-'+id).emit('input');
    const restored=fixture(query,view.storage); await restored.ready();
    assert.equal(restored.draft().units[0].reference,'94003-07011','El borrador corregido prevalece sobre el enlace inicial.');
    assert.equal(restored.draft().contextQuery,'94003-07010');
  });

  await test('Un código exacto va al campo de avería; una consulta libre no se convierte en referencia.', async()=>{
    const exact=fixture('?pieza=abs-3543&consulta=C2200&codigo=C2200'); await exact.ready();
    assert.equal(exact.draft().units[0].dtc,'C2200');
    assert.equal(exact.draft().units[0].reference,'');
    const free=fixture('?pieza=abs-3543&consulta=No+se+enciende'); await free.ready();
    assert.equal(free.draft().units[0].reference,''); assert.equal(free.draft().units[0].dtc,'');
    assert.equal(free.draft().contextQuery,'No se enciende');
  });

  await test('Modelo desconocido es una decisión explícita: envía blanco y un estado estructurado, conservando el texto del borrador.', async()=>{
    const draft=savedDraft([]);draft.step=0;
    const view=fixture('',withDraft(draft));await view.ready();
    view.element('vehicleModelUnknown').checked=true;await view.form.emit('change');
    assert.equal(view.element('vehicleModel').disabled,true);
    assert.equal(view.element('vehicleModel').value,'Civic');
    assert.equal(view.draft().values.vehicleModelUnknown,true);
    await view.next[0].emit('click');await view.next[1].emit('click');
    assert.equal(view.sections[2].hidden,false);
    assert.match(view.element('reviewContent').innerHTML,/Desconocido · necesitas ayuda para identificarlo/);
    view.element('privacyRead').checked=true;view.element('conditionsRead').checked=true;
    await view.form.emit('submit');
    assert.equal(view.posted.length,1);
    assert.equal(view.posted[0].vehicle.model,'');
    assert.equal(view.posted[0].vehicle.modelUnknown,true);
  });

  await test('Al restaurar y desmarcar modelo desconocido se recupera el nombre introducido sin sustituirlo por el catálogo.', async()=>{
    const draft=savedDraft([]);draft.step=0;draft.values.vehicleModelUnknown=true;draft.values.vehicleModel='Civic corregido';
    const view=fixture('',withDraft(draft));await view.ready();
    assert.equal(view.element('vehicleModel').disabled,true);
    view.element('vehicleModelUnknown').checked=false;await view.form.emit('change');
    assert.equal(view.element('vehicleModel').disabled,false);
    assert.equal(view.element('vehicleModel').value,'Civic corregido');
    const reloaded=fixture('',view.storage);await reloaded.ready();
    assert.equal(reloaded.element('vehicleModel').value,'Civic corregido');
    assert.equal(reloaded.element('vehicleModelUnknown').checked,false);
  });

  await test('Cambiar a envío no pierde datos ni permite saltarse el modelo pendiente desde un borrador en Revisión.', async()=>{
    const draft=savedDraft([]);draft.values.vehicleModelUnknown=true;
    Object.assign(draft.values,{taxId:'TEST-123',address:'Calle de prueba 1',city:'Madrid',postalCode:'28000',country:'España'});
    const view=fixture('',withDraft(draft));await view.ready();
    view.form.elements.intent.value='repair';await view.form.emit('change');
    view.element('privacyRead').checked=true;view.element('conditionsRead').checked=true;
    await view.form.emit('submit');
    assert.equal(view.posted.length,0);
    assert.equal(view.sections[0].hidden,false);
    assert.match(view.element('formErrors').innerHTML,/Para preparar el envío, indica el modelo/);
    assert.equal(view.element('vehicleModel').value,'Civic');
    assert.equal(view.element('customerEmail').value,'prueba@example.invalid');
    view.form.elements.intent.value='consultation';await view.form.emit('change');
    await view.next[0].emit('click');assert.equal(view.sections[1].hidden,false);
  });

  await test('El enlace de preparación de envío presenta su intención y consecuencia; el borrador conserva la elección posterior.', async()=>{
    const view=fixture('?intencion=envio');await view.ready();
    assert.equal(view.form.elements.intent.value,'repair');
    assert.equal(view.element('requestTitle').textContent,'Prepara la solicitud de envío.');
    assert.match(view.element('intentHelp').textContent,/no reserva una recogida/);
    view.form.elements.intent.value='consultation';await view.form.emit('change');
    const reload=fixture('?intencion=envio',view.storage);await reload.ready();
    assert.equal(reload.form.elements.intent.value,'consultation');
    assert.equal(reload.element('requestTitle').textContent,'Consulta tu pieza.');
  });

  await test('Los borradores anteriores con «Por identificar» se recuperan como modelo desconocido.', async()=>{
    const draft=savedDraft([]);draft.values.vehicleModel='Por identificar';
    const view=fixture('',withDraft(draft));await view.ready();
    assert.equal(view.element('vehicleModel').value,'');
    assert.equal(view.element('vehicleModelUnknown').checked,true);
    assert.equal(view.draft().values.vehicleModelUnknown,true);
  });

  await test('El resumen no presenta España por defecto como dirección de una consulta; conserva los datos de envío reales.', async()=>{
    const data={reference:'SOL-TEST',mode:'review',intent:'consultation',customer:{name:'Prueba',email:'test@example.invalid',phone:'600000000',country:'España',returnCountry:'España'},vehicle:{brand:'Honda',model:'',modelUnknown:true},units:[]};
    const consultation=await receiptMarkup(data);
    assert.match(consultation,/Modelo desconocido/);
    for(const label of ['Identificación fiscal','Dirección','Devolución'])assert.equal(consultation.includes('<dt>'+label+'</dt>'),false);
    assert.equal(consultation.includes('<dd class="pre">España</dd>'),false);
    Object.assign(data.customer,{taxId:'TEST-123',address:'Calle de prueba 1',city:'Madrid',postalCode:'28000'});
    const informed=await receiptMarkup(data);
    assert.match(informed,/<dt>Identificación fiscal<\/dt>/);assert.match(informed,/Calle de prueba 1, 28000, Madrid, España/);
    data.intent='repair';data.customer={...data.customer,address:'',city:'',postalCode:'',taxId:''};
    const shipping=await receiptMarkup(data);
    for(const label of ['Identificación fiscal','Dirección','Devolución'])assert.ok(shipping.includes('<dt>'+label+'</dt>'));
    assert.equal(shipping.includes('<dd class="pre">España</dd>'),false);
  });

  console.log('\n'+passed+' pruebas del controlador real de solicitud superadas.');
})().catch(error=>{console.error(error);process.exitCode=1;});
