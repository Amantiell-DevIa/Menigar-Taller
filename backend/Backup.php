<?php
declare(strict_types=1);
namespace Menigar;

use RuntimeException;
use SQLite3;
use ZipArchive;

final class Backup
{
    public static function create(Intake $intake, string $destination, string $publicRoot): array
    {
        if (!extension_loaded('sqlite3') || !extension_loaded('zip')) throw new RuntimeException('SQLite3 and ZIP are required');
        $parent = realpath(dirname($destination)); $public = realpath($publicRoot);
        if (!$parent || !$public || str_starts_with($parent . '/', $public . '/') || file_exists($destination)) throw new RuntimeException('Use a new backup path outside public/');
        $stage = $parent . '/.menigar-snapshot-' . bin2hex(random_bytes(8)); mkdir($stage, 0700);
        $partial = $destination . '.partial';
        try {
            // SQLite3::backup works with the hosting's SQLite 3.26 too. A file
            // copy or VACUUM INTO would not provide the same compatibility.
            $source = new SQLite3($intake->storage . '/solicitudes.sqlite3', SQLITE3_OPEN_READONLY);
            $snapshot = new SQLite3($stage . '/database.sqlite3');
            if (!$source->backup($snapshot)) throw new RuntimeException('SQLite snapshot failed');
            $snapshot->close(); $source->close();
            $database = new \PDO('sqlite:' . $stage . '/database.sqlite3', null, null, [\PDO::ATTR_ERRMODE => \PDO::ERRMODE_EXCEPTION, \PDO::ATTR_DEFAULT_FETCH_MODE => \PDO::FETCH_ASSOC]);
            if ($database->query('PRAGMA integrity_check')->fetchColumn() !== 'ok') throw new RuntimeException('Snapshot integrity failed');
            $files = ['database.sqlite3' => $stage . '/database.sqlite3'];
            $configuration = $intake->config;
            file_put_contents($stage . '/configuration.json', json_encode($configuration, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
            $files['configuration.json'] = $stage . '/configuration.json';
            foreach ($database->query('SELECT path,sha256 FROM files')->fetchAll() as $file) {
                if (!preg_match('~^SOL-\d{8}-[A-F0-9]{8}/[a-f0-9]{48}\.bin$~D', $file['path'])) throw new RuntimeException('Unexpected stored attachment path');
                $path = $intake->storage . '/uploads/' . $file['path'];
                if (!is_file($path) || hash_file('sha256', $path) !== $file['sha256']) throw new RuntimeException('Attachment snapshot mismatch');
                $files['uploads/' . $file['path']] = $path;
            }
            $required = array_sum(array_map('filesize', $files));
            if (disk_free_space($parent) < $required + (int) ($intake->config['minFreeBytes'] ?? 50 * 1024 * 1024)) throw new RuntimeException('Not enough free space for private backup');
            $manifest = ['version' => 1, 'createdAt' => gmdate('c'), 'requests' => (int) $database->query('SELECT count(*) FROM requests')->fetchColumn(), 'files' => []];
            $zip = new ZipArchive();
            if ($zip->open($partial, ZipArchive::CREATE | ZipArchive::EXCL) !== true) throw new RuntimeException('Private ZIP unavailable');
            foreach ($files as $name => $path) {
                $manifest['files'][$name] = ['bytes' => filesize($path), 'sha256' => hash_file('sha256', $path)];
                if (!$zip->addFile($path, $name)) throw new RuntimeException('ZIP add failed');
            }
            $zip->addFromString('manifest.json', json_encode($manifest, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
            if (!$zip->close()) throw new RuntimeException('ZIP write failed');
            chmod($partial, 0600);
            $verified = new ZipArchive();
            if ($verified->open($partial, ZipArchive::CHECKCONS) !== true) throw new RuntimeException('ZIP consistency failed');
            foreach ($manifest['files'] as $name => $expected) {
                $stream = $verified->getStream($name); $hash = hash_init('sha256'); $size = 0;
                if (!$stream) throw new RuntimeException('ZIP stream unavailable');
                while (!feof($stream)) { $chunk = fread($stream, 1024 * 1024); if ($chunk === false) throw new RuntimeException('ZIP read failed'); hash_update($hash, $chunk); $size += strlen($chunk); }
                fclose($stream);
                if ($size !== $expected['bytes'] || hash_final($hash) !== $expected['sha256']) throw new RuntimeException('ZIP contents differ from snapshot');
            }
            $verified->close();
            if (!rename($partial, $destination)) throw new RuntimeException('Backup finalization failed');
            $sha = hash_file('sha256', $destination);
            file_put_contents($destination . '.sha256', $sha . '  ' . basename($destination) . "\n"); chmod($destination . '.sha256', 0600);
            return ['path' => $destination, 'bytes' => filesize($destination), 'sha256' => $sha, 'requests' => $manifest['requests'], 'entries' => count($manifest['files']), 'containsPrivateConfiguration' => true];
        } finally {
            foreach (glob($stage . '/*') ?: [] as $file) if (is_file($file)) unlink($file);
            if (is_dir($stage)) rmdir($stage);
            if (is_file($partial)) unlink($partial);
        }
    }

    public static function restore(string $archive, string $expectedSha, string $destination, string $baseUrl, string $publicRoot): array
    {
        if (!preg_match('/^[a-f0-9]{64}$/D', $expectedSha) || !hash_equals($expectedSha, hash_file('sha256', $archive))) throw new RuntimeException('Backup SHA-256 mismatch');
        if (file_exists($destination) || !str_starts_with($destination, '/')) throw new RuntimeException('Use a new private restore directory');
        $parent = realpath(dirname($destination)); $public = realpath($publicRoot);
        if (!$parent || !$public || str_starts_with($parent . '/', $public . '/')) throw new RuntimeException('Restore outside the public document root');
        if (!preg_match('~^http://(?:127\.0\.0\.1|localhost)(?::\d+)?$~D', $baseUrl)) throw new RuntimeException('Recovery tests must use a loopback URL');
        $zip = new ZipArchive();
        if ($zip->open($archive, ZipArchive::CHECKCONS) !== true) throw new RuntimeException('Backup ZIP invalid');
        $manifest = json_decode($zip->getFromName('manifest.json') ?: '', true, 64, JSON_THROW_ON_ERROR);
        if (($manifest['version'] ?? null) !== 1 || !isset($manifest['files']['configuration.json'], $manifest['files']['database.sqlite3']) || $zip->numFiles !== count($manifest['files']) + 1) throw new RuntimeException('Backup manifest invalid');
        mkdir($destination, 0700, true);
        try {
            foreach ($manifest['files'] as $name => $expected) {
                if (!in_array($name, ['configuration.json','database.sqlite3'], true) && !preg_match('~^uploads/SOL-\d{8}-[A-F0-9]{8}/[a-f0-9]{48}\.bin$~D', $name)) throw new RuntimeException('Unsafe archive path');
                $stream = $zip->getStream($name);
                if (!$stream) throw new RuntimeException('Missing backup entry');
                $path = $destination . '/' . $name; $parent = dirname($path);
                if (!is_dir($parent)) mkdir($parent, 0700, true);
                $out = fopen($path, 'xb'); $hash = hash_init('sha256'); $size = 0;
                while (!feof($stream)) { $chunk = fread($stream, 1024 * 1024); if ($chunk === false) throw new RuntimeException('Backup read failed'); $size += strlen($chunk); if ($size > (int) $expected['bytes']) throw new RuntimeException('Backup size mismatch'); hash_update($hash, $chunk); if (fwrite($out, $chunk) !== strlen($chunk)) throw new RuntimeException('Restore write failed'); }
                fclose($stream); fclose($out); chmod($path, 0600);
                if ($size !== $expected['bytes'] || hash_final($hash) !== $expected['sha256']) throw new RuntimeException('Backup hash mismatch');
            }
            $zip->close();
            $configuration = json_decode(file_get_contents($destination . '/configuration.json'), true, 64, JSON_THROW_ON_ERROR);
            $configuration['mode'] = 'review'; $configuration['baseUrl'] = $baseUrl;
            $configuration['dataDir'] = $destination; $configuration['acceptSubmissions'] = false;
            $configuration['notifications'] = ['transport' => 'spool', 'to' => '', 'from' => ''];
            file_put_contents($destination . '/config.php', "<?php\nreturn " . var_export($configuration, true) . ";\n"); chmod($destination . '/config.php', 0600);
            $database = new \PDO('sqlite:' . $destination . '/database.sqlite3');
            if ($database->query('PRAGMA integrity_check')->fetchColumn() !== 'ok' || $database->query('PRAGMA foreign_key_check')->fetch()) throw new RuntimeException('Restored database invalid');
            $database = null;
            rename($destination . '/database.sqlite3', $destination . '/solicitudes.sqlite3');
            return ['config' => $destination . '/config.php', 'requests' => $manifest['requests'], 'mode' => 'review', 'notifications' => 'spool', 'acceptSubmissions' => false];
        } catch (\Throwable $error) {
            // Keep an incomplete recovery private for inspection. Never overwrite
            // another data directory, execute archived PHP or activate notifications.
            throw $error;
        }
    }
}
