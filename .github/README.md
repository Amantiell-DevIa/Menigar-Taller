# MENIGAR · Electrónica del automóvil

Nueva web de MENIGAR (Desarrollos Digitales Menigar, Alcobendas, desde 1989). Incluye la portada, un catálogo de 1.648 fichas de reparación, la búsqueda por marca, modelo y pieza, y la solicitud de reparación en tres pasos.

> Versión de revisión. Aún no está publicada para clientes y las páginas se sirven con `noindex`.

## Vista previa en Vercel

`vercel.json` define todo lo necesario: sin *framework*, compilación `node scripts/build_vercel_static.cjs` y salida en `dist`. La compilación copia solo la web pública, a partir de una lista permitida. Vercel añade `noindex`, `nosniff` y una política de seguridad de contenido estricta.

El backend PHP de la solicitud no funciona en Vercel. El formulario lo detecta, se muestra como «Vista previa de diseño» y desactiva el envío.

## Estructura

| Ruta | Contenido |
|---|---|
| `index.html`, `assets/css/portada.css` | Portada |
| `servicios.html`, `app.js`, `data/*.js` | Catálogo y búsqueda |
| `reparaciones/` | Fichas de reparación generadas |
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
