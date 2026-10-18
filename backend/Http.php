<?php
declare(strict_types=1);
namespace Menigar;

use Throwable;

final class Http
{
    public function __construct(private readonly Intake $intake) {}
    public static function headers(): void
    {
        header('Cache-Control: no-store, private'); header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer'); header('X-Robots-Tag: noindex, nofollow');
        header("Content-Security-Policy: default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'");
    }
    public static function json(array $data, int $status = 200): void
    {
        http_response_code($status); header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    }
    private function session(): void
    {
        if (session_status() !== PHP_SESSION_ACTIVE) {
            session_name('MENIGAR_INTAKE');
            session_start(['use_strict_mode' => 1, 'cookie_httponly' => true, 'cookie_samesite' => 'Lax',
                'cookie_secure' => str_starts_with($this->intake->config['baseUrl'], 'https://'), 'cookie_path' => '/']);
        }
        if (!isset($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    private function csrf(): string { $this->session(); return $_SESSION['csrf']; }
    private function checkPost(bool $form = false): void
    {
        $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
        if ($origin !== $this->intake->config['baseUrl']) throw new HttpError(403, 'El origen del envío no está permitido. Recarga la página de MENIGAR.');
        $this->session();
        $token = $form ? ($_POST['csrf'] ?? '') : ($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
        if (!is_string($token) || !hash_equals($_SESSION['csrf'], $token)) throw new HttpError(419, 'La sesión ha caducado. Recarga el formulario; conserva los datos antes de hacerlo.');
    }
    private function jsonBody(): array
    {
        if (!str_starts_with(strtolower($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json') || (int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 16384) throw new HttpError(415, 'El formato de la petición no es válido.');
        $body = json_decode(file_get_contents('php://input'), true, 64, JSON_THROW_ON_ERROR);
        if (!is_array($body)) throw new HttpError(400, 'No se han podido leer los datos.');
        return $body;
    }
    private function bearerRow(): array
    {
        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '';
        if (!preg_match('/^Bearer ([A-Za-z0-9_-]{43})$/D', $header, $match)) throw new HttpError(404, 'Solicitud no encontrada.');
        return $this->intake->byToken($match[1]);
    }
    private function staff(): string
    {
        $users = $this->intake->config['staffUsers'] ?? [];
        if (!$users) throw new HttpError(503, 'El acceso del equipo todavía no está habilitado.');
        $name = $_SERVER['PHP_AUTH_USER'] ?? ''; $password = $_SERVER['PHP_AUTH_PW'] ?? '';
        if (!$name && preg_match('/^Basic (.+)$/D', $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? '', $m)) {
            $decoded = base64_decode($m[1], true);
            if (is_string($decoded) && str_contains($decoded, ':')) [$name, $password] = explode(':', $decoded, 2);
        }
        $hash = $users[$name] ?? '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi';
        $valid = password_verify($password, $hash) && isset($users[$name]);
        if (!$valid) {
            $this->intake->throttle('staff-failure:' . ($_SERVER['REMOTE_ADDR'] ?? ''), 20);
            header('WWW-Authenticate: Basic realm="MENIGAR equipo", charset="UTF-8"');
            throw new HttpError(401, 'Identifícate con tu acceso del equipo.');
        }
        return $name;
    }
    private function uploads(): array
    {
        if (array_diff(array_keys($_FILES), ['files'])) throw new HttpError(422, 'Hay archivos sin una pieza asociada.');
        $group = $_FILES['files'] ?? []; $out = [];
        if (!$group) return [];
        if (!is_array($group['name'] ?? null)) throw new HttpError(422, 'El formato de los adjuntos no es válido.');
        foreach ($group['name'] as $key => $name) {
            if (!is_string($key) || !preg_match('/^u\d+a\d+$/D', $key) || !is_string($name)
                || !is_string($group['tmp_name'][$key] ?? null) || !is_int($group['error'][$key] ?? null)) throw new HttpError(422, 'El formato de los adjuntos no es válido.');
            $out[$key] = ['name' => $name, 'tmp_name' => $group['tmp_name'][$key], 'error' => $group['error'][$key]];
        }
        return $out;
    }
    private function file(array $row, string $id): void
    {
        if (!preg_match('/^[a-f0-9]{48}$/D', $id)) throw new HttpError(404, 'Archivo no encontrado.');
        $file = $this->intake->one('SELECT * FROM files WHERE id=? AND request_reference=?', [$id, $row['reference']]);
        if (!$file) throw new HttpError(404, 'Archivo no encontrado.');
        $root = $this->intake->storage . '/uploads/'; $path = realpath($root . $file['path']);
        if (!$path || !str_starts_with($path, $root) || !is_file($path)) throw new HttpError(404, 'Archivo no encontrado.');
        if (filesize($path) !== (int) $file['bytes'] || !hash_equals($file['sha256'], hash_file('sha256', $path))) throw new HttpError(503, 'El archivo no está disponible. Contacta con el taller.');
        $suffix = ['image/jpeg' => '.jpg', 'image/png' => '.png', 'image/webp' => '.webp', 'application/pdf' => '.pdf'][$file['mime']];
        header('Content-Type: ' . $file['mime']); header('Content-Length: ' . $file['bytes']);
        $downloadName = (pathinfo($file['name'], PATHINFO_FILENAME) ?: 'archivo') . $suffix;
        header('Content-Disposition: attachment; filename="archivo' . $suffix . '"; filename*=UTF-8\'\'' . rawurlencode($downloadName));
        if ($_SERVER['REQUEST_METHOD'] !== 'HEAD') readfile($path);
    }
    public function run(): void
    {
        self::headers();
        try {
            $host = strtolower($_SERVER['HTTP_HOST'] ?? '');
            $expected = strtolower((string) parse_url($this->intake->config['baseUrl'], PHP_URL_HOST)) . (parse_url($this->intake->config['baseUrl'], PHP_URL_PORT) ? ':' . parse_url($this->intake->config['baseUrl'], PHP_URL_PORT) : '');
            if ($host !== $expected) throw new HttpError(403, 'Dominio de solicitud no permitido.');
            if ($this->intake->config['mode'] === 'production' && !in_array(strtolower($_SERVER['HTTPS'] ?? ''), ['on','1'], true) && (int) ($_SERVER['SERVER_PORT'] ?? 0) !== 443) throw new HttpError(403, 'Utiliza la dirección HTTPS de MENIGAR.');
            $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH); $method = $_SERVER['REQUEST_METHOD'];
            if ($path === '/api/config' && $method === 'GET') {
                self::json(['mode' => $this->intake->config['mode'], 'submissions' => $this->intake->enabled(),
                    'transport' => 'multipart', 'receiptTransport' => 'bearer_fragment', 'recovery' => true,
                    'csrfToken' => $this->csrf(), 'emailConfigured' => ($this->intake->config['notifications']['transport'] ?? '') === 'sendmail',
                    'workshopIntegrationConfigured' => false, 'termsVersion' => $this->intake->config['termsVersion'] ?? 'draft',
                    ...$this->intake->limits]); return;
            }
            if ($path === '/api/solicitudes' && $method === 'POST') {
                $this->checkPost();
                if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > $this->intake->limits['maxBodyBytes']) throw new HttpError(413, 'El conjunto del envío supera el tamaño permitido. Reduce los archivos y vuelve a intentarlo.');
                if (!str_starts_with(strtolower($_SERVER['CONTENT_TYPE'] ?? ''), 'multipart/form-data;')) throw new HttpError(415, 'El formulario debe enviar los archivos en su formato original.');
                $this->intake->throttle('intake:' . ($_SERVER['REMOTE_ADDR'] ?? ''), (int) ($this->intake->config['requestsPerHour'] ?? 30));
                $payload = $_POST['payload'] ?? '';
                if (!is_string($payload) || strlen($payload) > 128 * 1024) throw new HttpError(400, 'No se han podido leer los datos del formulario.');
                $raw = json_decode($payload, true, 64, JSON_THROW_ON_ERROR);
                if (!is_array($raw)) throw new HttpError(400, 'No se han podido leer los datos del formulario.');
                [$code, $data] = $this->intake->save($raw, $this->uploads()); self::json($data, $code); return;
            }
            if ($path === '/api/recuperar' && $method === 'POST') {
                $this->checkPost(); $this->intake->throttle('recovery:' . ($_SERVER['REMOTE_ADDR'] ?? ''), 100);
                self::json($this->intake->recover((string) ($this->jsonBody()['idempotencyKey'] ?? ''))); return;
            }
            if ($path === '/api/resumen' && $method === 'GET') {
                $row = $this->bearerRow();
                self::json(['reference' => $row['reference'], 'createdAt' => $row['created_at'], 'mode' => $this->intake->config['mode'], ...json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR)]); return;
            }
            if (preg_match('~^/api/archivos/([a-f0-9]{48})$~D', $path, $m) && in_array($method, ['GET', 'HEAD'], true)) {
                $this->file($this->bearerRow(), $m[1]); return;
            }
            if (str_starts_with($path, '/equipo/')) {
                $actor = $this->staff(); $csrf = $this->csrf();
                if ($path === '/equipo/solicitudes' && $method === 'GET') {
                    $page = max(1, min(10000, (int) ($_GET['pagina'] ?? 1))); $offset = ($page - 1) * 100;
                    $rows = $this->intake->db->query('SELECT r.*,n.state notification_state FROM requests r LEFT JOIN notifications n ON n.request_reference=r.reference ORDER BY created_at DESC,reference DESC LIMIT 100 OFFSET ' . $offset)->fetchAll();
                    $total = (int) $this->intake->db->query('SELECT count(*) FROM requests')->fetchColumn();
                    header('Content-Type: text/html; charset=utf-8'); echo Views::inbox($rows, $page, $total); return;
                }
                if (preg_match('~^/equipo/solicitudes/(SOL-\d{8}-[A-F0-9]{8})(?:/(revisada|archivo/([a-f0-9]{48})))?$~D', $path, $m)) {
                    $row = $this->intake->byReference($m[1]); $action = $m[2] ?? '';
                    if ($action === '' && $method === 'GET') { header('Content-Type: text/html; charset=utf-8'); echo Views::staffRequest($row, $csrf, $this->intake->config['mode']); return; }
                    if (str_starts_with($action, 'archivo/') && in_array($method, ['GET', 'HEAD'], true)) { $this->file($row, $m[3]); return; }
                    if ($action === 'revisada' && $method === 'POST') {
                        $this->checkPost(true); $now = $this->intake->now();
                        $this->intake->db->exec('BEGIN IMMEDIATE');
                        try {
                            $previous = $this->intake->byReference($m[1]);
                            if (!$previous['reviewed_at']) {
                                $this->intake->execute('UPDATE requests SET reviewed_at=? WHERE reference=?', [$now, $m[1]]);
                                $this->intake->execute('INSERT INTO events(request_reference,kind,actor,created_at) VALUES (?,?,?,?)', [$m[1], 'reviewed', $actor, $now]);
                            }
                            $this->intake->db->exec('COMMIT');
                        } catch (Throwable $e) { $this->intake->db->exec('ROLLBACK'); throw $e; }
                        header('Location: /equipo/solicitudes/' . $m[1], true, 303); return;
                    }
                }
            }
            throw new HttpError(404, 'Ruta no disponible.');
        } catch (\JsonException $e) { self::json(['error' => 'No se han podido leer los datos. No se ha guardado una solicitud nueva.'], 400); }
        catch (HttpError $e) { self::json(['error' => $e->getMessage()], $e->status); }
        catch (Throwable $e) { error_log('MENIGAR intake: ' . get_class($e)); self::json(['error' => 'No se pudo completar la operación. Conserva los datos y vuelve a intentarlo.'], 500); }
        finally { if (session_status() === PHP_SESSION_ACTIVE) session_write_close(); }
    }
}
