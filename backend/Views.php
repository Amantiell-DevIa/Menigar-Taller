<?php
declare(strict_types=1);
namespace Menigar;

/**
 * Pages of the team area (/equipo), behind the team login (Http::staff).
 *
 * One purpose per screen: the inbox answers «what is new and where is it»; a request
 * answers «who is it, what do they send, what do I do now»; the work sheet travels with
 * the piece. Plain Spanish, «laboratorio» for MENIGAR, no claims about systems that are
 * not connected. No inline styles or scripts (strict CSP): look in assets/equipo.css/.js.
 */
final class Views
{
    private const EVENT_LABELS = [
        'submitted' => 'Recibida desde la web',
        'notification_accepted_by_mta' => 'Aviso enviado por correo',
        'notification_test_spooled' => 'Aviso guardado sin enviar (prueba)',
        'reviewed' => 'Revisada',
    ];

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

    private static function madrid(string $utc): ?\DateTimeImmutable
    {
        try {
            return (new \DateTimeImmutable($utc))->setTimezone(new \DateTimeZone('Europe/Madrid'));
        } catch (\Throwable) {
            return null;
        }
    }

    /** Stored times are UTC; the team reads Madrid time. */
    public static function when(string $utc): string
    {
        return self::madrid($utc)?->format('d/m/Y H:i') ?? $utc;
    }

    /** «ahora», «hace 12 min», «hoy 09:40», «ayer 18:05» or the date. */
    public static function ago(string $utc): string
    {
        $time = self::madrid($utc);
        if (!$time) return $utc;
        $now = new \DateTimeImmutable('now', new \DateTimeZone('Europe/Madrid'));
        $seconds = $now->getTimestamp() - $time->getTimestamp();
        if ($seconds < 60) return 'ahora';
        if ($seconds < 3600) return 'hace ' . intdiv($seconds, 60) . ' min';
        if ($time->format('Y-m-d') === $now->format('Y-m-d')) return 'hoy ' . $time->format('H:i');
        if ($time->format('Y-m-d') === $now->modify('-1 day')->format('Y-m-d')) return 'ayer ' . $time->format('H:i');
        return $time->format('d/m/Y');
    }

    private static function fold(string $text): string
    {
        return strtr(mb_strtolower($text), ['á' => 'a', 'é' => 'e', 'í' => 'i', 'ó' => 'o', 'ú' => 'u', 'ü' => 'u', 'ñ' => 'n']);
    }

    /** Search in the inbox: every word must appear in the reference, the customer, the vehicle or a piece. */
    public static function matches(array $row, string $query): bool
    {
        $p = json_decode($row['payload'], true) ?: [];
        $c = $p['customer'] ?? []; $v = $p['vehicle'] ?? [];
        $text = [$row['reference'], $c['name'] ?? '', $c['contact'] ?? '', $c['email'] ?? '', $c['phone'] ?? '', preg_replace('/\D/', '', $c['phone'] ?? ''),
            $v['brand'] ?? '', $v['model'] ?? '', $v['plate'] ?? '', preg_replace('/\s/', '', $v['plate'] ?? ''), $v['vin'] ?? ''];
        foreach ($p['units'] ?? [] as $u) array_push($text, $u['componentName'] ?? '', $u['reference'] ?? '', $u['manufacturer'] ?? '', $u['dtc'] ?? '');
        $haystack = self::fold(implode(' ', $text));
        foreach (preg_split('/\s+/u', self::fold($query), -1, PREG_SPLIT_NO_EMPTY) as $word) {
            if (!str_contains($haystack, $word)) return false;
        }
        return true;
    }

    private static function customerType(array $c): string
    {
        return ($c['type'] ?? '') === 'taller' ? 'Taller o empresa' : 'Particular';
    }

    private static function icon(string $name): string
    {
        $paths = [
            'back' => '<path d="M15 18l-6-6 6-6"/>',
            'phone' => '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
            'chat' => '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5.1A8 8 0 1 1 21 12z"/>',
            'mail' => '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
            'copy' => '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
            'print' => '<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7"/>',
            'sheet' => '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>',
            'download' => '<path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/>',
            'check' => '<path d="m5 12 5 5 9-10"/>',
            'search' => '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
            'file' => '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
            'more' => '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
            'refresh' => '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>',
        ];
        return '<svg class="eq-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' . ($paths[$name] ?? '') . '</svg>';
    }

    public static function shell(string $title, string $body, string $basePath = '', bool $test = false, string $actor = '', string $active = ''): string
    {
        $bp = self::e(rtrim($basePath, '/'));
        $current = static fn(string $key): string => $active === $key ? ' aria-current="page"' : '';
        $topbar = '<header class="eq-topbar"><div class="eq-topbar-inner">'
            . '<a class="eq-brand" href="' . $bp . '/equipo/solicitudes"><img src="' . $bp . '/assets/marca/menigar-logo-1x.webp" srcset="' . $bp . '/assets/marca/menigar-logo-2x.webp 2x" width="148" height="22" alt="MENIGAR"><span>Equipo</span></a>'
            . '<nav class="eq-nav" aria-label="Zona del equipo">'
            . '<a href="' . $bp . '/equipo/solicitudes"' . $current('inbox') . '>Solicitudes</a>'
            . '<a href="' . $bp . '/solicitud.html" target="_blank" rel="noopener">Formulario del cliente</a>'
            . '</nav>'
            . ($actor !== '' ? '<span class="eq-user" title="Has entrado con este usuario">' . self::e($actor) . '</span>' : '')
            . '</div></header>';
        $banner = $test ? '<p class="staff-test-banner" role="note"><strong>Prueba.</strong> Estas solicitudes vienen del formulario de prueba. No son clientes reales.</p>' : '';

        return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="same-origin"><title>' . self::e($title) . ' · Equipo MENIGAR</title><link rel="icon" href="' . $bp . '/favicon.ico"><link rel="stylesheet" href="' . $bp . '/style.css"><link rel="stylesheet" href="' . $bp . '/assets/equipo.css"><script src="' . $bp . '/assets/equipo.js" defer></script></head>'
            . '<body class="eq-body"><a class="eq-skip" href="#contenido">Saltar al contenido</a>' . $topbar . $banner
            . '<main class="eq-main" id="contenido" tabindex="-1">' . $body . '</main><p class="eq-sr" aria-live="polite" data-live></p></body></html>';
    }

    public static function details(array $items): string
    {
        $html = '<dl class="eq-dl">';
        foreach ($items as $label => $value) $html .= '<dt>' . self::e($label) . '</dt><dd class="pre">' . self::e($value ?: 'No indicado') . '</dd>';
        return $html . '</dl>';
    }

    private static function selectOptions(array $choices, string $selected): string
    {
        $out = '';
        foreach ($choices as $key => $label) {
            $out .= '<option value="' . self::e($key) . '"' . ((string) $key === $selected ? ' selected' : '') . '>' . self::e($label) . '</option>';
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

    private static function copyButton(string $value, string $what): string
    {
        return '<button type="button" class="eq-icon-btn" data-copy="' . self::e($value) . '" aria-label="Copiar ' . self::e($what) . '" title="Copiar ' . self::e($what) . '">' . self::icon('copy') . '</button>';
    }

    /** Spanish numbers without prefix get 34, for calls and WhatsApp. */
    private static function internationalPhone(string $phone): string
    {
        $digits = preg_replace('/\D/', '', $phone);
        if (str_starts_with(trim($phone), '+')) return $digits;
        if (str_starts_with($digits, '00')) return substr($digits, 2);
        return strlen($digits) === 9 && preg_match('/^[6789]/', $digits) ? '34' . $digits : $digits;
    }

    private static function chip(string $kind, string $text): string
    {
        return '<span class="eq-chip eq-chip-' . $kind . '">' . self::e($text) . '</span>';
    }

    // ----------------------------------------------------------------- inbox

    public static function inbox(array $rows, int $page, int $found, string $basePath = '', bool $test = false, array $options = []): string
    {
        $bp = self::e(rtrim($basePath, '/'));
        $view = $options['view'] ?? 'todas';
        $query = (string) ($options['query'] ?? '');
        $counts = ($options['counts'] ?? []) + ['todas' => $found, 'sin-revisar' => 0, 'envios' => 0, 'consultas' => 0];
        $link = static function (array $params) use ($bp, $view, $query): string {
            $params += ['vista' => $view, 'q' => $query];
            $params = array_filter($params, static fn($value, $key) => $value !== '' && !($key === 'vista' && $value === 'todas') && !($key === 'pagina' && (int) $value === 1), ARRAY_FILTER_USE_BOTH);
            return $bp . '/equipo/solicitudes' . ($params ? '?' . self::e(http_build_query($params)) : '');
        };
        $names = ['todas' => 'Todas', 'sin-revisar' => 'Sin revisar', 'envios' => 'Envíos', 'consultas' => 'Consultas'];

        $html = '<header class="eq-pagehead"><div>'
            . '<h1>Solicitudes</h1>'
            . '<p class="eq-lede">' . ($counts['sin-revisar'] ? '<strong>' . $counts['sin-revisar'] . ' sin revisar</strong> · ' : 'Todas revisadas · ') . $counts['todas'] . ' en total</p>'
            . '</div><a class="eq-btn eq-btn-quiet" href="' . $link([]) . '">' . self::icon('refresh') . 'Actualizar</a></header>'
            . '<div class="eq-toolbar">'
            . '<form class="eq-search" method="get" action="' . $bp . '/equipo/solicitudes" role="search">'
            . ($view !== 'todas' ? '<input type="hidden" name="vista" value="' . self::e($view) . '">' : '')
            . '<label class="eq-sr" for="eq-q">Buscar solicitudes</label>' . self::icon('search')
            . '<input id="eq-q" type="search" name="q" value="' . self::e($query) . '" placeholder="Cliente, matrícula, pieza…" autocomplete="off" data-search>'
            . '<button class="eq-btn" type="submit">Buscar</button></form>'
            . '<nav class="eq-segments" aria-label="Filtrar solicitudes">';
        foreach ($names as $key => $label) {
            $html .= '<a href="' . $link(['vista' => $key, 'pagina' => 1]) . '"' . ($view === $key ? ' aria-current="true"' : '') . '>' . $label . ' <span>' . (int) ($counts[$key] ?? 0) . '</span></a>';
        }
        $html .= '</nav></div>';

        if ($query !== '') {
            $html .= '<p class="eq-resultnote">' . $found . ($found === 1 ? ' resultado' : ' resultados') . ' para «' . self::e($query) . '» · <a href="' . $link(['q' => '', 'pagina' => 1]) . '">Quitar la búsqueda</a></p>';
        }

        if (!$rows) {
            $empty = $query !== '' ? ['Nada coincide con «' . $query . '».', 'Prueba con menos palabras, la matrícula o el final de la referencia.']
                : ($view === 'sin-revisar' ? ['No queda nada sin revisar.', 'Las solicitudes nuevas aparecerán aquí.']
                : ['Todavía no hay solicitudes.', 'Envía una desde el formulario del cliente para ver cómo llega.']);
            return self::shell('Solicitudes', $html . '<div class="eq-empty"><p class="eq-empty-title">' . self::e($empty[0]) . '</p><p>' . self::e($empty[1]) . '</p></div>', $basePath, $test, (string) ($options['actor'] ?? ''), 'inbox');
        }

        $mailProblems = ['retry' => 'Correo pendiente de reintento', 'uncertain' => 'Comprobar si llegó el correo', 'failed' => 'El correo no se pudo enviar'];
        $html .= '<ol class="eq-list">';
        foreach ($rows as $row) {
            $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
            $ref = (string) $row['reference'];
            $shipping = ($p['intent'] ?? '') === 'repair';
            $units = $p['units'] ?? [];
            $pieces = implode(' · ', array_map(fn($u) => $u['componentName'] ?? '', $units));
            $files = array_sum(array_map(fn($u) => count($u['attachments'] ?? []), $units));
            $vehicle = trim(($p['vehicle']['brand'] ?? '') . ' ' . (($p['vehicle']['modelUnknown'] ?? false) ? '(modelo por identificar)' : ($p['vehicle']['model'] ?? '')));
            $state = $row['reviewed_at'] ? 'Revisada' . (!empty($row['reviewed_by']) ? ' · ' . $row['reviewed_by'] : '') : 'Sin revisar';
            $html .= '<li class="eq-row' . ($row['reviewed_at'] ? '' : ' is-new') . '"><a class="eq-row-link" href="' . $bp . '/equipo/solicitudes/' . self::e($ref) . '">'
                . '<span class="eq-row-dot" aria-hidden="true"></span>'
                . '<span class="eq-row-main"><span class="eq-row-title">' . self::e($p['customer']['name'] ?? '') . '</span>'
                . '<span class="eq-row-sub">' . self::e($vehicle) . '</span>'
                . '<span class="eq-row-pieces">' . count($units) . (count($units) === 1 ? ' pieza: ' : ' piezas: ') . self::e($pieces) . ($files ? ' · ' . $files . ($files === 1 ? ' archivo' : ' archivos') : '') . '</span></span>'
                . '<span class="eq-row-meta">' . self::chip($shipping ? 'ship' : 'consult', $shipping ? 'Envío' : 'Consulta')
                . '<span class="eq-mono eq-row-ref">' . self::e($ref) . '</span></span>'
                . '<span class="eq-row-side"><time datetime="' . self::e($row['created_at']) . '" title="' . self::e(self::when((string) $row['created_at'])) . '">' . self::e(self::ago((string) $row['created_at'])) . '</time>'
                . '<span class="eq-row-state">' . self::e($state) . '</span>'
                . (isset($mailProblems[$row['notification_state'] ?? '']) ? '<span class="eq-row-warn">' . $mailProblems[$row['notification_state']] . '</span>' : '')
                . '</span></a></li>';
        }
        $html .= '</ol>';
        $pages = (int) ceil($found / 50);
        if ($pages > 1) {
            $html .= '<nav class="eq-pager" aria-label="Páginas">'
                . ($page > 1 ? '<a href="' . $link(['pagina' => $page - 1]) . '">← Anteriores</a>' : '<span></span>')
                . '<span>Página ' . $page . ' de ' . $pages . '</span>'
                . ($page < $pages ? '<a href="' . $link(['pagina' => $page + 1]) . '">Siguientes →</a>' : '<span></span>') . '</nav>';
        }
        return self::shell('Solicitudes', $html, $basePath, $test, (string) ($options['actor'] ?? ''), 'inbox');
    }

    // --------------------------------------------------------------- request

    private static function eventLabel(array $event): string
    {
        if (preg_match('/^unit_updated_P(\d+)$/', $event['kind'], $m)) return 'P' . $m[1] . ' actualizada';
        if (preg_match('/^ref_updated_P(\d+)$/', $event['kind'], $m)) return 'Referencia de P' . $m[1] . ' corregida';
        return self::EVENT_LABELS[$event['kind']] ?? $event['kind'];
    }

    public static function staffRequest(array $row, string $csrf, string $mode, array $units = [], string $basePath = '', int $savedUnit = 0, array $events = [], string $actor = ''): string
    {
        $bp = self::e(rtrim($basePath, '/'));
        $ref = (string) $row['reference'];
        $base = $bp . '/equipo/solicitudes/' . self::e($ref);
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $p['customer'];
        $v = $p['vehicle'];
        $shipping = $p['intent'] === 'repair';
        $unitCount = count($p['units']);
        $byUnit = [];
        foreach ($units['repair_orders'] ?? [] as $unitData) $byUnit[(int) ($unitData['vals']['x_unit_number'] ?? 0)] = $unitData;
        $lastByUnit = []; $reviewedBy = '';
        foreach ($events as $event) {
            if (preg_match('/^(?:unit|ref)_updated_P(\d+)$/', $event['kind'], $m)) $lastByUnit[(int) $m[1]] = $event;
            if ($event['kind'] === 'reviewed') $reviewedBy = $event['actor'];
        }

        // Header: who, what, and the one action that moves the request on.
        $html = '<a class="eq-back" href="' . $bp . '/equipo/solicitudes">' . self::icon('back') . 'Solicitudes</a>';
        $html .= '<header class="eq-head"><div class="eq-head-main">'
            . '<p class="eq-chips">' . self::chip($shipping ? 'ship' : 'consult', $shipping ? 'Envío de pieza' : 'Consulta')
            . self::chip('plain', $unitCount . ($unitCount === 1 ? ' pieza' : ' piezas'))
            . ($row['reviewed_at'] ? self::chip('done', 'Revisada') : self::chip('new', 'Sin revisar')) . '</p>'
            . '<h1>' . self::e($c['name']) . '</h1>'
            . '<p class="eq-head-meta"><span class="eq-mono">' . self::e($ref) . '</span>' . self::copyButton($ref, 'la referencia') . '</p>'
            . '<p class="eq-head-meta"><span>Recibida <time datetime="' . self::e($row['created_at']) . '" title="' . self::e(self::when((string) $row['created_at'])) . '">' . self::e(self::ago((string) $row['created_at'])) . '</time></span>'
            . '<span class="eq-dot" aria-hidden="true">·</span><span>' . self::e(self::vehicleLabel($v)) . '</span></p>'
            . '</div><div class="eq-head-actions">';
        if ($row['reviewed_at']) {
            $html .= '<p class="eq-reviewed">' . self::icon('check') . 'Revisada' . ($reviewedBy ? ' por ' . self::e($reviewedBy) : '') . ' · ' . self::e(self::when((string) $row['reviewed_at'])) . '</p>';
        } else {
            $html .= '<form method="post" action="' . $base . '/revisada"><input type="hidden" name="csrf" value="' . self::e($csrf) . '"><button class="eq-btn eq-btn-primary" type="submit">' . self::icon('check') . 'Marcar como revisada</button></form>';
        }
        $html .= '<a class="eq-btn" href="' . $base . '/hoja-tecnica">' . self::icon('sheet') . 'Hojas de trabajo</a>'
            . '<details class="eq-menu"><summary class="eq-btn" aria-label="Más acciones">' . self::icon('more') . '<span class="eq-menu-label">Más</span></summary><div class="eq-menu-list">'
            . '<a href="' . $base . '/correo">' . self::icon('mail') . 'Ver el correo de aviso</a>'
            . '<a href="' . $base . '/datos.csv">' . self::icon('download') . 'Descargar los datos (CSV)</a>'
            . '<button type="button" data-print>' . self::icon('print') . 'Imprimir esta ficha</button>'
            . '</div></details></div></header>';

        // Side column: contact first, because the next step is usually a call.
        $phone = (string) ($c['phone'] ?? ''); $email = (string) ($c['email'] ?? '');
        $intl = self::internationalPhone($phone);
        $person = $c['contact'] ?: $c['name'];
        $contact = static fn(string $id, string $where): string => '<section class="eq-card eq-contact ' . $where . '" aria-labelledby="' . $id . '"><h2 id="' . $id . '">Contacto</h2>'
            . '<p class="eq-contact-name">' . self::e($person) . '</p>'
            . '<p class="eq-muted">' . self::e(self::customerType($c)) . ($person !== $c['name'] ? ' · ' . self::e($c['name']) : '') . '</p>'
            . '<ul class="eq-contact-lines">'
            . '<li><span class="eq-contact-value">' . self::e($phone) . '</span>' . self::copyButton($phone, 'el teléfono') . '</li>'
            . '<li><span class="eq-contact-value">' . self::e($email) . '</span>' . self::copyButton($email, 'el correo') . '</li></ul>'
            . '<div class="eq-contact-actions">'
            . '<a class="eq-btn" href="tel:+' . self::e($intl) . '">' . self::icon('phone') . 'Llamar</a>'
            . '<a class="eq-btn" href="https://wa.me/' . self::e($intl) . '" target="_blank" rel="noopener noreferrer">' . self::icon('chat') . 'WhatsApp</a>'
            . '<a class="eq-btn" href="mailto:' . self::e($email) . '?subject=' . rawurlencode('MENIGAR · ' . $ref) . '">' . self::icon('mail') . 'Correo</a>'
            . '</div></section>';

        $address = self::addressLabel($c);
        $returnAddress = $c['returnDifferent'] ? self::addressLabel($c, true) : $address;
        [$inbound, $outbound] = self::logistics($c);
        if ($shipping) {
            $request = ['Qué pidió' => 'Preparar solicitud de envío', 'Llegada de la pieza' => $inbound, 'Devolución' => $outbound, 'Dirección' => $address, 'Devolver a' => $returnAddress, 'NIF/CIF' => $c['taxId']];
        } else {
            $request = ['Qué pidió' => 'Consultar mi pieza (orientación antes de enviarla)'];
            if ($address !== '') $request['Dirección'] = $address;
            if ($c['taxId']) $request['NIF/CIF'] = $c['taxId'];
        }
        // Phones show the contact first; wide screens keep it at the top of the side column.
        $side = $contact('eq-contacto', 'eq-only-wide')
            . '<section class="eq-card" aria-labelledby="eq-pedido"><h2 id="eq-pedido">' . ($shipping ? 'Envío y devolución' : 'Consulta') . '</h2>' . self::details($request) . '</section>'
            . '<section class="eq-card" aria-labelledby="eq-vehiculo"><h2 id="eq-vehiculo">Vehículo</h2>' . self::details([
                'Vehículo' => self::vehicleLabel($v),
                'Matrícula' => $v['plate'] ?: 'No indicada',
                'Bastidor (VIN)' => $v['vin'] ?: 'No indicado',
                'Año y kilómetros' => ($v['year'] ?: '—') . ' / ' . ($v['km'] ?: '—'),
                'Lo que buscó en la web' => $p['contextQuery'] ?: 'Entró directamente al formulario',
            ]) . '</section>';

        $history = '<ol class="eq-timeline">';
        foreach (array_reverse($events) as $event) {
            $who = in_array($event['actor'], ['customer', 'worker'], true) ? '' : ' · ' . self::e($event['actor']);
            $history .= '<li><span>' . self::e(self::eventLabel($event)) . $who . '</span><time datetime="' . self::e($event['created_at']) . '">' . self::e(self::when((string) $event['created_at'])) . '</time></li>';
        }
        $side .= '<section class="eq-card" aria-labelledby="eq-historial"><h2 id="eq-historial">Historial</h2>' . ($events ? $history . '</ol>' : '<p class="eq-muted">Sin movimientos.</p>') . '</section>'
            . '<section class="eq-card eq-card-quiet" id="exportar" aria-labelledby="eq-gestion"><h2 id="eq-gestion">Programa de gestión</h2>'
            . '<p>Esta prueba no está conectada a ningún programa: hoy los datos se teclean en MotorWin. Para comprobar si se pueden importar sin teclear, descarga el archivo (una fila por pieza).</p>'
            . '<a class="eq-btn" href="' . $base . '/datos.csv">' . self::icon('download') . 'Descargar CSV</a></section>';

        // Main column: one card per piece.
        $main = $contact('eq-contacto-movil', 'eq-only-narrow');
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
            $receptionLabel = OdooConnector::RECEPTION_STATES[$reception] ?? $reception;

            $client = ['Referencia que indica' => $declared];
            if ($changed) $client['Referencia comprobada'] = $confirmed;
            $client += ['Fabricante' => $unit['manufacturer'] ?: 'Por comprobar en la etiqueta', 'Código de avería' => $unit['dtc'] ?: 'No indicado', 'Accesorios' => $unit['accessories'] ?: 'Solo la pieza'];
            $otherVehicle = trim($unit['vehicleBrand'] . ' ' . $unit['vehicleModel']);
            if ($otherVehicle !== '') $client['Vehículo de esta pieza'] = $otherVehicle;

            $main .= '<section class="eq-card eq-piece" id="unidad-' . $num . '" aria-labelledby="eq-p' . $num . '">'
                . '<header class="eq-piece-head"><span class="eq-piece-code" aria-hidden="true">P' . $num . '</span>'
                . '<div class="eq-piece-title"><h2 id="eq-p' . $num . '">' . self::e($unit['componentName']) . '</h2><p class="eq-mono eq-muted">' . self::e($code) . '</p></div>'
                . '<span class="eq-state' . ($reception === 'pendiente_llegada' ? '' : ' is-in') . '">' . self::e($receptionLabel) . '</span></header>'
                . '<blockquote class="eq-quote"><p class="eq-quote-label">Qué le ocurre, según el cliente</p><p class="pre">' . self::e($unit['symptoms']) . '</p></blockquote>'
                . self::details($client);

            if (!empty($unit['attachments'])) {
                $main .= '<ul class="eq-files" aria-label="Fotos y documentos de P' . $num . '">';
                foreach ($unit['attachments'] as $i => $file) {
                    $url = $base . '/archivo/' . self::e($file['id']);
                    if (str_starts_with((string) ($file['mime'] ?? ''), 'image/')) {
                        $main .= '<li><a class="eq-thumb" href="' . $url . '?ver=1" target="_blank" rel="noopener"><img src="' . $url . '?ver=1" alt="Foto ' . ($i + 1) . ' de P' . $num . ': ' . self::e($file['name']) . '" loading="lazy" decoding="async"></a></li>';
                    } else {
                        $main .= '<li><a class="eq-filechip" href="' . $url . '">' . self::icon('file') . '<span>' . self::e($file['name']) . '</span></a></li>';
                    }
                }
                $main .= '</ul>';
            }

            if ($vals) {
                $last = $lastByUnit[$num] ?? null;
                $main .= '<form method="post" action="' . $base . '/unidad/' . $num . '" class="eq-form" data-unsaved>'
                    . '<h3>Recepción en el laboratorio</h3>'
                    . '<input type="hidden" name="csrf" value="' . self::e($csrf) . '">'
                    . '<div class="eq-fields">'
                    . '<label class="eq-field"><span>Llegada y embalaje</span><select name="reception_state">' . self::selectOptions(OdooConnector::RECEPTION_STATES, $reception) . '</select></label>'
                    . '<label class="eq-field"><span>Referencia comprobada en la etiqueta</span><input type="text" name="confirmed_reference" value="' . self::e($confirmed) . '" maxlength="120" autocomplete="off"></label>'
                    . '<label class="eq-field"><span>Estado en el laboratorio</span><select name="technical_state">' . self::selectOptions(OdooConnector::TECHNICAL_STATES, $technical) . '</select></label>'
                    . '<label class="eq-field"><span>Presupuesto y cobro</span><select name="commercial_state">' . self::selectOptions(OdooConnector::COMMERCIAL_STATES, $commercial) . '</select></label>'
                    . '<label class="eq-field"><span>Importe del presupuesto</span><input type="text" name="estimated_eur" value="' . self::e((string) ($vals['x_estimated_eur'] ?? '')) . '" placeholder="Ej. 240 € + IVA" maxlength="40" autocomplete="off"></label>'
                    . '<label class="eq-field"><span>Ticket del banco de pruebas</span><input type="text" name="bench_ticket" value="' . self::e((string) ($vals['x_bench_ticket'] ?? '')) . '" maxlength="80" autocomplete="off"></label>'
                    . '<label class="eq-field eq-field-wide"><span>Qué llegó realmente en el paquete</span><input type="text" name="reception_notes" value="' . self::e((string) ($vals['x_reception_notes'] ?? '')) . '" placeholder="Ej. Caja bien, llega con soporte y conector" maxlength="500" autocomplete="off"></label>'
                    . '<label class="eq-field eq-field-wide"><span>Notas del técnico</span><textarea name="technician_notes" rows="3" maxlength="1000">' . self::e((string) ($vals['internal_notes'] ?? '')) . '</textarea></label>'
                    . '</div><div class="eq-form-foot" id="unidad-' . $num . '-guardar">'
                    . '<button type="submit" class="eq-btn eq-btn-primary">Guardar P' . $num . '</button>'
                    . ($savedUnit === $num ? '<span class="eq-saved" role="status">' . self::icon('check') . 'Guardado. Lo que escribió el cliente no cambia.</span>' : '')
                    . '<span class="eq-dirty-note">Hay cambios sin guardar</span>'
                    . ($last ? '<span class="eq-muted eq-last">Último cambio: ' . self::e($last['actor']) . ' · ' . self::e(self::when((string) $last['created_at'])) . '</span>' : '')
                    . '<a class="eq-link" href="' . $base . '/hoja-tecnica#orden-' . $num . '">Hoja de trabajo de P' . $num . '</a>'
                    . '</div></form>';
            }
            $main .= '</section>';
        }

        $html .= '<div class="eq-layout"><div class="eq-col-main">' . $main . '</div><aside class="eq-col-side" aria-label="Datos del cliente">' . $side . '</aside></div>';
        return self::shell($ref . ' · ' . $c['name'], $html, $basePath, $mode !== 'production', $actor);
    }

    // ------------------------------------------------------------ work sheet

    /** One printable page per piece, to travel with it in its tray. */
    public static function workSheet(array $row, array $units, string $basePath = '', bool $test = false, string $actor = ''): string
    {
        $bp = self::e(rtrim($basePath, '/'));
        $ref = (string) $row['reference'];
        $p = json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $c = $p['customer'];
        $v = $p['vehicle'];
        $address = self::addressLabel($c);
        $returnAddress = $c['returnDifferent'] ? self::addressLabel($c, true) : $address;
        $total = count($units['repair_orders'] ?? []);
        [, $outbound] = self::logistics($c);

        $html = '<div class="eq-sheet-tools"><a class="eq-back" href="' . $bp . '/equipo/solicitudes/' . self::e($ref) . '">' . self::icon('back') . 'Volver a la solicitud</a>'
            . '<p class="eq-muted">Una hoja por pieza, en A4 y en blanco y negro.</p>'
            . '<button type="button" class="eq-btn eq-btn-primary" data-print>' . self::icon('print') . 'Imprimir ' . ($total === 1 ? 'la hoja' : 'las ' . $total . ' hojas') . '</button></div>';

        foreach ($units['repair_orders'] ?? [] as $idx => $unitData) {
            $u = $unitData['vals'];
            $num = $idx + 1;
            $html .= '<article class="eq-sheet" id="orden-' . $num . '">'
                . '<header class="eq-sheet-head"><div>'
                . '<p class="eq-sheet-brand">MENIGAR · Hoja de trabajo' . ($test ? ' · PRUEBA' : '') . '</p>'
                . '<h1>' . self::e($u['x_component_family']) . '</h1>'
                . '<p class="eq-mono">' . self::e($u['name']) . '</p>'
                . '<p>Recibida el ' . self::e(self::when((string) $row['created_at'])) . ' · ' . ($u['x_intent'] === 'envio_reparacion' ? 'Envío de pieza' : 'Consulta') . '</p>'
                . '</div><div class="eq-sheet-code"><span>Pieza</span><strong>P' . $num . '</strong><small>de ' . $total . '</small></div></header>'
                . '<div class="eq-sheet-grid">'
                . '<section><h2>Cliente</h2>' . self::details([
                    'Cliente' => $c['name'] . ' (' . self::customerType($c) . ')',
                    'Contacto' => $c['contact'] ?: $c['name'],
                    'Teléfono' => $c['phone'],
                    'Correo' => $c['email'],
                    'NIF/CIF' => $c['taxId'] ?: 'Pendiente',
                    'Devolución' => $outbound . ($returnAddress ? ' · ' . $returnAddress : ''),
                ]) . '</section>'
                . '<section><h2>Vehículo</h2>' . self::details([
                    'Marca y modelo' => trim(($u['x_vehicle_brand'] ?: $v['brand']) . ' ' . ($u['x_vehicle_model'] ?: '')),
                    'Matrícula' => $v['plate'] ?: 'No indicada',
                    'Bastidor (VIN)' => $v['vin'] ?: 'No indicado',
                    'Año y kilómetros' => ($v['year'] ?: '-') . ' / ' . ($v['km'] ?: '-'),
                ]) . '</section></div>'
                . '<section><h2>La pieza</h2>' . self::details([
                    'Fabricante' => $u['x_manufacturer'] ?: 'Por comprobar en la etiqueta',
                    'Referencia que indicó el cliente' => $u['x_declared_reference'],
                    'Referencia comprobada' => $u['x_confirmed_reference'],
                    'Código de avería' => $u['x_dtc_codes'] ?: 'No indicado',
                    'Accesorios declarados' => $u['x_accessories_declared'] ?: 'Solo la pieza',
                ]) . '<p class="eq-sheet-quote"><strong>Qué le ocurre, según el cliente:</strong> ' . self::e($u['description']) . '</p></section>'
                . '<section><h2>Recepción</h2><ul class="eq-checks">'
                . '<li>Llega la caja</li><li>Embalaje correcto</li><li>Accesorios completos</li><li>Referencia comprobada en la etiqueta</li></ul>'
                . '<p class="eq-sheet-line"><span>Qué llegó en el paquete</span>' . self::e($u['x_reception_notes'] ?: '') . '</p></section>'
                . '<section><h2>Laboratorio y salida</h2>' . self::details([
                    'Estado' => OdooConnector::TECHNICAL_STATES[$u['x_technical_state']] ?? $u['x_technical_state'],
                    'Presupuesto y cobro' => (OdooConnector::COMMERCIAL_STATES[$u['x_commercial_state']] ?? $u['x_commercial_state']) . ($u['x_estimated_eur'] ? ' · ' . $u['x_estimated_eur'] : ''),
                ])
                . '<p class="eq-sheet-line"><span>Ticket del banco de pruebas</span>' . self::e($u['x_bench_ticket'] ?: '') . '</p>'
                . '<p class="eq-sheet-line eq-sheet-notes"><span>Notas del técnico</span>' . self::e($u['internal_notes'] ?: '') . '</p>'
                . '<div class="eq-sheet-sign"><p><span>Técnico</span></p><p><span>Fecha de salida</span></p></div></section>'
                . '</article>';
        }
        return self::shell('Hojas de trabajo ' . $ref, $html, $basePath, $test, $actor);
    }

    // ------------------------------------------------------------ email view

    /** The notice as the team receives it. The real email uses inline styles, which this page's CSP blocks, so it is rebuilt with classes. */
    public static function emailPreview(array $row, array $email, ?array $notif, string $basePath = '', bool $test = false, string $actor = ''): string
    {
        $bp = self::e(rtrim($basePath, '/'));
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

        $html = '<a class="eq-back" href="' . $bp . '/equipo/solicitudes/' . self::e($ref) . '">' . self::icon('back') . 'Volver a la solicitud</a>'
            . '<header class="eq-pagehead"><div><h1>Así llega el correo de aviso</h1>'
            . '<p class="eq-lede">' . self::chip(in_array($notif['state'] ?? '', ['failed', 'uncertain', 'retry'], true) ? 'warn' : 'done', $state) . ' Se envía a ' . self::e($email['to']) . '. No lleva datos de contacto del cliente: están en la ficha, con usuario del equipo.</p></div></header>'
            . '<article class="eq-mail"><dl class="eq-mail-head">'
            . '<dt>De</dt><dd>' . self::e($email['from']) . '</dd><dt>Para</dt><dd>' . self::e($email['to']) . '</dd><dt>Asunto</dt><dd><strong>' . self::e($email['subject']) . '</strong></dd></dl>'
            . '<div class="eq-mail-body">'
            . ($test ? '<p class="staff-test-banner">PRUEBA: esta solicitud viene del formulario de prueba. No es un cliente real.</p>' : '')
            . '<div class="eq-mail-banner"><p>MENIGAR · ' . ($shipping ? 'Envío de pieza' : 'Consulta') . ' desde la web</p><h2>' . self::e($ref) . '</h2><p>' . $count . ($count === 1 ? ' pieza' : ' piezas') . ($vehicle !== '' ? ' · ' . self::e($vehicle) : '') . '</p></div>'
            . self::details(array_filter([
                'Recibida' => self::when((string) $row['created_at']),
                'Cliente' => self::customerType($c),
                'Vehículo' => $vehicle,
                'Llegada de la pieza' => $shipping ? $inbound : null,
                'Devolución' => $shipping ? $outbound : null,
            ], static fn($value) => $value !== null));
        foreach ($units as $idx => $u) {
            $num = $idx + 1;
            $html .= '<section class="eq-mail-piece"><h3>Pieza ' . $num . ' de ' . $count . ': ' . self::e($u['componentName'] ?? '') . ' <span class="eq-mono eq-muted">' . self::e($ref . '-P' . $num) . '</span></h3>'
                . self::details(array_filter([
                    'Fabricante' => $u['manufacturer'] ?: null,
                    'Referencia que indica el cliente' => ($u['unknownReference'] ?? false) || !$u['reference'] ? 'Sin identificar' : $u['reference'],
                    'Código de avería' => $u['dtc'] ?: null,
                    'Qué ocurre' => $u['symptoms'] ?? '',
                    'Accesorios' => $u['accessories'] ?: null,
                    'Fotos o documentos' => (string) (count($u['attachments'] ?? []) ?: 'ninguno'),
                ], static fn($value) => $value !== null))
                . '</section>';
        }
        $html .= '<p><a class="eq-btn eq-btn-primary" href="' . $bp . '/equipo/solicitudes/' . self::e($ref) . '">Abrir la ficha completa</a></p>'
            . '<p class="eq-muted">Los datos de contacto y las fotos están en la ficha, con tu usuario del equipo. Este aviso no confirma una orden de reparación ni un pago.</p>'
            . '</div></article>'
            . '<details class="eq-raw"><summary>Ver la versión en texto sin formato</summary><pre>' . self::e($email['body']) . '</pre></details>';
        return self::shell('Correo ' . $ref, $html, $basePath, $test, $actor);
    }
}
