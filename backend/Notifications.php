<?php
declare(strict_types=1);
namespace Menigar;

use Throwable;

final class Notifications
{
    public function __construct(private readonly Intake $intake) {}
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
                    $message = ['reference' => $reference, 'staffUrl' => $this->intake->config['baseUrl'] . '/equipo/solicitudes/' . $reference,
                        'subject' => 'MENIGAR: nueva solicitud ' . $reference,
                        'body' => "Nueva solicitud web: $reference\nConsulta los datos y archivos en el acceso privado del equipo:\n" . $this->intake->config['baseUrl'] . '/equipo/solicitudes/' . $reference . "\n\nEl registro no confirma una orden de reparación ni un pago.\n"];
                    if ($transport === 'spool') {
                        if ($this->intake->config['mode'] !== 'review') throw new \RuntimeException('Test transport cannot notify production');
                        $path = $this->intake->storage . '/spool/' . $reference . '.json';
                        if (file_put_contents($path, json_encode(['testOnly' => true, ...$message], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE), LOCK_EX) === false) throw new \RuntimeException('Spool write failed');
                        chmod($path, 0600); $state = 'test_spooled'; $result['testSpooled']++;
                    } elseif ($transport === 'sendmail' && $this->intake->config['mode'] === 'production') {
                        $to = $settings['to'] ?? ''; $from = $settings['from'] ?? '';
                        if (!filter_var($to, FILTER_VALIDATE_EMAIL) || !filter_var($from, FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/', $to . $from) || !function_exists('mail')) throw new \RuntimeException('Mail configuration unavailable');
                        $domain = parse_url($this->intake->config['baseUrl'], PHP_URL_HOST);
                        $messageId = hash_hmac('sha256', 'notification:' . $reference, $this->intake->config['secret']);
                        $deliveryUncertain = true;
                        $accepted = mail($to, $message['subject'], $message['body'], ['From' => 'MENIGAR <' . $from . '>', 'MIME-Version' => '1.0', 'Content-Type' => 'text/plain; charset=UTF-8', 'Message-ID' => '<' . $messageId . '@' . $domain . '>']);
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
