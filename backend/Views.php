<?php
declare(strict_types=1);
namespace Menigar;

/**
 * Pages of the team area (/equipo). Written for the laboratory staff: plain Spanish,
 * «laboratorio» (never «taller» for MENIGAR) and no claims about systems that are not
 * connected. Everything here sits behind the team login (Http::staff).
 */
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

    /** Stored times are UTC; the team reads Madrid time. */
    public static function when(string $utc): string
    {
        try {
            return (new \DateTimeImmutable($utc))->setTimezone(new \DateTimeZone('Europe/Madrid'))->format('d/m/Y H:i');
        } catch (\Throwable) {
            return $utc;
        }
    }

    private static function customerType(array $c): string
    {
        return ($c['type'] ?? '') === 'taller' ? 'Taller o empresa' : 'Particular';
    }

    public static function shell(string $title, string $body, string $basePath = '', bool $test = false): string
    {
        $bp = rtrim($basePath, '/');
        $topbar = '<header class="staff-topbar"><div class="staff-topbar-inner">'
            . '<div class="staff-brand-group">'
            . '<a class="staff-brand-logo" href="' . self::e($bp) . '/equipo/solicitudes"><img src="' . self::e($bp) . '/assets/marca/menigar-logo-1x.webp" width="168" height="25" alt="MENIGAR"></a>'
            . '<span class="staff-brand-divider"></span>'
            . '<span class="staff-brand-title">Solicitudes de la web · Equipo</span>'
            . '</div>'
            . '<nav class="staff-topnav" aria-label="Navegación del equipo">'
            . '<a href="' . self::e($bp) . '/equipo/solicitudes">Solicitudes</a>'
            . '<a href="' . self::e($bp) . '/solicitud.html">Abrir el formulario como cliente</a>'
            . '</nav>'
            . '</div></header>';
        $banner = $test ? '<p class="staff-test-banner" role="note"><strong>Prueba.</strong> Estas solicitudes vienen del formulario de prueba. No son clientes reales.</p>' : '';

        return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="same-origin"><title>' . self::e($title) . ' · Equipo MENIGAR</title><link rel="stylesheet" href="' . self::e($bp) . '/style.css"><link rel="stylesheet" href="' . self::e($bp) . '/solicitud.css"><link rel="stylesheet" href="' . self::e($bp) . '/assets/equipo.css"><script src="' . self::e($bp) . '/resumen.js" defer></script></head><body class="receipt-page staff-app-body">' . $topbar . $banner . '<main class="receipt staff-workspace">' . $body . '</main></body></html>';
    }

    public static function details(array $items): string
    {
        $html = '<dl>';
        foreach ($items as $label => $value) $html .= '<dt>' . self::e($label) . '</dt><dd class="pre">' . self::e($value ?: 'No indicado') . '</dd>';
        return $html . '</dl>';
    }

    private static function selectOptions(array $choices, string $selected): string
    {
        $out = '';
        foreach ($choices as $key => $label) {
            $sel = ((string) $key === $selected) ? ' selected' : '';
            $out .= '<option value="' . self::e($key) . '"' . $sel . '>' . self::e($label) . '</option>';
        }
        return $out;
    }

    private static function logistics(array $c): array
    {
        return [
            ($c['deliveryMethod'] ?? '') === 'entrega_mano' ? 'La entrega en mano en Alcobendas' : 'La envía por mensajería por su cuenta (le recomendamos MRW)',
            ($c['returnMethod'] ?? '') === 'recogida_mano' ? 'La recoge en mano en Alcobendas' : 'MENIGAR la devuelve por MRW',
        ];
    }

    public static function staffRequest(array $row, string $csrf, string $mode, array $units = [], string $basePath = '', bool $savedNotice = false): string
    {
        $bp = rtrim($basePath, '/');
        $ref = (string) $row['reference'];
        $base = self::e($bp) . '/equipo/solicitudes/' . self::e($ref);
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $p['customer'];
        $v = $p['vehicle'];
        $shipping = $p['intent'] === 'repair';
        $unitCount = count($p['units']);
        $byUnit = [];
        foreach ($units['repair_orders'] ?? [] as $unitData) $byUnit[(int) ($unitData['vals']['x_unit_number'] ?? 0)] = $unitData;

        $html = '<div class="receipt-tools">'
            . '<a class="staff-btn staff-btn-secondary" href="' . self::e($bp) . '/equipo/solicitudes">← Todas las solicitudes</a>'
            . '<div class="receipt-tools-group">'
            . '<a class="staff-btn staff-btn-secondary" href="' . $base . '/correo">Ver el correo de aviso</a>'
            . '<a class="staff-btn staff-btn-secondary" href="' . $base . '/hoja-tecnica">Hojas de trabajo para imprimir</a>'
            . '<button type="button" class="staff-btn staff-btn-secondary" data-print>Imprimir esta ficha</button>'
            . '</div></div>';

        if ($savedNotice) {
            $html .= '<div class="staff-alert-ok" role="status"><strong>Cambios guardados.</strong> Lo que escribió el cliente se conserva sin cambios.</div>';
        }

        $html .= '<section class="staff-hero-card"><div class="staff-hero-main">'
            . '<div class="staff-pill-row">'
            . '<span class="staff-pill ' . ($shipping ? 'staff-pill-shipping' : 'staff-pill-consult') . '">' . ($shipping ? 'Envío de pieza' : 'Consulta') . '</span>'
            . '<span class="staff-pill staff-pill-neutral">' . $unitCount . ($unitCount === 1 ? ' pieza' : ' piezas') . '</span>'
            . ($row['reviewed_at'] ? '<span class="staff-pill staff-pill-ok">Revisada</span>' : '<span class="staff-pill staff-pill-warn">Sin revisar</span>')
            . '</div>'
            . '<h1>' . self::e($ref) . ' · ' . self::e($c['name']) . '</h1>'
            . '<p class="staff-hero-sub">Recibida el <strong>' . self::e(self::when((string) $row['created_at'])) . '</strong> · ' . self::e(self::vehicleLabel($v)) . '</p>'
            . '</div></section>';

        $address = self::addressLabel($c);
        $returnAddress = $c['returnDifferent'] ? self::addressLabel($c, true) : $address;
        $customerDetails = [
            'Nombre o razón social' => $c['name'],
            'Tipo de cliente' => self::customerType($c),
            'Persona de contacto' => $c['contact'] ?: $c['name'],
            'Teléfono' => $c['phone'],
            'Correo' => $c['email'],
        ];
        if ($shipping || $c['taxId']) $customerDetails['NIF/CIF'] = $c['taxId'];
        [$inbound, $outbound] = self::logistics($c);
        // The customer's own words for what they chose, so the team reads the same as the form.
        $logistics = $shipping
            ? ['Qué pidió' => 'Preparar solicitud de envío', 'Llegada de la pieza' => $inbound, 'Devolución' => $outbound, 'Dirección' => $address, 'Devolver a' => $returnAddress]
            : ['Qué pidió' => 'Consultar mi pieza (orientación antes de enviarla)'];
        if (!$shipping && $address !== '') $logistics['Dirección'] = $address;

        $html .= '<div class="staff-summary-grid">'
            . '<section class="staff-summary-card"><h2>Cliente</h2>' . self::details($customerDetails) . '</section>'
            . '<section class="staff-summary-card"><h2>Vehículo</h2>' . self::details([
                'Vehículo' => self::vehicleLabel($v),
                'Matrícula' => $v['plate'] ?: 'No indicada',
                'Bastidor (VIN)' => $v['vin'] ?: 'No indicado',
                'Año y kilómetros' => ($v['year'] ?: '—') . ' / ' . ($v['km'] ?: '—'),
                'Lo que buscó en la web' => $p['contextQuery'] ?: 'Entró directamente al formulario',
            ]) . '</section>'
            . '<section class="staff-summary-card"><h2>' . ($shipping ? 'Envío y devolución' : 'Consulta') . '</h2>' . self::details($logistics) . '</section>'
            . '</div>';

        foreach ($p['units'] as $index => $unit) {
            $num = $index + 1;
            $code = $ref . '-P' . $num;
            $vals = $byUnit[$num]['vals'] ?? [];
            $declared = $unit['reference'] ?: 'Sin identificar';
            $confirmed = (string) ($vals['x_confirmed_reference'] ?? $declared);
            $changed = !empty($vals['x_reference_modified']);
            $reception = (string) ($vals['x_reception_state'] ?? 'pendiente_llegada');
            $technical = (string) ($vals['x_technical_state'] ?? 'pendiente_diagnostico');
            $commercial = (string) ($vals['x_commercial_state'] ?? 'pendiente_presupuesto');

            $html .= '<section class="piece staff-unit-card" id="unidad-' . $num . '">'
                . '<div class="piece-header-row"><div>'
                . '<span class="staff-unit-kicker">Pieza ' . $num . ' de ' . $unitCount . '</span>'
                . '<h2>' . self::e($unit['componentName']) . '</h2>'
                . '</div><div class="piece-badges">'
                . '<span class="erp-order-pill">' . self::e($code) . '</span>'
                . '<span class="erp-status-badge">' . self::e(OdooConnector::RECEPTION_STATES[$reception] ?? $reception) . '</span>'
                . '</div></div>'
                . '<div class="dual-ref-banner">'
                . '<div class="dual-ref-box"><span class="dual-ref-label">Referencia que indicó el cliente (no se modifica)</span><strong class="dual-ref-value">' . self::e($declared) . '</strong></div>'
                . '<div class="dual-ref-arrow" aria-hidden="true">→</div>'
                . '<div class="dual-ref-box ' . ($changed ? 'dual-ref-box-updated' : '') . '"><span class="dual-ref-label">Referencia comprobada en el laboratorio</span><strong class="dual-ref-value">' . self::e($confirmed) . '</strong>'
                . '<small>' . ($changed ? 'Corregida por el técnico; la del cliente se conserva' : 'Todavía es la que indicó el cliente') . '</small></div>'
                . '</div>'
                . self::details([
                    'Fabricante' => $unit['manufacturer'] ?: 'Por comprobar en la etiqueta',
                    'Código de avería' => $unit['dtc'] ?: 'No indicado',
                    'Qué ocurre' => $unit['symptoms'],
                    'Accesorios' => $unit['accessories'] ?: 'Solo la pieza',
                    'Vehículo de esta pieza' => trim($unit['vehicleBrand'] . ' ' . $unit['vehicleModel']) ?: self::vehicleLabel($v),
                ]);

            if (!empty($unit['attachments'])) {
                $html .= '<div class="staff-files-box"><p class="staff-files-title"><strong>Fotos y documentos (' . count($unit['attachments']) . ')</strong></p><ul class="staff-files">';
                foreach ($unit['attachments'] as $file) {
                    $html .= '<li><a href="' . $base . '/archivo/' . self::e($file['id']) . '">' . self::e($file['name']) . '</a></li>';
                }
                $html .= '</ul></div>';
            }

            if ($vals) {
                $html .= '<div class="workshop-unit-panel">'
                    . '<div class="workshop-panel-head"><h3>Recepción y seguimiento de ' . self::e($code) . '</h3>'
                    . '<span class="workshop-panel-sub">Lo que guardes aquí sale en la hoja de trabajo de esta pieza.</span></div>'
                    . '<form method="post" action="' . $base . '/unidad/' . $num . '" class="workshop-unit-form">'
                    . '<input type="hidden" name="csrf" value="' . self::e($csrf) . '">'
                    . '<div class="workshop-grid">'
                    . '<label class="workshop-field"><span>Llegada y embalaje</span><select name="reception_state">' . self::selectOptions(OdooConnector::RECEPTION_STATES, $reception) . '</select></label>'
                    . '<label class="workshop-field"><span>Referencia comprobada en la etiqueta</span><input type="text" name="confirmed_reference" value="' . self::e($confirmed) . '" maxlength="120"><small>La del cliente (' . self::e($declared) . ') se guarda igualmente.</small></label>'
                    . '<label class="workshop-field"><span>Estado en el laboratorio</span><select name="technical_state">' . self::selectOptions(OdooConnector::TECHNICAL_STATES, $technical) . '</select></label>'
                    . '<label class="workshop-field"><span>Presupuesto y cobro</span><select name="commercial_state">' . self::selectOptions(OdooConnector::COMMERCIAL_STATES, $commercial) . '</select></label>'
                    . '<label class="workshop-field"><span>Importe del presupuesto</span><input type="text" name="estimated_eur" value="' . self::e((string) ($vals['x_estimated_eur'] ?? '')) . '" placeholder="Ej. 240 € + IVA" maxlength="40"></label>'
                    . '<label class="workshop-field"><span>Ticket del banco de pruebas</span><input type="text" name="bench_ticket" value="' . self::e((string) ($vals['x_bench_ticket'] ?? '')) . '" maxlength="80"></label>'
                    . '</div><div class="workshop-grid-wide">'
                    . '<label class="workshop-field"><span>Qué llegó realmente en el paquete</span><input type="text" name="reception_notes" value="' . self::e((string) ($vals['x_reception_notes'] ?? '')) . '" placeholder="Ej. Caja bien, llega con soporte y conector" maxlength="500"></label>'
                    . '<label class="workshop-field"><span>Notas del técnico</span><textarea name="technician_notes" rows="2" maxlength="1000">' . self::e((string) ($vals['internal_notes'] ?? '')) . '</textarea></label>'
                    . '</div><div class="workshop-actions">'
                    . '<button type="submit" class="staff-btn">Guardar ' . self::e($code) . '</button>'
                    . '<a class="staff-btn staff-btn-secondary" href="' . $base . '/hoja-tecnica#orden-' . $num . '">Hoja de trabajo de ' . self::e($code) . '</a>'
                    . '</div></form></div>';
            }
            $html .= '</section>';
        }

        $html .= '<section class="odoo-bridge-card" id="exportar">'
            . '<h2>Pasar los datos al programa de gestión</h2>'
            . '<p>Hoy estos datos se teclean a mano en MotorWin. Esta prueba no está conectada a ningún programa. Para comprobar si se pueden importar sin teclear, descarga el archivo: una fila por pieza, con los datos del cliente, del vehículo y de la avería. La conexión directa depende de la decisión entre MotorWin y Odoo.</p>'
            . '<div class="receipt-tools-group"><a class="staff-btn staff-btn-secondary" href="' . $base . '/datos.csv">Descargar los datos (CSV, se abre con Excel)</a></div>'
            . '</section>';

        $html .= '<aside class="receipt-note"><h2>Revisión</h2>';
        if ($row['reviewed_at']) {
            $html .= '<p><strong>Revisada</strong> el ' . self::e(self::when((string) $row['reviewed_at'])) . '.</p>';
        } else {
            $html .= '<p>Márcala cuando alguien del equipo la haya leído.</p><form method="post" action="' . $base . '/revisada"><input type="hidden" name="csrf" value="' . self::e($csrf) . '"><button type="submit">Marcar como revisada</button></form>';
        }
        return self::shell($ref, $html . '</aside>', $bp, $mode !== 'production');
    }

    /** One printable sheet per piece, to travel with it in its tray. */
    public static function workSheet(array $row, array $units, string $basePath = '', bool $test = false): string
    {
        $bp = rtrim($basePath, '/');
        $ref = (string) $row['reference'];
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $p['customer'];
        $v = $p['vehicle'];
        $address = self::addressLabel($c);
        $returnAddress = $c['returnDifferent'] ? self::addressLabel($c, true) : $address;
        $total = count($units['repair_orders'] ?? []);

        $html = '<div class="receipt-tools">'
            . '<a class="staff-btn staff-btn-secondary" href="' . self::e($bp) . '/equipo/solicitudes/' . self::e($ref) . '">← Volver a la ficha ' . self::e($ref) . '</a>'
            . '<button type="button" class="staff-btn" data-print>Imprimir las hojas</button>'
            . '</div>';

        foreach ($units['repair_orders'] ?? [] as $idx => $unitData) {
            $u = $unitData['vals'];
            $num = $idx + 1;
            $html .= '<article class="work-order-sheet" id="orden-' . $num . '">'
                . '<header class="work-order-header"><div>'
                . '<p class="receipt-brand">MENIGAR · Hoja de trabajo de la pieza' . ($test ? ' · PRUEBA' : '') . '</p>'
                . '<h1>' . self::e($u['name']) . ' · ' . self::e($u['x_component_family']) . '</h1>'
                . '<p>Solicitud <strong>' . self::e($ref) . '</strong> · Pieza <strong>' . $num . ' de ' . $total . '</strong> · Recibida el ' . self::e(self::when((string) $row['created_at'])) . '</p>'
                . '</div><div class="work-order-box-code"><span>PIEZA</span><strong>P' . $num . ' / ' . $total . '</strong>'
                . '<small>' . ($u['x_intent'] === 'envio_reparacion' ? 'ENVÍO DE PIEZA' : 'CONSULTA') . '</small></div>'
                . '</header>'
                . '<div class="work-order-grid">'
                . '<section class="work-order-block"><h2>1. Cliente y devolución</h2>' . self::details([
                    'Cliente' => $c['name'] . ' (' . self::customerType($c) . ')',
                    'Persona de contacto' => $c['contact'] ?: $c['name'],
                    'NIF/CIF' => $c['taxId'] ?: 'Pendiente',
                    'Teléfono y correo' => $c['phone'] . ' · ' . $c['email'],
                    'Devolver a' => $returnAddress ?: 'Pendiente de confirmar',
                ]) . '</section>'
                . '<section class="work-order-block"><h2>2. Vehículo</h2>' . self::details([
                    'Marca y modelo' => trim(($u['x_vehicle_brand'] ?: $v['brand']) . ' ' . ($u['x_vehicle_model'] ?: '')),
                    'Matrícula' => $v['plate'] ?: 'No indicada',
                    'Bastidor (VIN)' => $v['vin'] ?: 'No indicado',
                    'Año y kilómetros' => ($v['year'] ?: '-') . ' / ' . ($v['km'] ?: '-'),
                    'Llegada y embalaje' => OdooConnector::RECEPTION_STATES[$u['x_reception_state']] ?? $u['x_reception_state'],
                ]) . '</section>'
                . '</div>'
                . '<section class="work-order-block"><h2>3. La pieza</h2>' . self::details([
                    'Tipo de pieza' => $u['x_component_family'],
                    'Fabricante' => $u['x_manufacturer'] ?: 'Por comprobar en la etiqueta',
                    'Referencia que indicó el cliente' => $u['x_declared_reference'],
                    'Referencia comprobada' => $u['x_confirmed_reference'],
                    'Accesorios' => $u['x_accessories_declared'] ?: 'Solo la pieza',
                    'Qué llegó en el paquete' => $u['x_reception_notes'] ?: 'Sin anotar',
                ]) . '</section>'
                . '<section class="work-order-block"><h2>4. Avería</h2>' . self::details([
                    'Código de avería' => $u['x_dtc_codes'] ?: 'No indicado',
                    'Qué ocurre, según el cliente' => $u['description'],
                ]) . '</section>'
                . '<section class="work-order-block"><h2>5. Laboratorio y salida</h2>' . self::details([
                    'Estado en el laboratorio' => OdooConnector::TECHNICAL_STATES[$u['x_technical_state']] ?? $u['x_technical_state'],
                    'Ticket del banco de pruebas' => $u['x_bench_ticket'] ?: '________________________________',
                    'Notas del técnico' => $u['internal_notes'] ?: "\n\n________________________________________________________________",
                    'Presupuesto y cobro' => (OdooConnector::COMMERCIAL_STATES[$u['x_commercial_state']] ?? $u['x_commercial_state']) . ($u['x_estimated_eur'] ? ' · ' . $u['x_estimated_eur'] : ''),
                ]) . '</section>'
                . '</article>';
        }
        return self::shell('Hojas de trabajo ' . $ref, $html, $bp, $test);
    }

    public static function inbox(array $rows, int $page, int $total, string $basePath = '', bool $test = false): string
    {
        $bp = rtrim($basePath, '/');
        $pieces = 0; $shippingCount = 0; $pending = 0;
        foreach ($rows as $r) {
            $pr = json_decode($r['payload'], true);
            $pieces += count($pr['units'] ?? []);
            if (($pr['intent'] ?? '') === 'repair') $shippingCount++;
            if (!$r['reviewed_at']) $pending++;
        }
        $mailStates = ['queued' => 'Pendiente de enviar', 'sent' => 'Enviado', 'test_spooled' => 'Guardado sin enviar (prueba)', 'retry' => 'Reintentando', 'sending' => 'Enviándose', 'uncertain' => 'Comprobar si llegó', 'failed' => 'No se pudo enviar'];

        $html = '<section class="staff-hero-card"><div class="staff-hero-main">'
            . '<h1>Solicitudes recibidas</h1>'
            . '<p class="staff-hero-sub">Cada solicitud de la web llega aquí con sus piezas separadas (P1, P2…). Desde su ficha se imprime la hoja de trabajo de cada pieza y se descargan los datos.</p>'
            . '</div></section>'
            . '<div class="staff-kpi-grid">'
            . '<div class="staff-kpi-card"><span>Solicitudes</span><strong>' . $total . '</strong></div>'
            . '<div class="staff-kpi-card"><span>Piezas en esta página</span><strong>' . $pieces . '</strong></div>'
            . '<div class="staff-kpi-card"><span>Envíos de pieza</span><strong>' . $shippingCount . '</strong></div>'
            . '<div class="staff-kpi-card"><span>Sin revisar</span><strong>' . $pending . '</strong></div>'
            . '</div>'
            . '<div class="staff-table-card"><div class="staff-table-wrap"><table class="staff-table"><thead><tr><th>Referencia y fecha</th><th>Tipo</th><th>Cliente y vehículo</th><th>Piezas</th><th>Estado</th><th>Correo de aviso</th><th>Abrir</th></tr></thead><tbody>';
        foreach ($rows as $row) {
            $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
            $ref = (string) $row['reference'];
            $link = self::e($bp) . '/equipo/solicitudes/' . self::e($ref);
            $isShip = ($p['intent'] ?? '') === 'repair';
            $count = count($p['units']);
            $html .= '<tr>'
                . '<td><a class="table-ref-link" href="' . $link . '">' . self::e($ref) . '</a><small>' . self::e(self::when((string) $row['created_at'])) . '</small></td>'
                . '<td><span class="staff-pill ' . ($isShip ? 'staff-pill-shipping' : 'staff-pill-consult') . '">' . ($isShip ? 'Envío de pieza' : 'Consulta') . '</span></td>'
                . '<td><strong>' . self::e($p['customer']['name']) . '</strong><small>' . self::e(($p['vehicle']['brand'] ?? '') . ' · ' . (($p['vehicle']['modelUnknown'] ?? false) ? 'Modelo por identificar' : ($p['vehicle']['model'] ?? ''))) . '</small></td>'
                . '<td><strong>' . $count . '</strong><small>' . self::e(implode(', ', array_map(fn($n) => 'P' . $n, range(1, $count)))) . '</small></td>'
                . '<td><span class="table-state-pill">' . ($row['reviewed_at'] ? 'Revisada' : 'Sin revisar') . '</span></td>'
                . '<td><span class="table-mail-status">' . self::e($mailStates[$row['notification_state']] ?? 'Pendiente de enviar') . '</span></td>'
                . '<td class="table-actions-cell">'
                . '<a class="staff-btn staff-btn-sm" href="' . $link . '">Ficha</a> '
                . '<a class="staff-btn staff-btn-secondary staff-btn-sm" href="' . $link . '/hoja-tecnica">Hojas</a> '
                . '<a class="staff-btn staff-btn-secondary staff-btn-sm" href="' . $link . '/correo">Correo</a>'
                . '</td></tr>';
        }
        if (!$rows) $html .= '<tr><td colspan="7">Todavía no hay solicitudes. Envía una desde el formulario para ver cómo llega.</td></tr>';
        $html .= '</tbody></table></div></div><nav class="staff-pagination" aria-label="Páginas de solicitudes">';
        if ($page > 1) $html .= '<a href="?pagina=' . ($page - 1) . '">← Anteriores</a>';
        if ($page * 100 < $total) $html .= '<a href="?pagina=' . ($page + 1) . '">Siguientes →</a>';
        return self::shell('Solicitudes recibidas', $html . '</nav>', $bp, $test);
    }

    /** Shows the notice as the team receives it. The real email uses inline styles, which this page's CSP blocks, so it is rebuilt here with classes. */
    public static function emailPreview(array $row, array $email, ?array $notif, string $basePath = '', bool $test = false): string
    {
        $bp = rtrim($basePath, '/');
        $ref = (string) $row['reference'];
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $p['customer'];
        $v = $p['vehicle'];
        $units = $p['units'] ?? [];
        $shipping = ($p['intent'] ?? '') === 'repair';
        $count = count($units);
        $states = ['sent' => 'Enviado', 'test_spooled' => 'Guardado sin enviar (prueba)', 'queued' => 'Pendiente de enviar', 'retry' => 'Reintentando', 'sending' => 'Enviándose', 'uncertain' => 'Comprobar si llegó', 'failed' => 'No se pudo enviar'];
        $state = $states[$notif['state'] ?? ''] ?? 'Pendiente de enviar';
        if (!empty($notif['sent_at'])) $state .= ' el ' . self::when((string) $notif['sent_at']);
        [$inbound, $outbound] = self::logistics($c);
        $vehicle = trim(($v['brand'] ?? '') . ' ' . (($v['modelUnknown'] ?? false) ? '(modelo por identificar)' : ($v['model'] ?? '')));

        $html = '<div class="receipt-tools">'
            . '<a class="staff-btn staff-btn-secondary" href="' . self::e($bp) . '/equipo/solicitudes/' . self::e($ref) . '">← Volver a la ficha ' . self::e($ref) . '</a>'
            . '<button type="button" class="staff-btn staff-btn-secondary" data-print>Imprimir</button>'
            . '</div>'
            . '<section class="staff-hero-card"><div class="staff-hero-main">'
            . '<div class="staff-pill-row"><span class="staff-pill staff-pill-ok">' . self::e($state) . '</span></div>'
            . '<h1>Así llega el correo de aviso</h1>'
            . '<p class="staff-hero-sub">Se envía a <strong>' . self::e($email['to']) . '</strong>. No lleva datos de contacto del cliente: están en la ficha, con usuario del equipo.</p>'
            . '</div></section>'
            . '<div class="mail-window"><div class="mail-window-header">'
            . '<div class="mail-header-row"><span>De:</span><strong>' . self::e($email['from']) . '</strong></div>'
            . '<div class="mail-header-row"><span>Para:</span><strong>' . self::e($email['to']) . '</strong></div>'
            . '<div class="mail-header-row"><span>Asunto:</span><strong>' . self::e($email['subject']) . '</strong></div>'
            . '</div><div class="mail-window-body"><div class="mail-card">'
            . ($test ? '<p class="staff-test-banner">PRUEBA: esta solicitud viene del formulario de prueba. No es un cliente real.</p>' : '')
            . '<div class="mail-card-banner"><span class="mail-card-kicker">MENIGAR · ' . ($shipping ? 'Envío de pieza' : 'Consulta') . ' desde la web</span>'
            . '<h2>' . self::e($ref) . '</h2><p>' . $count . ($count === 1 ? ' pieza' : ' piezas') . ($vehicle !== '' ? ' · ' . self::e($vehicle) : '') . '</p></div>'
            . '<div class="mail-card-content">'
            . self::details(array_filter([
                'Recibida' => self::when((string) $row['created_at']),
                'Cliente' => self::customerType($c),
                'Vehículo' => $vehicle,
                'Llegada de la pieza' => $shipping ? $inbound : null,
                'Devolución' => $shipping ? $outbound : null,
            ], static fn($value) => $value !== null));
        foreach ($units as $idx => $u) {
            $num = $idx + 1;
            $html .= '<div class="mail-unit-box"><div class="piece-header-row"><strong>Pieza ' . $num . ' de ' . $count . ': ' . self::e($u['componentName'] ?? '') . '</strong><span class="erp-order-pill">' . self::e($ref . '-P' . $num) . '</span></div>'
                . self::details(array_filter([
                    'Fabricante' => $u['manufacturer'] ?: null,
                    'Referencia que indica el cliente' => ($u['unknownReference'] ?? false) || !$u['reference'] ? 'Sin identificar' : $u['reference'],
                    'Código de avería' => $u['dtc'] ?: null,
                    'Qué ocurre' => $u['symptoms'] ?? '',
                    'Accesorios' => $u['accessories'] ?: null,
                    'Fotos o documentos' => (string) (count($u['attachments'] ?? []) ?: 'ninguno'),
                ], static fn($value) => $value !== null))
                . '</div>';
        }
        $html .= '<div class="mail-cta-bar"><a class="staff-btn" href="' . self::e($bp) . '/equipo/solicitudes/' . self::e($ref) . '">Abrir la ficha completa</a></div>'
            . '<p class="mail-footnote">Los datos de contacto y las fotos están en la ficha, con tu usuario del equipo. Este aviso no confirma una orden de reparación ni un pago.</p>'
            . '</div></div></div></div>'
            . '<details class="mail-raw-toggle"><summary>Ver la versión en texto sin formato</summary><pre class="erp-json-box erp-email-box">' . self::e($email['body']) . '</pre></details>';
        return self::shell('Correo ' . $ref, $html, $bp, $test);
    }
}
