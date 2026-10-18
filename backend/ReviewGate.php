<?php
declare(strict_types=1);
namespace Menigar;

use RuntimeException;

/** Independent staging access. Never consumes or replaces Authorization. */
final class ReviewGate
{
    private array $gate;
    private string $state;
    private bool $secure;
    private string $version;

    public function __construct(private readonly array $config, string $publicRoot)
    {
        $this->gate = $config['reviewGate'] ?? [];
        $base = $config['baseUrl'] ?? '';
        if (($config['mode'] ?? '') !== 'review' || ($this->gate['enabled'] ?? false) !== true
            || !is_string($base) || !preg_match('~^https?://[^/]+$~D', $base)
            || strlen($config['secret'] ?? '') < 32 || empty($this->gate['users']) || !is_array($this->gate['users'])) {
            throw new RuntimeException('Private review configuration unavailable');
        }
        foreach ($this->gate['users'] as $name => $hash) {
            if (!is_string($name) || !preg_match('/^[A-Za-z0-9_.-]{1,64}$/D', $name)
                || !is_string($hash) || empty(password_get_info($hash)['algo'])) {
                throw new RuntimeException('Private review users unavailable');
            }
        }
        $expected = strtolower((string) parse_url($base, PHP_URL_HOST))
            . (parse_url($base, PHP_URL_PORT) ? ':' . parse_url($base, PHP_URL_PORT) : '');
        if (strtolower($_SERVER['HTTP_HOST'] ?? '') !== $expected) throw new RuntimeException('Review host mismatch');
        $this->secure = str_starts_with($base, 'https://');
        $loopback = !$this->secure && ($this->gate['allowLoopbackHttp'] ?? false) === true
            && parse_url($base, PHP_URL_HOST) === '127.0.0.1' && ($_SERVER['REMOTE_ADDR'] ?? '') === '127.0.0.1';
        $https = in_array(strtolower($_SERVER['HTTPS'] ?? ''), ['on', '1'], true) || (int) ($_SERVER['SERVER_PORT'] ?? 0) === 443;
        if ((!$this->secure && !$loopback) || ($this->secure && !$https)) throw new RuntimeException('Review HTTPS required');
        $state = $this->gate['stateDir'] ?? (($config['dataDir'] ?? '') . '/review-gate');
        if (!is_string($state) || !str_starts_with($state, '/') || $state === '/review-gate') throw new RuntimeException('Private review storage unavailable');
        $old = umask(0077);
        try {
            if (is_link($state) || (!is_dir($state) && !mkdir($state, 0700, true))) throw new RuntimeException('Review storage unavailable');
            $this->state = realpath($state) ?: throw new RuntimeException('Review storage unavailable');
            $public = realpath($publicRoot) ?: throw new RuntimeException('Public root unavailable');
            if ($this->state === $public || str_starts_with($this->state . '/', $public . '/')) throw new RuntimeException('Review storage must be private');
            foreach (['sessions', 'attempts'] as $part) {
                $directory = $this->state . '/' . $part;
                if (is_link($directory) || (!is_dir($directory) && !mkdir($directory, 0700))) throw new RuntimeException('Review storage unavailable');
                chmod($directory, 0700);
            }
            chmod($this->state, 0700);
        } finally { umask($old); }
        $this->version = hash_hmac('sha256', json_encode($this->gate['users'], JSON_THROW_ON_ERROR), $config['secret']);
    }

    public static function headers(): void
    {
        header('Cache-Control: no-store, private');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: no-referrer');
    }

    private function startSession(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) throw new RuntimeException('Unexpected active session');
        session_name('MENIGAR_REVIEW');
        if (!session_start(['save_path' => $this->state . '/sessions', 'use_strict_mode' => 1, 'use_only_cookies' => 1,
            'cookie_httponly' => true, 'cookie_samesite' => 'Strict', 'cookie_secure' => $this->secure,
            'cookie_path' => '/', 'cookie_lifetime' => 0, 'gc_maxlifetime' => 28800])) throw new RuntimeException('Review session unavailable');
        if (!isset($_SESSION['csrf'])) $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }

    private function next(mixed $value): string
    {
        if (!is_string($value) || strlen($value) > 2048 || !str_starts_with($value, '/') || str_starts_with($value, '//')
            || preg_match('~[\x00-\x20\x7f\\\\#]~', rawurldecode($value))
            || str_starts_with($value, '/_revision/')) return '/';
        return $value;
    }

    private function json(array $data, int $status): void
    {
        http_response_code($status); header('Content-Type: application/json; charset=utf-8');
        echo json_encode($data, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
    }

    /** Failure counts survive cookie resets; no address, password or token enters the file. */
    private function attempts(bool $failure = false, bool $reset = false): bool
    {
        $bucket = hash_hmac('sha256', $_SERVER['REMOTE_ADDR'] ?? '', $this->config['secret']);
        $path = $this->state . '/attempts/' . $bucket . '.json';
        $handle = fopen($path, 'c+');
        if (!$handle || !flock($handle, LOCK_EX)) throw new RuntimeException('Review rate limit unavailable');
        try {
            chmod($path, 0600);
            $raw = stream_get_contents($handle);
            $row = $raw === '' ? ['until' => time() + 900, 'count' => 0] : json_decode($raw, true, 8, JSON_THROW_ON_ERROR);
            if (!is_array($row) || !isset($row['until'], $row['count'])) throw new RuntimeException('Review rate limit corrupt');
            if ($row['until'] <= time() || $reset) $row = ['until' => time() + 900, 'count' => 0];
            if ($failure) $row['count']++;
            rewind($handle); ftruncate($handle, 0);
            if (fwrite($handle, json_encode($row, JSON_THROW_ON_ERROR)) === false || !fflush($handle)) throw new RuntimeException('Review rate limit unavailable');
            return $row['count'] < min(30, max(1, (int) ($this->gate['attemptsPer15Minutes'] ?? 10)));
        } finally { flock($handle, LOCK_UN); fclose($handle); }
    }

    public function enforce(): bool
    {
        self::headers();
        $previousPath = (string) ini_get('session.save_path');
        $previousName = session_name();
        $continueToApplication = false;
        $this->startSession();
        try {
            $path = (string) parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
            $method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
            $json = str_contains($_SERVER['HTTP_ACCEPT'] ?? '', 'application/json');
            if ($path === '/_revision/acceso' && $method === 'POST') {
                if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $this->config['baseUrl']
                    || !is_string($_POST['csrf'] ?? null) || !hash_equals($_SESSION['csrf'], $_POST['csrf'])) {
                    $this->json(['error' => 'La sesión de acceso ha caducado. Recarga la página.'], 403); return false;
                }
                if ((int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 8192) { $this->json(['error' => 'Acceso no válido.'], 413); return false; }
                if (!$this->attempts()) { header('Retry-After: 900'); $this->json(['error' => 'Demasiados intentos. Vuelve a intentarlo más tarde.'], 429); return false; }
                $name = $_POST['user'] ?? ''; $password = $_POST['password'] ?? '';
                $name = is_string($name) ? $name : ''; $password = is_string($password) ? $password : '';
                $hash = $this->gate['users'][$name] ?? '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi';
                if (strlen($password) > 1024 || !password_verify($password, $hash) || !isset($this->gate['users'][$name])) {
                    $this->attempts(true); $this->json(['error' => 'Usuario o contraseña incorrectos.'], 401); return false;
                }
                $this->attempts(false, true);
                if (!session_regenerate_id(true)) throw new RuntimeException('Review session rotation unavailable');
                $_SESSION = ['csrf' => bin2hex(random_bytes(32)), 'user' => $name, 'issued' => time(), 'seen' => time(), 'version' => $this->version];
                $next = $this->next($_POST['next'] ?? '/');
                if ($json) $this->json(['authenticated' => true, 'next' => $next], 200);
                else { header('Location: ' . $next, true, 303); }
                return false;
            }
            if ($path === '/_revision/salir' && $method === 'POST') {
                if (($_SERVER['HTTP_ORIGIN'] ?? '') !== $this->config['baseUrl']
                    || !is_string($_POST['csrf'] ?? null) || !hash_equals($_SESSION['csrf'], $_POST['csrf'])) {
                    $this->json(['error' => 'La sesión de acceso ha caducado. Recarga la página.'], 403); return false;
                }
                $_SESSION = []; session_destroy();
                setcookie('MENIGAR_REVIEW', '', ['expires' => time() - 3600, 'path' => '/', 'secure' => $this->secure, 'httponly' => true, 'samesite' => 'Strict']);
                $this->json(['authenticated' => false], 200); return false;
            }
            $user = $_SESSION['user'] ?? '';
            $valid = is_string($user) && isset($this->gate['users'][$user])
                && hash_equals($this->version, $_SESSION['version'] ?? '')
                && time() - ($_SESSION['issued'] ?? 0) < min(28800, max(60, (int) ($this->gate['maxAgeSeconds'] ?? 28800)))
                && time() - ($_SESSION['seen'] ?? 0) < min(28800, max(30, (int) ($this->gate['idleSeconds'] ?? 1800)));
            if ($valid && !str_starts_with($path, '/_revision/')) {
                $_SESSION['seen'] = time();
                $continueToApplication = true;
                return true;
            }
            if (!in_array($method, ['GET', 'HEAD'], true) || str_starts_with($path, '/api/') || str_starts_with($path, '/equipo/') || $json) {
                $this->json(['error' => 'Accede primero a la revisión privada.', 'reviewAccessRequired' => true], 401); return false;
            }
            if ($path !== '/_revision/acceso' && str_starts_with($path, '/_revision/')) { http_response_code(404); return false; }
            $this->form($this->next($_SERVER['REQUEST_URI'] ?? '/'));
            return false;
        } finally {
            if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
            // Intake starts its own session later in this same request. Do not let
            // PHP reuse the gate ID or its save_path for MENIGAR_INTAKE.
            $_SESSION = [];
            // A response rendered by this gate ends dispatch; do not change PHP
            // session settings after its body has already sent the headers.
            if (!headers_sent()) {
                session_id(''); session_name($previousName);
                ini_set('session.save_path', $previousPath);
                if ($continueToApplication) {
                    // PHP does not select a second cookie automatically after
                    // a session has already been opened in this request. Pass
                    // Intake's existing cookie to its own strict-mode session;
                    // never let the gate session ID become the application ID.
                    $intakeId = $_COOKIE['MENIGAR_INTAKE'] ?? '';
                    if (is_string($intakeId) && preg_match('/^[A-Za-z0-9,-]{1,256}$/D', $intakeId)) {
                        session_id($intakeId);
                    }
                }
            }
        }
    }

    private function form(string $next): void
    {
        http_response_code(401); header('Content-Type: text/html; charset=utf-8');
        $nonce = base64_encode(random_bytes(24));
        header("Content-Security-Policy: default-src 'none'; script-src 'nonce-$nonce'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
        $csrf = htmlspecialchars($_SESSION['csrf'], ENT_QUOTES, 'UTF-8');
        $next = htmlspecialchars($next, ENT_QUOTES, 'UTF-8');
        echo '<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión privada · MENIGAR</title><h1>Revisión privada de MENIGAR</h1><p>Accede con tu usuario de revisión. Este entorno utiliza datos ficticios.</p><form id="reviewAccess" method="post" action="/_revision/acceso"><input type="hidden" name="csrf" value="' . $csrf . '"><input type="hidden" name="next" value="' . $next . '"><p><label>Usuario <input name="user" autocomplete="username" required maxlength="64"></label></p><p><label>Contraseña <input name="password" type="password" autocomplete="current-password" required maxlength="1024"></label></p><button>Acceder a la revisión</button><p id="accessError" role="alert"></p></form><script nonce="' . $nonce . '">';
        echo <<<'JS'
document.getElementById('reviewAccess').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget, error = document.getElementById('accessError');
  const fragment = location.hash; // Remains in this browser; never enters POST, next or a server URL.
  const button = form.querySelector('button'); button.disabled = true; error.textContent = '';
  try {
    const response = await fetch('/_revision/acceso', {method:'POST', credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}, body:new URLSearchParams(new FormData(form))});
    const result = await response.json();
    if (!response.ok || result.authenticated !== true || typeof result.next !== 'string' || !result.next.startsWith('/') || result.next.startsWith('//')) throw new Error(result.error || 'No se ha podido acceder. Vuelve a intentarlo.');
    const destination = result.next + fragment;
    // An identical URL with a fragment can be treated as a same-document
    // navigation. Reload so the newly authenticated request reaches PHP.
    if (new URL(destination, location.href).href === location.href) location.reload();
    else location.replace(destination);
  } catch (failure) { error.textContent = failure.message || 'No se ha podido acceder. Vuelve a intentarlo.'; button.disabled = false; }
});
JS;
        echo '</script></html>';
    }
}
