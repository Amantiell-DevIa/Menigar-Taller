<?php
declare(strict_types=1);

namespace Menigar;

use PDO;
use Throwable;

/**
 * Recepción por pieza y exportación de datos. NO se conecta a Odoo ni a MotorWin.
 *
 * - Una pieza = una unidad con su código (SOL-...-P1, SOL-...-P2).
 * - Guarda aparte la referencia que declara el cliente y la que confirma el técnico.
 * - Separa tres estados: llegada y embalaje, estado técnico y estado comercial o cobro
 *   (sectores 4 a 7 del manual de procesos).
 * - Prepara un CSV por solicitud para importarlo en el programa de gestión que se elija.
 *   Los nombres internos con «odoo» describen el formato del que parte la exportación,
 *   no una conexión: esa decisión (MotorWin u Odoo) sigue pendiente (plan general O04).
 */
final class OdooConnector
{
    public const RECEPTION_STATES = [
        'pendiente_llegada' => 'Pendiente de llegada física',
        'recibido_ok' => 'Paquete recibido · Embalaje correcto',
        'recibido_embalaje_danado' => 'Paquete recibido · Embalaje con daños',
        'recibido_faltan_accesorios' => 'Paquete recibido · Faltan accesorios declarados',
    ];

    public const TECHNICAL_STATES = [
        'pendiente_diagnostico' => 'En cola de diagnóstico',
        'en_reparacion' => 'En reparación (laboratorio)',
        'reparado_probado' => 'Reparada y comprobada en banco',
        'intercambio' => 'Solución por intercambio / recambio',
        'irreparable' => 'Irreparable / Devolución',
    ];

    public const COMMERCIAL_STATES = [
        'pendiente_presupuesto' => 'Pendiente de valorar presupuesto',
        'reparacion_adelantada' => 'Reparando antes de que acepte el presupuesto',
        'presupuesto_enviado' => 'Presupuesto enviado al cliente',
        'presupuesto_aceptado' => 'Presupuesto aceptado (pendiente cobro)',
        'pagado_verificado' => 'Cobro comprobado · Puede salir por MRW',
        'contrarreembolso_autorizado' => 'Contrarreembolso autorizado por Silvia o José Luis',
    ];

    public function __construct(private readonly Intake $intake)
    {
        $this->initSchema();
    }

    private function initSchema(): void
    {
        $this->intake->db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS workshop_units (
    unit_reference TEXT PRIMARY KEY,
    request_reference TEXT NOT NULL REFERENCES requests(reference),
    unit_number INTEGER NOT NULL,
    declared_reference TEXT NOT NULL,
    confirmed_reference TEXT NOT NULL DEFAULT '',
    reference_updated_by TEXT NOT NULL DEFAULT '',
    reference_updated_at TEXT NOT NULL DEFAULT '',
    reception_state TEXT NOT NULL DEFAULT 'pendiente_llegada',
    reception_notes TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    technical_state TEXT NOT NULL DEFAULT 'pendiente_diagnostico',
    commercial_state TEXT NOT NULL DEFAULT 'pendiente_presupuesto',
    estimated_eur TEXT NOT NULL DEFAULT '',
    bench_ticket TEXT NOT NULL DEFAULT '',
    technician_notes TEXT NOT NULL DEFAULT '',
    odoo_order_id INTEGER,
    odoo_synced_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
SQL);
    }

    public function ensureUnitsForRequest(array $row): array
    {
        $reference = (string) $row['reference'];
        $payload = json_decode((string) $row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $units = $payload['units'] ?? [];
        $now = $this->intake->now();

        foreach ($units as $idx => $unit) {
            $num = $idx + 1;
            $unitRef = $reference . '-P' . $num;
            $declared = ($unit['unknownReference'] ?? false)
                ? 'Sin identificar'
                : (string) ($unit['reference'] ?: 'No indicada');

            $existing = $this->intake->one('SELECT unit_reference FROM workshop_units WHERE unit_reference=?', [$unitRef]);
            if (!$existing) {
                $this->intake->execute(
                    'INSERT INTO workshop_units(unit_reference,request_reference,unit_number,declared_reference,confirmed_reference,odoo_order_id,odoo_synced_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                    [$unitRef, $reference, $num, $declared, $declared, 1081000 + (crc32($unitRef) % 9000), $now, $now]
                );
            }
        }

        $stmt = $this->intake->db->prepare('SELECT * FROM workshop_units WHERE request_reference=? ORDER BY unit_number ASC');
        $stmt->execute([$reference]);
        $rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
        $byNum = [];
        foreach ($rows as $r) {
            $byNum[(int) $r['unit_number']] = $r;
        }
        return $byNum;
    }

    public function updateUnit(string $requestReference, int $unitNumber, array $input, string $actor): void
    {
        $row = $this->intake->byReference($requestReference);
        $units = $this->ensureUnitsForRequest($row);
        if (!isset($units[$unitNumber])) {
            throw new HttpError(404, 'Unidad no encontrada en la solicitud.');
        }
        $current = $units[$unitNumber];
        $unitRef = $current['unit_reference'];
        $now = $this->intake->now();

        $confirmedRef = trim((string) ($input['confirmed_reference'] ?? $current['confirmed_reference']));
        $refBy = $current['reference_updated_by'];
        $refAt = $current['reference_updated_at'];
        if ($confirmedRef !== $current['confirmed_reference']) {
            $refBy = $actor;
            $refAt = $now;
            $this->intake->execute(
                'INSERT INTO events(request_reference,kind,actor,created_at) VALUES (?,?,?,?)',
                [$requestReference, 'ref_updated_P' . $unitNumber, $actor, $now]
            );
        }

        $receptionState = (string) ($input['reception_state'] ?? $current['reception_state']);
        if (!isset(self::RECEPTION_STATES[$receptionState])) {
            $receptionState = $current['reception_state'];
        }
        $receivedAt = $current['received_at'];
        if ($receptionState !== 'pendiente_llegada' && !$receivedAt) {
            $receivedAt = $now;
        } elseif ($receptionState === 'pendiente_llegada') {
            $receivedAt = '';
        }

        $technicalState = (string) ($input['technical_state'] ?? $current['technical_state']);
        if (!isset(self::TECHNICAL_STATES[$technicalState])) {
            $technicalState = $current['technical_state'];
        }

        $commercialState = (string) ($input['commercial_state'] ?? $current['commercial_state']);
        if (!isset(self::COMMERCIAL_STATES[$commercialState])) {
            $commercialState = $current['commercial_state'];
        }

        $receptionNotes = mb_substr(trim((string) ($input['reception_notes'] ?? $current['reception_notes'])), 0, 500);
        $estimatedEur = mb_substr(trim((string) ($input['estimated_eur'] ?? $current['estimated_eur'])), 0, 40);
        $benchTicket = mb_substr(trim((string) ($input['bench_ticket'] ?? $current['bench_ticket'])), 0, 80);
        $techNotes = mb_substr(trim((string) ($input['technician_notes'] ?? $current['technician_notes'])), 0, 1000);

        $this->intake->execute(
            'INSERT INTO events(request_reference,kind,actor,created_at) VALUES (?,?,?,?)',
            [$requestReference, 'unit_updated_P' . $unitNumber, $actor, $now]
        );
        $this->intake->execute(
            'UPDATE workshop_units SET confirmed_reference=?, reference_updated_by=?, reference_updated_at=?, reception_state=?, reception_notes=?, received_at=?, technical_state=?, commercial_state=?, estimated_eur=?, bench_ticket=?, technician_notes=?, odoo_synced_at=?, updated_at=? WHERE unit_reference=?',
            [$confirmedRef, $refBy, $refAt, $receptionState, $receptionNotes, $receivedAt, $technicalState, $commercialState, $estimatedEur, $benchTicket, $techNotes, $now, $now, $unitRef]
        );
    }

    /**
     * Genera la estructura completa lista para Odoo ERP (res.partner + fleet.vehicle + N x repair.order + ir.attachment)
     */
    public function buildOdooPayload(array $row): array
    {
        $payload = json_decode((string) $row['payload'], true, 512, JSON_THROW_ON_ERROR);
        $customer = $payload['customer'] ?? [];
        $vehicle = $payload['vehicle'] ?? [];
        $units = $payload['units'] ?? [];
        $workshopUnits = $this->ensureUnitsForRequest($row);

        $partner = [
            'model' => 'res.partner',
            'vals' => [
                'name' => $customer['name'] ?? '',
                'company_type' => ($customer['type'] ?? '') === 'taller' ? 'company' : 'person',
                'vat' => $customer['taxId'] ?? '',
                'phone' => $customer['phone'] ?? '',
                'email' => $customer['email'] ?? '',
                'street' => $customer['address'] ?? '',
                'zip' => $customer['postalCode'] ?? '',
                'city' => $customer['city'] ?? '',
                'state_name' => $customer['province'] ?? '',
                'country_name' => $customer['country'] ?? 'España',
                'x_contact_person' => $customer['contact'] ?? '',
                'x_menigar_customer_type' => $customer['type'] ?? 'particular',
            ],
        ];

        if (!empty($customer['returnDifferent'])) {
            $partner['delivery_address'] = [
                'model' => 'res.partner',
                'vals' => [
                    'type' => 'delivery',
                    'name' => ($customer['name'] ?? '') . ' (Dirección de devolución)',
                    'street' => $customer['returnAddress'] ?? '',
                    'zip' => $customer['returnPostalCode'] ?? '',
                    'city' => $customer['returnCity'] ?? '',
                    'country_name' => $customer['returnCountry'] ?? 'España',
                ],
            ];
        }

        $vehicleModel = ($vehicle['modelUnknown'] ?? false)
            ? 'Modelo pendiente de confirmar'
            : ($vehicle['model'] ?? '');

        $repairOrders = [];
        foreach ($units as $idx => $u) {
            $num = $idx + 1;
            $w = $workshopUnits[$num] ?? [];
            $unitRef = $row['reference'] . '-P' . $num;
            $declaredRef = ($u['unknownReference'] ?? false)
                ? 'Sin identificar'
                : (string) ($u['reference'] ?: 'No indicada');
            $confirmedRef = (string) ($w['confirmed_reference'] ?? $declaredRef);

            $attachments = [];
            foreach ($u['attachments'] ?? [] as $att) {
                $attachments[] = [
                    'model' => 'ir.attachment',
                    'name' => $att['downloadName'] ?? ($att['name'] ?? 'adjunto'),
                    'mimetype' => $att['mime'] ?? 'application/octet-stream',
                    'file_size' => $att['size'] ?? 0,
                    'checksum' => $att['sha256'] ?? '',
                    'menigar_file_id' => $att['id'] ?? '',
                ];
            }

            $repairOrders[] = [
                'model' => 'repair.order',
                'odoo_virtual_id' => (int) ($w['odoo_order_id'] ?? (1081000 + $num)),
                'vals' => [
                    'name' => $unitRef,
                    'x_parent_request' => $row['reference'],
                    'x_unit_number' => $num,
                    'x_intent' => ($payload['intent'] ?? '') === 'repair' ? 'envio_reparacion' : 'consulta_previa',
                    'x_component_family' => $u['componentName'] ?? '',
                    'x_manufacturer' => $u['manufacturer'] ?? '',
                    'x_declared_reference' => $declaredRef,
                    'x_confirmed_reference' => $confirmedRef,
                    'x_reference_modified' => $confirmedRef !== $declaredRef,
                    'x_reference_updated_by' => $w['reference_updated_by'] ?? '',
                    'x_reference_updated_at' => $w['reference_updated_at'] ?? '',
                    'x_dtc_codes' => $u['dtc'] ?? '',
                    'description' => $u['symptoms'] ?? '',
                    'x_accessories_declared' => $u['accessories'] ?? '',
                    'x_vehicle_brand' => $u['vehicleBrand'] ?: ($vehicle['brand'] ?? ''),
                    'x_vehicle_model' => $u['vehicleModel'] ?: $vehicleModel,
                    'x_vehicle_plate' => $vehicle['plate'] ?? '',
                    'x_vehicle_vin' => $vehicle['vin'] ?? '',
                    'x_vehicle_year' => $vehicle['year'] ?? '',
                    'x_vehicle_km' => $vehicle['km'] ?? '',
                    'x_reception_state' => $w['reception_state'] ?? 'pendiente_llegada',
                    'x_reception_notes' => $w['reception_notes'] ?? '',
                    'x_received_at' => $w['received_at'] ?? '',
                    'x_technical_state' => $w['technical_state'] ?? 'pendiente_diagnostico',
                    'x_commercial_state' => $w['commercial_state'] ?? 'pendiente_presupuesto',
                    'x_estimated_eur' => $w['estimated_eur'] ?? '',
                    'x_bench_ticket' => $w['bench_ticket'] ?? '',
                    'internal_notes' => $w['technician_notes'] ?? '',
                ],
                'attachments' => $attachments,
            ];
        }

        return [
            'schema' => 'menigar.recepcion.v1',
            'request_reference' => $row['reference'],
            'created_at' => $row['created_at'],
            'partner' => $partner,
            'vehicle' => [
                'brand' => $vehicle['brand'] ?? '',
                'model' => $vehicleModel,
                'plate' => $vehicle['plate'] ?? '',
                'vin' => $vehicle['vin'] ?? '',
                'year' => $vehicle['year'] ?? '',
                'km' => $vehicle['km'] ?? '',
            ],
            'repair_orders_count' => count($repairOrders),
            'repair_orders' => $repairOrders,
        ];
    }

    /**
     * Genera un CSV compatible con Excel/ERP con 1 fila por orden de reparación (unidad)
     */
    public function buildCsvExport(array $row): string
    {
        $odoo = $this->buildOdooPayload($row);
        $p = $odoo['partner']['vals'];
        $v = $odoo['vehicle'];

        $headers = [
            'Codigo_Pieza', 'Solicitud_Web', 'Pieza_N', 'Modalidad',
            'Tipo_Cliente', 'Cliente_Razon_Social', 'Persona_Contacto', 'NIF_CIF', 'Telefono', 'Email', 'Direccion', 'CP', 'Localidad', 'Provincia',
            'Vehiculo_Marca', 'Vehiculo_Modelo', 'Matricula', 'Bastidor_VIN', 'Anio', 'Kilometros',
            'Pieza_Familia', 'Fabricante_Pieza', 'Referencia_Declarada_Cliente', 'Referencia_Confirmada_Tecnico',
            'Codigos_DTC', 'Sintomas_Cliente', 'Accesorios_Declarados', 'Adjuntos_N',
            'Estado_Recepcion', 'Estado_Tecnico', 'Estado_Comercial_Cobro', 'Presupuesto_EUR', 'Ticket_Banco_Pruebas', 'Notas_Tecnico'
        ];

        $escape = static function (string $val): string {
            $val = str_replace(["\r\n", "\r", "\n"], ' | ', $val);
            if (preg_match('/^[=+\-@]/', $val)) {
                $val = "'" . $val;
            }
            return '"' . str_replace('"', '""', $val) . '"';
        };

        $lines = ["\xEF\xBB\xBF" . implode(';', array_map($escape, $headers))];
        foreach ($odoo['repair_orders'] as $ro) {
            $vals = $ro['vals'];
            $rowCells = [
                (string) $vals['name'],
                (string) $vals['x_parent_request'],
                (string) $vals['x_unit_number'],
                $vals['x_intent'] === 'envio_reparacion' ? 'Envío de pieza' : 'Consulta',
                $p['x_menigar_customer_type'] === 'taller' ? 'Taller o empresa' : 'Particular',
                (string) $p['name'],
                (string) $p['x_contact_person'],
                (string) $p['vat'],
                (string) $p['phone'],
                (string) $p['email'],
                (string) $p['street'],
                (string) $p['zip'],
                (string) $p['city'],
                (string) $p['state_name'],
                (string) $vals['x_vehicle_brand'],
                (string) $vals['x_vehicle_model'],
                (string) $v['plate'],
                (string) $v['vin'],
                (string) $v['year'],
                (string) $v['km'],
                (string) $vals['x_component_family'],
                (string) $vals['x_manufacturer'],
                (string) $vals['x_declared_reference'],
                (string) $vals['x_confirmed_reference'],
                (string) $vals['x_dtc_codes'],
                (string) $vals['description'],
                (string) $vals['x_accessories_declared'],
                (string) count($ro['attachments']),
                self::RECEPTION_STATES[$vals['x_reception_state']] ?? (string) $vals['x_reception_state'],
                self::TECHNICAL_STATES[$vals['x_technical_state']] ?? (string) $vals['x_technical_state'],
                self::COMMERCIAL_STATES[$vals['x_commercial_state']] ?? (string) $vals['x_commercial_state'],
                (string) $vals['x_estimated_eur'],
                (string) $vals['x_bench_ticket'],
                (string) $vals['internal_notes'],
            ];
            $lines[] = implode(';', array_map($escape, $rowCells));
        }

        return implode("\r\n", $lines) . "\r\n";
    }
}
