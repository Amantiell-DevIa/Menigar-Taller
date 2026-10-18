<?php
declare(strict_types=1);

// Public front controller. The application/configuration live outside public/.
$applicationRoot = defined('MENIGAR_APP_ROOT') ? MENIGAR_APP_ROOT : dirname(__DIR__, 2);
require $applicationRoot . '/backend/Intake.php';
require $applicationRoot . '/backend/Views.php';
require $applicationRoot . '/backend/Http.php';
\Menigar\Http::headers();
try {
    $path = getenv('MENIGAR_CONFIG') ?: $applicationRoot . '/private/config.php';
    if (!is_file($path)) throw new \Menigar\HttpError(503, 'La recepción de solicitudes todavía no está habilitada. Contacta con el taller.');
    $configuration = require $path;
    (new \Menigar\Http(new \Menigar\Intake($configuration, dirname(__DIR__))))->run();
} catch (\Menigar\HttpError $error) { \Menigar\Http::json(['error' => $error->getMessage()], $error->status); }
catch (\Throwable $error) { error_log('MENIGAR bootstrap: ' . get_class($error)); \Menigar\Http::json(['error' => 'El servicio de solicitudes no está disponible. Contacta con el taller.'], 503); }
