#!/usr/bin/env python3
"""Generate source-backed public information pages and repair detail pages.

Only the Python standard library is required. No source caches are changed and
no page is published by this script. Review pages deliberately remain noindex.
Run from any directory: python3 scripts/build_pages.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import re
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET
from hyundai_views import pilot_content, pilot_references
from bmw_views import bmw_content
from source_sections import render_sections
from public_copy import public_text, reset_copy_report, write_copy_report


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://www.menigar.com"
ADDRESS = "C/ José Echegaray 16, Edificio A1 · Planta 2.ª · Nave 4, 28100 Alcobendas, Madrid"
PHONE = "91 662 27 81"
EMAIL = "informacion@menigar.com"


def e(value):
    return html.escape(str(value or ""), quote=True)


def safe_url(value):
    value = str(value or "")
    parsed = urlparse(value)
    if parsed.scheme in ("https", "http") or (value.startswith("/") and not value.startswith("//")):
        return e(value)
    return "#"


def paragraphs(value):
    if not value:
        return ""
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"\n\s*\n", str(value))
    return "".join(f"<p>{e(item)}</p>" for item in items if str(item).strip())


def list_html(items, class_name=""):
    items = [str(item).strip() for item in (items or []) if str(item).strip()]
    if not items:
        return ""
    return f'<ul class="{e(class_name)}">' + "".join(f"<li>{e(item)}</li>" for item in items) + "</ul>"


def header(active=""):
    links = [("servicios.html", "Servicios"), ("envios.html", "Cómo enviar"),
             ("taller.html", "El taller"), ("ayuda.html", "Ayuda")]
    nav = "".join(f'<li><a href="/{path}"' + (' aria-current="page"' if path == active else '') + f'>{label}</a></li>' for path, label in links)
    return f'''<a class="skip-link" href="#contenido">Saltar al contenido</a>
<header class="site-header"><div class="container header-inner">
  <a class="brand" href="/index.html" aria-label="MENIGAR, inicio"><span class="brand-name">MENIGAR<span class="brand-dot">.</span></span><span class="brand-caption">Electrónica del automóvil · Desde 1989</span></a>
  <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><span>Menú</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
  <nav id="site-nav" aria-label="Navegación principal"><ul class="nav-list">{nav}</ul><a class="button button-primary header-cta" href="/solicitud.html?tipo=consulta">Consultar mi pieza <span aria-hidden="true">↗</span></a></nav>
</div></header>'''


def footer():
    return f'''<footer class="site-footer"><div class="container footer-grid">
  <div><a class="brand" href="/index.html"><span class="brand-name">MENIGAR<span class="brand-dot">.</span></span><span class="brand-caption">Electrónica del automóvil · Desde 1989</span></a><p>Reparación de electrónica del automóvil.<br>Talleres y particulares.</p><a class="footer-phone" href="tel:+34916622781">{PHONE}</a></div>
  <div><h2>Tu reparación</h2><a href="/servicios.html">Buscar mi pieza</a><a href="/solicitud.html?tipo=consulta">Consultar mi pieza</a><a href="/solicitud.html?intencion=envio">Preparar solicitud de envío</a><a href="/ayuda.html#reparacion-en-curso">Consultar una reparación en curso</a><a href="/envios.html">Cómo preparar el paquete</a></div>
  <div><h2>Encuéntranos</h2><p>C/ José Echegaray, 16<br>Edificio A1 · Planta 2ª · Nave 4<br>28100 Alcobendas, Madrid</p><a href="mailto:{EMAIL}">{EMAIL}</a><a href="https://www.google.com/maps/search/?api=1&amp;query=Menigar+Alcobendas" target="_blank" rel="noopener noreferrer">Cómo llegar ↗</a></div>
  <div><h2>Horario de atención</h2><p>Lunes a jueves<br><strong>8:00–16:00</strong></p><p>Viernes<br><strong>8:00–14:00</strong></p><a href="/ayuda.html#contacto">Consultar con el equipo →</a></div>
</div><div class="container footer-bottom"><span>© <span data-current-year>2026</span> MENIGAR</span><div><a href="/privacidad.html">Privacidad</a><a href="/condiciones.html">Condiciones</a><a href="/cookies.html">Cookies</a></div><span>Alcobendas · Madrid</span></div></footer>'''


def page(title, description, path, body, active="", extra_head="", body_class=""):
    document_manifest = ROOT / 'data/documentos-local-manifest.json'
    if document_manifest.exists():
        for document in json.loads(document_manifest.read_text()):
            old = 'https://www.menigar.com' + document['sourcePath']
            for original in (old, old.replace(' ', '%20')):
                body = body.replace(original, document['localPath'])
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} | Menigar</title><meta name="description" content="{e(description)}"><meta name="robots" content="noindex, nofollow">
<link rel="canonical" href="{ORIGIN}{e(path)}"><link rel="stylesheet" href="/style.css">{extra_head}<script src="/app.js" defer></script></head>
<body class="{e(body_class)}">{header(active)}<main id="contenido">{body}</main>{footer()}</body></html>\n'''


def page_intro(kicker, title, intro, breadcrumb=""):
    crumb = f'<nav class="breadcrumb" aria-label="Ruta de navegación"><a href="/">Inicio</a><span aria-hidden="true">/</span>{breadcrumb}</nav>' if breadcrumb else ""
    return f'<section class="page-intro page-heading"><div class="container">{crumb}<p class="eyebrow">{e(kicker)}</p><h1>{e(title)}</h1><p class="lead">{e(intro)}</p></div></section>'


def contact_card(title="¿Necesitas ayuda?"):
    return f'''<aside class="card contact-card"><p class="eyebrow">Atención humana</p><h2>{e(title)}</h2><p>Si no sabes qué pieza enviar, cuéntanos qué falla y añade una foto de su etiqueta.</p><a class="button button-primary" href="/solicitud.html?tipo=consulta">Consultar mi pieza</a><p><a href="tel:+34916622781">{PHONE}</a></p><p><a href="/ayuda.html#reparacion-en-curso">Consultar una reparación en curso</a></p><p class="source-note">Lunes a jueves, de 8:00 a 16:00.<br>Viernes, de 8:00 a 14:00.</p></aside>'''


def write_info_pages():
    envios = page_intro("Tu pieza, bien preparada", "Cómo enviar tu pieza a Menigar", "Prepara el envío con la información necesaria y protege la pieza para que podamos identificarla al recibirla.", "Cómo enviar")
    envios += f'''<section class="section"><div class="container subpage-grid"><div class="prose">
<details class="card packaging-guide"><summary>Ver guía visual de embalaje</summary><figure style="max-width:680px;margin:20px auto 0"><img src="/assets/ayuda-embalaje.svg" alt="Guía de embalaje: proteger los conectores, inmovilizar la pieza dentro de la caja e incluir el resumen de solicitud" width="680" height="1090" loading="lazy" style="max-width:100%;height:auto"><figcaption>Guía general de preparación. Consulta las instrucciones específicas de tu pieza. <a href="/assets/ayuda-embalaje.svg" target="_blank" rel="noopener">Ampliar esquema ↗</a></figcaption></figure></details>
<ol class="steps-list"><li><span class="step-number">01</span><div><h2>Identifica la pieza y cuéntanos el fallo</h2><p>Busca tu servicio o describe la avería. Añade la referencia y una foto de la etiqueta si la tienes. Si el caso no está claro, consúltanos antes de enviar.</p><a class="button button-primary" href="/solicitud.html?tipo=consulta">Consultar mi pieza</a></div></li>
<li><span class="step-number">02</span><div><h2>Incluye un resumen dentro de la caja</h2><p>Incluye la petición de reparación cumplimentada o el resumen de solicitud, con tus datos de contacto, la pieza y el fallo observado. Si envías varias unidades, identifica cada una y sus accesorios.</p><p>Durante esta revisión de la nueva web, la solicitud digital solo sirve para pruebas. Para un envío real utiliza el documento vigente y confirma las instrucciones con el taller.</p><a href="https://www.menigar.com/docs/peticion_reparacion%202026a.pdf" target="_blank" rel="noopener">Descargar petición de reparación vigente (PDF)</a></div></li>
<li><span class="step-number">03</span><div><h2>Protege las partes delicadas</h2><p>Utiliza una caja resistente ajustada a la pieza. Envuelve la unidad con material protector, protege conectores y rellena los huecos para que no se mueva. No envíes componentes adicionales sin comprobar las instrucciones del servicio.</p><a href="https://www.menigar.com/docs/como_embalar.pdf" target="_blank" rel="noopener">Ver instrucciones de embalaje (PDF)</a></div></li>
<li><span class="step-number">04</span><div><h2>Confirma el transporte y guarda el seguimiento</h2><p>Puedes consultar al taller las opciones de envío y sus condiciones. Para Canarias, Ceuta, Melilla o envíos internacionales, confirma previamente la documentación necesaria. Conserva el justificante y número de seguimiento.</p><p>No confundas el número del transportista con la referencia de tu solicitud.</p></div></li></ol>
<div class="card"><p class="eyebrow">Destino del envío</p><h2>Menigar · Alcobendas, Madrid</h2><address>{e(ADDRESS)}<br>Desarrollos Digitales Menigar, S.L.<br>Teléfono: {PHONE}</address><p><a href="https://www.menigar.com/docs/direccion_envio.pdf" target="_blank" rel="noopener">Descargar etiqueta con la dirección (PDF)</a></p></div>
<h2>Cada pieza puede necesitar una preparación distinta</h2><p>En algunos servicios debe enviarse el conjunto completo; en otros, una parte concreta. Revisa la ficha de tu pieza o pregúntanos antes de desmontar y enviar. Los componentes de seguridad deben ser manipulados por personal cualificado.</p><a href="/servicios.html" class="button button-secondary">Consultar mi servicio</a>
<p class="source-note">Información preparada a partir de las instrucciones de <a href="https://www.menigar.com/envios/" target="_blank" rel="noopener">envíos de Menigar</a>. Las modalidades y tarifas de transporte deben confirmarse para cada envío.</p>
</div>{contact_card()}</div></section>'''
    (ROOT / "envios.html").write_text(page("Cómo enviar tu pieza", "Prepara e identifica tu pieza antes de enviarla al taller Menigar en Alcobendas. Dirección, embalaje y petición de reparación.", "/envios.html", envios, "envios.html"), encoding="utf-8")

    taller = page_intro("Electrónica del automóvil", "Taller de electrónica del automóvil en Alcobendas", "Cuadros de instrumentos, ABS, pantallas y módulos electrónicos. Atención para talleres y particulares desde Alcobendas, Madrid.", "El taller")
    taller += f'''<section class="section"><div class="container subpage-grid"><div class="prose"><figure class="workshop-figure"><img src="/assets/hero-lab.jpg" alt="Banco de trabajo de electrónica con instrumental y una pieza en revisión" loading="lazy" width="1000" height="680"><figcaption>Trabajo especializado en electrónica del automóvil.</figcaption></figure>
<p class="eyebrow">Menigar · Desde 1989</p><h2>Encontrar una solución empieza por entender el fallo</h2><p>Trabajamos con componentes electrónicos del automóvil y con las averías descritas en nuestro catálogo. Cuéntanos qué ocurre y aporta la referencia de la pieza o los códigos de diagnosis disponibles.</p><div class="card-grid"><article class="card"><h3>Para talleres</h3><p>Fichas con referencias y fallos relacionados para consultar el servicio y preparar el envío de la pieza de tu cliente.</p></article><article class="card"><h3>Para particulares</h3><p>Ayuda para identificar la pieza, explicar los síntomas y preparar la solicitud aunque no conozcas su código.</p></article></div>
<h2>Una alternativa a estudiar antes de sustituir</h2><p>Si tu pieza tiene reparación, recuperar su funcionamiento puede evitar una sustitución completa. La solución y el presupuesto dependen de la unidad, la avería y su estado. También puedes consultar disponibilidad de recambio cuando sea necesario.</p><h2>La información útil, a mano</h2><ul><li>Marca, modelo y año del vehículo.</li><li>Referencia o fotografía legible de la etiqueta.</li><li>Qué falla y cuándo ocurre.</li><li>Códigos de diagnosis, si los tienes.</li></ul><a class="button button-primary" href="/servicios.html">Buscar mi pieza o avería</a>
<div class="card"><h2>Estamos en Alcobendas</h2><address>{e(ADDRESS)}</address><p><a href="https://www.google.com/maps/search/?api=1&amp;query=Menigar+Jose+Echegaray+16+Alcobendas" target="_blank" rel="noopener">Ver ubicación en Google Maps ↗</a></p><p><strong>Atención telefónica</strong><br>Lunes a jueves, de 8:00 a 16:00. Viernes, de 8:00 a 14:00.</p></div>
</div>{contact_card("Habla con el taller")}</div></section>'''
    (ROOT / "taller.html").write_text(page("El taller", "Menigar, taller especializado en electrónica del automóvil para profesionales y particulares en Alcobendas, Madrid.", "/taller.html", taller, "taller.html"), encoding="utf-8")

    faqs = [
        ("¿Atendéis a particulares o solo a talleres?", "Atendemos tanto a talleres y profesionales del sector como a particulares. Puedes buscar el servicio o contarnos qué falla, aunque no conozcas la referencia."),
        ("¿Y si no encuentro mi pieza o avería?", "Consúltanos antes de enviarla. Indica marca, modelo y referencia si la tienes; añade fotos y códigos de diagnosis. Que una pieza no aparezca en la búsqueda no significa que no podamos ayudarte."),
        ("¿Cómo encuentro la referencia de la pieza?", "Suele figurar en una etiqueta o inscripción sobre la unidad. Si no sabes cuál es, envía una foto nítida de la etiqueta completa y describe el vehículo y el fallo. No desmontes componentes de seguridad por tu cuenta."),
        ("¿Puedo enviar varias piezas?", "Sí: identifica cada unidad y describe su fallo por separado. Distingue las piezas que quieres revisar de cables, llaves u otros accesorios incluidos. Consulta qué componentes requiere el servicio antes de preparar la caja."),
        ("¿Lo que aparece en el catálogo confirma la reparación?", "El catálogo ayuda a localizar servicios y fallos relacionados. La posibilidad de reparación y el presupuesto se confirman tras valorar el caso y revisar la unidad."),
        ("¿Cuánto cuesta y cuánto tarda?", "Depende del servicio y de la avería. Consulta la ficha o pide orientación con los datos de tu pieza. El taller te comunica el presupuesto correspondiente; el tiempo de reparación y el transporte son distintos."),
        ("¿Puedo enviar una pieza que ya se ha manipulado?", "Cuéntanos qué intervención ha tenido y cuál es su estado antes de enviarla. Menigar debe valorar la admisión del caso. No ocultes humedad, daños ni intentos de reparación previos."),
        ("¿Necesita ajustes al volver a montarla?", "Depende de la pieza y de la intervención. Si requiere observaciones para su reinstalación, el taller te lo indicará. El montaje debe realizarlo personal cualificado."),
        ("¿Cómo preparo el paquete?", "Protege la pieza y sus conectores, rellena los huecos de la caja e incluye la petición cumplimentada con tus datos. Revisa las instrucciones específicas del servicio y conserva el seguimiento del envío."),
        ("¿Cómo consulto una reparación que ya está en Menigar?", "Contacta directamente con el taller e indica el número de orden, si lo tienes, y los datos necesarios para localizar el caso. El buscador y la solicitud nueva no son un seguimiento de reparaciones existentes."),
    ]
    faq_html = "".join(f'<details class="faq-item"' + (' id="reparacion-en-curso-pregunta"' if q.startswith("¿Cómo consulto una reparación") else "") + f'><summary>{e(q)}</summary><div>{paragraphs(a)}</div></details>' for q, a in faqs)
    ayuda = page_intro("Preguntas y contacto", "Ayuda para reparar y enviar tu pieza", "Información para consultar un servicio, preparar la solicitud y enviar la unidad. Si tu caso necesita más contexto, habla con el taller.", "Ayuda")
    ayuda += f'''<section class="section"><div class="container subpage-grid"><div><div class="faq-list">{faq_html}</div><section class="card existing-repair-contact" id="reparacion-en-curso"><p class="eyebrow">Tu pieza ya está en Menigar</p><h2>Consultar una reparación en curso</h2><p>Contacta con el taller e indica el número de orden, si lo tienes, y el nombre de quien solicitó la reparación. No necesitas crear otra consulta nueva.</p><a class="button button-primary" href="mailto:{EMAIL}?subject=Consulta%20de%20reparaci%C3%B3n%20en%20curso">Escribir sobre mi reparación</a><p><a href="tel:+34916622781">Llamar al {PHONE}</a></p></section><div class="card" id="contacto"><p class="eyebrow">Consulta tu caso</p><h2>Atención directa de Menigar</h2><p>Para una reparación ya enviada, ten a mano tu número de orden y los datos del solicitante.</p><p><strong>Asistencia técnica:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a><br><strong>Administración:</strong> <a href="mailto:admon@menigar.com">admon@menigar.com</a><br><strong>Teléfonos:</strong> <a href="tel:+34916622781">{PHONE}</a> / <a href="tel:+34916610397">91 661 03 97</a></p><p>Lunes a jueves: 8:00–16:00. Viernes: 8:00–14:00.</p></div><p class="source-note">Contenido adaptado de las <a href="https://www.menigar.com/preguntas-frecuentes/" target="_blank" rel="noopener">preguntas frecuentes actuales</a> y del proceso documentado del taller. Las condiciones concretas se comunican para cada caso.</p></div>{contact_card()}</div></section>'''
    (ROOT / "ayuda.html").write_text(page("Ayuda y contacto", "Preguntas frecuentes sobre las reparaciones de Menigar. Cómo identificar tu pieza, preparar el envío y contactar con el taller.", "/ayuda.html", ayuda, "ayuda.html"), encoding="utf-8")


def write_legal_pages():
    note = '<div class="notice"><strong>Documento en revisión para la nueva web.</strong><p>Esta página recoge información de la web vigente. Antes de utilizar el nuevo servicio con clientes deben validarse sus condiciones y la información sobre el tratamiento de datos. El prototipo utiliza únicamente datos de prueba.</p></div>'
    privacy = page_intro("Información sobre tus datos", "Privacidad", "Identificación del responsable y vías de contacto para consultas sobre datos personales.", "Privacidad")
    privacy += f'''<section class="section"><div class="container prose legal-prose">{note}<h2>Responsable</h2><p>Desarrollos Digitales Menigar, S.L. · NIF B87461950.<br>{e(ADDRESS)}<br><a href="mailto:admon@menigar.com">admon@menigar.com</a>.</p><h2>Consultas y solicitudes</h2><p>La política vigente de Menigar contempla tramitar encargos y solicitudes, responder consultas y atender las peticiones realizadas por sus vías de contacto. La finalidad de la nueva solicitud es aportar la información necesaria para consultar y gestionar la reparación de una pieza.</p><h2>Información que puede incluir la solicitud</h2><p>Datos de contacto e identificación del solicitante, información del vehículo y de la pieza, descripción de la avería, dirección para la devolución y archivos aportados. No adjuntes documentación personal ajena a la reparación ni datos bancarios.</p><h2>Conservación, proveedores y base del tratamiento</h2><p>La política de origen indica que los datos se conservan durante el tiempo necesario para su finalidad y las obligaciones legales que correspondan. El nuevo servicio debe confirmar sus plazos concretos, la base jurídica aplicable y los proveedores que intervienen antes de su publicación. No se presume que un proveedor o una integración estén ya configurados.</p><h2>Tus derechos y contacto</h2><p>La política vigente informa sobre acceso, rectificación, supresión, portabilidad, limitación y oposición, y sobre la retirada del consentimiento cuando sea aplicable. Puedes dirigirte a <a href="mailto:admon@menigar.com">admon@menigar.com</a>. También puedes presentar una reclamación ante la <a href="https://www.aepd.es/" target="_blank" rel="noopener">Agencia Española de Protección de Datos</a>.</p><h2>Política de origen</h2><p><a href="https://www.menigar.com/politica-de-privacidad/" target="_blank" rel="noopener">Consultar la política de privacidad publicada por Menigar</a>.</p><p class="source-note">Adaptación informativa de la política conservada en las fuentes del proyecto. No sustituye la revisión y aprobación de la información aplicable al nuevo servicio.</p></div></section>'''
    (ROOT / "privacidad.html").write_text(page("Privacidad", "Información de privacidad y contacto del responsable Menigar. Documento en revisión para el nuevo servicio de solicitudes.", "/privacidad.html", privacy), encoding="utf-8")

    terms = page_intro("Información del servicio", "Aviso legal y condiciones", "Datos del titular y condiciones que debes confirmar para tu reparación.", "Aviso legal y condiciones")
    terms += f'''<section class="section"><div class="container prose legal-prose">{note}<h2>Titular del sitio</h2><dl class="detail-list"><dt>Denominación social</dt><dd>Desarrollos Digitales Menigar, S.L.</dd><dt>NIF</dt><dd>B87461950</dd><dt>Dirección</dt><dd>{e(ADDRESS)}</dd><dt>Contacto</dt><dd><a href="mailto:admon@menigar.com">admon@menigar.com</a> · <a href="tel:+34916610397">91 661 03 97</a></dd><dt>Datos registrales publicados</dt><dd>Registro Mercantil de Madrid, tomo 34.319, folio 1, sección 8, hoja M-617387, inscripción 1.ª.</dd></dl><h2>Catálogo y solicitud</h2><p>Las fichas describen servicios y referencias relacionados. Consultarlas o preparar una solicitud no confirma el diagnóstico de una unidad, su reparabilidad ni un presupuesto final. Si falta información o no sabes qué enviar, consulta con el taller.</p><h2>Presupuesto, transporte y garantía</h2><p>Confirma las condiciones aplicables a tu servicio con Menigar. El coste, el plazo y las instrucciones pueden depender de la pieza y de su estado. Las condiciones de garantía y transporte de la web actual deben revisarse y aprobarse para esta nueva web antes de publicarla.</p><ul><li><a href="https://www.menigar.com/garantias/" target="_blank" rel="noopener">Información de garantía actualmente publicada</a>.</li><li><a href="https://www.menigar.com/envios/" target="_blank" rel="noopener">Información de transporte actualmente publicada</a>.</li><li><a href="https://www.menigar.com/avisos-legales/" target="_blank" rel="noopener">Aviso legal actualmente publicado</a>.</li></ul><h2>Contenido y marcas</h2><p>El aviso de origen identifica al titular de los contenidos propios y reconoce los derechos de los titulares de marcas y contenidos de terceros. La mención de una marca de vehículo o fabricante de componente sirve para identificar el servicio relacionado.</p><h2>Estado del prototipo</h2><p>Esta versión se utiliza para revisar la nueva experiencia y realizar pruebas. No formaliza pedidos ni confirma cobros, reparaciones o transportes reales.</p></div></section>'''
    (ROOT / "condiciones.html").write_text(page("Aviso legal y condiciones", "Titular de la web Menigar e información del servicio. Condiciones pendientes de validación para la nueva web.", "/condiciones.html", terms), encoding="utf-8")

    cookies = page_intro("Preferencias y navegación", "Cookies y almacenamiento", "Información sobre el funcionamiento de esta versión y su política de origen.", "Cookies")
    cookies += f'''<section class="section"><div class="container prose legal-prose">{note}<h2>Esta versión en revisión</h2><p>El prototipo no incorpora herramientas de publicidad ni seguimiento de visitas. Las fotografías y los recursos principales se sirven desde el propio proyecto. Los enlaces a mapas, correo y documentos externos solo abren esos servicios cuando los utilizas.</p><h2>Vídeos y mapa de la portada</h2><p>La portada enseña vídeos del canal de YouTube de MENIGAR y un mapa de Google, pero no los carga al abrir la página: hasta que pulsas «Reproducir» o «Ver el mapa aquí» solo se ve una imagen servida desde el propio proyecto. Al pulsar, el navegador se conecta con YouTube, en su modo de privacidad mejorada (youtube-nocookie.com), o con Google Maps. Esos servicios reciben tu dirección IP y pueden usar sus propias cookies según sus políticas. Si prefieres no hacerlo, puedes abrir los vídeos en YouTube o la ubicación en Google Maps desde sus enlaces.</p><h2>Datos de prueba en tu dispositivo</h2><p>El formulario puede conservar un borrador en el navegador para no perder lo escrito al cambiar de paso. Utiliza únicamente datos ficticios. La acción para borrar el borrador está disponible en el propio formulario cuando esta función esté activada.</p><h2>Antes de publicar</h2><p>La política definitiva debe corresponder a las herramientas y al almacenamiento realmente instalados. Si se añaden analítica u otros servicios, deben revisarse sus condiciones y los controles de consentimiento que correspondan. El texto sobre los vídeos y el mapa debe confirmarlo el asesor legal de la empresa.</p><h2>Política de la web actual</h2><p><a href="https://www.menigar.com/politica-de-cookies/" target="_blank" rel="noopener">Consultar la política de cookies publicada por Menigar</a>.</p><p class="source-note">La política de origen describe servicios de la web actual; no se atribuyen automáticamente a este prototipo.</p></div></section>'''
    (ROOT / "cookies.html").write_text(page("Cookies y almacenamiento", "Información sobre cookies, almacenamiento de borradores y política de origen de Menigar.", "/cookies.html", cookies), encoding="utf-8")


def instruction_tables(groups):
    parts = []
    for group in groups or []:
        label = group.get("label", "Instrucciones según el caso")
        columns = group.get("columns") or []
        rows = group.get("rows") or []
        if not rows:
            continue
        heading = f'<h3>{e(label)}</h3>'
        if columns:
            heading += '<div class="instruction-table-wrap"><table><thead><tr>' + ''.join(f'<th scope="col">{e(v)}</th>' for v in columns) + '</tr></thead><tbody>'
            for row in rows:
                values = list(row.values()) if isinstance(row, dict) else row
                if not isinstance(values, (list, tuple)):
                    values = [values]
                heading += '<tr>' + ''.join(f'<td>{e(v)}</td>' for v in values) + '</tr>'
            heading += '</tbody></table></div>'
        else:
            heading += list_html([' · '.join(str(v) for v in row) if isinstance(row, (list, tuple)) else str(row) for row in rows])
        parts.append(heading)
    return "".join(parts)


def repair_page(record, records_by_id):
    uid = record["uid"]
    title = public_text(record.get("title") or record.get("variant") or record.get("model") or record.get("componentName"), uid, 'title')
    description = public_text(record.get("description") or f'Información sobre {title}. Consulta referencias y cuéntanos la avería de tu pieza.', uid, 'description')
    family = record.get("componentName") or "Reparación electrónica"
    brand = record.get("brand") or ""
    model = record.get("model") or ""
    vehicle = " · ".join(dict.fromkeys(v for v in [brand, model] if v and v.lower() not in ["varios", "general", "multimarca", "otras marcas"]))
    path = record["localPath"]
    request = "/solicitud.html?pieza=" + quote(uid, safe="") + "&tipo=consulta"
    crumb = f'<a href="/servicios.html">Servicios</a><span aria-hidden="true">/</span><span>{e(family)}</span>'
    body = page_intro(family, title, description, crumb)
    if record.get("isInstruction"):
        body += '<section class="section"><div class="container subpage-grid"><div class="prose">'
    else:
        body += '<section class="section"><div class="container subpage-grid"><div class="prose">'
    if vehicle:
        body += f'<p class="eyebrow">{e(vehicle)}</p>'
    # Keep the initial focus on identifying the unit. Budget conditions remain
    # next to the consultation action and in the request review, without an
    # additional warning card before every model selector.
    if record.get("isAggregator") and not record.get('contentExpansion') and not record.get('contentPilot'):
        body += '<div class="notice"><strong>Elige tu modelo o consulta tu pieza.</strong><p>Busca el modelo o la referencia concreta para consultar su variante. Si no aparece, cuéntanos el caso.</p></div>'
    body += pilot_content(record, records_by_id)
    body += bmw_content(record, records_by_id)
    body += render_sections(record)
    if record.get("symptoms") and not record.get('contentExpansion'):
        body += '<h2>¿Tu pieza tiene alguno de estos fallos?</h2><p>Comprueba si coinciden con lo que observas. La revisión de tu unidad permite confirmar el caso.</p>' + list_html([public_text(value, uid, 'symptom:' + str(i)) for i, value in enumerate(record["symptoms"])])
    if record.get("dtcCodes"):
        body += '<h2>Códigos de avería de esta ficha</h2><p>El código ayuda a identificar el caso; por sí solo no confirma el origen del fallo.</p>' + list_html(record["dtcCodes"], "reference-list")
        details = [item for item in record.get("dtcDetails", []) if item.get("description") and item.get("code") in record["dtcCodes"]]
        if details and not record.get("isInstruction"):
            body += '<details class="card"><summary>Ver descripción de los códigos</summary><dl class="detail-list">' + ''.join(f'<dt>{e(item["code"])}</dt><dd>{e(item["description"])}</dd>' for item in details) + '</dl></details>'
    if record.get("referenceGroups"):
        body += pilot_references(record)
    elif record.get("references") and record.get('contentExpansion') != 'source-v1':
        body += f'<details class="card references-panel"><summary>Ver referencias de pieza ({len(record["references"])})</summary><p>Comprueba la etiqueta completa y la variante. Si no estás seguro, añade una fotografía a tu solicitud.</p>' + list_html(record["references"], "reference-list") + '</details>'
    if record.get("instructions") or record.get("instructionGroups") or record.get("relatedInstructions"):
        body += '<h2>Qué debes tener en cuenta antes de enviar</h2>' + list_html(record.get("instructions")) + instruction_tables(record.get("instructionGroups"))
        related = []
        for related_uid in record.get("relatedInstructions") or []:
            item = records_by_id.get(related_uid)
            if item:
                related.append(f'<li><a href="{safe_url(item["localPath"])}">{e(item.get("title") or "Instrucciones específicas del servicio")}</a></li>')
        if related:
            body += '<ul class="related-instructions">' + ''.join(related) + '</ul>'
        body += '<p>Si no identificas con seguridad la variante o los componentes que se solicitan, confirma con Menigar antes de enviar. No desmontes componentes de seguridad sin personal cualificado.</p>'
    else:
        body += '<h2>Prepara tu consulta</h2><p>Incluye la referencia de la pieza, fotos de su etiqueta y una descripción del fallo. Antes de enviarla, comprueba con el taller qué elementos necesita este servicio.</p>'
    if record.get("sourceText") and not record.get("contentPilot") and not record.get('contentExpansion'):
        body += '<details class="card source-detail"><summary>Más información del servicio y sus variantes</summary><p class="source-note">Consulta la generación y referencia de tu unidad; los fallos descritos no se atribuyen automáticamente a todas las variantes.</p><div class="source-excerpt">' + paragraphs([public_text(value, uid, 'additional:' + str(i)) for i, value in enumerate(str(record["sourceText"]).splitlines())]) + '</div></details>'
    if record.get("timing") or record.get("warranty"):
        body += '<h2>Plazo y garantía de este servicio</h2><dl class="detail-list">'
        if record.get("timing"):
            body += f'<dt>Plazo indicado</dt><dd>{e(public_text(record["timing"], uid, "timing"))}</dd>'
        if record.get("warranty"):
            body += f'<dt>Garantía indicada</dt><dd>{e(public_text(record["warranty"], uid, "warranty"))}</dd>'
        body += '</dl><p>Confirma las condiciones aplicables a tu pieza con Menigar. El plazo del taller no incluye automáticamente el transporte.</p>'
    body += '<p class="source-note">La selección del servicio no confirma un diagnóstico ni un presupuesto final.</p>'
    body += f'''</div><aside class="card contact-card"><p class="eyebrow">Tu siguiente paso</p><h2>Consulta con los datos de tu pieza</h2><p>Cuéntanos qué falla y añade fotos. Este servicio quedará seleccionado y podrás corregirlo.</p><a class="button button-primary" href="{e(request)}">Consultar mi pieza <span aria-hidden="true">↗</span></a><p>El taller podrá orientarte. El presupuesto final depende de la revisión de tu unidad.</p><hr><h3>¿No es tu variante?</h3><a class="button button-secondary" href="/servicios.html">Volver a buscar</a><p><a href="/ayuda.html#reparacion-en-curso">Consultar una reparación en curso</a></p><p class="source-note">Esta versión solo admite pruebas. Para una consulta real, contacta directamente con el taller.</p></aside></div></section>'''
    detail_head = '<style>.repair-detail-page .page-heading h1{font-size:3rem;line-height:1.1;max-width:1050px;overflow-wrap:anywhere}.repair-detail-page .page-heading .lead{max-width:850px}@media(max-width:760px){.repair-detail-page .page-heading h1{font-size:2rem;line-height:1.15}}</style>'
    if record.get('contentPilot'):
        detail_head += '<link rel="stylesheet" href="/hyundai.css">'
    if record.get('contentExpansion') == 'bmw-v1':
        detail_head += '<link rel="stylesheet" href="/bmw.css">'
    detail_head += '<link rel="stylesheet" href="/reparaciones.css">'
    return page(title, description[:240], path, body, "servicios.html", detail_head, "repair-detail-page")


def write_catalogue():
    reset_copy_report()
    catalog_path = ROOT / "data" / "catalogo-v2.json"
    if not catalog_path.exists():
        print("Information pages generated. Catalogue pending: data/catalogo-v2.json")
        return []
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if isinstance(catalog, dict):
        catalog = catalog.get("records") or catalog.get("items") or catalog.get("catalog") or []
    lookup = {record["uid"]: record for record in catalog}
    if len(lookup) != len(catalog):
        raise ValueError("Duplicate catalogue UID; pages were not generated")
    seen_paths = set()
    for record in catalog:
        path = record.get("localPath", "")
        if not re.fullmatch(r"/reparaciones/[a-zA-Z0-9_-]+/", path):
            raise ValueError(f"Unsafe catalogue path: {path!r}")
        if path in seen_paths:
            raise ValueError(f"Duplicate catalogue path: {path}")
        seen_paths.add(path)
    for record in catalog:
        folder = ROOT / record["localPath"].lstrip("/")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(repair_page(record, lookup), encoding="utf-8")
    write_copy_report(ROOT)
    print(f"Generated {len(catalog)} source-backed repair pages")
    return sorted(seen_paths)


def write_search_engine_files(paths):
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    tree = ET.Element(f"{{{namespace}}}urlset")
    for path in ["/", "/servicios.html", "/envios.html", "/taller.html", "/ayuda.html"] + paths:
        item = ET.SubElement(tree, f"{{{namespace}}}url")
        ET.SubElement(item, f"{{{namespace}}}loc").text = ORIGIN + path
    ET.indent(tree, space="  ")
    ET.ElementTree(tree).write(ROOT / "sitemap.xml", encoding="utf-8", xml_declaration=True)
    (ROOT / "robots.txt").write_text(
        "# Review prototype: documents carry noindex; do not announce this sitemap yet.\n"
        "# robots.txt is not access control. Private resources are blocked by the server.\n"
        "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /private/\n"
        "Disallow: /_private/\nDisallow: /scripts/\nDisallow: /data/cache/\nDisallow: /data/cache_abs/\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_info_pages()
    write_legal_pages()
    paths = write_catalogue()
    write_search_engine_files(paths)
