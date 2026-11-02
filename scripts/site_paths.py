"""Public addresses of the new website: those of www.menigar.com (URL parity, 2 Nov 2026).

The migration must keep the search ranking built over ten years, so a page keeps the address of the
WordPress page it replaces. Every ficha answers at its WordPress address: its localPath is the path of
its url. Each general page answers at the address of its WordPress counterpart; the menu labels do not
change. scripts/build_redirects.py writes the old addresses that do change, each with its reason.
"""
from __future__ import annotations

import re

# A ficha address is its WordPress path: a service folder (/reparacion-abs/, /reparacion-displays/,
# /fallo-display-fis-mfa-grupo-vag/...) and up to three folders below it. The local servers, the PHP
# routers and the Vercel build serve this shape, the general pages below and the root files.
FICHA_PATH = re.compile(r'/(?:reparacion|fallo|programacion|sustitucion)-[a-z0-9_-]+/(?:[a-z0-9_-]+/){0,3}')

# «path» is the public address, «wordpress» the WordPress page it keeps (None for a new page) and
# «prototype» the address the prototype used until 2 Nov 2026, which vercel.json redirects.
GENERAL_PAGES = [
    {'key': 'servicios', 'path': '/servicios/', 'wordpress': '/servicios/', 'prototype': '/servicios.html',
     'decision': 'Equivalente 1:1 de la página de servicios de WordPress.'},
    {'key': 'como-funciona', 'path': '/envios/', 'wordpress': '/envios/', 'prototype': '/como-funciona.html',
     'decision': 'Cómo funciona nació de «Envíos» (cómo preparar y enviar la pieza) y conserva su dirección.'},
    {'key': 'garantia', 'path': '/garantias/', 'wordpress': '/garantias/', 'prototype': '/garantia.html',
     'decision': 'Equivalente 1:1: las mismas condiciones de garantía.'},
    {'key': 'ayuda', 'path': '/preguntas-frecuentes/', 'wordpress': '/preguntas-frecuentes/', 'prototype': '/ayuda.html',
     'decision': 'Ayuda une las preguntas frecuentes y el contacto. Conserva /preguntas-frecuentes/, indexable y en el '
                 'mapa del sitio de WordPress; /contacto/, bloqueada en su robots.txt, redirige a su apartado de contacto.'},
    {'key': 'sobre-nosotros', 'path': '/sobre-nosotros/', 'wordpress': None, 'prototype': '/sobre-nosotros.html',
     'decision': 'Página nueva, sin equivalente en WordPress: dirección nueva, con barra final como las demás.'},
    {'key': 'privacidad', 'path': '/politica-de-privacidad/', 'wordpress': '/politica-de-privacidad/', 'prototype': '/privacidad.html',
     'decision': 'Equivalente 1:1 de la política de privacidad.'},
    {'key': 'cookies', 'path': '/politica-de-cookies/', 'wordpress': '/politica-de-cookies/', 'prototype': '/cookies.html',
     'decision': 'Equivalente 1:1 de la política de cookies.'},
    {'key': 'condiciones', 'path': '/avisos-legales/', 'wordpress': '/avisos-legales/', 'prototype': '/condiciones.html',
     'decision': 'Equivalente 1:1 del aviso legal.'},
]
PAGE = {page['key']: page['path'] for page in GENERAL_PAGES}
# Names the prototype had used before, already redirected since 28 Oct 2026.
OLDER_PROTOTYPE_PAGES = {'/envios.html': PAGE['como-funciona'], '/taller.html': PAGE['sobre-nosotros']}

CONTACT = PAGE['ayuda'] + '#contacto'
ABS_RESULTS = PAGE['servicios'] + '?pieza=abs#resultados'
EMPTY_PAGE = 'Página publicada sin contenido: lleva a la ficha de su marca, la página superior en WordPress.'

# WordPress pages that are neither a ficha nor one of the general pages: (destination, kind, reason).
# The six copies merged into a ficha come from MERGED_COPIES in build_catalog.py, and the old addresses
# that WordPress itself redirects, from data/legacy-link-resolution.json.
WORDPRESS_PAGES = {
    '/home/': ('/', 'duplicate-home', 'Copia de la portada publicada como página aparte, con su propia dirección.'),
    '/contacto/': (CONTACT, 'merged-page', 'Contacto se une a Ayuda, que conserva /preguntas-frecuentes/. '
                   'El robots.txt de WordPress bloqueaba esta dirección.'),
    '/top-repair/': (PAGE['servicios'], 'no-equivalent', 'Lista de reparaciones frecuentes sin página propia en la nueva web; '
                     'Servicios presenta las destacadas. Pendiente de confirmar con el dueño.'),
    '/ofertas-de-empleo/': (PAGE['sobre-nosotros'], 'no-equivalent', 'Ofertas de empleo antiguas (noindex en WordPress) sin '
                            'página en la nueva web; Sobre nosotros presenta la empresa. Pendiente de confirmar con el dueño.'),
    '/reparacion-abs/': (ABS_RESULTS, 'no-equivalent', 'Portada de la web de ABS. La nueva web no tiene una página propia de ABS '
                         'y lleva a sus resultados en Servicios. Es la redirección con más riesgo SEO.'),
    '/reparacion-abs/home-abs-coches/': (ABS_RESULTS, 'no-equivalent', 'Portada de ABS para coches, sin página propia en la nueva web.'),
    '/reparacion-abs/home-abs-motos/': (ABS_RESULTS, 'no-equivalent', 'Portada de ABS para motos, sin página propia en la nueva web.'),
    '/reparacion-abs/404-2/': (ABS_RESULTS, 'no-equivalent', 'Página de error de la web de ABS, publicada como indexable y en su mapa del sitio.'),
    '/reparacion-abs/contacto/': (CONTACT, 'merged-page', 'Contacto de la web de ABS; la nueva web tiene un solo contacto, en Ayuda.'),
    '/reparacion-abs/politica-de-privacidad/': (PAGE['privacidad'], 'merged-page', 'Copia de la política de privacidad en la web de ABS; la nueva web tiene una sola.'),
    '/reparacion-abs/politica-de-cookies/': (PAGE['cookies'], 'merged-page', 'Copia de la política de cookies en la web de ABS; la nueva web tiene una sola.'),
    '/reparacion-abs/avisos-legales/': (PAGE['condiciones'], 'merged-page', 'Copia del aviso legal en la web de ABS; la nueva web tiene uno solo.'),
    '/reparacion-abs/yamaha-moto/xj6-2009-2016/': ('/reparacion-abs/yamaha-moto/', 'empty-page', EMPTY_PAGE),
    '/reparacion-abs/land-rover/freelander-1997-2006-ate-mk25/': ('/reparacion-abs/land-rover/', 'empty-page', EMPTY_PAGE),
}
# WordPress pages that disappear without a redirect.
WORDPRESS_DROPPED = {
    '/error-404/': 'Página de error de WordPress: noindex y bloqueada en su robots.txt, nunca estuvo en Google.',
}
# The other addresses listed in the sitemaps of the two WordPress installations.
WORDPRESS_SITEMAP = 'Mapa del sitio XML de WordPress; el nuevo /sitemap.xml reúne todas las páginas de las dos webs.'
WORDPRESS_OTHER = {
    '/reparacion-abs/sitemap.html': (ABS_RESULTS, 'old-sitemap', 'Mapa del sitio en HTML de la web de ABS.'),
    **{path: ('/sitemap.xml', 'old-sitemap', WORDPRESS_SITEMAP) for path in (
        '/sitemap-posttype-page.xml', '/sitemap-author.xml', '/reparacion-abs/sitemap.xml',
        '/reparacion-abs/page-sitemap.xml', '/reparacion-abs/sitemap-misc.xml')},
}


def prototype_path(record):
    """The address the prototype gave a ficha until 2 Nov 2026."""
    return f"/reparaciones/{record['uid']}-{record['slug']}/"
