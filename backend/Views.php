<?php
declare(strict_types=1);
namespace Menigar;

final class Views
{
    public static function e(mixed $value): string { return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
    public static function vehicleLabel(array $vehicle): string
    {
        return $vehicle['brand'] . ' · ' . (($vehicle['modelUnknown'] ?? false) ? 'Modelo desconocido' : $vehicle['model']);
    }
    public static function addressLabel(array $customer, bool $return = false): string
    {
        $fields = $return ? ['returnAddress', 'returnPostalCode', 'returnCity'] : ['address', 'postalCode', 'city', 'province'];
        $parts = array_filter(array_map(fn($key) => $customer[$key] ?? '', $fields));
        if (!$parts) return '';
        $parts[] = $customer[$return ? 'returnCountry' : 'country'] ?? '';
        return implode(', ', array_filter($parts));
    }
    public static function shell(string $title, string $body): string
    {
        return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>' . self::e($title) . ' · MENIGAR</title><link rel="stylesheet" href="/solicitud.css"><link rel="stylesheet" href="/assets/equipo.css"><script src="/resumen.js" defer></script></head><body class="receipt-page"><main class="receipt">' . $body . '</main></body></html>';
    }
    public static function details(array $items): string
    {
        $html = '<dl>';
        foreach ($items as $label => $value) $html .= '<dt>' . self::e($label) . '</dt><dd class="pre">' . self::e($value ?: 'No indicado') . '</dd>';
        return $html . '</dl>';
    }
    public static function staffRequest(array $row, string $csrf, string $mode): string
    {
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR); $c = $p['customer']; $v = $p['vehicle'];
        $html = '<div class="receipt-tools"><a href="/equipo/solicitudes">← Solicitudes</a><button type="button" data-print>Imprimir o guardar PDF</button></div><p class="receipt-brand">MENIGAR · Solicitud web' . ($mode === 'review' ? ' · Prueba' : '') . '</p><h1>' . self::e($row['reference']) . '</h1><p>Registrada el ' . self::e($row['created_at']) . '. Esta referencia identifica una solicitud; no es una orden de reparación.</p>';
        $shipping = $p['intent'] === 'repair';
        $address = self::addressLabel($c); $returnAddress = $c['returnDifferent'] ? self::addressLabel($c, true) : $address;
        $shippingDetails = [];
        if ($shipping || $c['taxId']) $shippingDetails['NIF/CIF'] = $c['taxId'];
        if ($shipping || $address) $shippingDetails['Dirección'] = $address;
        if ($shipping || $returnAddress) $shippingDetails['Devolución'] = $returnAddress;
        $html .= self::details(['Tipo' => $shipping ? 'Preparar solicitud de envío' : 'Consultar mi pieza', 'Solicitante' => $c['name'], 'Persona de contacto' => $c['contact'], 'Correo' => $c['email'], 'Teléfono' => $c['phone'], ...$shippingDetails, 'Vehículo' => self::vehicleLabel($v), 'Matrícula' => $v['plate'], 'Bastidor' => $v['vin'], 'Año / kilómetros' => $v['year'] . ' / ' . $v['km'], 'Contexto de consulta' => $p['contextQuery']]);
        foreach ($p['units'] as $index => $unit) {
            $html .= '<section class="piece"><h2>Pieza ' . ($index + 1) . ': ' . self::e($unit['componentName']) . '</h2>' . self::details(['Identificador de unidad' => $row['reference'] . '-P' . ($index + 1), 'Fabricante' => $unit['manufacturer'], 'Referencia declarada por el cliente' => $unit['reference'] ?: 'Por identificar', 'Código de avería' => $unit['dtc'], 'Qué ocurre' => $unit['symptoms'], 'Accesorios' => $unit['accessories'], 'Vehículo de esta pieza' => trim($unit['vehicleBrand'] . ' ' . $unit['vehicleModel']) ?: self::vehicleLabel($v)]);
            $html .= '<ul class="staff-files">';
            foreach ($unit['attachments'] as $file) $html .= '<li><a href="/equipo/solicitudes/' . self::e($row['reference']) . '/archivo/' . self::e($file['id']) . '">' . self::e($file['name']) . '</a></li>';
            $html .= '</ul></section>';
        }
        $html .= '<aside class="receipt-note"><h2>Revisión de la solicitud</h2><p>Los datos declarados se conservan tal como llegaron. El diagnóstico, la referencia corregida, el presupuesto y la orden se gestionan en el sistema del taller.</p>';
        if ($row['reviewed_at']) $html .= '<p><strong>Solicitud revisada:</strong> ' . self::e($row['reviewed_at']) . '</p>';
        else $html .= '<form method="post" action="/equipo/solicitudes/' . self::e($row['reference']) . '/revisada"><input type="hidden" name="csrf" value="' . self::e($csrf) . '"><button type="submit">Marcar solicitud como revisada</button></form>';
        return self::shell($row['reference'], $html . '</aside>');
    }
    public static function inbox(array $rows, int $page, int $total): string
    {
        $html = '<div class="receipt-tools"><a href="/">Ver la web</a></div><p class="receipt-brand">MENIGAR · Acceso del equipo</p><h1>Solicitudes recibidas</h1><p>Consultas y peticiones de la web. Su registro no confirma la llegada de una pieza, su reparación ni su pago.</p><div class="staff-table-wrap"><table class="staff-table"><thead><tr><th>Solicitud</th><th>Cliente</th><th>Piezas</th><th>Revisión</th><th>Aviso al equipo</th></tr></thead><tbody>';
        foreach ($rows as $row) {
            $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
            $notification = ['queued' => 'Pendiente', 'sent' => 'Aceptado por el servidor de correo', 'test_spooled' => 'Simulado en prueba', 'retry' => 'Reintento pendiente', 'sending' => 'En proceso', 'uncertain' => 'Comprobar envío', 'failed' => 'Revisar aviso'][$row['notification_state']] ?? 'Pendiente';
            $html .= '<tr><td><a href="/equipo/solicitudes/' . self::e($row['reference']) . '">' . self::e($row['reference']) . '</a><small>' . self::e($row['created_at']) . '</small></td><td>' . self::e($p['customer']['name']) . '</td><td>' . count($p['units']) . '</td><td>' . ($row['reviewed_at'] ? 'Revisada' : 'Nueva') . '</td><td>' . self::e($notification) . '</td></tr>';
        }
        if (!$rows) $html .= '<tr><td colspan="5">Todavía no hay solicitudes.</td></tr>';
        $html .= '</tbody></table></div><nav class="staff-pagination" aria-label="Páginas de solicitudes">';
        if ($page > 1) $html .= '<a href="?pagina=' . ($page - 1) . '">← Anteriores</a>';
        if ($page * 100 < $total) $html .= '<a href="?pagina=' . ($page + 1) . '">Siguientes →</a>';
        return self::shell('Solicitudes recibidas', $html . '</nav>');
    }
}
