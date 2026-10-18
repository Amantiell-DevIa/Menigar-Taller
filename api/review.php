<?php
declare(strict_types=1);
// Only for an isolated, fully protected review installation. Never a public launch gate.
$applicationRoot = defined('MENIGAR_APP_ROOT') ? MENIGAR_APP_ROOT : dirname(__DIR__, 2);
$publicRoot = dirname(__DIR__);
require $applicationRoot . '/backend/review-router.php';
