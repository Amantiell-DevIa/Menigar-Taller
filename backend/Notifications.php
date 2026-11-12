<?php
declare(strict_types=1);
namespace Menigar;

use Throwable;

final class Notifications
{
    public function __construct(private readonly Intake $intake) {}

    /**
     * Team notice for a new request. It carries what the laboratory needs to triage the
     * piece, but no contact or tax data: name, phone, email, address, NIF, plate and VIN
     * stay behind the team login (plan general O03, paso 2). The mailbox is a copy that
     * travels and stays on servers; the inbox is the single place with personal data.
     */
    private function buildRichBody(string $reference, string $staffUrl): array
    {
        $test = ($this->intake->config['mode'] ?? '') !== 'production';
        $prefix = $test ? 'PRUEBA · ' : '';
        $row = $this->intake->one('SELECT * FROM requests WHERE reference=?', [$reference]);
        if (!$row) {
            return [
                'subject' => $prefix . 'MENIGAR: nueva solicitud ' . $reference,
                'body' => "Nueva solicitud web: $reference\nConsulta los datos y archivos en el acceso del equipo:\n$staffUrl\n",
            ];
        }
        $payload = json_decode((string) $row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $payload['customer'] ?? [];
        $v = $payload['vehicle'] ?? [];
        $units = $payload['units'] ?? [];
        $shipping = ($payload['intent'] ?? '') === 'repair';
        $vehicle = trim(($v['brand'] ?? '') . ' ' . (($v['modelUnknown'] ?? false) ? '(modelo por identificar)' : ($v['model'] ?? '')));
        $unitCount = count($units);
        $pieces = $unitCount . ($unitCount === 1 ? ' pieza' : ' piezas');
        $kind = $shipping ? 'Envío de pieza' : 'Consulta';
        $client = ($c['type'] ?? '') === 'taller' ? 'Taller o empresa' : 'Particular';
        $when = self::madridTime((string) ($row['created_at'] ?? ''));
        $inbound = ($c['deliveryMethod'] ?? '') === 'entrega_mano' ? 'La entrega en mano en Alcobendas' : 'La envía por mensajería por su cuenta';
        $outbound = ($c['returnMethod'] ?? '') === 'recogida_mano' ? 'La recoge en mano en Alcobendas' : 'MENIGAR la devuelve por MRW';
        $declared = static fn(array $u): string => ($u['unknownReference'] ?? false) || !($u['reference'] ?? '') ? 'Sin identificar' : (string) $u['reference'];

        $subject = $prefix . 'MENIGAR · ' . $kind . ' ' . $reference . ' · ' . $pieces . ($vehicle !== '' ? ' · ' . $vehicle : '');

        $lines = [];
        if ($test) {
            $lines[] = 'PRUEBA: esta solicitud viene del formulario de prueba. No es un cliente real.';
            $lines[] = '';
        }
        $lines[] = ($shipping ? 'Nuevo envío de pieza' : 'Nueva consulta') . ' desde la web';
        $lines[] = 'Referencia: ' . $reference;
        $lines[] = 'Recibida: ' . $when;
        $lines[] = 'Cliente: ' . $client;
        $lines[] = 'Vehículo: ' . ($vehicle !== '' ? $vehicle : 'No indicado');
        if ($shipping) {
            $lines[] = 'Llegada de la pieza: ' . $inbound;
            $lines[] = 'Devolución: ' . $outbound;
        }
        $lines[] = '';
        foreach ($units as $idx => $u) {
            $num = $idx + 1;
            $lines[] = 'Pieza ' . $num . ' de ' . $unitCount . ' (' . $reference . '-P' . $num . '): ' . ($u['componentName'] ?? '');
            if (!empty($u['manufacturer'])) $lines[] = '  Fabricante: ' . $u['manufacturer'];
            $lines[] = '  Referencia que indica el cliente: ' . $declared($u);
            if (!empty($u['dtc'])) $lines[] = '  Código de avería: ' . $u['dtc'];
            $lines[] = '  Qué ocurre: ' . ($u['symptoms'] ?? '');
            if (!empty($u['accessories'])) $lines[] = '  Accesorios: ' . $u['accessories'];
            $attachments = count($u['attachments'] ?? []);
            $lines[] = '  Fotos o documentos: ' . ($attachments ?: 'ninguno');
            $lines[] = '';
        }
        $lines[] = 'Datos de contacto, fotos y ficha completa (pide tu usuario del equipo):';
        $lines[] = $staffUrl;
        $lines[] = '';
        $lines[] = 'Este aviso no confirma una orden de reparación ni un pago.';

        $e = static fn($value): string => htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $cell = 'padding:4px 0;vertical-align:top;';
        $label = $cell . 'color:#556b7d;width:38%;';
        $unitsHtml = '';
        foreach ($units as $idx => $u) {
            $num = $idx + 1;
            $attachments = count($u['attachments'] ?? []);
            $unitsHtml .= '<div style="margin:0 0 12px;padding:14px 16px;border:1px solid #d5dfe8;border-radius:10px;background:#f8fbfd;">'
                . '<p style="margin:0 0 8px;font-size:15px;font-weight:700;color:#0b2234;">Pieza ' . $num . ' de ' . $unitCount . ': ' . $e($u['componentName'] ?? '')
                . ' <span style="font-weight:400;color:#556b7d;font-size:13px;">' . $e($reference . '-P' . $num) . '</span></p>'
                . '<table style="width:100%;border-collapse:collapse;font-size:13px;color:#1e3342;">'
                . (!empty($u['manufacturer']) ? '<tr><td style="' . $label . '">Fabricante</td><td style="' . $cell . '">' . $e($u['manufacturer']) . '</td></tr>' : '')
                . '<tr><td style="' . $label . '">Referencia que indica el cliente</td><td style="' . $cell . 'font-weight:600;">' . $e($declared($u)) . '</td></tr>'
                . (!empty($u['dtc']) ? '<tr><td style="' . $label . '">Código de avería</td><td style="' . $cell . 'font-family:monospace;">' . $e($u['dtc']) . '</td></tr>' : '')
                . '<tr><td style="' . $label . '">Qué ocurre</td><td style="' . $cell . '">' . nl2br($e($u['symptoms'] ?? '')) . '</td></tr>'
                . (!empty($u['accessories']) ? '<tr><td style="' . $label . '">Accesorios</td><td style="' . $cell . '">' . $e($u['accessories']) . '</td></tr>' : '')
                . '<tr><td style="' . $label . '">Fotos o documentos</td><td style="' . $cell . '">' . ($attachments ?: 'ninguno') . '</td></tr>'
                . '</table></div>';
        }
        $rows = '<tr><td style="' . $label . '">Recibida</td><td style="' . $cell . '">' . $e($when) . '</td></tr>'
            . '<tr><td style="' . $label . '">Cliente</td><td style="' . $cell . '">' . $e($client) . '</td></tr>'
            . '<tr><td style="' . $label . '">Vehículo</td><td style="' . $cell . 'font-weight:600;">' . $e($vehicle !== '' ? $vehicle : 'No indicado') . '</td></tr>'
            . ($shipping ? '<tr><td style="' . $label . '">Llegada de la pieza</td><td style="' . $cell . '">' . $e($inbound) . '</td></tr>'
                . '<tr><td style="' . $label . '">Devolución</td><td style="' . $cell . '">' . $e($outbound) . '</td></tr>' : '');

        $html = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,Helvetica,Arial,sans-serif;max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #d5dfe8;border-radius:12px;overflow:hidden;color:#162633;">'
            . ($test ? '<div style="background:#fff4d6;color:#7a4b00;padding:10px 24px;font-size:13px;font-weight:700;">PRUEBA: esta solicitud viene del formulario de prueba. No es un cliente real.</div>' : '')
            . '<div style="background:#0b1e2d;color:#ffffff;padding:20px 24px;">'
            . '<div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#8bb4d0;margin-bottom:6px;">MENIGAR · ' . $e($kind) . ' desde la web</div>'
            . '<div style="font-size:22px;font-weight:800;">' . $e($reference) . '</div>'
            . '<div style="font-size:14px;color:#cfe0ec;margin-top:4px;">' . $e($pieces) . ($vehicle !== '' ? ' · ' . $e($vehicle) : '') . '</div>'
            . '</div>'
            . '<div style="padding:20px 24px;">'
            . '<table style="width:100%;border-collapse:collapse;font-size:13px;color:#1e3342;margin-bottom:16px;">' . $rows . '</table>'
            . $unitsHtml
            . '<p style="margin:18px 0 6px;"><a href="' . $e($staffUrl) . '" style="display:inline-block;background:#0f3852;color:#ffffff;text-decoration:none;padding:11px 18px;border-radius:8px;font-weight:700;font-size:14px;">Abrir la ficha completa</a></p>'
            . '<p style="margin:0;font-size:12px;color:#586f82;">Los datos de contacto y las fotos están en la ficha, con tu usuario del equipo. Este aviso no confirma una orden de reparación ni un pago.</p>'
            . '</div></div>';

        return ['subject' => $subject, 'body' => implode("\r\n", $lines) . "\r\n", 'html' => $html];
    }

    private static function madridTime(string $utc): string
    {
        try {
            return (new \DateTimeImmutable($utc))->setTimezone(new \DateTimeZone('Europe/Madrid'))->format('d/m/Y H:i');
        } catch (Throwable) {
            return $utc;
        }
    }

    /** One address or a list (for a test: the laboratory mailbox plus a copy). */
    private function recipients(array $settings): array
    {
        $raw = $settings['to'] ?? '';
        $list = is_array($raw) ? $raw : explode(',', (string) $raw);
        return array_values(array_filter(array_map(static fn($value) => trim((string) $value), $list), static fn($value) => $value !== ''));
    }

    public function previewEmail(string $reference): array
    {
        $settings = $this->intake->config['notifications'] ?? [];
        $basePath = rtrim((string) ($this->intake->config['basePath'] ?? ''), '/');
        $staffUrl = $this->intake->config['baseUrl'] . $basePath . '/equipo/solicitudes/' . $reference;
        $rich = $this->buildRichBody($reference, $staffUrl);
        return [
            'to' => implode(', ', $this->recipients($settings) ?: ['informacion@menigar.com']),
            'from' => 'MENIGAR Recepción <' . ($settings['from'] ?? 'informacion@menigar.com') . '>',
            'subject' => $rich['subject'],
            'body' => $rich['body'],
            'html' => $rich['html'] ?? '',
            'staffUrl' => $staffUrl,
        ];
    }

    public function run(int $limit = 30): array
    {
        $lock = fopen($this->intake->storage . '/notifications.lock', 'c');
        if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) return ['busy' => true, 'acceptedByMailServer' => 0, 'testSpooled' => 0];
        $result = ['busy' => false, 'acceptedByMailServer' => 0, 'testSpooled' => 0, 'retry' => 0, 'failed' => 0];
        try {
            // A previous worker died after claiming a job. It may have handed the
            // message to the MTA already: flag for review instead of resending.
            $this->intake->execute("UPDATE notifications SET state='uncertain',last_error='previous_worker_interrupted' WHERE state='sending'");
            for ($i = 0; $i < min(100, max(1, $limit)); $i++) {
                $job = $this->intake->one("SELECT * FROM notifications WHERE state IN ('queued','retry') AND next_attempt<=? ORDER BY id LIMIT 1", [time()]);
                if (!$job) break;
                $attempt = (int) $job['attempts'] + 1;
                $this->intake->execute("UPDATE notifications SET state='sending',attempts=? WHERE id=?", [$attempt, $job['id']]);
                $deliveryUncertain = false;
                try {
                    $settings = $this->intake->config['notifications'] ?? [];
                    $transport = $settings['transport'] ?? 'spool';
                    $reference = $job['request_reference'];
                    $basePath = rtrim((string) ($this->intake->config['basePath'] ?? ''), '/');
                    $staffUrl = $this->intake->config['baseUrl'] . $basePath . '/equipo/solicitudes/' . $reference;
                    $message = ['reference' => $reference, 'staffUrl' => $staffUrl,
                        'subject' => 'MENIGAR: nueva solicitud ' . $reference,
                        'body' => "Nueva solicitud web: $reference\nConsulta los datos y archivos en el acceso privado del equipo:\n" . $staffUrl . "\n\nEl registro no confirma una orden de reparación ni un pago.\n"];
                    if (($settings['richEmail'] ?? false) === true) {
                        $rich = $this->buildRichBody($reference, $staffUrl);
                        $message['subject'] = $rich['subject'];
                        $message['body'] = $rich['body'];
                        $message['html'] = $rich['html'] ?? '';
                    }
                    if ($transport === 'spool') {
                        if ($this->intake->config['mode'] !== 'review') throw new \RuntimeException('Test transport cannot notify production');
                        $path = $this->intake->storage . '/spool/' . $reference . '.json';
                        if (file_put_contents($path, json_encode(['testOnly' => true, ...$message], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), LOCK_EX) === false) throw new \RuntimeException('Spool write failed');
                        chmod($path, 0600); $state = 'test_spooled'; $result['testSpooled']++;
                    } elseif ($transport === 'sendmail' && in_array($this->intake->config['mode'], ['production', 'review'], true)) {
                        $recipients = $this->recipients($settings); $from = $settings['from'] ?? '';
                        foreach ($recipients as $address) if (!filter_var($address, FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n,]/', $address)) throw new \RuntimeException('Mail configuration unavailable');
                        if (!$recipients || !filter_var($from, FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/', $from) || !function_exists('mail')) throw new \RuntimeException('Mail configuration unavailable');
                        $to = implode(', ', $recipients);
                        $domain = parse_url($this->intake->config['baseUrl'], PHP_URL_HOST);
                        $messageId = hash_hmac('sha256', 'notification:' . $reference, $this->intake->config['secret']);
                        $deliveryUncertain = true;
                        $encodedSubject = '=?UTF-8?B?' . base64_encode($message['subject']) . '?=';
                        if (!empty($message['html'])) {
                            $boundary = '=_Menigar_' . substr($messageId, 0, 24);
                            $headers = [
                                'From' => '=?UTF-8?B?' . base64_encode('MENIGAR Recepción') . '?= <' . $from . '>',
                                'Reply-To' => $from,
                                'MIME-Version' => '1.0',
                                'Content-Type' => 'multipart/alternative; boundary="' . $boundary . '"',
                                'Message-ID' => '<' . $messageId . '@' . $domain . '>',
                            ];
                            $mimeBody = "--{$boundary}\r\n"
                                . "Content-Type: text/plain; charset=UTF-8\r\n"
                                . "Content-Transfer-Encoding: 8bit\r\n\r\n"
                                . $message['body'] . "\r\n"
                                . "--{$boundary}\r\n"
                                . "Content-Type: text/html; charset=UTF-8\r\n"
                                . "Content-Transfer-Encoding: 8bit\r\n\r\n"
                                . $message['html'] . "\r\n"
                                . "--{$boundary}--\r\n";
                        } else {
                            $headers = ['From' => '=?UTF-8?B?' . base64_encode('MENIGAR Recepción') . '?= <' . $from . '>', 'Reply-To' => $from, 'MIME-Version' => '1.0', 'Content-Type' => 'text/plain; charset=UTF-8', 'Message-ID' => '<' . $messageId . '@' . $domain . '>'];
                            $mimeBody = $message['body'];
                        }
                        $accepted = @mail($to, $encodedSubject, $mimeBody, $headers, '-f' . $from);
                        if (!$accepted) {
                            $accepted = @mail($to, $encodedSubject, $mimeBody, $headers);
                        }
                        if (!$accepted) { $deliveryUncertain = false; throw new \RuntimeException('Mail transport rejected message'); }
                        $state = 'sent'; $result['acceptedByMailServer']++;
                    } else throw new \RuntimeException('Notification transport unavailable');
                    $this->intake->execute('UPDATE notifications SET state=?,last_error=NULL,sent_at=? WHERE id=?', [$state, $state === 'sent' ? $this->intake->now() : null, $job['id']]);
                    $this->intake->execute('INSERT INTO events(request_reference,kind,actor,created_at) VALUES (?,?,?,?)', [$reference, $state === 'sent' ? 'notification_accepted_by_mta' : 'notification_test_spooled', 'worker', $this->intake->now()]);
                } catch (Throwable $error) {
                    $state = $deliveryUncertain ? 'uncertain' : ($attempt < 5 ? 'retry' : 'failed');
                    $this->intake->execute('UPDATE notifications SET state=?,next_attempt=?,last_error=? WHERE id=?', [$state, time() + min(3600, 60 * (2 ** ($attempt - 1))), 'notification_transport_failed', $job['id']]);
                    $result[$state] = ($result[$state] ?? 0) + 1;
                }
            }
            return $result;
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
