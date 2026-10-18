<?php
require __DIR__ . '/common.php';
$options = getopt('', ['config:', 'public-root:']);
reportCli(function () use ($options) {
    $app = intakeFromOptions($options);
    return ['php' => PHP_VERSION, 'sqlite' => $app->db->query('SELECT sqlite_version()')->fetchColumn(),
        'privateStorage' => true, 'limits' => $app->limits, 'mode' => $app->config['mode'],
        'submissionsEnabled' => $app->enabled(), 'staffUsersConfigured' => count($app->config['staffUsers'] ?? []),
        'notificationTransport' => $app->config['notifications']['transport'] ?? 'not_configured',
        'storageBytes' => $app->storageBytes(), 'storageBudgetBytes' => $app->config['storageBudgetBytes'] ?? 128 * 1024 * 1024,
        'integrity' => $app->db->query('PRAGMA integrity_check')->fetchColumn(),
        'workshopIntegrationConfigured' => false,
        'remainingChecks' => ['Staff notification delivery is not proved by this command.', 'Validate the deployed HTTP flow, access protection, backup/restore and workshop reception before production.']];
});
