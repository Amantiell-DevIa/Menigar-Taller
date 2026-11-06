<?php
declare(strict_types=1);
// Local PHP review only. Prevents exposing source code, captures and private data.
$root = dirname(__DIR__);
// Optional isolated test gate. Existing loopback previews/configurations are unchanged.
if (getenv('MENIGAR_REVIEW_GATE') === '1') {
    define('MENIGAR_APP_ROOT', $root);
    $applicationRoot = $root; $publicRoot = $root;
    require __DIR__ . '/review-router.php';
    return;
}
$path = rawurldecode((string) parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
if (str_contains($path, '..') || str_contains($path, "\0")) { http_response_code(404); exit; }
if (preg_match('~^/(?:wp-content/uploads/|reparacion-abs/wp-content/uploads/|docs/)~', $path)) {
    define('MENIGAR_APP_ROOT', $root);
    require $root . '/api/legacy-media.php';
    return;
}
if (preg_match('~^/(api|equipo)(/|$)~', $path)) {
    define('MENIGAR_APP_ROOT', $root);
    require $root . '/api/index.php';
    return;
}
$rootFiles = ['index.html','solicitud.html','resumen.html','opciones-hero.html','laboratorio.html','laboratorio.js','style.css','solicitud.css','hyundai.css','bmw.css','reparaciones.css','garantia.css','servicios.css','paginas.css','app.js','solicitud.js','resumen.js','receipt.js','robots.txt','sitemap.xml','favicon.ico','apple-touch-icon.png'];
// Pages served from a folder at their WordPress address (scripts/site_paths.py): the general pages and every ficha.
$pageFolders = ['servicios/','envios/','garantias/','preguntas-frecuentes/','sobre-nosotros/','politica-de-privacidad/','politica-de-cookies/','avisos-legales/'];
$isPage = static fn(string $folder): bool => in_array($folder, $pageFolders, true)
    || preg_match('~^(?:reparacion|fallo|programacion|sustitucion)-[a-z0-9_-]+/(?:[a-z0-9_-]+/){0,3}$~D', $folder) === 1;
$relative = ltrim($path, '/');
// Like WordPress, a page address without its final slash answers with a 301 to the address with it.
if ($relative !== '' && !str_ends_with($relative, '/') && $isPage($relative . '/') && is_file($root . '/' . $relative . '/index.html')) {
    $query = (string) parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY);
    header('Location: /' . $relative . '/' . ($query !== '' ? '?' . $query : ''), true, 301);
    exit;
}
$folder = preg_replace('~index\.html$~D', '', $relative);
// A folder without its own index.html would make the PHP server look for one in the folders above it.
$allowed = $path === '/' || in_array($relative, $rootFiles, true)
    || in_array($relative, ['data/catalogo-v2.js','data/home-index.js','data/family-media.js'], true)
    || (str_starts_with($path, '/assets/') && preg_match('~\.(?:jpg|jpeg|png|gif|webp|svg|ico|pdf|css|woff2|mp4)$~i', $path))
    || ($isPage($folder) && is_file($root . '/' . $folder . 'index.html'));
$target = realpath($root . ($path === '/' ? '/index.html' : $path));
if (!$allowed || !$target || !str_starts_with($target, $root . '/')) { http_response_code(404); exit; }
return false;
