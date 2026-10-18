<?php
require __DIR__ . '/common.php';
$options = getopt('', ['config:', 'public-root:', 'limit:']);
reportCli(fn() => (new \Menigar\Notifications(intakeFromOptions($options)))->run((int) ($options['limit'] ?? 30)));
