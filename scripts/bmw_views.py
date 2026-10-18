"""Readable, source-context-preserving view for the BMW display page."""
import html
import json
from urllib.parse import urlencode
from public_copy import public_text


def e(value):
    return html.escape(str(value or ''), quote=True)


def photo(image, service_label, ordinal, total):
    source = image['src']
    if not source.startswith(('/assets/bmw/', 'https://www.menigar.com/wp-content/uploads/')):
        return ''
    label = f"{image['alt']} · {service_label}"
    if total > 1:
        label += f' · foto {ordinal} de {total}'
    return f'''<figure class="bmw-photo"><a href="{e(source)}" target="_blank" rel="noopener" aria-label="Ampliar: {e(label)}"><img src="{e(source)}" alt="{e(label)}" width="640" height="480" loading="lazy" decoding="async"><span aria-hidden="true">Ampliar ↗</span></a><figcaption>{e(service_label)} · foto {ordinal} de {total}</figcaption></figure>'''


def bmw_content(record, lookup):
    if record.get('contentExpansion') != 'bmw-v1':
        return ''
    vehicle_groups = [group for group in record['modelGroups'] if group['vehicleModel']]
    other_groups = [group for group in record['modelGroups'] if not group['vehicleModel']]
    jumps = ''.join(f'<a href="#{e(group["anchor"])}" data-model-group="{e(group["model"])}" data-model-anchor="{e(group["anchor"])}">{e(group["model"])}</a>' for group in vehicle_groups)

    def card(group):
        model = group['model']
        vehicle_aliases = group.get('modelAliases') or [model]
        consultation_links = []
        for vehicle in vehicle_aliases if group['vehicleModel'] else ['']:
            query_data = {'pieza': record['uid'], 'marca': 'BMW', 'tipo': 'consulta'}
            if vehicle:
                query_data['modelo'] = vehicle
            label = 'Consultar mi ' + vehicle if vehicle else 'Consultar este servicio'
            consultation_links.append(f'<a class="bmw-model-consult" href="/solicitud.html?{e(urlencode(query_data))}">{e(label)} <span aria-hidden="true">→</span></a>')
        blocks = []
        for block in group['blocks']:
            paragraphs = ''.join(f'<p>{e(public_text(text, record["uid"], "module:" + block["sourceModuleId"]))}</p>' for text in block['paragraphs'])
            links = ''.join(f'<a class="bmw-related-link" href="{e(link.get("localPath") or link["url"])}">{e(link["text"])} →</a>' for link in block['links'])
            images = block['images']
            photos = ''.join(photo(image, block['serviceLabel'], ordinal, len(images)) for ordinal, image in enumerate(images, 1))
            blocks.append(f'''<div class="bmw-model-block" data-source-module="{e(block['sourceModuleId'])}"><p class="bmw-screen-type">{e(block['serviceLabel'])}</p>{paragraphs}<div class="bmw-photo-grid">{photos}</div>{links}</div>''')
        context = f' data-model-group="{e(model)}" data-model-anchor="{e(group["anchor"])}" data-model-aliases="{e(json.dumps(vehicle_aliases, ensure_ascii=False))}"' if group['vehicleModel'] else ''
        return f'''<article class="bmw-model-card {'repair-variant' if group['vehicleModel'] else ''} {'bmw-double-screen' if len(group['blocks']) > 1 else ''}"{context} id="{e(group['anchor'])}"><div class="bmw-model-heading"><p class="eyebrow">{'Pantallas BMW' if group['vehicleModel'] else 'Otros servicios BMW'}</p><h3>{e(model)}</h3></div>{''.join(blocks)}<div class="bmw-consult-options">{''.join(consultation_links)}</div></article>'''

    faults = ''.join(f'<li>{e(text)}</li>' for text in record['symptoms'])
    return f'''<section class="bmw-content repair-source" data-repair-uid="{e(record['uid'])}" data-repair-brand="BMW" aria-labelledby="bmw-index-title"><div class="bmw-index-intro"><p class="eyebrow">Encuentra tu pantalla</p><h2 id="bmw-index-title">Elige tu modelo BMW</h2><p>Ve las fotos y el tipo de pantalla descritos en esta ficha. Si no reconoces tu pieza, consúltanos con una foto.</p><details class="bmw-model-index"><summary><span>Ver lista de modelos</span><span class="bmw-index-family">Series 1, 2, 3, 5, 6 y 7 · X · Z · Alpina</span></summary><nav class="bmw-model-jumps" aria-label="Ir a las pantallas de un modelo BMW">{jumps}</nav></details></div><div id="repair-model-context" class="repair-model-context" role="status" hidden></div><div class="bmw-fault-overview"><p class="eyebrow">¿Qué le pasa a tu pantalla?</p><h2 id="bmw-fallos">Fallos habituales en pantallas BMW</h2><p>Estos son los fallos generales de este servicio. Más abajo puedes comparar las pantallas de cada modelo.</p><ul class="bmw-fault-list">{faults}</ul></div><div class="bmw-model-section" aria-labelledby="modelos-bmw"><p class="eyebrow">Compara tu pieza</p><h2 id="modelos-bmw">Pantallas BMW por modelo</h2><p>Consulta las imágenes y el tipo de pantalla. Para saber cuál es la tuya, envíanos una foto de la pantalla y de su etiqueta.</p><div class="bmw-model-grid">{''.join(card(group) for group in vehicle_groups)}</div></div><div class="bmw-other-screens" aria-labelledby="otros-bmw"><p class="eyebrow">También puedes consultar</p><h2 id="otros-bmw">Arañazos en pantallas digitales y de reposacabezas</h2><div class="bmw-model-grid">{''.join(card(group) for group in other_groups)}</div></div><aside class="bmw-unlisted"><h2>¿No ves tu modelo o tu pantalla?</h2><p>Envíanos una foto y cuéntanos qué falla. Que tu pieza no aparezca aquí no significa que no podamos ayudarte.</p><a class="button button-primary" href="/solicitud.html?pieza=main-2321&amp;marca=BMW&amp;tipo=consulta">Consultar mi pantalla BMW →</a></aside></section>'''
