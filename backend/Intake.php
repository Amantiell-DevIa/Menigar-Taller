<?php
declare(strict_types=1);

namespace Menigar;

use PDO;
use RuntimeException;
use Throwable;

final class HttpError extends RuntimeException
{
    public function __construct(public readonly int $status, string $message) { parent::__construct($message); }
}

final class Intake
{
    public readonly PDO $db;
    public readonly array $limits;
    public readonly string $storage;

    public static function bytes(string $value): int
    {
        $value = trim($value);
        if ($value === '' || $value === '0' || $value === '-1') return PHP_INT_MAX;
        $power = ['k' => 1, 'm' => 2, 'g' => 3][strtolower(substr($value, -1))] ?? 0;
        return (int) ((float) $value * (1024 ** $power));
    }

    public function __construct(public readonly array $config, string $publicRoot)
    {
        if (!in_array($config['mode'] ?? '', ['review', 'production'], true)
            || strlen($config['secret'] ?? '') < 32
            || !preg_match('~^https?://[^/]+$~D', $config['baseUrl'] ?? '')
            || parse_url($config['baseUrl'], PHP_URL_USER) !== null
            || ($config['mode'] === 'production' && !str_starts_with($config['baseUrl'], 'https://'))) {
            throw new HttpError(503, 'El servicio de solicitudes todavía no está habilitado. Contacta con el taller.');
        }
        if (!extension_loaded('pdo_sqlite') || !extension_loaded('fileinfo')) {
            throw new HttpError(503, 'El servicio de solicitudes no está disponible. Contacta con el taller.');
        }
        $directory = $config['dataDir'] ?? '';
        if (!$directory || !str_starts_with($directory, DIRECTORY_SEPARATOR)) throw new HttpError(503, 'Configuración privada pendiente.');
        $oldMask = umask(0077);
        try {
            if (!is_dir($directory) && !mkdir($directory, 0700, true)) throw new RuntimeException('Private directory unavailable');
            $this->storage = realpath($directory) ?: throw new RuntimeException('Private directory unavailable');
            $public = realpath($publicRoot) ?: throw new RuntimeException('Public directory unavailable');
            if ($this->storage === $public || str_starts_with($this->storage . '/', $public . '/')) {
                throw new HttpError(503, 'El almacenamiento de solicitudes debe ser privado.');
            }
            foreach (['uploads', 'spool'] as $sub) {
                if (!is_dir($this->storage . '/' . $sub)) mkdir($this->storage . '/' . $sub, 0700);
                if (is_link($this->storage . '/' . $sub)) throw new RuntimeException('Unexpected symbolic directory');
            }
            chmod($this->storage, 0700);
            $this->db = new PDO('sqlite:' . $this->storage . '/solicitudes.sqlite3', null, null,
                [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
            $this->db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;');
            $this->db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS requests (
 reference TEXT PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, token_hash TEXT UNIQUE NOT NULL,
 payload_hash TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS files (
 id TEXT PRIMARY KEY, request_reference TEXT NOT NULL REFERENCES requests(reference),
 unit_number INTEGER NOT NULL, name TEXT NOT NULL, mime TEXT NOT NULL,
 bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, path TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, request_reference TEXT NOT NULL UNIQUE REFERENCES requests(reference),
 state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt INTEGER NOT NULL DEFAULT 0, last_error TEXT, sent_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, request_reference TEXT NOT NULL REFERENCES requests(reference),
 kind TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (bucket TEXT NOT NULL, window INTEGER NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(bucket,window));
SQL);
            chmod($this->storage . '/solicitudes.sqlite3', 0600);
        } finally { umask($oldMask); }
        $postLimit = self::bytes((string) ini_get('post_max_size'));
        $headroom = min(256 * 1024, (int) ($postLimit / 8));
        $total = min((int) ($config['maxTotalBytes'] ?? 15 * 1024 * 1024), max(0, $postLimit - $headroom));
        // Whole MiB makes the visible limit understandable and reserves metadata space.
        $total = (int) floor($total / (1024 * 1024)) * 1024 * 1024;
        $this->limits = [
            'maxFileBytes' => min((int) ($config['maxFileBytes'] ?? 5 * 1024 * 1024), self::bytes((string) ini_get('upload_max_filesize'))),
            'maxFilesPerUnit' => min(5, max(1, (int) ($config['maxFilesPerUnit'] ?? 5))),
            'maxTotalBytes' => $total,
            'maxTotalFiles' => min((int) ($config['maxTotalFiles'] ?? 50), (int) ini_get('max_file_uploads')),
            'maxUnits' => min(10, max(1, (int) ($config['maxUnits'] ?? 10))),
            'maxBodyBytes' => min($postLimit, $total + 256 * 1024),
        ];
        if ($total < 1024 * 1024 || $this->limits['maxTotalFiles'] < 1) throw new HttpError(503, 'Los adjuntos todavía no están habilitados.');
    }

    public function enabled(): bool
    {
        if (($this->config['acceptSubmissions'] ?? false) !== true) return false;
        if ($this->config['mode'] !== 'production') return true;
        $mail = $this->config['notifications'] ?? [];
        return !empty($this->config['staffUsers']) && ($mail['transport'] ?? '') === 'sendmail'
            && filter_var($mail['to'] ?? '', FILTER_VALIDATE_EMAIL) && filter_var($mail['from'] ?? '', FILTER_VALIDATE_EMAIL);
    }
    public function storageBytes(): int
    {
        $bytes = (int) $this->db->query('SELECT COALESCE(sum(bytes),0) FROM files')->fetchColumn();
        foreach (['solicitudes.sqlite3', 'solicitudes.sqlite3-wal', 'solicitudes.sqlite3-shm'] as $file) if (is_file($this->storage . '/' . $file)) $bytes += filesize($this->storage . '/' . $file);
        foreach (glob($this->storage . '/spool/*.json') ?: [] as $file) $bytes += filesize($file);
        return $bytes;
    }
    public function now(): string { return gmdate('Y-m-d\TH:i:s\Z'); }
    public function token(string $key): string { return rtrim(strtr(base64_encode(hash_hmac('sha256', 'receipt:' . $key, $this->config['secret'], true)), '+/', '-_'), '='); }
    public function keyHash(string $key): string { return hash_hmac('sha256', 'idempotency:' . $key, $this->config['secret']); }
    public function one(string $query, array $params = []): ?array
    {
        $s = $this->db->prepare($query); $s->execute($params); return $s->fetch() ?: null;
    }
    public function execute(string $query, array $params = []): void { $s = $this->db->prepare($query); $s->execute($params); }

    public function throttle(string $bucket, int $limit, int $seconds = 3600): void
    {
        $bucket = hash_hmac('sha256', $bucket, $this->config['secret']);
        $window = (int) floor(time() / $seconds) * $seconds;
        $this->db->exec('BEGIN IMMEDIATE');
        try {
            $row = $this->one('SELECT count FROM rate_limits WHERE bucket=? AND window=?', [$bucket, $window]);
            if (($row['count'] ?? 0) >= $limit) throw new HttpError(429, 'Se han realizado varios intentos. Espera unos minutos o contacta con el taller.');
            $this->execute('INSERT OR REPLACE INTO rate_limits VALUES (?,?,?)', [$bucket, $window, ($row['count'] ?? 0) + 1]);
            $this->execute('DELETE FROM rate_limits WHERE window < ?', [time() - 86400]);
            $this->db->exec('COMMIT');
        } catch (Throwable $e) { $this->db->exec('ROLLBACK'); throw $e; }
    }

    private function text(mixed $value, int $max = 300): string
    {
        if ($value === null) return '';
        if (!is_string($value) && !is_int($value)) throw new HttpError(422, 'Revisa los datos del formulario.');
        $value = trim((string) $value);
        if (strlen($value) > $max * 4 || mb_strlen($value, 'UTF-8') > $max || str_contains($value, "\0")) throw new HttpError(422, 'Uno de los campos supera el tamaño permitido.');
        return $value;
    }

    public function normalize(array $raw, array $uploads): array
    {
        $key = $this->text($raw['idempotencyKey'] ?? null, 100);
        if (!preg_match('/^[A-Za-z0-9_-]{16,100}$/D', $key)) throw new HttpError(422, 'Falta la identificación de este envío. Recarga e inténtalo de nuevo.');
        if (($raw['website'] ?? '') !== '') throw new HttpError(422, 'No se ha podido enviar la solicitud. Vuelve a intentarlo.');
        $intent = $raw['intent'] ?? '';
        if (!in_array($intent, ['consultation', 'repair'], true)) throw new HttpError(422, 'Selecciona el tipo de solicitud.');
        if (!is_array($raw['customer'] ?? null) || !is_array($raw['vehicle'] ?? null)) throw new HttpError(422, 'Completa los datos de contacto y del vehículo.');
        $customer = [];
        foreach (['type', 'name', 'contact', 'email', 'phone', 'taxId', 'address', 'city', 'province', 'postalCode', 'country', 'returnAddress', 'returnCity', 'returnPostalCode', 'returnCountry'] as $field) $customer[$field] = $this->text($raw['customer'][$field] ?? null);
        $customer['returnDifferent'] = ($raw['customer']['returnDifferent'] ?? false) === true;
        if (!in_array($customer['type'], ['particular', 'taller'], true) || mb_strlen($customer['name']) < 2 || !filter_var($customer['email'], FILTER_VALIDATE_EMAIL) || strlen(preg_replace('/\D/', '', $customer['phone'])) < 7) throw new HttpError(422, 'Revisa tu nombre, correo y teléfono de contacto.');
        if ($customer['type'] === 'taller' && !$customer['contact']) throw new HttpError(422, 'Indica la persona de contacto del taller.');
        if ($intent === 'repair') {
            foreach (['taxId', 'address', 'city', 'postalCode', 'country'] as $field) if (!$customer[$field]) throw new HttpError(422, 'Completa los datos fiscales y de devolución para preparar el envío.');
            if ($customer['returnDifferent']) foreach (['returnAddress', 'returnCity', 'returnPostalCode', 'returnCountry'] as $field) if (!$customer[$field]) throw new HttpError(422, 'Completa la dirección de devolución.');
        }
        $vehicle = [];
        foreach (['brand', 'model', 'plate', 'vin', 'year', 'km'] as $field) $vehicle[$field] = $this->text($raw['vehicle'][$field] ?? null, 120);
        // Accept older consultation drafts while storing unknown data structurally.
        $legacyUnknownModel = mb_strtolower($vehicle['model'], 'UTF-8') === 'por identificar';
        $vehicle['modelUnknown'] = ($raw['vehicle']['modelUnknown'] ?? false) === true || $legacyUnknownModel;
        if ($vehicle['modelUnknown']) $vehicle['model'] = '';
        if (!$vehicle['brand']) throw new HttpError(422, 'Indica la marca del vehículo.');
        if ($intent === 'repair' && $vehicle['modelUnknown']) throw new HttpError(422, 'Para preparar el envío necesitamos el modelo. Si no lo conoces, elige «Consultar mi pieza».');
        if (!$vehicle['model'] && !$vehicle['modelUnknown']) throw new HttpError(422, 'Indica el modelo o marca «No conozco el modelo» para una consulta.');
        if (!is_array($raw['units'] ?? null) || !array_is_list($raw['units']) || count($raw['units']) < 1 || count($raw['units']) > $this->limits['maxUnits']) throw new HttpError(422, 'Añade entre una y diez piezas a la solicitud.');
        $units = []; $files = []; $usedUploads = []; $total = 0;
        foreach ($raw['units'] as $position => $unitRaw) {
            if (!is_array($unitRaw)) throw new HttpError(422, 'Revisa los datos de cada pieza.');
            $unit = [];
            foreach (['catalogUid', 'componentKey', 'componentName', 'manufacturer', 'reference', 'dtc', 'symptoms', 'accessories', 'vehicleBrand', 'vehicleModel'] as $field) $unit[$field] = $this->text($unitRaw[$field] ?? null, in_array($field, ['symptoms', 'accessories'], true) ? 2000 : 200);
            $unit['unknownReference'] = ($unitRaw['unknownReference'] ?? false) === true;
            if (!$unit['componentName'] || mb_strlen($unit['symptoms']) < 8 || (!$unit['reference'] && !$unit['unknownReference'])) throw new HttpError(422, 'Completa la pieza, su referencia o «No sé identificarla», y describe el fallo.');
            $attachments = $unitRaw['attachments'] ?? [];
            if (!is_array($attachments) || !array_is_list($attachments) || count($attachments) > $this->limits['maxFilesPerUnit']) throw new HttpError(422, 'Hay demasiados archivos en una pieza.');
            $unit['attachments'] = [];
            foreach ($attachments as $attachment) {
                if (!is_array($attachment)) throw new HttpError(422, 'Revisa los archivos adjuntos.');
                $uploadKey = $attachment['uploadKey'] ?? '';
                if (!is_string($uploadKey) || !preg_match('/^u\d+a\d+$/D', $uploadKey) || isset($usedUploads[$uploadKey]) || !isset($uploads[$uploadKey])) throw new HttpError(422, 'Falta uno de los archivos. Vuelve a adjuntarlo antes de enviar.');
                $usedUploads[$uploadKey] = true;
                $upload = $uploads[$uploadKey];
                if ($upload['error'] !== UPLOAD_ERR_OK || !is_uploaded_file($upload['tmp_name'])) throw new HttpError(422, 'No se ha recibido un archivo completo. Vuelve a adjuntarlo.');
                $size = filesize($upload['tmp_name']);
                if (!$size || $size > $this->limits['maxFileBytes']) throw new HttpError(422, 'Uno de los archivos supera el tamaño permitido.');
                $mime = (new \finfo(FILEINFO_MIME_TYPE))->file($upload['tmp_name']);
                if (!in_array($mime, ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'], true)) throw new HttpError(422, 'Solo se admiten fotos JPG, PNG, WebP e informes PDF.');
                $start = file_get_contents($upload['tmp_name'], false, null, 0, 12);
                if ($mime === 'application/pdf') {
                    if (!str_starts_with($start, '%PDF-')) throw new HttpError(422, 'El PDF no tiene un formato válido.');
                } else {
                    $dimensions = @getimagesize($upload['tmp_name']);
                    if (!$dimensions || $dimensions['mime'] !== $mime || $dimensions[0] * $dimensions[1] > 100000000) throw new HttpError(422, 'La imagen no tiene un formato o tamaño válido.');
                }
                if (($attachment['mime'] ?? $mime) !== $mime) throw new HttpError(422, 'El contenido de un archivo no coincide con su formato.');
                $name = basename(str_replace('\\', '/', $this->text($attachment['name'] ?? $upload['name'], 180)));
                $name = preg_replace('/[\x00-\x1f\x7f]/u', '_', $name) ?: 'archivo';
                $hash = hash_file('sha256', $upload['tmp_name']);
                $extension = ['image/jpeg' => '.jpg', 'image/png' => '.png', 'image/webp' => '.webp', 'application/pdf' => '.pdf'][$mime];
                $stem = pathinfo($name, PATHINFO_FILENAME) ?: 'archivo';
                $meta = ['name' => $name, 'downloadName' => $stem . $extension, 'mime' => $mime, 'size' => $size, 'sha256' => $hash];
                $unit['attachments'][] = $meta;
                $files[] = ['uploadKey' => $uploadKey, 'unit' => $position + 1, 'attachment' => count($unit['attachments']) - 1, 'tmp' => $upload['tmp_name'], 'meta' => $meta];
                $total += $size;
                if ($total > $this->limits['maxTotalBytes'] || count($files) > $this->limits['maxTotalFiles']) throw new HttpError(422, 'El conjunto de archivos supera el límite indicado en el formulario.');
            }
            $units[] = $unit;
        }
        if (count($usedUploads) !== count($uploads)) throw new HttpError(422, 'Hay archivos sin una pieza asociada.');
        if (!is_array($raw['acceptance'] ?? null) || ($raw['acceptance']['privacyRead'] ?? false) !== true || ($raw['acceptance']['conditionsRead'] ?? false) !== true) throw new HttpError(422, 'Revisa la información de privacidad y las condiciones de la solicitud.');
        if (($raw['acceptance']['version'] ?? '') !== ($this->config['termsVersion'] ?? 'draft')) throw new HttpError(422, 'Las condiciones de la solicitud han cambiado. Revisa la versión actual antes de enviar.');
        return [$key, ['intent' => $intent, 'customer' => $customer, 'vehicle' => $vehicle, 'units' => $units,
            'contextQuery' => $this->text($raw['contextQuery'] ?? null, 300),
            'acceptance' => ['privacyRead' => true, 'conditionsRead' => true, 'version' => $this->config['termsVersion'] ?? 'draft']], $files];
    }

    public function save(array $raw, array $uploads): array
    {
        if (!$this->enabled()) throw new HttpError(503, 'La recepción de solicitudes todavía no está habilitada. Contacta con el taller.');
        [$key, $payload, $files] = $this->normalize($raw, $uploads);
        $digest = hash('sha256', json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE));
        $this->db->exec('BEGIN IMMEDIATE'); $savedFiles = []; $directory = null;
        try {
            $previous = $this->one('SELECT reference,payload_hash,payload,created_at FROM requests WHERE key_hash=?', [$this->keyHash($key)]);
            if ($previous) {
                if (!hash_equals($previous['payload_hash'], $digest)) throw new HttpError(409, 'Este envío ya se guardó con otros datos. Recupera el resumen o inicia una nueva solicitud.');
                $this->db->exec('COMMIT');
                return [200, $this->receipt($previous, $this->token($key))];
            }
            $bytes = array_sum(array_column(array_column($files, 'meta'), 'size'));
            $free = disk_free_space($this->storage);
            if ($free === false || $free < (int) ($this->config['minFreeBytes'] ?? 50 * 1024 * 1024) + $bytes) throw new HttpError(503, 'No se ha podido guardar la solicitud. Conserva los datos y contacta con el taller.');
            if ($this->storageBytes() + $bytes + 256 * 1024 > (int) ($this->config['storageBudgetBytes'] ?? 128 * 1024 * 1024)) throw new HttpError(503, 'No se ha podido guardar la solicitud. Conserva los datos y contacta con el taller.');
            $reference = 'SOL-' . (new \DateTimeImmutable('now', new \DateTimeZone('Europe/Madrid')))->format('Ymd') . '-' . strtoupper(bin2hex(random_bytes(4)));
            $directory = $this->storage . '/uploads/' . $reference;
            if (!mkdir($directory, 0700)) throw new RuntimeException('Private request directory unavailable');
            $created = $this->now();
            foreach ($files as &$file) {
                $id = bin2hex(random_bytes(24)); $destination = $directory . '/' . $id . '.bin';
                if (!move_uploaded_file($file['tmp'], $destination)) throw new RuntimeException('Upload persistence failed');
                chmod($destination, 0600); $savedFiles[] = $destination;
                $file['id'] = $id; $file['path'] = $reference . '/' . $id . '.bin';
                $payload['units'][$file['unit'] - 1]['attachments'][$file['attachment']]['id'] = $id;
            }
            unset($file);
            $encoded = json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
            $this->execute('INSERT INTO requests(reference,key_hash,token_hash,payload_hash,payload,created_at) VALUES (?,?,?,?,?,?)', [$reference, $this->keyHash($key), hash('sha256', $this->token($key)), $digest, $encoded, $created]);
            foreach ($files as $file) $this->execute('INSERT INTO files VALUES (?,?,?,?,?,?,?,?)', [$file['id'], $reference, $file['unit'], $file['meta']['name'], $file['meta']['mime'], $file['meta']['size'], $file['meta']['sha256'], $file['path']]);
            $this->execute('INSERT INTO notifications(request_reference) VALUES (?)', [$reference]);
            $this->execute('INSERT INTO events(request_reference,kind,actor,created_at) VALUES (?,?,?,?)', [$reference, 'submitted', 'customer', $created]);
            $this->db->exec('COMMIT');
            return [201, $this->receipt(['reference' => $reference, 'payload' => $encoded, 'created_at' => $created], $this->token($key))];
        } catch (Throwable $e) {
            $this->db->exec('ROLLBACK');
            foreach ($savedFiles as $file) if (is_file($file)) unlink($file);
            if ($directory && is_dir($directory)) rmdir($directory);
            throw $e;
        }
    }

    public function receipt(array $row, string $token): array
    {
        $payload = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $notification = $this->one('SELECT state FROM notifications WHERE request_reference=?', [$row['reference']]);
        return ['reference' => $row['reference'], 'requestId' => $token, 'mode' => $this->config['mode'],
            'unitReferences' => array_map(fn($n) => $row['reference'] . '-P' . $n, range(1, count($payload['units']))),
            'units' => array_map(fn($u) => ['componentName' => $u['componentName'], 'reference' => $u['reference']], $payload['units']),
            'summaryUrl' => '/resumen.html#' . $token, 'downloadUrl' => '/resumen.html#' . $token . '&descargar=datos',
            'status' => 'saved_for_review', 'emailSent' => ($notification['state'] ?? '') === 'sent', 'notificationState' => $notification['state'] ?? 'queued', 'workshopIntegration' => 'not_configured'];
    }

    public function recover(string $key): array
    {
        if (!preg_match('/^[A-Za-z0-9_-]{16,100}$/D', $key)) throw new HttpError(404, 'Solicitud no encontrada.');
        $row = $this->one('SELECT * FROM requests WHERE key_hash=?', [$this->keyHash($key)]);
        if (!$row) throw new HttpError(404, 'Solicitud no encontrada.');
        return $this->receipt($row, $this->token($key));
    }

    public function byToken(string $token): array
    {
        if (!preg_match('/^[A-Za-z0-9_-]{43}$/D', $token)) throw new HttpError(404, 'Solicitud no encontrada.');
        return $this->one('SELECT * FROM requests WHERE token_hash=?', [hash('sha256', $token)]) ?? throw new HttpError(404, 'Solicitud no encontrada.');
    }

    public function byReference(string $reference): array
    {
        if (!preg_match('/^SOL-\d{8}-[A-F0-9]{8}$/D', $reference)) throw new HttpError(404, 'Solicitud no encontrada.');
        return $this->one('SELECT * FROM requests WHERE reference=?', [$reference]) ?? throw new HttpError(404, 'Solicitud no encontrada.');
    }
}
