<?php
declare(strict_types=1);

// Copy to private/config.php OUTSIDE the public document root. Never publish it.
// A production configuration requires HTTPS, a stable random secret and staff users.
return [
    'mode' => 'review',
    'acceptSubmissions' => false,
    'baseUrl' => 'https://www.menigar.com',
    'secret' => '', // At least 32 random bytes, encoded as hex/base64; retain in backups.
    'dataDir' => __DIR__ . '/data', // Resolve this from the actual PRIVATE config location.
    'termsVersion' => 'draft-2026-10-15',
    'maxFileBytes' => 5 * 1024 * 1024,
    'maxTotalBytes' => 15 * 1024 * 1024,
    'maxFilesPerUnit' => 5,
    'maxTotalFiles' => 50, // Effective limit also respects PHP max_file_uploads.
    'maxUnits' => 10,
    'minFreeBytes' => 50 * 1024 * 1024,
    'storageBudgetBytes' => 128 * 1024 * 1024, // Confirm account quota before production.
    'requestsPerHour' => 30,
    'staffUsers' => [
        // 'name' => password_hash('a password chosen by that person', PASSWORD_DEFAULT),
    ],
    // Mandatory when hosting a review through api/review.php. Local loopback preview
    // can remain ungated only without MENIGAR_REVIEW_GATE=1; never expose that server.
    'reviewGate' => [
        'enabled' => false, // Fail closed at the review controller until configured.
        'users' => [/* 'reviewer' => password_hash('separate review password', PASSWORD_DEFAULT), */],
        'stateDir' => __DIR__ . '/review-access', // Private, writable, outside public/.
        'allowLoopbackHttp' => false, // Tests only: requires actual 127.0.0.1 peer and host.
        'maxAgeSeconds' => 28800,
        'idleSeconds' => 1800,
        'attemptsPer15Minutes' => 10,
    ],
    'notifications' => [
        'transport' => 'spool', // Private test spool; never sends mail. Production: sendmail.
        'to' => 'informacion@menigar.com', // Confirmed: customer service.
        'from' => 'informacion@menigar.com', // Validate acceptance/delivery in the target MTA.
    ],
];
