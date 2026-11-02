# MENIGAR · Electrónica del automóvil

Nueva web de MENIGAR (Desarrollos Digitales Menigar, Alcobendas, desde 1989). Incluye la portada, un catálogo de 1.648 fichas de reparación, la búsqueda por marca, modelo y pieza, y la solicitud de reparación en tres pasos.

> Versión de revisión. Aún no está publicada para clientes y las páginas se sirven con `noindex`.

## Vista previa en Vercel

`vercel.json` define todo lo necesario: sin *framework*, compilación `node scripts/build_vercel_static.cjs` y salida en `dist`. La compilación copia solo la web pública, a partir de una lista permitida. Vercel añade `noindex`, `nosniff` y una política de seguridad de contenido estricta.

Cada página responde en la misma dirección que en www.menigar.com: las fichas en la de su página de WordPress y las páginas generales en la de su equivalente (Cómo funciona en `/envios/`, Garantía en `/garantias/`, Ayuda en `/preguntas-frecuentes/`…). Como en WordPress, una dirección sin la barra final lleva a la que la tiene (`trailingSlash`). Las redirecciones de `vercel.json` las genera `scripts/build_redirects.py`: las direcciones de WordPress que cambian, con su motivo en `data/redirects.json`, y las direcciones anteriores del prototipo (`/reparaciones/…`, `/como-funciona.html`…).

El backend PHP de la solicitud no funciona en Vercel. El formulario lo detecta, se muestra como «Vista previa de diseño» y desactiva el envío.

Los vídeos de YouTube y el mapa de Google de la portada se cargan solo cuando el visitante pulsa reproducir o «Ver el mapa aquí». La CSP permite únicamente esos dos marcos (`youtube-nocookie.com` y `google.com`).

## Estructura

| Ruta | Contenido |
|---|---|
| `index.html`, `assets/css/portada.css`, `assets/home/` | Portada y sus fotos |
| `opciones-hero.html`, `assets/css/opciones-hero.css` | Opciones de hero para revisión |
| `laboratorio.html`, `laboratorio.js`, `scripts/build_laboratorio.cjs` | Laboratorio de portada: página aparte, generada desde `index.html`, para comparar los diseños |
| `servicios/index.html`, `app.js`, `data/*.js` | Catálogo y búsqueda, en `/servicios/` |
| `reparacion-*/`, `fallo-*/`, `programacion-*/`, `sustitucion-*/` | Fichas de reparación generadas, en la dirección de su página de WordPress |
| `envios/`, `garantias/`, `preguntas-frecuentes/`, `sobre-nosotros/`, `politica-de-privacidad/`, `politica-de-cookies/`, `avisos-legales/` | Páginas generales generadas |
| `scripts/site_paths.py` | Direcciones públicas y decisión de cada página sin equivalente |
| `solicitud.html`, `solicitud.css`, `solicitud.js`, `resumen.html`, `receipt.js` | Solicitud y resumen |
| `style.css`, `reparaciones.css`, `bmw.css`, `hyundai.css` | Sistema visual compartido |
| `assets/` | Fotografías, documentos y la fuente Inter (licencia OFL) |
| `backend/`, `api/` | Backend PHP de la solicitud (no se usa en Vercel) |
| `scripts/` | Generación del catálogo, las fichas, los paquetes de revisión y la compilación para Vercel |
| `tests/` | Pruebas |

## Pruebas

```sh
python3 -m unittest discover -s tests
node tests/test_busqueda.cjs
node tests/test_home_index.cjs
node tests/test_solicitud.cjs
```

Las capturas originales de WordPress que usan los scripts de reconstrucción del catálogo no forman parte de este repositorio.
