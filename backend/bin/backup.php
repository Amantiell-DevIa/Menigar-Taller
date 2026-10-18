<?php
require __DIR__ . '/common.php';
$options = getopt('', ['config:', 'public-root:', 'output:']);
reportCli(function () use ($options) {
    if (empty($options['output'])) throw new \RuntimeException('Specify a private --output path');
    $public = $options['public-root'] ?? dirname(__DIR__, 2) . '/public';
    if (!is_dir($public)) $public = dirname(__DIR__, 2);
    return \Menigar\Backup::create(intakeFromOptions($options), $options['output'], $public);
});
