"""Reviewed public wording layered over the immutable WordPress archive.

Only the phrases listed below are changed. Model names, references, fault codes,
source blocks, media membership and the catalogue remain untouched. The build
records every public replacement so an editor can review or revert it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

# These edits clarify commercial uncertainty; they are not new price, warranty,
# compatibility or turnaround promises.
RULES = [
    ('best-price', r'\bal mejor (?:precio|coste)\b', 'con un presupuesto específico para cada caso'),
    ('shortest-time', r'\ben el menor tiempo\b', 'con un plazo que debe confirmarse para cada caso'),
    ('maximum-warranty', r'\bcon la máxima garantía\b', 'con las condiciones de garantía aplicables al servicio'),
    ('total-warranty', r'\bcon total garantía\b', 'con las condiciones de garantía aplicables al servicio'),
    ('maximum-efficacy', r'\bcon la máxima eficacia\b', 'según el estado de la unidad'),
    ('maximum-speed', r'\bcon la máxima velocidad\b', 'con un plazo que debe confirmarse para cada caso'),
    ('record-time', r'\by tiempo r[eé]cord\b', 'y un plazo que debe confirmarse para cada caso'),
    ('in-record-time', r'\ben tiempo r[eé]cord\b', 'con un plazo que debe confirmarse para cada caso'),
    ('guaranteed-repair', r'\bgarantizar su reparación\b', 'trabajar en su reparación'),
    ('legacy-typo', r'\bgarantiar su reparación\b', 'trabajar en su reparación'),
    ('menigar-laboratorio', r'\b(n)uestro taller\b', r'\1uestro laboratorio'),
]

OVERRIDES = {
    ('main-3915', 'title'): {
        'expected': 'Reparación Display Hyundai',
        'text': 'Reparación de pantallas del cuadro de instrumentos Hyundai',
        'reason': 'Explica el componente en lenguaje común, conservando el alcance del servicio.'},
    ('main-3915', 'description'): {
        'expected': 'En Menigar reparamos los display o pantallas de los cuadros de instrumentos de Hyundai, para distintos modelos.',
        'text': 'Busca tu modelo Hyundai y consulta la reparación de la pantalla del cuadro de instrumentos. Puedes comparar las fotos y aportar los datos de tu pieza.',
        'reason': 'Orienta a reconocer el modelo y a consultar sin añadir compatibilidades ni promesas.'},
    ('main-2942', 'title'): {
        'expected': 'Reparación Display Mazda',
        'text': 'Reparación de la pantalla del cuadro de instrumentos Mazda',
        'reason': 'Nombre común de la pieza y alcance fiel al servicio de origen.'},
    ('main-2942', 'description'): {
        'expected': 'En Menigar reparamos los display de los cuadros de instrumentos (pantallas LCD) de Mazda, para distintos modelos. Reparación de los fallos y averías en los píxeles del display o pantalla, fallos de iluminación, fallo total del display...',
        'text': '¿La pantalla del cuadro de tu Mazda pierde píxeles, no se ilumina o deja de funcionar? Compara las versiones documentadas y consulta con los datos de tu pieza.',
        'reason': 'Los síntomas figuran en la descripción de origen; orienta a reconocer la variante sin confirmar un diagnóstico.'},
    ('main-2942', 'section:detalle-3'): {
        'expected': 'Vehículos Mazda que reparamos su display',
        'text': 'Pantallas Mazda por modelo',
        'reason': 'Título literal y legible.'},
    ('main-2942', 'block:4'): {
        'expected': 'A continuación el display de Mazda que reparamos. Contamos con un gran stock de recambios para garantiar su reparación en el menor tiempo y con la máxima garantía. Si su modelo no aparece en el listado póngase en contacto con nosotros.',
        'text': 'Compara las imágenes de las versiones que aparecen a continuación. Si no reconoces tu pieza o no ves tu modelo, puedes consultar con una foto de su etiqueta.',
        'reason': 'Sustituye una promesa general de stock, plazo y garantía por orientación para identificar la pieza.'},
    ('main-2942', 'block:50'): {
        'expected': 'En Menigar contamos con más de 30 años de experiencia en la reparación de pantallas y displays de información en vehículos. Ponemos a su disposición un enorme stock de material para la reparación, que nos permite reparar los fallos de display al mejor precio y con la máxima eficacia. Contacte con nosotros sobre las opciones de arreglar su Mazda con nosotros mediante nuestros teléfonos 91 662 27 81 | 91 661 03 97 , email o si lo prefiere puede visitar nuestras oficinas en Madrid.',
        'text': 'Para consultar tu pantalla Mazda, indica el modelo, describe lo que falla y añade una foto de la pieza o de su etiqueta. El laboratorio podrá orientarte; el presupuesto final depende de la revisión de tu unidad.',
        'reason': 'Cierra con datos útiles y expectativa correcta, sin introducir operaciones internas ni comparativas sin evidencia.'},
}

# Titles shared by two or more fichas on the old website (26 Oct 2026). Each new title uses only
# what its own page states: the model, unit or screen references in its address, variant and text.
OVERRIDES.update({
    ('main-8026', 'title'): {
        'expected': 'Reparación cuadro de instrumentos Audi 100',
        'text': 'Reparación cuadro de instrumentos Audi V8',
        'reason': 'El título repetía el del Audi 100; la ficha trata del Audi V8 (dirección, modelo y texto).'},
    ('abs-2855', 'title'): {
        'expected': 'Reparación módulo ABS Motos KTM',
        'text': 'Reparación módulo ABS Moto Guzzi',
        'reason': 'El título repetía el de KTM; la ficha trata de Moto Guzzi (dirección, marca y texto).'},
    ('abs-4420', 'title'): {
        'expected': 'Reparación módulo ABS Bosch 5.3 Renault Mascott 2004-2010',
        'text': 'Reparación módulo ABS Bosch 8.0 Renault Mascott 2004-2010',
        'reason': 'El título repetía el de la versión Bosch 5.3; la ficha trata de la unidad Bosch 8.0.'},
    ('abs-2499', 'title'): {
        'expected': 'Reparación módulo ABS Seat Leon 2008-2012',
        'text': 'Reparación módulo ABS Seat Toledo 2004-2009 ATE MK61',
        'reason': 'El título repetía el del Seat Leon; la ficha trata del Toledo 2004-2009 con ATE MK61.'},
    ('abs-3079', 'title'): {
        'expected': 'Reparación módulo ABS Motos Suzuki',
        'text': 'Reparación módulo ABS Suzuki DL650 V-Strom',
        'reason': 'Distingue la ficha del modelo, como la nombra su texto, de la página general de motos Suzuki.'},
    ('abs-2233', 'title'): {
        'expected': 'Reparación módulo ABS Motos Suzuki',
        'text': 'Reparación módulo ABS motos Suzuki: defectos comunes',
        'reason': 'Distingue la página de defectos comunes de la página general que lista los modelos.'},
    ('abs-989', 'title'): {
        'expected': 'Reparación módulo ABS Suzuki Swift 2004-2010',
        'text': 'Reparación módulo ABS Suzuki Swift 2004-2010 ATE MK60',
        'reason': 'Añade la unidad que nombra la propia ficha; la distingue de la versión ATE MK70.'},
    ('abs-985', 'title'): {
        'expected': 'Reparación módulo ABS Suzuki Swift 2004-2010',
        'text': 'Reparación módulo ABS Suzuki Swift 2004-2010 ATE MK70',
        'reason': 'Añade la unidad que nombra la propia ficha; la distingue de la versión ATE MK60.'},
    ('abs-2192', 'title'): {
        'expected': 'Reparación módulo ABS Suzuki Splash 2004-2010',
        'text': 'Reparación módulo ABS Suzuki Splash 2004-2010 ATE MK70',
        'reason': 'Añade la unidad que nombra la propia ficha; la distingue de la ficha general del Splash.'},
    ('abs-1399', 'title'): {
        'expected': 'Reparación módulo ABS Renault Master 2 1998-2010',
        'text': 'Reparación módulo ABS Renault Master 2 1998-2010 ATE MK20',
        'reason': 'Añade la unidad que nombra la propia ficha; la distingue de la versión TRW EBC430.'},
    ('abs-3022', 'title'): {
        'expected': 'Reparación módulo ABS Renault Master 2 1998-2010',
        'text': 'Reparación módulo ABS Renault Master 2 1998-2010 TRW EBC430',
        'reason': 'Añade la unidad que nombra la propia ficha; la distingue de la versión ATE MK20.'},
    ('main-13204', 'title'): {
        'expected': 'Reparación Pantalla Cuadro Citroen C4 Picasso',
        'text': 'Reparación Pantalla Cuadro Citroen C4 Picasso 9814748580, 9813590280 y 9816911280',
        'reason': 'Añade las referencias de la pantalla que figuran en la ficha; distingue las cuatro fichas del C4 Picasso.'},
    ('main-13206', 'title'): {
        'expected': 'Reparación Pantalla Cuadro Citroen C4 Picasso',
        'text': 'Reparación Pantalla Cuadro Citroen C4 Picasso 9827062880 y 9828380580',
        'reason': 'Añade las referencias de la pantalla que figuran en la ficha; distingue las cuatro fichas del C4 Picasso.'},
    ('main-13207', 'title'): {
        'expected': 'Reparación Pantalla Cuadro Citroen C4 Picasso',
        'text': 'Reparación Pantalla Cuadro Citroen C4 Picasso LLB123LT01 y B123LT01',
        'reason': 'Añade las referencias de la pantalla que figuran en la ficha; distingue las cuatro fichas del C4 Picasso.'},
    ('main-13208', 'title'): {
        'expected': 'Reparación Pantalla Cuadro Citroen C4 Picasso',
        'text': 'Reparación Pantalla Cuadro Citroen C4 Picasso LPM123G216A y LPM123G',
        'reason': 'Añade las referencias de la pantalla que figuran en la ficha; distingue las cuatro fichas del C4 Picasso.'},
    ('main-9197', 'title'): {
        'expected': 'Reparación Pantalla Táctil Multimedia Navegador MMI Audi',
        'text': 'Reparación Pantalla Táctil Multimedia MMI Audi: principales fallos',
        'reason': 'Distingue la página de fallos de la que lista los modelos de Audi.'},
})

# Captions reviewed against the actual eight image files on 17 October 2026.
# Keys are full local paths, never image position or a filename-only guess.
REVIEWED_CAPTIONS = {
    '/assets/media/09/0978ba55626204a5-mazda-3.webp': ('main-2942', 'Cuadro completo · Mazda 3 BK'),
    '/assets/media/12/1285c65a92623f7e-display-mazda-3.webp': ('main-2942', 'Detalle de la pantalla · Mazda 3 BK'),
    '/assets/media/e6/e63407d3a5535405-mazda-3-bm.webp': ('main-2942', 'Cuadro completo · Mazda 3 BM'),
    '/assets/media/e3/e3b161ebb4bdbfc6-display-mazda-3-bm.webp': ('main-2942', 'Detalle de la pantalla de velocidad · Mazda 3 BM'),
    '/assets/media/37/3796efae0f4eb31d-mazda-5-2.webp': ('main-2942', 'Cuadro completo · Mazda 5'),
    '/assets/media/04/043f5ea1e7fd640a-display-mazda-5.webp': ('main-2942', 'Detalle de la pantalla · Mazda 5'),
    '/assets/media/52/52c057a3aba2edd2-mazda-6.webp': ('main-2942', 'Cuadro completo · Mazda 6'),
    '/assets/media/43/43ecd0453b61812d-display-mazda-6.webp': ('main-2942', 'Detalle de la pantalla · Mazda 6'),
}

# Each anchor is an explicit source heading, not a compatibility inference.
REVIEWED_INDEX_GROUPS = {
    'main-2942': [
        {'label': 'Versiones del Mazda 3', 'anchors': ['detalle-6', 'detalle-17']},
        {'label': 'Otros modelos Mazda', 'anchors': ['detalle-28', 'detalle-39']},
    ],
}

_changes = {}


def public_text(value, uid='', location=''):
    original = str(value or '')
    text = original
    applied = []
    override = OVERRIDES.get((uid, location))
    if override:
        if original != override['expected']:
            raise ValueError(f'Public copy override source changed: {uid} {location}')
        text = override['text']
        applied.append('reviewed:' + location)
    else:
        for name, pattern, replacement in RULES:
            updated = re.sub(pattern, replacement, text, flags=re.I)
            if updated != text:
                applied.append(name)
                text = updated
    if text != original:
        _changes[(uid, location, original)] = {
            'uid': uid, 'location': location, 'sourceText': original,
            'publicText': text, 'rules': applied,
            'sourceTextSha256': hashlib.sha256(original.encode()).hexdigest(),
        }
    return text


def photo_caption(record, image, section_title='', ordinal=1, total=1):
    reviewed = REVIEWED_CAPTIONS.get(image['src'])
    if reviewed and reviewed[0] == record['uid']:
        return reviewed[1]
    context = section_title or record.get('title') or 'este servicio'
    return f'Foto {ordinal} de {total} · {context}'


def reset_copy_report():
    _changes.clear()


def write_copy_report(root):
    report = {
        'schemaVersion': 1, 'reviewDate': '2026-10-17',
        'scope': 'Public presentation only; archived sources and catalogue unchanged.',
        'rules': [{'id': name, 'pattern': pattern, 'replacement': replacement}
                  for name, pattern, replacement in RULES],
        'reviewedOverrides': [{'uid': uid, 'location': location, **value}
                              for (uid, location), value in OVERRIDES.items()],
        'reviewedPhotoCaptions': [{'uid': uid, 'localPath': path, 'caption': caption,
                                  'evidence': 'Actual image visually reviewed; source section membership retained.'}
                                 for path, (uid, caption) in REVIEWED_CAPTIONS.items()],
        'reviewedIndexGroups': REVIEWED_INDEX_GROUPS,
        'replacements': sorted(_changes.values(), key=lambda row: (row['uid'], row['location'], row['sourceText'])),
        'constraints': {'catalogueModified': False, 'archiveModified': False,
                       'referencesReassigned': False, 'newCommercialPromises': False},
    }
    destination = Path(root) / 'data/public-copy-report.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report
