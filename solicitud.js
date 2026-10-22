/* Request intake: runtime limits and transport, separate from workshop integration. */
'use strict';
(() => {
  const form = document.getElementById('requestForm');
  if (!form) return;
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const uuid = () => crypto.randomUUID ? crypto.randomUUID() : [...crypto.getRandomValues(new Uint8Array(16))].map(value=>value.toString(16).padStart(2,'0')).join('');
  const families = window.MENIGAR_FAMILIES || [];
  const catalogue = window.MENIGAR_CATALOG || [];
  const params = new URLSearchParams(location.search);
  // Each entry keeps its own draft so another service cannot replace its context.
  const draftKey = 'menigar-request-v2:' + params.toString();
  const receiptKey = draftKey + ':receipt';
  const customerFields = ['clientType','customerName','customerContact','customerEmail','customerPhone','taxId','address','city','province','postalCode','country','returnAddress','returnCity','returnPostalCode','returnCountry'];
  const vehicleFields = ['vehicleBrand','vehicleModel','vehiclePlate','vehicleVin','vehicleYear','vehicleKm'];
  let state = {key:uuid(),step:0,units:[],contextQuery:params.get('q') || params.get('consulta') || ''};
  let config = null;
  let submitting = false;
  let removed = null;
  const limits = () => ({maxFileBytes:config?.maxFileBytes || 5*1024*1024,maxFilesPerUnit:config?.maxFilesPerUnit || 5,maxTotalBytes:config?.maxTotalBytes || 15*1024*1024,maxTotalFiles:config?.maxTotalFiles || 50});
  const mb = bytes => Number((bytes/1024/1024).toFixed(2)).toLocaleString('es-ES');
  const vehicleLabel = vehicle => [vehicle.brand, vehicle.modelUnknown ? 'Modelo desconocido' : vehicle.model].filter(Boolean).join(' · ');
  const submitLabel = () => config?.mode === 'production' ? 'Enviar solicitud →' : 'Guardar solicitud de prueba →';
  const attachmentNotice = () => {
    const value=limits(),count=state.units.reduce((sum,item)=>sum+item.files.length,0);
    $('attachmentNotice').textContent=(count ? `${count} archivo(s) preparado(s). ` : '') + `Hasta ${value.maxFilesPerUnit} archivos por pieza, ${mb(value.maxFileBytes)} MB por archivo y ${mb(value.maxTotalBytes)} MB en total; máximo ${value.maxTotalFiles} archivos. JPG, PNG, WebP y PDF.`;
  };
  function fileErrors(units=state.units) {
    const value=limits(),errors=[],files=units.flatMap(unit=>unit.files);
    if(units.some(unit=>unit.files.length>value.maxFilesPerUnit))errors.push({message:`Puedes añadir hasta ${value.maxFilesPerUnit} archivos por pieza.`});
    files.forEach(file=>{
      if(!['image/jpeg','image/png','image/webp','application/pdf'].includes(file.type))errors.push({message:`${file.name}: utiliza JPG, PNG, WebP o PDF.`});
      if(file.size>value.maxFileBytes||!file.size)errors.push({message:`${file.name}: cada archivo debe ocupar entre 1 byte y ${mb(value.maxFileBytes)} MB.`});
    });
    if(files.length>value.maxTotalFiles)errors.push({message:`La solicitud admite hasta ${value.maxTotalFiles} archivos en total.`});
    if(files.reduce((sum,file)=>sum+file.size,0)>value.maxTotalBytes)errors.push({message:`El conjunto de archivos no puede superar ${mb(value.maxTotalBytes)} MB.`});
    return errors;
  }

  function blankUnit() {
    return {id:uuid(),catalogUid:'',componentKey:'',componentName:'',manufacturer:'',reference:'',unknownReference:false,dtc:'',symptoms:'',accessories:'',vehicleBrand:'',vehicleModel:'',files:[]};
  }

  function pendingFileNames(unit) {
    return [...new Set((Array.isArray(unit.missingFiles) ? unit.missingFiles : []).filter(name => typeof name === 'string' && name))];
  }

  function missingFilesMarkup(unit, index, review = false) {
    const names = pendingFileNames(unit);
    if (!names.length) return '';
    return `<div class="missing-files-notice" id="${review ? 'review-missing-' : 'missing-'}${escape(unit.id)}" tabindex="-1"><p><strong>Faltan archivos de la pieza ${index+1}</strong></p><p>Al recargar se han conservado los datos, pero estos archivos no están adjuntos:</p><ul>${names.map(name => `<li>${escape(name)}</li>`).join('')}</ul><p>Vuelve a adjuntarlos o elige continuar sin ellos.</p><div class="missing-file-actions">${review ? `<button type="button" class="review-edit" data-replace-missing="${escape(unit.id)}">Volver a adjuntar</button>` : ''}<button type="button" class="review-edit" data-discard-missing="${escape(unit.id)}">Continuar sin estos archivos</button></div></div>`;
  }

  function bindMissingFileActions(root) {
    root.querySelectorAll('[data-replace-missing]').forEach(button => button.addEventListener('click', () => {
      goStep(1);
      $('files-' + button.dataset.replaceMissing)?.focus();
    }));
    root.querySelectorAll('[data-discard-missing]').forEach(button => button.addEventListener('click', () => {
      captureUnits();
      const unit = state.units.find(item => item.id === button.dataset.discardMissing);
      if (!unit) return;
      unit.missingFiles = [];
      renderUnits();
      if (state.step === 2) renderReview();
      saveDraft(); attachmentNotice();
      (state.step === 2 ? $('reviewTitle') : $('files-' + unit.id))?.focus();
    }));
  }

  function showErrors(errors) {
    const box = $('formErrors');
    if (!errors.length) { box.hidden = true; box.innerHTML = ''; return; }
    box.innerHTML = '<p><strong>Revisa estos datos para continuar:</strong></p><ul>' + errors.map(item => `<li>${item.id ? `<a href="#${escape(item.id)}">${escape(item.message)}</a>` : escape(item.message)}</li>`).join('') + '</ul>';
    box.hidden = false;
    box.focus();
    box.querySelectorAll('a').forEach(link => link.addEventListener('click', event => {
      event.preventDefault();
      $(link.hash.slice(1))?.focus();
    }));
  }

  function updateConditionalFields() {
    const business = $('clientType').value === 'taller';
    $('contactField').hidden = !business;
    $('customerContact').required = business;
    const shipping = form.elements.intent.value === 'repair';
    const modelUnknown = $('vehicleModelUnknown').checked;
    $('vehicleModel').disabled = modelUnknown;
    $('vehicleModel').required = !modelUnknown;
    $('vehicleModelRequired').hidden = modelUnknown;
    $('vehicleModelHelp').textContent = shipping
      ? 'Para preparar el envío necesitamos identificar el modelo. Si todavía no lo sabes, elige «Consultar mi pieza» y te ayudaremos.'
      : modelUnknown ? 'Lo indicaremos como modelo desconocido. Puedes añadir fotos de la pieza o su etiqueta en el siguiente paso.' : 'Si no lo conoces, márcalo y continúa la consulta con la información que tengas.';
    $('requestEyebrow').textContent = shipping ? 'Prepara tu envío' : 'Consulta tu pieza';
    $('requestTitle').textContent = shipping ? 'Prepara la solicitud de envío.' : 'Consulta tu pieza.';
    $('requestIntro').textContent = shipping
      ? 'Reúne el contacto, los datos del vehículo y las piezas que quieres enviar. Podrás revisar e imprimir el resumen; espera las instrucciones del laboratorio antes de enviarlas.'
      : 'Cuéntanos qué ocurre para que podamos orientarte. Puedes aportar fotos si no conoces la referencia o el modelo.';
    $('intentHelp').textContent = shipping
      ? 'Preparar esta solicitud no reserva una recogida ni autoriza una reparación. Espera la confirmación del laboratorio.'
      : 'Una consulta no autoriza una reparación ni prepara una recogida.';
    document.title = (shipping ? 'Preparar solicitud de envío' : 'Consultar mi pieza') + ' · MENIGAR';
    $('shippingFields').hidden = !shipping;
    ['taxId','address','city','postalCode','country'].forEach(id => $(id).required = shipping);
    const different = shipping && $('returnDifferent').checked;
    $('returnFields').hidden = !different;
    ['returnAddress','returnCity','returnPostalCode','returnCountry'].forEach(id => $(id).required = different);
  }

  function captureUnits() {
    state.units.forEach(unit => {
      const card = $('unit-' + unit.id);
      if (!card) return;
      card.querySelectorAll('[data-unit-field]').forEach(input => {
        unit[input.dataset.unitField] = input.type === 'checkbox' ? input.checked : input.value;
      });
      const family = families.find(item => item.key === unit.componentKey);
      unit.componentName = family?.name || unit.customComponent || (unit.componentKey === 'otro' ? '' : unit.componentName);
    });
  }

  function saveDraft() {
    captureUnits();
    const values = {};
    [...customerFields,...vehicleFields].forEach(id => values[id] = $(id).value);
    values.intent = form.elements.intent.value;
    values.returnDifferent = $('returnDifferent').checked;
    values.vehicleModelUnknown = $('vehicleModelUnknown').checked;
    // File bytes cannot survive a reload. Keep both already-missing names and
    // names of current attachments until they are reattached or discarded.
    const draft = {...state,values,units:state.units.map(unit => ({...unit,files:[],missingFiles:[...new Set([...pendingFileNames(unit),...unit.files.map(file => file.name)])]}))};
    try { sessionStorage.setItem(draftKey, JSON.stringify(draft)); } catch (_) { /* Input remains in memory if storage is unavailable. */ }
  }

  function renderUnits() {
    $('unitsContainer').innerHTML = state.units.map((unit,index) => {
      const options = families.map(family => `<option value="${escape(family.key)}" ${unit.componentKey===family.key?'selected':''}>${escape(family.name)}</option>`).join('');
      return `<article class="unit-card" id="unit-${escape(unit.id)}"><div class="unit-heading"><h3>Pieza ${index+1}</h3>${state.units.length>1?`<button class="unit-remove" type="button" data-remove-unit="${escape(unit.id)}">Quitar pieza ${index+1}</button>`:''}</div><div class="unit-body">
      ${unit.catalogUid?'<p class="unit-origin">Servicio seleccionado en el catálogo. Puedes revisar y corregir sus datos.</p>':''}
      <div class="form-grid"><div class="field"><label for="family-${unit.id}">Tipo de pieza *</label><select id="family-${unit.id}" data-unit-field="componentKey"><option value="">Selecciona una pieza</option>${options}<option value="otro" ${unit.componentKey==='otro'?'selected':''}>Otra pieza / por identificar</option></select></div><div class="field"><label for="manufacturer-${unit.id}">Fabricante de la pieza, si lo conoces</label><input id="manufacturer-${unit.id}" data-unit-field="manufacturer" maxlength="120" value="${escape(unit.manufacturer)}" placeholder="Puede ser distinto de la marca del coche"></div></div>
      <div class="field custom-component" ${unit.componentKey==='otro'?'':'hidden'}><label for="custom-${unit.id}">¿De qué pieza se trata? *</label><input id="custom-${unit.id}" data-unit-field="customComponent" maxlength="180" value="${escape(unit.customComponent || '')}"></div>
      <div class="field"><label for="reference-${unit.id}">Referencia de la pieza *</label><input id="reference-${unit.id}" data-unit-field="reference" maxlength="180" value="${escape(unit.reference)}" ${unit.unknownReference?'disabled':''} placeholder="Tal como aparece en su etiqueta"><label class="checkbox-field"><input type="checkbox" data-unit-field="unknownReference" ${unit.unknownReference?'checked':''}>No sé identificar la referencia</label></div>
      <details class="reference-help"><summary>¿Dónde encuentro la referencia?</summary><figure class="reference-illustration"><img src="/assets/ayuda-referencia.svg" alt="Ejemplo ilustrativo: la referencia está en la etiqueta de la pieza; el código de avería se obtiene de un informe de diagnosis. Son datos diferentes." width="680" height="830" loading="lazy"><figcaption>Ejemplo ilustrativo. El aspecto y la posición de las etiquetas varían. <a href="/assets/ayuda-referencia.svg" target="_blank" rel="noopener">Ampliar esquema ↗</a></figcaption></figure><p>Busca la etiqueta o el grabado del propio componente. Puede incluir letras, números, puntos y guiones. Cópialo tal como aparece o adjunta una foto nítida de toda la etiqueta.</p><p>El código de avería procede del equipo o informe de diagnosis; se introduce en el siguiente campo. No es la matrícula ni el número de bastidor.</p></details>
      <div class="field"><label for="dtc-${unit.id}">Código de avería, si lo tienes</label><input id="dtc-${unit.id}" data-unit-field="dtc" maxlength="180" value="${escape(unit.dtc)}" placeholder="Código que aparece en la diagnosis"></div>
      <div class="field"><label for="symptoms-${unit.id}">¿Qué ocurre y cuándo? *</label><textarea id="symptoms-${unit.id}" data-unit-field="symptoms" rows="4" maxlength="2000" placeholder="Describe el fallo y si sucede siempre o de forma intermitente"${unit.symptomFromCatalog ? ` aria-describedby="symptom-help-${unit.id}"` : ''}>${escape(unit.symptoms)}</textarea>${unit.symptomFromCatalog ? `<p class="input-help" id="symptom-help-${unit.id}">Has elegido un fallo del catálogo. Ajusta esta descripción a lo que le ocurre a tu pieza.</p>` : ''}</div>
      <div class="field"><label for="accessories-${unit.id}">Accesorios que acompañan a esta pieza</label><textarea id="accessories-${unit.id}" data-unit-field="accessories" rows="2" maxlength="2000" placeholder="Llaves, cables, carcasas u otros elementos; indica cantidad si procede">${escape(unit.accessories)}</textarea></div>
      <details class="optional-details"><summary>Esta pieza corresponde a otro vehículo</summary><div class="form-grid"><div class="field"><label for="ubrand-${unit.id}">Marca de ese vehículo</label><input id="ubrand-${unit.id}" data-unit-field="vehicleBrand" maxlength="120" value="${escape(unit.vehicleBrand)}"></div><div class="field"><label for="umodel-${unit.id}">Modelo de ese vehículo</label><input id="umodel-${unit.id}" data-unit-field="vehicleModel" maxlength="120" value="${escape(unit.vehicleModel)}"></div></div></details>
      <div class="upload-zone"><label for="files-${unit.id}">Fotos e informes de esta pieza</label><p class="input-help">Etiqueta, pieza e informe de diagnosis. Solo archivos relacionados con este caso.</p><input id="files-${unit.id}" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" multiple data-unit-files="${unit.id}"><ul class="file-list" id="files-list-${unit.id}">${unit.files.map((file,i)=>`<li><span>${escape(file.name)} · ${(file.size/1024/1024).toFixed(2)} MB</span><button type="button" class="file-remove" data-remove-file="${unit.id}" data-file-index="${i}" aria-label="Quitar ${escape(file.name)}">Quitar</button></li>`).join('')}</ul>${missingFilesMarkup(unit,index)}</div>
      </div></article>`;
    }).join('');
    $('unitsContainer').querySelectorAll('[data-unit-field]').forEach(input => {
      input.addEventListener('input', () => {
        if (input.dataset.unitField === 'unknownReference') {
          const card = input.closest('.unit-card');
          card.querySelector('[data-unit-field="reference"]').disabled = input.checked;
        }
        if (input.dataset.unitField === 'componentKey') {
          input.closest('.unit-card').querySelector('.custom-component').hidden = input.value !== 'otro';
        }
        input.removeAttribute('aria-invalid');
        saveDraft();
      });
    });
    $('unitsContainer').querySelectorAll('[data-remove-unit]').forEach(button => button.addEventListener('click', () => {
      captureUnits();
      const index = state.units.findIndex(unit => unit.id === button.dataset.removeUnit);
      removed = {unit:state.units[index],index};
      state.units.splice(index,1);
      renderUnits();
      const undo = document.createElement('div');
      undo.className = 'undo-notice'; undo.setAttribute('role','status');
      undo.innerHTML = 'Se ha quitado la pieza. <button class="review-edit" type="button">Deshacer</button>';
      undo.querySelector('button').addEventListener('click', () => {captureUnits(); state.units.splice(removed.index,0,removed.unit); removed=null; renderUnits(); saveDraft();});
      $('unitsContainer').prepend(undo);
      saveDraft();
    }));
    $('unitsContainer').querySelectorAll('[data-unit-files]').forEach(input => input.addEventListener('change', () => {
      captureUnits();
      const unit = state.units.find(item => item.id === input.dataset.unitFiles);
      const incoming = Array.from(input.files);
      const errors = fileErrors(state.units.map(item=>item===unit ? {...item,files:[...item.files,...incoming]} : item));
      if (errors.length) {input.value=''; showErrors(errors); return;}
      unit.files.push(...incoming);
      // Selecting one replacement must not silently discard other missing files.
      unit.missingFiles=pendingFileNames(unit).filter(name => !incoming.some(file => file.name === name));
      renderUnits(); saveDraft();
      attachmentNotice();
    }));
    $('unitsContainer').querySelectorAll('[data-remove-file]').forEach(button => button.addEventListener('click', () => {
      captureUnits();
      state.units.find(unit=>unit.id===button.dataset.removeFile).files.splice(Number(button.dataset.fileIndex),1);
      renderUnits(); saveDraft(); attachmentNotice();
    }));
    $('addUnit').disabled = state.units.length >= 10;
    bindMissingFileActions($('unitsContainer'));
  }

  function validateStep(step) {
    const errors=[];
    if(step>0)errors.push(...fileErrors());
    if (step===0) {
      form.querySelectorAll('[data-step="0"] input').forEach(input => {
        if (input.disabled || input.type === 'radio' || input.type === 'checkbox') return;
        const label = form.querySelector(`label[for="${input.id}"]`)?.textContent.replace('*','').trim() || 'este dato';
        if (input.required && !input.value.trim()) errors.push({id:input.id,message:'Completa ' + label + '.'});
        else if (input.type==='email' && !input.validity.valid) errors.push({id:input.id,message:'Indica un correo electrónico válido.'});
      });
      if ($('customerPhone').value && $('customerPhone').value.replace(/\D/g,'').length<7) errors.push({id:'customerPhone',message:'Revisa el teléfono de contacto.'});
      if (form.elements.intent.value === 'repair' && $('vehicleModelUnknown').checked) errors.push({id:'vehicleModelUnknown',message:'Para preparar el envío, indica el modelo. Si no lo conoces, elige «Consultar mi pieza» para que te ayudemos.'});
    }
    if (step===1) {
      captureUnits();
      state.units.forEach((unit,index)=>{
        if (!unit.componentKey) errors.push({id:'family-'+unit.id,message:`Selecciona el tipo de la pieza ${index+1}.`});
        if (unit.componentKey==='otro' && !unit.customComponent?.trim()) errors.push({id:'custom-'+unit.id,message:`Describe qué es la pieza ${index+1}.`});
        if (!unit.reference.trim() && !unit.unknownReference) errors.push({id:'reference-'+unit.id,message:`Indica la referencia de la pieza ${index+1} o marca que no la conoces.`});
        if (unit.symptoms.trim().length<8) errors.push({id:'symptoms-'+unit.id,message:`Describe con algo más de detalle qué ocurre en la pieza ${index+1}.`});
      });
    }
    if (step===2) {
      state.units.forEach((unit,index) => {
        if (pendingFileNames(unit).length) errors.push({id:'review-missing-'+unit.id,message:`Pieza ${index+1}: vuelve a adjuntar los archivos pendientes o elige continuar sin ellos.`});
      });
      if (!$('privacyRead').checked) errors.push({id:'privacyRead',message:'Revisa la información de privacidad.'});
      if (!$('conditionsRead').checked) errors.push({id:'conditionsRead',message:'Revisa las condiciones de la solicitud.'});
    }
    errors.forEach(error=>$(error.id)?.setAttribute('aria-invalid','true'));
    showErrors(errors);
    return !errors.length;
  }

  function getData() {
    captureUnits();
    return {
      idempotencyKey:state.key,intent:form.elements.intent.value,contextQuery:state.contextQuery,website:$('requestWebsite')?.value || '',
      customer:{type:$('clientType').value,name:$('customerName').value,contact:$('customerContact').value,email:$('customerEmail').value,phone:$('customerPhone').value,taxId:$('taxId').value,address:$('address').value,city:$('city').value,province:$('province').value,postalCode:$('postalCode').value,country:$('country').value,returnDifferent:$('returnDifferent').checked,returnAddress:$('returnAddress').value,returnCity:$('returnCity').value,returnPostalCode:$('returnPostalCode').value,returnCountry:$('returnCountry').value},
      vehicle:{brand:$('vehicleBrand').value,model:$('vehicleModelUnknown').checked?'':$('vehicleModel').value,modelUnknown:$('vehicleModelUnknown').checked,plate:$('vehiclePlate').value,vin:$('vehicleVin').value,year:$('vehicleYear').value,km:$('vehicleKm').value},
      units:state.units.map(({id,files,missingFiles,customComponent,...unit})=>({...unit,reference:unit.unknownReference?'':unit.reference,attachments:[]})),
      acceptance:{privacyRead:$('privacyRead').checked,conditionsRead:$('conditionsRead').checked,version:config?.termsVersion || 'review-2026-10-13'}
    };
  }

  function renderReview() {
    const data=getData();
    const block=(title,rows,step)=>`<section class="review-block"><h3>${escape(title)}</h3><dl>${rows.map(([key,value])=>`<dt>${escape(key)}</dt><dd>${escape(value||'No indicado')}</dd>`).join('')}</dl><button type="button" class="review-edit" data-edit-step="${step}">Editar ${escape(title.toLowerCase())} →</button></section>`;
    let markup=block('Contacto',[['Solicitante',data.customer.name],['Contacto',data.customer.contact||data.customer.name],['Email',data.customer.email],['Teléfono',data.customer.phone],['Tipo',data.intent==='repair'?'Preparar solicitud de envío':'Consultar mi pieza']],0);
    if(data.contextQuery)markup+=`<section class="review-block"><h3>Tu búsqueda</h3><p>${escape(data.contextQuery)}</p><p class="input-help">Es el texto que escribiste al buscar. Comprueba los datos de la pieza antes de enviar.</p></section>`;
    markup+=block('Vehículo',[['Marca',data.vehicle.brand],['Modelo',data.vehicle.modelUnknown?'Desconocido · necesitas ayuda para identificarlo':data.vehicle.model],['Matrícula',data.vehicle.plate],['Bastidor',data.vehicle.vin],['Año',data.vehicle.year],['Kilómetros',data.vehicle.km]],0);
    if(data.intent==='repair')markup+=block('Datos de devolución',[['Identificación fiscal',data.customer.taxId],['Dirección',[data.customer.address,data.customer.postalCode,data.customer.city,data.customer.province,data.customer.country].filter(Boolean).join(', ')],...(data.customer.returnDifferent?[['Devolución a',[data.customer.returnAddress,data.customer.returnPostalCode,data.customer.returnCity,data.customer.returnCountry].filter(Boolean).join(', ')]]:[])],0);
    data.units.forEach((unit,index)=>markup+=block('Pieza '+(index+1),[['Componente',unit.componentName],['Fabricante',unit.manufacturer],['Referencia que indicas',unit.reference||'No identificada'],['Vehículo de esta pieza',(unit.vehicleBrand+' '+unit.vehicleModel).trim()||vehicleLabel(data.vehicle)],['Código de avería que indicas',unit.dtc],['Qué ocurre',unit.symptoms],['Accesorios',unit.accessories],['Archivos adjuntos',state.units[index].files.map(file=>file.name).join(', ')||'Sin archivos']],1)+missingFilesMarkup(state.units[index],index,true));
    $('reviewContent').innerHTML=markup;
    $('reviewContent').querySelectorAll('[data-edit-step]').forEach(button=>button.addEventListener('click',()=>goStep(Number(button.dataset.editStep))));
    bindMissingFileActions($('reviewContent'));
  }

  function goStep(step,focus=true) {
    state.step=step;
    document.querySelectorAll('.request-step').forEach(section=>section.hidden=Number(section.dataset.step)!==step);
    document.querySelectorAll('[data-step-label]').forEach(label=>{
      if(Number(label.dataset.stepLabel)===step)label.setAttribute('aria-current','step');else label.removeAttribute('aria-current');
    });
    $('formErrors').hidden=true;
    if(step===2)renderReview();
    if(focus)form.querySelector(`[data-step="${step}"] h2`).focus({preventScroll:false});
    saveDraft();
  }

  form.querySelectorAll('[data-next]').forEach(button=>button.addEventListener('click',()=>{if(validateStep(state.step))goStep(state.step+1);}));
  form.querySelectorAll('[data-back]').forEach(button=>button.addEventListener('click',()=>{captureUnits();goStep(state.step-1);}));
  form.addEventListener('input',event=>{state.pending=false;event.target.removeAttribute('aria-invalid');updateConditionalFields();saveDraft();});
  form.addEventListener('change',()=>{updateConditionalFields();saveDraft();});
  $('addUnit').addEventListener('click',()=>{captureUnits();state.units.push(blankUnit());renderUnits();saveDraft();$('family-'+state.units.at(-1).id)?.focus();});

  const readFile = file => new Promise((resolve,reject)=>{
    const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('No se ha podido leer '+file.name));reader.readAsDataURL(file);
  });

  function showConfirmation(result, units, focus = true) {
    $('confirmationReference').textContent=result.reference;
    $('confirmationUnits').innerHTML='<ul>'+units.map((unit,i)=>`<li>Pieza ${i+1}: ${escape(unit.componentName)} · ${escape(unit.reference||'por identificar')}</li>`).join('')+'</ul>';
    $('summaryLink').href=result.summaryUrl;$('downloadLink').href=result.downloadUrl;
    if(result.downloadUrl.startsWith('/resumen.html#')){$('downloadLink').removeAttribute('download');$('downloadLink').target='_blank';$('downloadLink').rel='noopener';}
    else{$('downloadLink').download=result.reference+'.json';$('downloadLink').removeAttribute('target');}
    const production=result.mode==='production';
    $('confirmationKicker').textContent=production?'Solicitud registrada':'Solicitud guardada en esta vista previa';
    $('confirmationMessage').textContent=production?'Tus datos y archivos se han registrado para que el equipo de MENIGAR revise la solicitud.':'Los datos y archivos se han guardado en el entorno de pruebas. No se ha enviado un correo ni una orden al laboratorio.';
    $('confirmationNext').textContent=production?'Esta referencia identifica tu solicitud; no es una orden de reparación. Espera la confirmación y las instrucciones del laboratorio antes de enviar material.':'Esta referencia identifica la solicitud de prueba. Espera la confirmación y las instrucciones del laboratorio antes de enviar material.';
    $('requestWorkspace').hidden=true;$('confirmation').hidden=false;
    if(focus)$('confirmation').focus();
  }

  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(submitting)return;
    // Changing intention or restoring a draft must never bypass earlier requirements.
    for(const step of [0,1,2]) if(!validateStep(step)){goStep(step);validateStep(step);return;}
    if(!config?.submissions){showErrors([{message:'El guardado no está disponible en esta vista. Los datos siguen en el formulario.'}]);return;}
    submitting=true;state.pending=true;saveDraft();$('submitRequest').disabled=true;$('submitRequest').textContent=config.mode==='production'?'Enviando solicitud…':'Guardando solicitud…';
    try{
      const data=getData();
      let body,headers={};
      if(config.transport==='multipart'){
        body=new FormData();
        data.units.forEach((unit,i)=>{unit.attachments=state.units[i].files.map((file,j)=>{const uploadKey=`u${i}a${j}`;body.append(`files[${uploadKey}]`,file,file.name);return {uploadKey,name:file.name,mime:file.type,size:file.size};});});
        body.append('payload',JSON.stringify(data));headers['X-CSRF-Token']=config.csrfToken;
      }else{
        for(let i=0;i<data.units.length;i++)data.units[i].attachments=await Promise.all(state.units[i].files.map(async file=>({name:file.name,mime:file.type,size:file.size,data:await readFile(file)})));
        body=JSON.stringify(data);headers['Content-Type']='application/json';
      }
      let response=await fetch('/api/solicitudes',{method:'POST',headers,body});
      if(response.status===419&&config.transport==='multipart'){
        const refresh=await fetch('/api/config',{cache:'no-store'});if(refresh.ok){config=await refresh.json();headers['X-CSRF-Token']=config.csrfToken;response=await fetch('/api/solicitudes',{method:'POST',headers,body});}
      }
      let result;try{result=await response.json();}catch(_){throw new Error('No se pudo completar el envío. Conserva los datos y vuelve a intentarlo.');}
      if(!response.ok)throw new Error(result.error||'No se pudo guardar la solicitud.');
      showConfirmation(result,data.units);
      try{
        sessionStorage.removeItem(draftKey);
        sessionStorage.setItem(receiptKey,JSON.stringify({result,units:data.units.map(unit=>({componentName:unit.componentName,reference:unit.reference}))}));
      }catch(_){}
    }catch(error){showErrors([{message:error.message||'No se pudo guardar. Conserva los datos y vuelve a intentarlo.'}]);}
    finally{submitting=false;$('submitRequest').disabled=!config?.submissions;$('submitRequest').textContent=submitLabel();}
  });

  $('newRequest').addEventListener('click',()=>{
    try{sessionStorage.removeItem(receiptKey);}catch(_){}
    form.reset();state={key:uuid(),step:0,units:[blankUnit()],contextQuery:''};removed=null;
    $('confirmation').hidden=true;$('requestWorkspace').hidden=false;updateConditionalFields();renderUnits();goStep(0);
  });

  let restored=false;
  try{
    const draft=JSON.parse(sessionStorage.getItem(draftKey)||'null');
    if(draft?.units?.length&&draft.values){
      state={...draft,units:draft.units.map(unit=>({...unit,files:[]}))};
      [...customerFields,...vehicleFields].forEach(id=>{if(draft.values[id]!==undefined)$(id).value=draft.values[id];});
      form.elements.intent.value=draft.values.intent||'consultation';$('returnDifferent').checked=!!draft.values.returnDifferent;
      $('vehicleModelUnknown').checked=draft.values.vehicleModelUnknown === true;
      // Older drafts used a filler string; recover it as an explicit unknown value.
      if (/^por identificar$/i.test($('vehicleModel').value.trim())) {$('vehicleModel').value='';$('vehicleModelUnknown').checked=true;}
      restored=true;
    }
  }catch(_){}
  if(!restored){
    const unit=blankUnit();const selected=catalogue.find(item=>item.uid===params.get('pieza'));
    if(selected){unit.catalogUid=selected.uid;unit.componentKey=selected.componentKey;unit.componentName=selected.componentName;$('vehicleBrand').value=selected.brand||'';$('vehicleModel').value=selected.model||'';}
    if(params.get('marca'))$('vehicleBrand').value=params.get('marca');if(params.get('modelo'))$('vehicleModel').value=params.get('modelo');
    if(params.get('intencion')==='envio'||params.get('intent')==='repair')form.elements.intent.value='repair';
    if(params.get('tipo')==='taller'||params.get('cliente')==='empresa')$('clientType').value='taller';
    if(!selected&&params.get('familia')){const family=families.find(item=>item.key===params.get('familia'));if(family){unit.componentKey=family.key;unit.componentName=family.name;}}
    if(params.get('referencia'))unit.reference=params.get('referencia');if(params.get('codigo'))unit.dtc=params.get('codigo');
    if(params.get('sintoma')){unit.symptoms=params.get('sintoma').slice(0,2000);unit.symptomFromCatalog=true;}
    state.units=[unit];
  }
  $('vehicleBrands').innerHTML=[...new Set(catalogue.map(item=>item.brand).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'es')).map(brand=>`<option value="${escape(brand)}"></option>`).join('');
  updateConditionalFields();renderUnits();goStep(Math.min(Number(state.step)||0,2),false);
  try{
    const receipt=JSON.parse(sessionStorage.getItem(receiptKey)||'null');
    if(receipt?.result?.reference&&Array.isArray(receipt.units)&&
       (/^\/api\/solicitudes\/[A-Za-z0-9_-]+\/resumen$/.test(receipt.result.summaryUrl)||/^\/resumen\.html#[A-Za-z0-9_-]{43}$/.test(receipt.result.summaryUrl))&&
       (/^\/api\/solicitudes\/[A-Za-z0-9_-]+\/datos$/.test(receipt.result.downloadUrl)||/^\/resumen\.html#[A-Za-z0-9_-]{43}&descargar=datos$/.test(receipt.result.downloadUrl))){
      showConfirmation(receipt.result,receipt.units,false);sessionStorage.removeItem(draftKey);
    }
  }catch(_){}
  fetch('/api/config').then(response=>{if(!response.ok)throw new Error();return response.json();}).then(value=>{
    config=value;
    const production=value.mode==='production';
    $('reviewNotice').textContent=production?'Tu solicitud se enviará al equipo de MENIGAR para su revisión.':'Vista previa · Las solicitudes se guardan en el entorno de pruebas. No se envían al laboratorio.';
    $('saveNote').textContent=production?'Al enviar se registrarán tus datos y archivos para que el equipo revise el caso.':'La solicitud de esta vista previa se guardará únicamente en el entorno de pruebas.';
    if(!value.submissions)$('saveNote').textContent='El envío no está disponible. Conserva los datos y contacta con el laboratorio.';
    $('submitRequest').disabled=!value.submissions;$('submitRequest').textContent=submitLabel();attachmentNotice();
    if(restored&&state.pending&&value.recovery){
      fetch('/api/recuperar',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':value.csrfToken},body:JSON.stringify({idempotencyKey:state.key})}).then(async response=>{if(!response.ok)return;const result=await response.json();showConfirmation(result,result.units||[]);try{sessionStorage.setItem(receiptKey,JSON.stringify({result,units:result.units||[]}));sessionStorage.removeItem(draftKey);}catch(_){} }).catch(()=>{});
    }
  }).catch(()=>{
    $('reviewNotice').textContent='Vista previa de diseño · El guardado no está disponible. Puedes completar y revisar los datos.';
    $('saveNote').textContent='Esta vista permite revisar el formulario, pero no enviar solicitudes.';$('submitRequest').disabled=true;
  });
})();
