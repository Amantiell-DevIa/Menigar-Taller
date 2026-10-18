<?php
require __DIR__ . '/common.php';
$options = getopt('', ['archive:', 'sha256:', 'destination:', 'base-url:', 'public-root:']);
reportCli(function () use ($options) {
    foreach (['archive','sha256','destination','base-url'] as $required) if (empty($options[$required])) throw new \RuntimeException('Missing --' . $required);
    $public = $options['public-root'] ?? dirname(__DIR__, 2) . '/public';
    if (!is_dir($public)) $public = dirname(__DIR__, 2);
    return \Menigar\Backup::restore($options['archive'], $options['sha256'], $options['destination'], $options['base-url'], $public);
});
