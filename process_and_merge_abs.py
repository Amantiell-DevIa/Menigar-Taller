#!/usr/bin/env python3
"""
Procesador y Unificador de la Base de Datos ABS con el Catálogo General de Menigar
Lee las 840 páginas en caché de data/cache_abs/ y las fusiona con:
1. data/averias_menigar.json (Catálogo completo unificado: Cuadros, Pantallas, Centralitas y ABS)
2. data/dtc_database.json & data/dtc_database.js (Códigos DTC enriquecidos con diagnosis de frenada)
3. data/catalogo_buscador.js (Índice unificado con ~1.600 modelos y referencias OEM para búsqueda instantánea)
"""

import os
import sys
import glob
import json
import re
import html
from collections import defaultdict
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CACHE_ABS_DIR = os.path.join(DATA_DIR, 'cache_abs')

CATALOG_JSON = os.path.join(DATA_DIR, 'averias_menigar.json')
DTC_JSON = os.path.join(DATA_DIR, 'dtc_database.json')
DTC_JS = os.path.join(DATA_DIR, 'dtc_database.js')
CATALOG_JS = os.path.join(DATA_DIR, 'catalogo_buscador.js')

# Mapeo de Marcas de Coches y Motos
BRANDS_MAP = {
    # Coches
    'vw': 'Volkswagen', 'audi': 'Audi', 'opel': 'Opel', 'ford': 'Ford', 'mercedes': 'Mercedes-Benz',
    'renault': 'Renault', 'seat': 'Seat', 'citroen': 'Citroën', 'bmw': 'BMW', 'peugeot': 'Peugeot',
    'volvo': 'Volvo', 'skoda': 'Skoda', 'fiat': 'Fiat', 'hyundai': 'Hyundai', 'nissan': 'Nissan',
    'suzuki': 'Suzuki', 'chevrolet': 'Chevrolet', 'honda': 'Honda', 'mazda': 'Mazda', 'kia': 'Kia',
    'mitsubishi': 'Mitsubishi', 'toyota': 'Toyota', 'jaguar': 'Jaguar', 'chrysler': 'Chrysler',
    'jeep': 'Jeep', 'alfa-romeo': 'Alfa Romeo', 'dacia': 'Dacia', 'ssangyong': 'SsangYong',
    'land-rover': 'Land Rover', 'subaru': 'Subaru', 'ferrari': 'Ferrari', 'mini': 'Mini',
    'dodge': 'Dodge', 'saab': 'Saab', 'smart': 'Smart', 'porsche': 'Porsche', 'mg': 'MG',
    'iveco': 'Iveco', 'rover': 'Rover', 'maserati': 'Maserati', 'bentley': 'Bentley',
    'infiniti': 'Infiniti', 'lotus': 'Lotus',
    # Motos
    'bmw-motorrad': 'BMW Motorrad', 'yamaha-moto': 'Yamaha Motor', 'piaggio': 'Piaggio',
    'motos-suzuki': 'Suzuki Moto', 'vespa': 'Vespa', 'kymco': 'Kymco', 'aprilia': 'Aprilia',
    'moto-guzzi': 'Moto Guzzi', 'benelli': 'Benelli', 'ktm': 'KTM', 'triumph': 'Triumph',
    'kawasaki': 'Kawasaki', 'motos-honda': 'Honda Moto', 'harley-davidson': 'Harley-Davidson',
    'ducati': 'Ducati'
}

MOTO_BRANDS = {
    'bmw-motorrad', 'yamaha-moto', 'piaggio', 'motos-suzuki', 'vespa',
    'kymco', 'aprilia', 'moto-guzzi', 'benelli', 'ktm', 'triumph',
    'kawasaki', 'motos-honda', 'harley-davidson', 'ducati'
}

IGNORABLE_SLUGS = {
    'politica-de-cookies', 'avisos-legales', 'politica-de-privacidad', 'contacto',
    'home-abs-coches', 'home-abs-motos', '404-2', 'informacion-abs-ate-esp-mk61'
}

REAL_DTC_REGEX = re.compile(
    r'(?<![0-9A-Za-z\.\-])(?:(?:c[oó]digo(?:\s+de)?\s+aver[ií]a|c[oó]digo(?:\s+de)?\s+error|fallo|dtc)\s+)?([CPBU][0-9]{4}|DF[0-9]{3,4}|5[DE][0-9A-Z]{2,3}|(?:00283|00285|00287|00290|00301|00493|01130|01201|01276|01314|01316|01418|01419|01420|01421|01435|16349|16350|16352|16355|04FC|059B))(?![0-9A-Za-z\.\-])',
    re.IGNORECASE
)

# Diccionario de descripciones técnicas de alta precisión para DTCs de ABS
KNOWN_ABS_DTCS = {
    '01130': 'Grupo VAG (VW, Seat, Audi, Skoda) - Señal de funcionamiento de ABS no plausible (046A). Despresurización en circuito interno.',
    '01276': 'Grupo VAG - Bomba hidráulica de ABS (V64). Fallo en alimentación, bobinado o escobillas del motor de recirculación.',
    '01435': 'Grupo VAG - Transmisor 1 para presión de frenado (G201). Fallo eléctrico en circuito / calibración fuera de rango.',
    '00493': 'Grupo VAG - Unidad sensora ESP (G419) sin señal o fallo de comunicación CAN-Bus con el bloque hidráulico.',
    '01201': 'Grupo VAG - Tensión de alimentación insuficiente para la bomba de recirculación de ABS (04B1).',
    '01418': 'Grupo VAG - Válvula de conmutación 1 a alta presión para control electrónico de estabilidad ESP (N225).',
    '01419': 'Grupo VAG - Válvula de conmutación 2 a alta presión para control dinámico del vehículo (N226).',
    '01420': 'Grupo VAG - Válvula de conmutación de alta presión 1 para dinámica de conducción (N227).',
    '01421': 'Grupo VAG - Válvula de conmutación de alta presión 2 para dinámica de conducción (N228).',
    '16349': 'Grupo VAG - Unidad de control de frenos defectuosa (3FDD). Fallo de hardware en microcontrolador interno.',
    '16352': 'Grupo VAG - Unidad de control electrónico defectuosa (3FE0). Error interno de hardware en módulo ABS.',
    '16355': 'Grupo VAG - Unidad de control defectuosa (3FE3). Error memoria EEPROM o microcontrolador de frenada.',
    '04FC': 'Grupo VAG - Relé de motor o bomba hidráulica de ABS agarrotada / avería circuito potencia.',
    '059B': 'Grupo VAG - Sensor de presión de frenado defectuoso en bloque hidráulico ATE MK60.',
    '5DF5': 'BMW - Unidad de mando ABS/DSC defectuosa (ATE MK60 / MK61). Fallo interno del procesador o memoria.',
    '5DF0': 'BMW - Motor de la bomba hidráulica de DSC bloqueado o circuito de alimentación abierto.',
    '5DF1': 'BMW - Suministro de tensión de motor de bomba ABS/DSC fuera de rango.',
    '5E20': 'BMW - Sensor de presión de frenado 1 defectuoso (G201). Presión estática anómala.',
    '5DAA': 'BMW - Sensor de presión de freno delantero defectuoso en bloque DSC.',
    '5DBA': 'BMW - Sensor de presión de freno circuito secundario defectuoso.',
    '5DCA': 'BMW - Sensor de presión hidráulica DSC fuera de rango de tolerancia.',
    'C1380': 'Citroën / Peugeot (ATE MK70) - Fallo interno motor bomba de recirculación de ABS.',
    'C1350': 'Citroën / Peugeot - Relé de electroválvulas en bloque ABS fallo circuito interno.',
    'C1385': 'Citroën / Peugeot - Relé de electroválvula de ABS permanentemente abierto.',
    'C1288': 'Ford / Mazda (ATE MK60) - Transductor de presión de freno primario defectuoso en bomba hidráulica.',
    'C1095': 'Ford / Mazda - Avería en circuito del motor de la bomba hidráulica de ABS.',
    'C1096': 'Ford - Circuito del motor de la bomba hidráulica abierto.',
    'C1111': 'Nissan / Suzuki - Mal funcionamiento del motor de la bomba hidráulica de ABS.',
    'C1028': 'Suzuki / Toyota - Sensor de presión del circuito hidráulico de freno averiado.',
    'C1061': 'Suzuki - Motor de la bomba de ABS / relé del motor defectuoso.',
    'C2116': 'Toyota / Lexus - Tensión anormal en el motor de la bomba de recirculación de ABS.',
    'C1246': 'Toyota / Lexus - Mal funcionamiento del sensor de presión del cilindro maestro.',
    'C1251': 'Toyota - Fallo en circuito eléctrico del motor de la bomba de ABS.',
    'C0004': 'Opel / General Motors - Circuito del sensor de presión de freno defectuoso.',
    'C0020': 'Opel / GM / Renault - Motor de la bomba de ABS mal funcionamiento del circuito.',
    'C0110': 'Opel - Motor de la bomba de ABS gripado o circuito abierto.',
    'C0121': 'Opel - Relé de válvulas de ABS / circuito de control defectuoso.',
    'C0265': 'Opel / Chevrolet - Relé de ABS circuito abierto o cortocircuito a masa.',
    'C2200': 'Chrysler / Jeep / Dodge - Unidad de control ABS interna con función defectuosa.',
    'C2402': 'Hyundai / Kia - Fallo del circuito del motor de la bomba de ABS.',
    'C2498': 'Mercedes-Benz (SBC Clase E W211 / CLS) - Contador de ciclo de frenadas SBC superado / mantenimiento.',
    'DF010': 'Renault - Circuito del motor de la bomba de ABS / alimentación interrumpida.',
    'DF088': 'Renault - Circuito del sensor de presión de frenado defectuoso.',
    'DF017': 'Renault - Calculador / centralita de ABS defectuosa.',
    'DF185': 'Renault - Válvula magnética de servofreno fallo circuito.',
    'U0121': 'Universal CAN-Bus - Pérdida de comunicación con el módulo de control del sistema de frenos (ABS/ESP).',
    'U3000': 'Universal - Unidad de control electrónico (módulo de frenos) - Fallo electrónico interno de hardware.'
}

def clean_html_abs(raw_html):
    if not raw_html:
        return ""
    # 1. Eliminar estilos, scripts y textareas (donde Live Composer guarda su CSS/JSON)
    text = re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<textarea[^>]*>.*?</textarea>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # 2. Reemplazar saltos de bloque
    text = re.sub(r'</?(?:p|div|li|h[1-6]|br|tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?td[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    
    # 3. Eliminar artefactos de maquetación de Live Composer
    text = re.sub(r'Anchura del elemento\s+(?:(?:\d+/12)\s*)+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:desktop|tablet|phone)\s+(?:enabled|disabled)\b', '', text, flags=re.IGNORECASE)
    
    boilerplate = {
        'inicio', 'servicios', 'cuadros de instrumentos', 'abs', 'displays',
        'pantalla multimedia', 'electrónica cambio automático', 'palanca selectora cambio',
        'bluetooth blue&me fiat', 'centralitas ecu', 'clima', 'bsi/confort', 'inmovilizadores',
        'contacto', 'envíos', 'garantías', 'faq', '- seleccionar -', 'cómo llegar',
        'síguenos en las redes sociales', 'horario de apertura y atención telefónica',
        'política de privacidad', 'avisos legales', 'política de cookies',
        'marcas abs', 'alfa romeo', 'aprilia', 'audi', 'benelli', 'bentley', 'bmw',
        'bmw motorrad', 'chevrolet', 'chrysler', 'citroen', 'dacia', 'dodge', 'ducati',
        'fiat', 'ford', 'harley davidson', 'honda', 'honda motos', 'hyundai', 'infiniti',
        'iveco', 'jaguar', 'jeep', 'kawasaki', 'kia', 'ktm', 'kymco', 'land rover', 'lotus',
        'maserati', 'mazda', 'mercedes', 'mini', 'mitsubishi', 'moto guzzi', 'nissan', 'opel',
        'peugeot', 'piaggio', 'porsche', 'renault', 'rover', 'saab', 'seat', 'skoda', 'smart',
        'ssangyong', 'suzuki', 'suzuki motos', 'toyota', 'triumph', 'vespa', 'volkswagen',
        'volvo', 'yamaha', 'copyright © 2017 - desarrollos digitales menigar'
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

def extract_references_from_html(raw_html):
    """Extrae referencias OEM y de fabricante desde tablas <td> y texto."""
    refs = set()
    # 1. Desde celdas <td>
    tds = re.findall(r'<td[^>]*>(.*?)</td>', raw_html, flags=re.DOTALL | re.IGNORECASE)
    for td in tds:
        clean = re.sub(r'<[^>]+>', '', td).strip()
        if clean and len(clean) >= 4:
            # Descartar cabeceras tipo 'Referencia ATE' o textos largos
            if clean.lower().startswith('referencia') or len(clean) > 30:
                continue
            # Asegurar que contiene números
            if re.search(r'\d', clean):
                refs.add(clean)
                # Variante compacta sin espacios
                compact = clean.replace(' ', '')
                if compact != clean and len(compact) >= 5:
                    refs.add(compact)

    # 2. Desde líneas de texto que tienen patrones tipo 10.0960-0311.3 o 0 265 254 602
    text_refs = re.findall(r'\b(?:\d{2}\.\d{4}-\d{4}\.\d|\d\s\d{3}\s\d{3}\s\d{3}|[0-9A-Z]{3,4}\s[0-9A-Z]{3}\s[0-9A-Z]{3}[A-Z]?)\b', raw_html)
    for r in text_refs:
        refs.add(r.strip())
        compact = r.replace(' ', '')
        if compact != r:
            refs.add(compact)

    return sorted(list(refs))

def extract_hardware_family(title, text):
    """Identifica la familia del módulo ABS (ATE MK60, MK70, MK100, Bosch 9.0, etc.)"""
    combined = (title + ' ' + text).lower()
    families = [
        ('ATE MK100', 'ATE MK100'),
        ('ATE MK70M', 'ATE MK70M'),
        ('ATE MK70', 'ATE MK70'),
        ('ATE MK61', 'ATE MK61'),
        ('ATE MK60', 'ATE MK60'),
        ('ATE MK26', 'ATE MK26'),
        ('ATE MK25', 'ATE MK25'),
        ('ATE MK20', 'ATE MK20'),
        ('Bosch 9.0', 'Bosch 9.0'),
        ('Bosch 8.2', 'Bosch 8.2'),
        ('Bosch 8.0', 'Bosch 8.0'),
        ('Bosch 5.7', 'Bosch 5.7'),
        ('Bosch 5.3', 'Bosch 5.3'),
        ('Bosch ESP', 'Bosch ESP'),
        ('TRW Lucas', 'TRW Lucas'),
        ('TRW', 'TRW'),
        ('Kelsey-Hayes', 'Kelsey-Hayes'),
        ('Nissin', 'Nissin')
    ]
    for key, name in families:
        if key.lower() in combined:
            return name
    return 'Módulo ABS / ESP'

def parse_abs_pages():
    cache_files = sorted(glob.glob(os.path.join(CACHE_ABS_DIR, 'abs_page_*.json')))
    print(f"Archivos de caché ABS encontrados: {len(cache_files)}")
    
    parsed_items = []
    abs_dtc_map = defaultdict(lambda: {'pages': [], 'brands': set(), 'desc': ''})
    
    for cf in cache_files:
        with open(cf, 'r', encoding='utf-8') as f:
            pages = json.load(f)
            
        for p in pages:
            slug = p.get('slug', '').lower()
            link = p.get('link', '')
            title = html.unescape(p.get('title', {}).get('rendered', '')).strip()
            raw_html = p.get('content', {}).get('rendered', '')
            
            # Filtro de páginas de cabecera / legales
            if slug in IGNORABLE_SLUGS:
                continue
                
            parts = [s for s in link.replace('https://www.menigar.com/reparacion-abs/', '').strip('/').split('/') if s]
            if len(parts) < 2:
                # Páginas índice de marca o home
                continue
                
            brand_slug = parts[0]
            brand = BRANDS_MAP.get(brand_slug)
            if not brand:
                continue
                
            is_moto = brand_slug in MOTO_BRANDS or 'moto' in brand.lower()
            vehicle_type = 'moto' if is_moto else 'coche'
            
            clean_text = clean_html_abs(raw_html)
            if not clean_text or len(clean_text) < 40:
                continue
                
            # Extraer referencias
            references = extract_references_from_html(raw_html)
            hw_family = extract_hardware_family(title, clean_text)
            
            # Nombre de modelo limpio
            model_name = title
            # Eliminar marca del modelo si está repetida
            clean_m = re.sub(re.escape(brand), '', title, flags=re.IGNORECASE).strip(' -:,')
            # Eliminar el tipo de módulo al final si se desea
            if clean_m and len(clean_m) >= 2:
                model_name = clean_m
                
            # Extraer DTCs y sus explicaciones de la página
            lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
            page_dtcs = set()
            
            for line in lines:
                for m in REAL_DTC_REGEX.finditer(line):
                    code = m.group(1).upper()
                    if code in {'2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026', '28100'}:
                        continue
                    page_dtcs.add(code)
                    
                    # Guardar descripción para la base de datos de DTC
                    if not abs_dtc_map[code]['desc']:
                        if len(line) >= len(code) + 8 and not line.lower().startswith('referencia'):
                            abs_dtc_map[code]['desc'] = line
                    abs_dtc_map[code]['brands'].add(brand)
                    if title not in abs_dtc_map[code]['pages']:
                        abs_dtc_map[code]['pages'].append(title)
                        
            # Extraer síntomas de frenado (líneas clave de fallos)
            symptom_bullets = []
            for l in lines:
                l_low = l.lower()
                if (l.startswith('-') or 'fallo' in l_low or 'presión' in l_low or 'rueda' in l_low or 
                    'bomba' in l_low or 'bloquead' in l_low or 'testigo' in l_low or 'comunicación' in l_low or
                    'pedal' in l_low) and not l_low.startswith('garantía') and not l_low.startswith('ventajas') and len(l) < 140:
                    if l not in symptom_bullets:
                        symptom_bullets.append(l)
                    if len(symptom_bullets) >= 7:
                        break
                        
            # Resumen descriptivo
            desc_lines = [l for l in lines if len(l) > 30 and not l.startswith('-') and not l.startswith('Código') and not l.startswith('DTC')]
            summary_desc = ' '.join(desc_lines[:2]) if desc_lines else f"Reparación profesional del sistema de frenado ABS {hw_family} para {brand} {model_name} en 24h con 2 años de garantía."
            if len(summary_desc) > 280:
                summary_desc = summary_desc[:277] + '...'
                
            entry = {
                'id': p.get('id'),
                'title': title,
                'slug': slug,
                'url': link,
                'isAggregator': False,
                'componentKey': 'abs',
                'componentName': 'Módulo o Bomba de ABS / ESP',
                'brand': brand,
                'model': model_name,
                'hardwareFamily': hw_family,
                'vehicleType': vehicle_type,
                'dtcCodes': sorted(list(page_dtcs)),
                'symptoms': symptom_bullets,
                'references': references[:30], # Top 30 referencias directas
                'totalReferencesCount': len(references),
                'description': summary_desc,
                'fullText': clean_text[:2500]
            }
            parsed_items.append(entry)
            
    print(f"Páginas ABS analizadas con éxito: {len(parsed_items)}")
    return parsed_items, abs_dtc_map

def merge_and_update():
    parsed_abs_items, abs_dtc_map = parse_abs_pages()
    
    # 1. Cargar catálogo existente
    with open(CATALOG_JSON, 'r', encoding='utf-8') as f:
        existing_catalog = json.load(f)
        
    print(f"Catálogo existente (cuadros, pantallas, centralitas...): {len(existing_catalog)} elementos")
    
    # Filtrar cualquier página previa de ABS que fuera placeholder o estuviera en la raíz si se duplica
    existing_urls = {item.get('url') for item in existing_catalog}
    
    new_abs_added = 0
    for item in parsed_abs_items:
        if item['url'] not in existing_urls:
            existing_catalog.append(item)
            existing_urls.add(item['url'])
            new_abs_added += 1
            
    print(f"Nuevos modelos de ABS agregados: {new_abs_added}")
    print(f"Total catálogo unificado: {len(existing_catalog)} elementos")
    
    # Guardar catálogo JSON completo
    with open(CATALOG_JSON, 'w', encoding='utf-8') as f:
        json.dump(existing_catalog, f, ensure_ascii=False, indent=2)
    print(f" -> Guardado: {CATALOG_JSON}")
    
    # 2. Actualizar Base de Datos de Códigos DTC
    with open(DTC_JSON, 'r', encoding='utf-8') as f:
        dtc_db = json.load(f)
        
    print(f"Base de datos DTC previa: {len(dtc_db)} códigos")
    
    # Enriquecer con los DTCs de ABS
    for code, info in abs_dtc_map.items():
        known_desc = KNOWN_ABS_DTCS.get(code)
        target_desc = known_desc or info['desc'] or f"Fallo en sistema de frenos ABS / ESP / Control de Tracción (Código {code})."
        
        if code not in dtc_db:
            dtc_db[code] = {
                'code': code,
                'title': f"Avería ABS / ESP - Código {code}",
                'component': 'Módulo o Bomba de ABS / ESP',
                'componentKey': 'abs',
                'brands': sorted(list(info['brands'])),
                'desc': target_desc,
                'url': 'https://www.menigar.com/reparacion-abs/',
                'pages': info['pages'][:5]
            }
        else:
            # Enriquecer marcas y descripción si no tenía o si la conocida es mejor
            entry = dtc_db[code]
            for b in info['brands']:
                if b not in entry.get('brands', []):
                    entry.setdefault('brands', []).append(b)
            if known_desc:
                entry['desc'] = known_desc
            elif not entry.get('desc') or len(entry['desc']) < 25:
                entry['desc'] = target_desc
            if 'abs' not in entry.get('componentKey', ''):
                entry['componentKey'] = 'abs'
                entry['component'] = 'Módulo o Bomba de ABS / ESP'
                
    # Inyectar todos los códigos de alta precisión conocidos
    for code, desc in KNOWN_ABS_DTCS.items():
        if code not in dtc_db:
            dtc_db[code] = {
                'code': code,
                'title': f"Avería Frenado ABS/ESP - Código {code}",
                'component': 'Módulo o Bomba de ABS / ESP',
                'componentKey': 'abs',
                'brands': ['Audi', 'Volkswagen', 'Seat', 'BMW', 'Renault', 'Citroën', 'Peugeot', 'Ford'],
                'desc': desc,
                'url': 'https://www.menigar.com/reparacion-abs/',
                'pages': ['Catálogo Especializado ABS Menigar']
            }
        else:
            dtc_db[code]['desc'] = desc

    print(f"Base de datos DTC final: {len(dtc_db)} códigos indexados")
    
    with open(DTC_JSON, 'w', encoding='utf-8') as f:
        json.dump(dtc_db, f, ensure_ascii=False, indent=2)
    print(f" -> Guardado: {DTC_JSON}")
    
    with open(DTC_JS, 'w', encoding='utf-8') as f:
        f.write("// Base de datos de Códigos DTC de Menigar (Cuadros, Cambio, ABS, Inmovilizador, ECU)\n")
        f.write("window.MENIGAR_DTC_DATABASE = ")
        json.dump(dtc_db, f, ensure_ascii=False)
        f.write(";\n")
    print(f" -> Guardado: {DTC_JS}")
    
    def clean_symptom_text(s):
        if not s:
            return None
        s_clean = s.strip()
        s_low = s_clean.lower()
        # Descartar menús, navegación, cabeceras y avisos
        if any(bp in s_low for bp in ['seleccionar', 'inicio servicios', 'desarrollos digitales', 'parque empresarial', 'horario de apertura', 'politica de', 'avisos legales', 'cookies']):
            return None
        # Descartar códigos DTC técnicos y referencias
        if any(tech in s_low for tech in ['código', 'codigo', 'dtc', 'referencia', 'ref.']):
            return None
        if re.match(r'^(?:[0-9A-Z\.\-]{4,}\s*)+$', s_clean):
            return None
        # Limpiar viñetas o guiones iniciales
        cleaned = re.sub(r'^[\s\-•·–—*]+', '', s_clean).strip()
        if len(cleaned) < 8 or len(cleaned) > 160:
            return None
        return cleaned

    # 3. Generar Índice Ultraligero para catalogo_buscador.js
    # Estructura compacta para rendimiento instantáneo en navegador (búsqueda predictiva con fuzzy score)
    catalog_index = []
    for item in existing_catalog:
        if item.get('isAggregator'):
            continue
        
        # Filtrar síntomas humanos sin tecnicismos
        cleaned_syms = []
        for s in (item.get('symptoms') or []):
            cs = clean_symptom_text(s)
            if cs and cs not in cleaned_syms:
                cleaned_syms.append(cs)
            if len(cleaned_syms) >= 5:
                break
                
        # Mini objeto optimizado
        mini = {
            'id': item.get('id'),
            't': item.get('title'),
            'b': item.get('brand'),
            'm': item.get('model'),
            'ck': item.get('componentKey'),
            'cn': item.get('componentName'),
            'd': item.get('description', '')[:190],
            'dtc': item.get('dtcCodes', []),
            'sym': cleaned_syms,
            'refs': item.get('references', [])[:15], # Para búsqueda directa por referencia OEM
            'u': item.get('url')
        }
        if item.get('vehicleType'):
            mini['vt'] = item['vehicleType']
        catalog_index.append(mini)
        
    print(f"Índice de modelos y averías para buscador web: {len(catalog_index)} entradas")
    
    with open(CATALOG_JS, 'w', encoding='utf-8') as f:
        f.write("// Índice ultraligero de averías y modelos Menigar (Buscador Predictivo Omni-Search)\n")
        f.write("window.MENIGAR_CATALOG_INDEX = ")
        json.dump(catalog_index, f, ensure_ascii=False)
        f.write(";\n")
    print(f" -> Guardado: {CATALOG_JS}")
    
    print("\n=======================================================")
    print(" ¡FUSIÓN Y OPTIMIZACIÓN COMPLETADA CON ÉXITO!")
    print(f" 1. Total Catálogo Unificado: {len(existing_catalog)} modelos y páginas")
    print(f" 2. Códigos DTC Totales:      {len(dtc_db)} averías diagnosticadas")
    print(f" 3. Índice Web Instantáneo:   {len(catalog_index)} vehículos y sistemas")
    print("=======================================================\n")

if __name__ == '__main__':
    merge_and_update()
