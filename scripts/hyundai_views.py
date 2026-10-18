"""Public views for the two reviewed Hyundai pilot records, not a global rollout."""
import html
import re
from urllib.parse import urlencode
from public_copy import public_text


def e(value):
    return html.escape(str(value or ''), quote=True)


def photo(image, context='', ordinal=1, total=1):
    source = image['src']
    if not source.startswith(('/assets/hyundai/', 'https://www.menigar.com/wp-content/uploads/')):
        return ''
    caption = f'Foto {ordinal} de {total} · {context}' if context else image['alt']
    return f'''<figure class="component-photo"><a href="{e(source)}" target="_blank" rel="noopener" aria-label="Ampliar: {e(caption)}"><img src="{e(source)}" alt="{e(image['alt'])}" width="640" height="480" loading="lazy" decoding="async"><span class="photo-zoom" aria-hidden="true">Ampliar ↗</span></a><figcaption>{e(caption)}</figcaption></figure>'''


def pilot_content(record, lookup):
    if record.get('contentPilot') != 'hyundai-v1':
        return ''
    if record['uid'] == 'main-1604':
        target = lookup['main-3915']
        display_query = urlencode({'pieza': target['uid'], 'marca': 'Hyundai', 'modelo': 'i30', 'tipo': 'consulta'})
        return f'''<section class="component-gallery" aria-labelledby="fotos-i30"><p class="eyebrow">Reconoce tu componente</p><h2 id="fotos-i30">El cuadro Hyundai i30, en imágenes</h2><p>Compara la forma y la etiqueta con tu unidad. Las imágenes por sí solas no confirman la variante.</p><div class="component-gallery-grid">{''.join(photo(image, 'Cuadro Hyundai i30', i, len(record['gallery'])) for i, image in enumerate(record['gallery'], 1))}</div><a class="button button-primary component-consult" href="/solicitud.html?pieza=main-1604&amp;tipo=consulta">Consultar mi cuadro i30 <span aria-hidden="true">→</span></a></section>
        <aside class="component-scope"><h3>¿Tu consulta es sobre el display?</h3><p>Esta ficha reúne información del cuadro completo: display, iluminación y agujas. También puedes consultar específicamente el display de tu i30.</p><div class="component-links"><a href="{e(target['localPath'])}#modelo-i30">Ver imágenes de los displays Hyundai i30 ↗</a><a href="/solicitud.html?{e(display_query)}">Consultar el display de mi i30 →</a></div></aside>'''
    groups = record['modelGroups']
    jump = ''.join(f'<a href="#modelo-{re.sub(r"[^a-z0-9]+", "-", group["model"].lower()).strip("-")}" data-model-group="{e(group["model"])}" data-model-anchor="modelo-{re.sub(r"[^a-z0-9]+", "-", group["model"].lower()).strip("-")}">{e(group["model"])}</a>' for group in groups)
    cards = []
    for group in groups:
        model = group['model']
        anchor = re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')
        descriptions = list(dict.fromkeys(text for block in group['blocks'] for text in block['paragraphs']))
        description = descriptions[0] if descriptions else ''
        pictures = []
        for index, block in enumerate(group['blocks'], 1):
            label = f'<p class="model-image-label">{"Primer conjunto de imágenes" if index == 1 else "Otro conjunto de imágenes"}</p>' if len(group['blocks']) > 1 else ''
            pictures.append(f'<div class="model-image-group" data-source-module="{e(block["sourceModuleId"])}">{label}<div class="model-photo-pair">' + ''.join(photo(image, 'Hyundai ' + model, ordinal, len(block['images'])) for ordinal, image in enumerate(block['images'], 1)) + '</div></div>')
        query = urlencode({'pieza': record['uid'], 'marca': 'Hyundai', 'modelo': model, 'tipo': 'consulta'})
        related = ''
        target = lookup.get(group.get('relatedServiceUid'))
        if target:
            related = f'''<div class="model-related"><strong>Más información del cuadro i30</strong><p>Consulta sus referencias y los fallos de display, iluminación y agujas. Las referencias del cuadro no identifican por sí solas el display de recambio.</p><a href="{e(target['localPath'])}">{e(group['relatedServiceLabel'])} ↗</a></div>'''
        cards.append(f'''<article class="hyundai-model-card repair-variant {'model-featured' if len(group['blocks']) > 1 else ''}" data-model-group="{e(model)}" data-model-anchor="modelo-{anchor}" id="modelo-{anchor}"><div class="model-card-heading"><p class="eyebrow">Hyundai</p><h3>{e(model)}</h3></div><p>{e(public_text(description, record['uid'], 'model:' + model))}</p><div class="model-image-sets">{''.join(pictures)}</div>{related}<a class="model-consult" href="/solicitud.html?{e(query)}">Consultar la pantalla de mi {e(model)} →</a></article>''')
    return f'''<section class="hyundai-models repair-source" data-repair-uid="{e(record['uid'])}" data-repair-brand="Hyundai" aria-labelledby="modelos-hyundai"><p class="eyebrow">Encuentra tu modelo</p><h2 id="modelos-hyundai">Pantallas del cuadro Hyundai, modelo a modelo</h2><p>Localiza tu vehículo y compara las imágenes. Si no reconoces tu pieza, una foto de su etiqueta nos ayuda a orientarte.</p><nav class="model-jump-links" aria-label="Modelos Hyundai">{jump}</nav><div id="repair-model-context" class="repair-model-context" role="status" hidden></div><div class="hyundai-model-grid">{''.join(cards)}</div></section>'''


def pilot_references(record):
    if not record.get('referenceGroups'):
        return ''
    groups = record['referenceGroups']
    primary = ''.join(f'<li><code>{e(group["display"])}</code></li>' for group in groups)
    aliases = ''.join(f'<li><code>{e(group["display"])}</code><span> → </span>' + ', '.join(f'<code>{e(value)}</code>' for value in group['spellings'] if value != group['display']) + '</li>' for group in groups if len(group['spellings']) > 1)
    return f'''<section class="pilot-reference-section" aria-labelledby="referencias-i30"><h2 id="referencias-i30">Referencias del cuadro ({len(groups)})</h2><p>Comprueba el código completo de la etiqueta. Estas referencias pertenecen al cuadro; consulta la variante de tu unidad antes de elegir un recambio.</p><details class="card references-panel" open><summary>Consultar las referencias</summary><ul class="reference-list pilot-reference-list">{primary}</ul></details><details class="card reference-aliases"><summary>Ver los mismos códigos sin guiones</summary><p>Son formatos alternativos de las referencias anteriores, no piezas adicionales.</p><ul>{aliases}</ul></details></section>'''
