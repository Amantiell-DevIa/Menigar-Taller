<?php
declare(strict_types=1);

// Exact public-media aliases only. No intake credentials, database or user files.
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex');
$root = defined('MENIGAR_APP_ROOT') ? MENIGAR_APP_ROOT : dirname(__DIR__, 2);
$mapPath = defined('MENIGAR_APP_ROOT') ? $root . '/data/legacy-media-routes.json' : $root . '/backend/legacy-media-routes.json';
try {
    $path = rawurldecode((string) parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH));
    if (!in_array($_SERVER['REQUEST_METHOD'], ['GET', 'HEAD'], true)
        || !preg_match('~^/(?:wp-content/uploads/|reparacion-abs/wp-content/uploads/|docs/)~D', $path)
        || preg_match('~[\x00-\x1f\x7f\\\\]~', $path) || str_contains($path, '..')) {
        http_response_code(404); exit;
    }
    $routes = json_decode(file_get_contents($mapPath), true, 8, JSON_THROW_ON_ERROR);
    $target = $routes[$path] ?? '';
    if (!is_string($target) || !preg_match('~^/assets/(?:media|documentos)/[A-Za-z0-9/_\-.]+$~D', $target)) {
        http_response_code(404); exit;
    }
    $public = defined('MENIGAR_APP_ROOT') ? $root : dirname(__DIR__);
    if (!is_file($public . $target)) { http_response_code(503); exit; }
    header('Cache-Control: public, max-age=3600');
    header('Location: ' . $target, true, 301);
} catch (Throwable $error) {
    error_log('MENIGAR legacy media: ' . get_class($error));
    http_response_code(503);
}
