<?php
declare(strict_types=1);
// Invoked by api/review.php in a NEW review root, or explicitly opted-in dev-router.
// $applicationRoot and $publicRoot are absolute, server-chosen paths, never user input.
require_once $applicationRoot . '/backend/ReviewGate.php';
try {
    $configurationPath = getenv('MENIGAR_CONFIG') ?: $applicationRoot . '/private/config.php';
    if (!is_file($configurationPath)) throw new RuntimeException('Review configuration unavailable');
    $configuration = require $configurationPath;
    if (!is_array($configuration)) throw new RuntimeException('Review configuration invalid');
    if (!(new \Menigar\ReviewGate($configuration, $publicRoot))->enforce()) return;
    $path = rawurldecode((string) parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH));
    if (preg_match('~[\x00-\x1f\x7f\\\\]~', $path) || str_contains($path, '..') || str_starts_with($path, '//')) { http_response_code(404); return; }
    if (preg_match('~^/(?:wp-content/uploads/|reparacion-abs/wp-content/uploads/|docs/)~', $path)) {
        require $publicRoot . '/api/legacy-media.php'; return;
    }
    if (preg_match('~^/(?:api|equipo)(?:/|$)~', $path)) {
        if ($path === '/api/review.php') { http_response_code(404); return; }
        require $publicRoot . '/api/index.php'; return;
    }
    $files = ['index.html','servicios.html','solicitud.html','resumen.html','envios.html','taller.html','ayuda.html','privacidad.html','condiciones.html','cookies.html','style.css','solicitud.css','hyundai.css','bmw.css','reparaciones.css','app.js','solicitud.js','resumen.js','receipt.js','robots.txt','sitemap.xml','data/catalogo-v2.js','data/home-index.js','data/family-media.js'];
    $allowed = $path === '/' || in_array(ltrim($path, '/'), $files, true)
        || (str_starts_with($path, '/assets/') && preg_match('~\.(?:jpg|jpeg|png|gif|webp|svg|ico|pdf|css|woff2)$~iD', $path))
        || preg_match('~^/reparaciones/[A-Za-z0-9_-]+/(?:index\.html)?$~D', $path);
    $target = realpath($publicRoot . ($path === '/' ? '/index.html' : $path));
    if ($target && is_dir($target)) $target = realpath($target . '/index.html');
    if (!$allowed || !$target || !is_file($target) || !str_starts_with($target, realpath($publicRoot) . '/')) { http_response_code(404); return; }
    if (!in_array($_SERVER['REQUEST_METHOD'] ?? '', ['GET', 'HEAD'], true)) { header('Allow: GET, HEAD'); http_response_code(405); return; }
    $types = ['html'=>'text/html; charset=utf-8','css'=>'text/css; charset=utf-8','js'=>'text/javascript; charset=utf-8','xml'=>'application/xml; charset=utf-8','txt'=>'text/plain; charset=utf-8','jpg'=>'image/jpeg','jpeg'=>'image/jpeg','png'=>'image/png','gif'=>'image/gif','webp'=>'image/webp','svg'=>'image/svg+xml','ico'=>'image/x-icon','pdf'=>'application/pdf','woff2'=>'font/woff2'];
    header('Content-Type: ' . ($types[strtolower(pathinfo($target, PATHINFO_EXTENSION))] ?? 'application/octet-stream'));
    header('Content-Length: ' . filesize($target));
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'HEAD') readfile($target);
} catch (Throwable $error) {
    \Menigar\ReviewGate::headers();
    error_log('MENIGAR review access: ' . get_class($error));
    http_response_code(503); header('Content-Type: application/json; charset=utf-8');
    echo '{"error":"La revisión privada no está disponible. Contacta con el responsable."}';
}
