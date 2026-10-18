#!/usr/bin/env python3
"""
Extractor y Procesador de Averías, Códigos DTC y Soluciones de Menigar.com
Analiza la estructura jerárquica de URL y contenidos de Menigar para construir:
1. data/averias_menigar.json (Catálogo completo de 820+ averías clasificadas por Componente, Marca, Modelo)
2. data/dtc_database.json (Base de datos DTC y códigos de máquina con diagnóstico y enlaces)
3. data/dtc_database.js (Módulo cargable directamente para el buscador web)
"""

import os
import sys
import json
import time
import re
import html
import urllib.request
import urllib.error
from urllib.parse import urlparse

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'cache')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'data', 'averias_menigar.json')
DTC_FILE = os.path.join(os.path.dirname(__file__), 'data', 'dtc_database.json')
JS_DTC_FILE = os.path.join(os.path.dirname(__file__), 'data', 'dtc_database.js')

BASE_URL = "https://www.menigar.com/wp-json/wp/v2/pages"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

BRAND_SLUGS = {
    'alfa-romeo': 'Alfa Romeo', 'audi': 'Audi', 'bmw': 'BMW', 'chevrolet': 'Chevrolet',
    'chrysler': 'Chrysler', 'citroen': 'Citroën', 'dacia': 'Dacia', 'dodge': 'Dodge',
    'fiat': 'Fiat', 'ford': 'Ford', 'honda': 'Honda', 'hyundai': 'Hyundai',
    'iveco': 'Iveco', 'jaguar': 'Jaguar', 'jeep': 'Jeep', 'kia': 'Kia',
    'lancia': 'Lancia', 'land-rover': 'Land Rover', 'lexus': 'Lexus', 'man': 'MAN',
    'maserati': 'Maserati', 'mazda': 'Mazda', 'mercedes': 'Mercedes-Benz',
    'mini': 'Mini', 'mitsubishi': 'Mitsubishi', 'nissan': 'Nissan', 'opel': 'Opel',
    'peugeot': 'Peugeot', 'porsche': 'Porsche', 'renault': 'Renault', 'saab': 'Saab',
    'scania': 'Scania', 'seat': 'Seat', 'skoda': 'Skoda', 'smart': 'Smart',
    'subaru': 'Subaru', 'suzuki': 'Suzuki', 'toyota': 'Toyota', 'volkswagen': 'Volkswagen',
    'vw': 'Volkswagen', 'volvo': 'Volvo'
}

SLUG_TO_COMP = {
    'reparacion-cuadro-instrumentos': ('cuadro', 'Cuadro de Instrumentos'),
    'reparacion-pantalla-tactil-multimedia': ('multimedia', 'Pantalla Táctil / Multimedia'),
    'reparacion-pantalla-navegador': ('multimedia', 'Pantalla Táctil / Multimedia'),
    'reparacion-burbuja-pantalla-tactil-multimedia': ('multimedia', 'Pantalla Táctil / Multimedia'),
    'reparacion-pantalla-multimedia': ('multimedia', 'Pantalla Táctil / Multimedia'),
    'reparacion-puntos-negros-en-pantallas-multimedia': ('multimedia', 'Pantalla Táctil / Multimedia'),
    'reparacion-displays': ('display', 'Display LCD / Cuentakilómetros'),
    'reparacion-electronica-cambio': ('cambio', 'Electrónica Cambio Automático'),
    'reparacion-palanca-selectora-cambio-automatico': ('cambio', 'Electrónica Cambio Automático'),
    'reparacion-abs-ate-mk100-grupo-vag': ('abs', 'Módulo o Bomba de ABS / ESP'),
    'reparacion-fallo-abs-c1380-citroen-ate-mk70': ('abs', 'Módulo o Bomba de ABS / ESP'),
    'reparacion-error-fallo-5df5-abs-bmw-ate-mk60-y-mk61': ('abs', 'Módulo o Bomba de ABS / ESP'),
    'reparacion-fallo-abs-renault-ate-mk60': ('abs', 'Módulo o Bomba de ABS / ESP'),
    'reparacion-modulo-bluetooth-blueme-fiat': ('inmo', 'Inmovilizador & Blue&Me'),
    'reparacion-inmovilizadores-transponder': ('inmo', 'Inmovilizador & Blue&Me'),
    'reparacion-bsi': ('bsi', 'Módulo BSI / Confort'),
    'reparacion-centralita-opel-isuzu': ('ecu', 'Centralita de Motor (ECU)'),
    'reparacion-unidad-de-mando-hibrida-gm-opel': ('ecu', 'Centralita de Motor (ECU)'),
    'programacion-reparacion-centralitas': ('ecu', 'Centralita de Motor (ECU)'),
    'reparacion-centralitas-clima': ('ecu', 'Centralita Clima / ECU'),
    'reparacion-fallo-399999-km': ('display', 'Display LCD / Cuentakilómetros'),
    'reparacion-fallo-oil-display-nissan-cabstar-y-atleon': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-cuentakilometros-888888-chevrolet-captiva-opel-antara': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-cuentakilometros-fiat-doblo': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-display-cuentakilometros-mercedes-clase-a-y-b': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-display-cuentakilometros-mercedes-vito': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-display-cuentakilometros-bmw-serie5-e34-e39': ('display', 'Display LCD / Cuentakilómetros'),
    'fallo-display-fis-mfa-grupo-vag': ('display', 'Display LCD / Cuentakilómetros'),
    'reparacion-cuentakilometros': ('cuadro', 'Cuadro de Instrumentos'),
    'reparacion-cuentakilometros-porsche-365': ('cuadro', 'Cuadro de Instrumentos'),
    'cambio-iluminacion-del-cuadro-de-instrumentos': ('cuadro', 'Cuadro de Instrumentos'),
    'sustitucion-mph-por-kmh-cuadro-de-instrumentos': ('cuadro', 'Cuadro de Instrumentos'),
    'reparacion-aranazos-en-pantalla-display-tft-del-cuadro-de-instrumentos': ('cuadro', 'Cuadro de Instrumentos'),
    'fallo-iluminacion-cuadro-de-instrumentos-grupo-vag': ('cuadro', 'Cuadro de Instrumentos'),
    'reparacion-fallo-iluminacion-cuadro-renault-laguna-3': ('cuadro', 'Cuadro de Instrumentos'),
    'reparacion-fallo-iluminacion-cuadro-renault-megane-3': ('cuadro', 'Cuadro de Instrumentos')
}

IGNORABLE_SLUGS = [
    'politica-de-privacidad', 'avisos-legales', 'politica-de-cookies', 'contacto',
    'ofertas-de-empleo', 'envios', 'garantias', 'faq', 'preguntas-frecuentes', 'como-llegar',
    'presupuesto', 'aviso-legal', 'error-404'
]

AGGREGATOR_SLUGS = {'inicio', 'home', 'top-repair', 'servicios'}

KNOWN_CODE_DESCRIPTIONS = {
    '5DF5': 'BMW Módulo ABS (ATE MK60 / MK61) - Fallo interno centralita / procesador. Sin comunicación o fallo de alimentación.',
    '5DF0': 'BMW ABS - Fallo motor de la bomba hidráulica de recirculación. Desgaste de escobillas o gripaje.',
    '5E20': 'BMW ABS - Sensor de presión de frenado 1 defectuoso (G201). Pérdida de calibración.',
    '01130': 'Grupo VAG (VW, Seat, Audi, Skoda) - ABS Funcionamiento no plausible. Pérdida de señal hidráulica.',
    '01276': 'Grupo VAG - Bomba hidráulica de ABS (V64) / fallo alimentación circuito motor.',
    '01435': 'Grupo VAG - Transmisor 1 para presión de frenado (G201). Reparación y calibración en banco.',
    '01420': 'Grupo VAG - Válvula de conmutación a alta presión para ESP (N227).',
    '01421': 'Grupo VAG - Válvula de conmutación a alta presión para ESP (N228).',
    '16352': 'Grupo VAG - Unidad de control eléctrico de frenado / confort defectuosa. Error en hardware interno.',
    'C1380': 'Citroën / Peugeot (ATE MK70) - Fallo interno motor bomba de recirculación de ABS.',
    'C1350': 'Citroën / Peugeot - Relé de válvulas / electroválvulas fallo interno en bloque ABS.',
    'C101600': 'Grupo VAG (ATE MK100) - Funcionamiento del ABS inverosímil / pérdida de presión en ruedas.',
    'C1288': 'Ford Focus II / Mazda 3 - Transductor de presión de freno primario en bomba ATE MK60.',
    'DF088': 'Renault Megane II / Scenic II - Circuito del sensor de presión de frenado defectuoso.',
    'DF010': 'Renault - Circuito del motor de la bomba de ABS / alimentación interrumpida.',
    'DF017': 'Renault - Unidad de control de ABS / calculador defectuoso.',
    'P0251': 'Opel 1.7 DTi (Isuzu / Delphi) - Válvula dosificación bomba inyección / coche se para en caliente.',
    'P0705': 'Mercedes / Audi - Sensor de rango de transmisión (PRNDS) fallo señal o palanca.',
    'P0706': 'Audi Multitronic / VW DSG - Sensor de rango de marcha señal inadmisible en cuadro.',
    '399999': 'Citroën Jumper / Fiat Ducato / Peugeot Boxer - Cuentakilómetros bloqueado al llegar a 399.999 km.',
    'OIL': 'Nissan Industriales (Atleon, Cabstar, Interstar) - Mensaje de aviso OIL persistente en display sin avería real.'
}

def clean_html(raw_html):
    if not raw_html:
        return ""
    # 1. Eliminar estilos, scripts y textareas (donde Live Composer guarda su CSS/JSON)
    text = re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<textarea[^>]*>.*?</textarea>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # 2. Reemplazar saltos de bloque
    text = re.sub(r'</?(?:p|div|li|h[1-6]|br|tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # 3. Eliminar cualquier otro tag HTML
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    
    # 4. Eliminar artefactos de maquetación de Live Composer
    text = re.sub(r'Anchura del elemento\s+(?:(?:\d+/12)\s*)+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:desktop|tablet|phone)\s+(?:enabled|disabled)\b', '', text, flags=re.IGNORECASE)
    
    boilerplate = {
        'inicio', 'servicios', 'cuadros de instrumentos', 'abs', 'displays',
        'pantalla multimedia', 'electrónica cambio automático', 'palanca selectora cambio',
        'bluetooth blue&me fiat', 'centralitas ecu', 'clima', 'bsi/confort', 'inmovilizadores',
        'contacto', 'envíos', 'garantías', 'faq', '- seleccionar -', 'cómo llegar',
        'síguenos en las redes sociales', 'horario de apertura y atención telefónica',
        'política de privacidad', 'avisos legales', 'política de cookies',
        'copyright © 2017 - desarrollos digitales menigar'
    }
    
    clean_lines = []
    for l in text.splitlines():
        line = ' '.join(l.split()).strip()
        lower = line.lower()
        if not line or len(line) < 3 or lower in boilerplate:
            continue
        if 'desarrollos digitales menigar' in lower or 'parque empresarial casablanca' in lower:
            continue
        if '91 662 27 81' in lower or 'informacion@menigar.com' in lower:
            continue
        if re.match(r'^(?:1[0-2]|[1-9])/12', line):
            continue
        clean_lines.append(line)
        
    return '\n'.join(clean_lines)

def parse_taxonomy(url, title, clean_text):
    path = urlparse(url).path.strip('/')
    parts = path.split('/')
    cat_slug = parts[0] if parts else ''
    
    # 1. Componente
    comp_info = SLUG_TO_COMP.get(cat_slug)
    if not comp_info:
        for slug_k, (ck, cn) in SLUG_TO_COMP.items():
            if slug_k in path:
                comp_info = (ck, cn)
                break
    if not comp_info:
        comp_info = ('otros', 'Diagnóstico y Reparación Avanzada')
        
    comp_key, comp_name = comp_info
    
    # 2. Marca
    brand = None
    if len(parts) >= 2 and parts[1] in BRAND_SLUGS:
        brand = BRAND_SLUGS[parts[1]]
    else:
        combined = (path + ' ' + title).lower()
        for b_slug, b_name in BRAND_SLUGS.items():
            if re.search(r'\b' + re.escape(b_slug) + r'\b', combined) or re.search(r'\b' + re.escape(b_name.lower()) + r'\b', combined):
                brand = b_name
                break
                
    # 3. Modelo
    model = title
    if brand:
        clean_model = re.sub(r'^(?:reparaci[oó]n|cuadro de instrumentos|pantalla|display)\s+', '', title, flags=re.IGNORECASE)
        clean_model = re.sub(re.escape(brand), '', clean_model, flags=re.IGNORECASE).strip(' -:,')
        if clean_model and len(clean_model) >= 2:
            model = clean_model
            
    return comp_key, comp_name, brand, model

def build_datasets():
    pages = []
    for i in range(1, 100):
        cache_path = os.path.join(CACHE_DIR, f"pages_page_{i}.json")
        if not os.path.exists(cache_path):
            break
        with open(cache_path, 'r', encoding='utf-8') as f:
            pages.extend(json.load(f))
            
    print(f"Páginas cargadas de caché: {len(pages)}")
    
    dtc_pattern = re.compile(
        r'\b([CPBU][0-9]{4,6}|DF[0-9]{3,4}|5[DE][0-9A-Z]{2,3}|0[0-9]{4}|16352|399\.?999|Aviso OIL)\b',
        re.IGNORECASE
    )
    
    catalog = []
    dtc_db = {}
    
    for p in pages:
        slug = p.get('slug', '').lower()
        if any(ign in slug for ign in IGNORABLE_SLUGS):
            continue
            
        title = html.unescape(p.get('title', {}).get('rendered', '')).strip()
        link = p.get('link', '')
        raw_html = p.get('content', {}).get('rendered', '')
        text = clean_html(raw_html)
        
        if not text or len(text) < 40:
            continue
            
        comp_key, comp_name, brand, model = parse_taxonomy(link, title, text)
        is_agg = slug in AGGREGATOR_SLUGS
        
        # Extraer códigos DTC
        page_dtc_map = {}
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            matches = dtc_pattern.findall(line)
            for m in matches:
                code = m.upper().replace('.', '').replace('AVISO ', '')
                if code in {'2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '28100'}:
                    continue
                desc = line
                if len(line) <= len(code) + 5 and i + 1 < len(lines):
                    desc = f"{code} - {lines[i+1]}"
                page_dtc_map[code] = desc
                
        # Extraer problemas / síntomas específicos (líneas que empiezan por "-" o mencionan fallos)
        symptom_bullets = []
        for l in lines:
            if l.startswith('-') or 'fallo' in l.lower() or 'problemas comunes' in l.lower():
                symptom_bullets.append(l)
                if len(symptom_bullets) >= 6:
                    break
                    
        # Excerpt descriptivo limpio
        good_lines = [l for l in lines if len(l) > 25 and not l.startswith('http') and not l.startswith('-')]
        desc_summary = ' '.join(good_lines[:2]) if good_lines else title
        if len(desc_summary) > 280:
            desc_summary = desc_summary[:277] + '...'
            
        catalog_entry = {
            'id': p.get('id'),
            'title': title,
            'slug': slug,
            'url': link,
            'isAggregator': is_agg,
            'componentKey': comp_key,
            'componentName': comp_name,
            'brand': brand,
            'model': model,
            'dtcCodes': list(page_dtc_map.keys()),
            'symptoms': symptom_bullets,
            'description': desc_summary,
            'fullText': text[:2500]
        }
        catalog.append(catalog_entry)
        
        # Registrar en dtc_db
        for code, specific_desc in page_dtc_map.items():
            known_desc = KNOWN_CODE_DESCRIPTIONS.get(code)
            clean_title = f"{comp_name} - {title}" if not is_agg else f"Código {code}"
            
            if code not in dtc_db:
                dtc_db[code] = {
                    'code': code,
                    'title': clean_title,
                    'component': comp_name,
                    'componentKey': comp_key,
                    'brands': [brand] if brand and not is_agg else [],
                    'desc': known_desc or specific_desc,
                    'url': link if not is_agg else 'https://www.menigar.com/',
                    'pages': [title]
                }
            else:
                entry = dtc_db[code]
                if title not in entry['pages']:
                    entry['pages'].append(title)
                if not is_agg and (entry['url'] == 'https://www.menigar.com/' or 'Inicio' in entry['title']):
                    entry['title'] = clean_title
                    entry['url'] = link
                    entry['component'] = comp_name
                    entry['componentKey'] = comp_key
                    if brand and brand not in entry['brands']:
                        entry['brands'] = [brand]
                    if not known_desc:
                        entry['desc'] = specific_desc
                elif not is_agg and brand and brand not in entry['brands']:
                    entry['brands'].append(brand)

    # Inyectar códigos clave conocidos si faltaban
    for code, known_desc in KNOWN_CODE_DESCRIPTIONS.items():
        if code not in dtc_db:
            dtc_db[code] = {
                'code': code,
                'title': f"Avería Código {code}",
                'component': 'Módulo ABS / Electrónica',
                'componentKey': 'abs',
                'brands': ['Citroën', 'BMW', 'Peugeot', 'Volkswagen'],
                'desc': known_desc,
                'url': 'https://www.menigar.com/',
                'pages': ['Catálogo Menigar']
            }
        else:
            if not dtc_db[code].get('desc') or len(dtc_db[code]['desc']) < 30:
                dtc_db[code]['desc'] = known_desc

    # Guardar archivos JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
        
    with open(DTC_FILE, 'w', encoding='utf-8') as f:
        json.dump(dtc_db, f, ensure_ascii=False, indent=2)

    with open(JS_DTC_FILE, 'w', encoding='utf-8') as f:
        f.write("// Base de datos de Códigos DTC extraída de Menigar.com\n")
        f.write("window.MENIGAR_DTC_DATABASE = ")
        json.dump(dtc_db, f, ensure_ascii=False)
        f.write(";\n")

    print(f"\n=======================================================")
    print(f" ¡BASE DE DATOS OPTIMIZADA CON ÉXITO!")
    print(f"=======================================================")
    print(f" 1. Páginas clasificadas: {len(catalog)}")
    print(f" 2. Códigos DTC indexados: {len(dtc_db)}")
    print(f" 3. Catálogo JSON: {OUTPUT_FILE}")
    print(f" 4. Códigos DTC JSON: {DTC_FILE}")
    print(f" 5. Módulo DTC JS: {JS_DTC_FILE}")
    print(f"=======================================================\n")

if __name__ == '__main__':
    build_datasets()
