/* Receipt access uses the URL fragment and an Authorization header, never a token in server URLs. */
'use strict';
(() => {
  const root = document.getElementById('receipt');
  if (!root) return;
  const [token, action] = location.hash.slice(1).split('&');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const headers = {Authorization: 'Bearer ' + token};
  const rows = values => '<dl>' + values.map(([label, value]) => '<dt>' + escape(label) + '</dt><dd class="pre">' + escape(value || 'No indicado') + '</dd>').join('') + '</dl>';
  const vehicleLabel = v => [v.brand,v.modelUnknown ? 'Modelo desconocido' : v.model].filter(Boolean).join(' · ');
  const address = (c, prefix = '') => {
    const parts = [c[prefix ? 'returnAddress' : 'address'],c[prefix ? 'returnPostalCode' : 'postalCode'],c[prefix ? 'returnCity' : 'city'],...(!prefix ? [c.province] : [])].filter(Boolean);
    // A default country alone is not a postal or return address.
    return parts.length ? [...parts,c[prefix ? 'returnCountry' : 'country']].filter(Boolean).join(', ') : '';
  };
  const download = (blob, name) => {
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
  const failure = message => { root.innerHTML = '<h1>No se ha podido abrir el resumen</h1><p>' + escape(message) + '</p><p><a href="/ayuda.html#contacto">Contactar con el laboratorio</a></p>'; };
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) { failure('Utiliza el enlace completo que apareció al registrar tu solicitud.'); return; }
  fetch('/api/resumen', {headers, cache:'no-store'}).then(async response => {
    if (!response.ok) throw new Error('El enlace no es válido o el servicio no está disponible.');
    return response.json();
  }).then(data => {
    const c = data.customer, v = data.vehicle;
    const tools = '<div class="receipt-tools"><a href="/">Volver a la web</a><button type="button" id="printReceipt">Imprimir o guardar PDF</button><button type="button" id="downloadReceipt">Descargar datos</button></div>';
    let html = tools + '<p class="receipt-brand">MENIGAR · Resumen de solicitud' + (data.mode === 'review' ? ' · Prueba' : '') + '</p><h1>' + escape(data.reference) + '</h1><p>' + (data.mode === 'review' ? 'Guardada en el entorno de pruebas. No se ha enviado al laboratorio.' : 'Solicitud registrada para su revisión por el equipo de MENIGAR.') + '</p>';
    const shipping=data.intent==='repair',postalAddress=address(c),returnAddress=c.returnDifferent?address(c,'return'):postalAddress;
    const shippingRows=[...(shipping||c.taxId?[['Identificación fiscal',c.taxId]]:[]),...(shipping||postalAddress?[['Dirección',postalAddress]]:[]),...(shipping||returnAddress?[['Devolución',returnAddress]]:[])];
    html += rows([['Tipo',shipping ? 'Preparar solicitud de envío' : 'Consultar mi pieza'],['Solicitante',c.name],['Persona de contacto',c.contact || c.name],['Correo y teléfono',c.email + ' · ' + c.phone],...shippingRows,['Vehículo',vehicleLabel(v)],['Matrícula / bastidor',(v.plate || 'No indicada') + ' / ' + (v.vin || 'No indicado')],['Año / kilómetros',(v.year || 'No indicado') + ' / ' + (v.km || 'No indicados')]]);
    data.units.forEach((unit,index) => {
      html += '<section class="piece"><h2>Pieza ' + (index+1) + ': ' + escape(unit.componentName) + '</h2>' + rows([['Identificador de unidad',data.reference + '-P' + (index+1)],['Fabricante',unit.manufacturer],['Referencia declarada',unit.reference || 'Por identificar'],['Código de avería',unit.dtc],['Qué ocurre',unit.symptoms],['Accesorios',unit.accessories],['Vehículo de esta pieza',(unit.vehicleBrand+' '+unit.vehicleModel).trim() || vehicleLabel(v)]]) + '<ul>' + unit.attachments.map(file => '<li><a href="#" data-file="' + escape(file.id) + '" data-name="' + escape(file.downloadName || file.name) + '">' + escape(file.name) + '</a></li>').join('') + '</ul></section>';
    });
    html += '<aside class="receipt-note"><h2>Antes de enviar tu pieza</h2><p>Esta referencia identifica tu solicitud; no es una orden de reparación. Espera la confirmación y las instrucciones del laboratorio antes de enviar material. El registro no confirma un diagnóstico, un presupuesto ni un pago.</p><p>Conserva este enlace privado para volver a consultar el resumen.</p></aside>';
    root.innerHTML = html;
    document.title = data.reference + ' · MENIGAR';
    document.getElementById('printReceipt').addEventListener('click', () => window.print());
    const downloadData = () => download(new Blob([JSON.stringify(data,null,2)], {type:'application/json'}), data.reference + '.json');
    document.getElementById('downloadReceipt').addEventListener('click', downloadData);
    root.querySelectorAll('[data-file]').forEach(link => link.addEventListener('click', async event => {
      event.preventDefault();
      try {
        const response = await fetch('/api/archivos/' + encodeURIComponent(link.dataset.file), {headers,cache:'no-store'});
        if (!response.ok) throw new Error();
        download(await response.blob(),link.dataset.name);
      } catch (_) { link.textContent = link.dataset.name + ' · No se ha podido descargar. Vuelve a intentarlo.'; }
    }));
    if (action === 'descargar=datos') downloadData();
  }).catch(error => failure(error.message));
})();
