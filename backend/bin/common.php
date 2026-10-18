<?php
declare(strict_types=1);
require dirname(__DIR__) . '/Intake.php';
require dirname(__DIR__) . '/Notifications.php';
require dirname(__DIR__) . '/Backup.php';
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
function intakeFromOptions(array $options): \Menigar\Intake {
    $path = $options['config'] ?? getenv('MENIGAR_CONFIG');
    if (!$path || !is_file($path)) throw new \RuntimeException('Specify a private --config path');
    $configuration = require $path;
    $root = $options['public-root'] ?? dirname(__DIR__, 2) . '/public';
    // A source checkout uses the project root; deployed releases use public/.
    if (!is_dir($root)) $root = dirname(__DIR__, 2);
    return new \Menigar\Intake($configuration, $root);
}
function reportCli(callable $run): void {
    try { echo json_encode($run(), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n"; }
    catch (\Throwable $error) { fwrite(STDERR, json_encode(['error' => $error->getMessage()], JSON_UNESCAPED_UNICODE) . "\n"); exit(1); }
}
