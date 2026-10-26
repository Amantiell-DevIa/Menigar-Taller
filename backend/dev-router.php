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
$rootFiles = ['index.html','servicios.html','solicitud.html','resumen.html','envios.html','garantia.html','taller.html','ayuda.html','privacidad.html','condiciones.html','cookies.html','opciones-hero.html','laboratorio.html','laboratorio.js','style.css','solicitud.css','hyundai.css','bmw.css','reparaciones.css','garantia.css','app.js','solicitud.js','resumen.js','receipt.js','robots.txt','sitemap.xml','favicon.ico','apple-touch-icon.png'];
$allowed = $path === '/' || in_array(ltrim($path, '/'), $rootFiles, true)
    || in_array(ltrim($path, '/'), ['data/catalogo-v2.js','data/home-index.js','data/family-media.js'], true)
    || (str_starts_with($path, '/assets/') && preg_match('~\.(?:jpg|jpeg|png|gif|webp|svg|ico|pdf|css|woff2)$~i', $path))
    || (preg_match('~^/reparaciones/[a-zA-Z0-9_-]+/(?:index\.html)?$~D', $path));
$target = realpath($root . ($path === '/' ? '/index.html' : $path));
if (!$allowed || !$target || !str_starts_with($target, $root . '/')) { http_response_code(404); exit; }
return false;
