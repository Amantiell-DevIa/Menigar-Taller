#!/usr/bin/env python3
"""
Extractor y Procesador del Subsitio Especializado de ABS de Menigar.com
Endpoint: https://www.menigar.com/reparacion-abs/wp-json/wp/v2/pages
Descarga y cachea todas las páginas del subsitio de ABS (840 páginas)
para extraer modelos de vehículos, módulos ABS (Bosch, ATE, TRW, etc.),
referencias OEM / fabricante, síntomas de frenado y códigos DTC.
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

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'cache_abs')
BASE_URL = "https://www.menigar.com/reparacion-abs/wp-json/wp/v2/pages"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

def download_all_pages():
    os.makedirs(CACHE_DIR, exist_ok=True)
    page = 1
    per_page = 100
    total_downloaded = 0
    
    print(f"Iniciando descarga de catálogo ABS desde {BASE_URL}...")
    
    while True:
        cache_file = os.path.join(CACHE_DIR, f"abs_page_{page}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Página {page} cargada desde caché local ({len(data)} elementos)")
            total_downloaded += len(data)
            if len(data) < per_page:
                break
            page += 1
            continue
            
        url = f"{BASE_URL}?per_page={per_page}&page={page}"
        print(f"Descargando página {page}: {url}...")
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f" -> Página {page} guardada ({len(data)} elementos)")
                total_downloaded += len(data)
                if len(data) < per_page:
                    break
                page += 1
                time.sleep(1) # Respetar el servidor
        except urllib.error.HTTPError as e:
            if e.code == 400: # Superado el total de páginas
                print(f"Fin de paginación alcanzado en página {page}.")
                break
            else:
                print(f"Error HTTP {e.code} en página {page}: {e.reason}")
                break
        except Exception as e:
            print(f"Error descargando página {page}: {e}")
            break
            
    print(f"Descarga finalizada. Total páginas ABS en caché: {total_downloaded}")

if __name__ == '__main__':
    download_all_pages()
