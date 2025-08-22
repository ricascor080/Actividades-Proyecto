<?php
/**
 * FACTURA GLOBAL CFDI 4.0 (Tipo I) — SOLO XML (sin sello/cert)
 * Genera 3,000 conceptos aleatorios con IVA 16% y totales correctos.
 * Guarda: cfdi_global40_pre.xml
 *
 * PHP 7/8 — No requiere OpenSSL/XSLT.
 */

date_default_timezone_set('America/Mexico_City');

// ============ PARÁMETROS DEL COMPROBANTE ============
$datos = [
  // Comprobante
  'Serie'              => 'FG',           // Serie Global
  'Folio'              => '10001',
  'LugarExpedicion'    => '61652',
  'Moneda'             => 'MXN',
  'TipoDeComprobante'  => 'I',
  'Exportacion'        => '01',
  'FormaPago'          => '01',           // Efectivo (ajusta según tu operación)
  'MetodoPago'         => 'PUE',          // Usual en factura global

  // Emisor
  'EmisorRfc'          => 'EKU9003173C9',
  'EmisorNombre'       => 'ESCUELA KEMPER URGATE',
  'EmisorRegimen'      => '601',

  // Receptor (Público en general)
  'ReceptorRfc'        => 'XAXX010101000',
  'ReceptorNombre'     => 'PUBLICO EN GENERAL',
  'ReceptorUsoCFDI'    => 'S01',
  'ReceptorRegimen'    => '616',          // Recomendado para XAXX
  'ReceptorCP'         => '61652',
];

// ============ GENERADOR DE CONCEPTOS ALEATORIOS ============
/**
 * Genera N conceptos válidos con IVA 16% (tasa 0.160000)
 * - Precios aleatorios en 2 decimales entre $precioMin y $precioMax
 * - Cantidad entera entre cantMin y cantMax (impresa con 2 decimales)
 * - ClaveProdServ genérica 01010101 (OK para pruebas/global)
 */
function generarConceptosAleatorios($n = 3000, $precioMin = 5.00, $precioMax = 500.00, $cantMin = 1, $cantMax = 5) {
  // Semilla fija para reproducibilidad (cámbiala si quieres variedad)
  mt_srand(20250822);

  $out = [];
  $tasa = '0.160000';  // IVA 16% con 6 decimales

  for ($i = 1; $i <= $n; $i++) {
    $cantEntera = mt_rand($cantMin, $cantMax);
    $precio     = mt_rand((int)($precioMin*100), (int)($precioMax*100)) / 100.0;

    $out[] = [
      'ClaveProdServ'    => '01010101',
      'NoIdentificacion' => str_pad((string)$i, 6, '0', STR_PAD_LEFT),
      'Cantidad'         => number_format($cantEntera, 2, '.', ''),
      'ClaveUnidad'      => 'H87',
      'Unidad'           => 'Pieza',
      'Descripcion'      => 'Concepto aleatorio #'.$i,
      'ValorUnitario'    => number_format($precio, 2, '.', ''),
      'ObjetoImp'        => '02',        // objeto de impuesto (gravado)
      'Impuesto'         => '002',       // IVA
      'TipoFactor'       => 'Tasa',
      'TasaOCuota'       => $tasa,       // 0.160000
    ];
  }
  return $out;
}

// ============ DATOS DE CONCEPTOS ============
$conceptos_input = generarConceptosAleatorios(3000, 5.00, 500.00, 1, 5);

// ============ CONSTRUCCIÓN DEL XML ============
$xml = new DOMDocument('1.0', 'UTF-8');
$xml->formatOutput = true;

// Raíz
$root = $xml->createElement('cfdi:Comprobante');
$xml->appendChild($root);

cargaAtt($root, [
  'xmlns:cfdi' => 'http://www.sat.gob.mx/cfd/4',
  'xmlns:xsi'  => 'http://www.w3.org/2001/XMLSchema-instance',
  'xsi:schemaLocation' => 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd',
  'Version'            => '4.0',
  'Serie'              => $datos['Serie'],
  'Folio'              => $datos['Folio'],
  'Fecha'              => date('Y-m-d') . 'T' . date('H:i:s'),
  'Sello'              => '',
  'NoCertificado'      => '',
  'Certificado'        => '',
  'SubTotal'           => '0.00', // se recalcula
  'Moneda'             => $datos['Moneda'],
  'Total'              => '0.00', // se recalcula
  'TipoDeComprobante'  => $datos['TipoDeComprobante'],
  'Exportacion'        => $datos['Exportacion'],
  'LugarExpedicion'    => $datos['LugarExpedicion'],
  'FormaPago'          => $datos['FormaPago'],
  'MetodoPago'         => $datos['MetodoPago'],
]);

// Emisor
$emisor = $xml->createElement('cfdi:Emisor');
$root->appendChild($emisor);
cargaAtt($emisor, [
  'Rfc'           => $datos['EmisorRfc'],
  'Nombre'        => $datos['EmisorNombre'],
  'RegimenFiscal' => $datos['EmisorRegimen'],
]);

// Receptor
$receptor = $xml->createElement('cfdi:Receptor');
$root->appendChild($receptor);
cargaAtt($receptor, [
  'Rfc'                      => $datos['ReceptorRfc'],
  'Nombre'                   => $datos['ReceptorNombre'],
  'UsoCFDI'                  => $datos['ReceptorUsoCFDI'],
  'RegimenFiscalReceptor'    => $datos['ReceptorRegimen'],
  'DomicilioFiscalReceptor'  => $datos['ReceptorCP'],
]);

// Conceptos
$conceptos = $xml->createElement('cfdi:Conceptos');
$root->appendChild($conceptos);

// Acumuladores de totales
$subtotal = 0.0;
$traslados_totales = []; // clave: impuesto|tipo|tasa => importe
$traslados_sum = 0.0;

// Construir cada concepto con IVA 16%
foreach ($conceptos_input as $c) {
  $cantidad      = (float)$c['Cantidad'];
  $valorUnitario = (float)$c['ValorUnitario'];
  $importe       = round($cantidad * $valorUnitario, 2); // 2 decimales

  $subtotal += $importe;

  $con = $xml->createElement('cfdi:Concepto');
  $conceptos->appendChild($con);

  cargaAtt($con, [
    'ClaveProdServ'    => $c['ClaveProdServ'],
    'NoIdentificacion' => $c['NoIdentificacion'],
    'Cantidad'         => formato2($cantidad),
    'ClaveUnidad'      => $c['ClaveUnidad'],
    'Unidad'           => $c['Unidad'],
    'Descripcion'      => $c['Descripcion'],
    'ValorUnitario'    => formato2($valorUnitario),
    'Importe'          => formato2($importe),
    'ObjetoImp'        => $c['ObjetoImp'], // '02'
  ]);

  // Impuestos a nivel concepto (traslado IVA)
  if ($c['ObjetoImp'] === '02') {
    $impuestos = $xml->createElement('cfdi:Impuestos');
    $con->appendChild($impuestos);

    $traslados = $xml->createElement('cfdi:Traslados');
    $impuestos->appendChild($traslados);

    $tras = $xml->createElement('cfdi:Traslado');
    $traslados->appendChild($tras);

    // IVA del concepto
    $tasa6 = $c['TasaOCuota']; // string 6 decimales
    $iva_importe = round($importe * (float)$tasa6, 2);

    cargaAtt($tras, [
      'Base'       => formato2($importe),
      'Impuesto'   => $c['Impuesto'],   // '002'
      'TipoFactor' => $c['TipoFactor'], // 'Tasa'
      'TasaOCuota' => formato6($tasa6), // '0.160000'
      'Importe'    => formato2($iva_importe),
    ]);

    // Acumular a nivel global por clave (impuesto|tipo|tasa)
    $key = $c['Impuesto'].'|'.$c['TipoFactor'].'|'.formato6($tasa6);
    if (!isset($traslados_totales[$key])) {
      $traslados_totales[$key] = 0.0;
    }
    $traslados_totales[$key] += $iva_importe;
    $traslados_sum += $iva_importe;
  }
}

// Nodo de Impuestos globales
$impuestos_global = $xml->createElement('cfdi:Impuestos');
$root->appendChild($impuestos_global);

if ($traslados_sum > 0) {
  $traslados_glob = $xml->createElement('cfdi:Traslados');
  $impuestos_global->appendChild($traslados_glob);

  foreach ($traslados_totales as $key => $importeTotal) {
    [$imp, $tipo, $tasa] = explode('|', $key);
    $t_tras = $xml->createElement('cfdi:Traslado');
    $traslados_glob->appendChild($t_tras);
    cargaAtt($t_tras, [
      'Impuesto'   => $imp,             // '002'
      'TipoFactor' => $tipo,            // 'Tasa'
      'TasaOCuota' => $tasa,            // '0.160000'
      'Importe'    => formato2($importeTotal),
    ]);
  }

  cargaAtt($impuestos_global, [
    'TotalImpuestosTrasladados' => formato2($traslados_sum),
  ]);
}

// Totales del comprobante
$subtotal = round($subtotal, 2);
$total    = round($subtotal + $traslados_sum, 2);

// Actualizar raíz
$root->setAttribute('SubTotal', formato2($subtotal));
$root->setAttribute('Total',    formato2($total));

// Guardar XML
$nombreArchivo = __DIR__ . DIRECTORY_SEPARATOR . 'cfdi_global40_pre.xml';
$xml->save($nombreArchivo);

echo "XML GLOBAL generado (sin sello): $nombreArchivo\n";

// ================= Helpers =================
function cargaAtt(DOMElement $nodo, array $attr) {
  foreach ($attr as $key => $val) {
    if ($val === null || $val === false) continue;
    $val = strval($val);
    $val = preg_replace('/\s\s+/', ' ', $val);
    $val = trim($val);
    if ($val === '') continue;
    $val = str_replace('|', '/', $val); // prohibir pipes
    $nodo->setAttribute($key, $val);
  }
}
function formato2($n) {
  return number_format((float)$n, 2, '.', '');
}
function formato6($n) {
  return number_format((float)$n, 6, '.', '');
}
