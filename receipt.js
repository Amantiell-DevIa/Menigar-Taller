/* Receipt access uses the URL fragment and an Authorization header, never a token in server URLs. */
'use strict';
(() => {
  const root = document.getElementById('receipt');
  if (!root) return;
  // Folder this script is served from ('' at the site root, '/pruebas' in the test install).
  const apiBase = (() => { try { const src = document.currentScript && document.currentScript.src; return src ? new URL('.', src).pathname.replace(/\/$/, '') : ''; } catch (_) { return ''; } })();
  const [token, action] = location.hash.slice(1).split('&');
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const headers = {Authorization: 'Bearer ' + token, 'X-Receipt-Token': token};
  const rows = (values, cls = 'doc-dl') => '<dl class="' + cls + '">' + values.map(([label, value]) => '<dt>' + escape(label) + '</dt><dd class="pre">' + escape(value || 'No indicado') + '</dd>').join('') + '</dl>';
  const vehicleLabel = v => [v.brand, v.modelUnknown ? 'Modelo desconocido' : v.model].filter(Boolean).join(' · ');
  const formatDate = iso => {
    const raw = String(iso || '').slice(0, 10);
    const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : (raw || 'Hoy');
  };
  const address = (c, prefix = '') => {
    const parts = [c[prefix ? 'returnAddress' : 'address'],c[prefix ? 'returnPostalCode' : 'postalCode'],c[prefix ? 'returnCity' : 'city'],...(!prefix ? [c.province] : [])].filter(Boolean);
    // A default country alone is not a postal or return address.
    return parts.length ? [...parts,c[prefix ? 'returnCountry' : 'country']].filter(Boolean).join(', ') : '';
  };
  const download = (blob, name) => {
    const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
  };
  const failure = message => { root.innerHTML = '<h1>No se ha podido abrir el resumen</h1><p>' + escape(message) + '</p><p>Si lo necesitas, llama al laboratorio: <a href="tel:+34916622781">91 662 27 81</a>.</p>'; };
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) { failure('Utiliza el enlace completo que apareció al registrar tu solicitud.'); return; }
  fetch(apiBase + '/api/resumen', {headers, cache:'no-store'}).then(async response => {
    if (!response.ok) throw new Error('El enlace no es válido o el servicio no está disponible.');
    return response.json();
  }).then(data => {
    const c = data.customer, v = data.vehicle;
    const shipping = data.intent === 'repair';
    const unitsCount = Array.isArray(data.units) ? data.units.length : 0;
    const logoSrc = (apiBase || '') + '/assets/marca/menigar-logo-1x.webp';

    // Top bar (screen only, never printed in customer PDF)
    let html = '<div class="receipt-tools no-print">'
      + '<a class="receipt-back" href="' + (apiBase || '/') + '">← Volver a la web</a>'
      + '<div class="receipt-tools-actions">'
      + '<button type="button" id="printReceipt" class="btn-print-main">' + (shipping ? 'Imprimir o guardar en PDF (hoja y etiqueta)' : 'Imprimir o guardar en PDF') + '</button>'
      + '</div>'
      + '</div>';

    // A test document must never pass for a real one, on screen or on paper.
    if (data.mode !== 'production') {
      html += '<p class="doc-test-banner" role="note"><strong>PRUEBA.</strong> Documento del formulario de prueba de MENIGAR: no envíes ninguna pieza con él.</p>';
    }

    // Official Printable Document Sheet
    html += '<article class="doc-sheet">'
      + '<header class="doc-header">'
      + '<div class="doc-brand-col">'
      + '<img class="doc-logo" src="' + escape(logoSrc) + '" width="220" height="33" alt="MENIGAR">'
      + '<p class="doc-company"><strong>Desarrollos Digitales Menigar, S.L.</strong> · Laboratorio de Electrónica del Automóvil<br>'
      + 'C/ José Echegaray 16, Edificio A1 · Planta 2.ª · Nave 4 · 28100 Alcobendas (Madrid)<br>'
      + 'Tel.: <strong>91 662 27 81</strong> · informacion@menigar.com · www.menigar.com</p>'
      + '</div>'
      + '<div class="doc-ref-box">'
      + '<span class="doc-ref-type">' + (shipping ? 'HOJA DE ENTRADA A LABORATORIO' : 'RESGUARDO DE CONSULTA TÉCNICA') + '</span>'
      + '<h1>' + escape(data.reference) + '</h1>'
      + '<div class="doc-ref-meta">'
      + '<span>Fecha: <strong>' + escape(formatDate(data.createdAt)) + '</strong></span>'
      + '<span>Unidades: <strong>' + unitsCount + (unitsCount === 1 ? ' pieza' : ' piezas') + '</strong></span>'
      + '</div>'
      + '</div>'
      + '</header>';

    if (shipping) {
      html += '<section class="doc-steps" aria-label="Pasos para preparar tu paquete">'
        + '<div class="doc-step"><span>1</span><div><strong>Introduce esta hoja en la caja</strong><p>Coloca la parte superior de este documento dentro de la caja junto con la(s) pieza(s) bien protegida(s).</p></div></div>'
        + '<div class="doc-step"><span>2</span><div><strong>Pega la etiqueta exterior</strong><p>Recorta la etiqueta inferior por la línea de puntos (✂️) y pégala con precinto transparente por fuera del paquete.</p></div></div>'
        + '<div class="doc-step"><span>3</span><div><strong>Envío inicial y devolución MRW</strong><p>Envíanos el paquete por tu cuenta (recomendamos <strong>MRW</strong>) o en mano en Alcobendas. <strong>MENIGAR gestiona el envío final de vuelta por MRW.</strong></p></div></div>'
        + '</section>';
    } else {
      html += '<section class="doc-banner-consult">'
        + '<strong>Consulta técnica registrada correctamente:</strong> Nuestro equipo de laboratorio revisará los síntomas y fotografías adjuntas y se pondrá en contacto contigo por correo o teléfono para confirmarte viabilidad y presupuesto orientativo antes de enviar la pieza.'
        + '</section>';
    }

    const postalAddress = address(c), returnAddress = c.returnDifferent ? address(c, 'return') : postalAddress;
    const inboundText = c.deliveryMethod === 'entrega_mano' ? 'Entrega en mano en mostrador de Alcobendas' : 'Envío por mensajería por cuenta del cliente (recomendado MRW)';
    const outboundText = c.returnMethod === 'recogida_mano' ? 'Recogida en mano en mostrador de Alcobendas' : 'Envío final gestionado por MENIGAR (vía MRW)';
    const clientBadge = c.type === 'taller' ? 'Taller o empresa' : 'Particular';

    const shippingRows = [
      ...(shipping ? [['Llegada al laboratorio', inboundText], ['Devolución pieza reparada', outboundText]] : []),
      ...(shipping || c.taxId ? [['Identificación fiscal', c.taxId]] : []),
      ...(shipping || postalAddress ? [['Dirección', postalAddress]] : []),
      ...(shipping || returnAddress ? [['Devolución', returnAddress]] : [])
    ];

    html += '<div class="doc-grid-2">'
      + '<section class="doc-panel">'
      + '<h2 class="doc-panel-title">1. Datos del solicitante y logística</h2>'
      + rows([
          ['Modalidad', shipping ? 'Orden de envío / entrada en laboratorio' : 'Consulta previa de pieza'],
          ['Tipo de cliente', clientBadge],
          ['Solicitante', c.name],
          ['Persona de contacto', c.contact || c.name],
          ['Correo y teléfono', c.email + ' · ' + c.phone],
          ...shippingRows
        ])
      + '</section>'
      + '<section class="doc-panel">'
      + '<h2 class="doc-panel-title">2. Datos del vehículo</h2>'
      + rows([
          ['Vehículo', vehicleLabel(v)],
          ['Matrícula', v.plate || 'No indicada'],
          ['Bastidor (VIN)', v.vin || 'No indicado'],
          ['Año aproximado', v.year || 'No indicado'],
          ['Kilómetros', v.km || 'No indicados']
        ])
      + '</section>'
      + '</div>';

    html += '<section class="doc-units-section">'
      + '<h2 class="doc-section-heading">3. Detalle de piezas registradas (' + unitsCount + ')</h2>';

    data.units.forEach((unit, index) => {
      const unitCode = data.reference + '-P' + (index + 1);
      const filesList = Array.isArray(unit.attachments) && unit.attachments.length
        ? '<div class="doc-unit-files"><strong>Archivos adjuntos (' + unit.attachments.length + '):</strong><ul>' + unit.attachments.map(file => '<li><a href="#" data-file="' + escape(file.id) + '" data-name="' + escape(file.downloadName || file.name) + '">' + escape(file.name) + '</a></li>').join('') + '</ul></div>'
        : '';
      html += '<section class="piece doc-unit-card">'
        + '<div class="doc-unit-header">'
        + '<div><span class="doc-unit-num">PIEZA ' + (index + 1) + ' DE ' + unitsCount + '</span><h3>' + escape(unit.componentName) + '</h3></div>'
        + '<span class="doc-unit-badge">' + escape(unitCode) + '</span>'
        + '</div>'
        + rows([
            ['Identificador de unidad', unitCode],
            ['Fabricante', unit.manufacturer || 'No indicado'],
            ['Referencia declarada', unit.reference || 'Por identificar en laboratorio'],
            ['Código de avería (DTC)', unit.dtc || 'No indicado'],
            ['Vehículo de esta pieza', (unit.vehicleBrand + ' ' + unit.vehicleModel).trim() || vehicleLabel(v)],
            ['Accesorios incluidos en la caja', unit.accessories || 'Ningún accesorio adicional declarado'],
            ['Síntomas y fallo descrito', unit.symptoms]
          ])
        + filesList
        + '</section>';
    });
    html += '</section>';

    if (shipping) {
      html += '<section class="doc-checklist">'
        + '<h2>4. Verificación rápida antes de cerrar la caja</h2>'
        + '<ul class="doc-check-grid">'
        + '<li><span class="doc-checkbox" aria-hidden="true"></span>He introducido esta <strong>Hoja de Entrada (' + escape(data.reference) + ')</strong> dentro de la caja.</li>'
        + '<li><span class="doc-checkbox" aria-hidden="true"></span>La pieza va envuelta en burbuja con los conectores/pines protegidos y sin holgura.</li>'
        + '<li><span class="doc-checkbox" aria-hidden="true"></span>He incluido únicamente los accesorios declarados en cada unidad.</li>'
        + '<li><span class="doc-checkbox" aria-hidden="true"></span>He pegado la <strong>Etiqueta Exterior</strong> inferior por fuera del paquete.</li>'
        + '</ul>'
        + '</section>';

      html += '<section class="box-outer-label" aria-label="Etiqueta recortable para exterior de caja">'
        + '<div class="box-cut-line"><span>✂️ RECORTAR POR ESTA LÍNEA Y PEGAR EN EL EXTERIOR DE LA CAJA (O ENTREGAR EN MOSTRADOR)</span></div>'
        + '<div class="box-label-card">'
        + '<div class="box-label-top">'
        + '<div class="box-label-sender">'
        + '<span class="box-label-kicker">REMITENTE</span>'
        + '<strong>' + escape(c.name) + '</strong>'
        + (c.contact ? '<div>Att: ' + escape(c.contact) + '</div>' : '')
        + '<div>Tel.: <strong>' + escape(c.phone) + '</strong> · ' + escape(c.email) + '</div>'
        + '<div>' + escape(returnAddress || postalAddress || '') + '</div>'
        + '</div>'
        + '<div class="box-label-code">'
        + '<span>' + (data.mode !== 'production' ? 'PRUEBA · ' : '') + 'REFERENCIA</span>'
        + '<strong>' + escape(data.reference) + '</strong>'
        + '<small>' + unitsCount + (unitsCount === 1 ? ' UNIDAD' : ' UNIDADES') + (v.plate ? ' · MATRÍCULA ' + escape(v.plate) : '') + '</small>'
        + '<small>' + escape(vehicleLabel(v)) + '</small>'
        + '</div>'
        + '</div>'
        + '<div class="box-label-dest">'
        + '<div class="box-dest-main">'
        + '<span class="box-label-kicker">DESTINATARIO (LABORATORIO DE ELECTRÓNICA DEL AUTOMÓVIL)</span>'
        + '<h2>MENIGAR · Desarrollos Digitales Menigar, S.L.</h2>'
        + '<p class="box-dest-address">C/ José Echegaray 16, Edificio A1 · Planta 2.ª · Nave 4<br><strong>28100 ALCOBENDAS (MADRID)</strong> · Teléfono recepción: <strong>91 662 27 81</strong></p>'
        + '</div>'
        + '<div class="box-fragile-badge">⚠️ FRÁGIL<br><small>MATERIAL ELECTRÓNICO</small></div>'
        + '</div>'
        + '<div class="box-dest-meta">'
        + '<span><strong>Llegada inicial:</strong> ' + escape(inboundText) + '</span>'
        + '<span><strong>Devolución final:</strong> ' + escape(outboundText) + '</span>'
        + '</div>'
        + '</div>'
        + '</section>';
    }

    html += '<footer class="doc-footer">'
      + '<p>Documento generado digitalmente por el sistema de recepción de <strong>MENIGAR</strong> · Referencia <strong>' + escape(data.reference) + '</strong>. La revisión física de la unidad en banco de pruebas determinará el diagnóstico técnico y el presupuesto final antes de intervenir.</p>'
      + '</footer>'
      + '</article>';

    root.innerHTML = html;
    document.title = data.reference + ' · ' + (shipping ? 'Hoja de envío' : 'Resguardo de consulta') + ' · MENIGAR';
    document.getElementById('printReceipt')?.addEventListener('click', () => window.print());
    root.querySelectorAll('[data-file]').forEach(link => link.addEventListener('click', async event => {
      event.preventDefault();
      try {
        const response = await fetch(apiBase + '/api/archivos/' + encodeURIComponent(link.dataset.file), {headers,cache:'no-store'});
        if (!response.ok) throw new Error();
        download(await response.blob(),link.dataset.name);
      } catch (_) { link.textContent = link.dataset.name + ' · No se ha podido descargar. Vuelve a intentarlo.'; }
    }));
    if (action === 'imprimir=1' || action === 'descargar=pdf') {
      setTimeout(() => { if (typeof window.print === 'function') window.print(); }, 250);
    }
  }).catch(error => failure(error.message));
})();
