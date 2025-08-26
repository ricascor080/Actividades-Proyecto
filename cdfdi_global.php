
<?php
/**
 * CFDI 4.0 Global básico (sin traslados)
 * - Conceptos sencillos (ObjetoImp=01)
 * - Total = SubTotal
 * - Incluye InformacionGlobal
 */

date_default_timezone_set('America/Mexico_City');

// ===== Config rápida =====
$N = 3000; // cámbialo a 3000 si quieres

$datos = [
  'Serie'             => 'FG',
  'Folio'             => '10001',
  'LugarExpedicion'   => '61652',
  'Moneda'            => 'MXN',
  'TipoDeComprobante' => 'I',
  'Exportacion'       => '01',
  'FormaPago'         => '01',
  'MetodoPago'        => 'PUE',

  'EmisorRfc'         => 'EKU9003173C9',
  'EmisorNombre'      => 'ESCUELA KEMPER URGATE',
  'EmisorRegimen'     => '601',

  'ReceptorRfc'       => 'XAXX010101000',
  'ReceptorNombre'    => 'PUBLICO EN GENERAL',
  'ReceptorUsoCFDI'   => 'S01',
  'ReceptorRegimen'   => '616',
  'ReceptorCP'        => '61652',
];

// InformacionGlobal (obligatoria en factura global)
$infoGlobal = [
  'Periodicidad' => '04', // Mensual
  'Meses'        => '08', // Agosto
  'Año'          => '2025',
];

// ===== Genera conceptos básicos (sin impuestos) =====
function generarConceptosBasicos($n = 10, $precioMin = 5.00, $precioMax = 500.00, $cantMin = 1, $cantMax = 5) {
  mt_srand(20250822);
  $out = [];
  for ($i = 1; $i <= $n; $i++) {
    $cant   = mt_rand($cantMin, $cantMax);
    $precio = mt_rand((int)round($precioMin*100), (int)round($precioMax*100))/100;
    $out[] = [
      'ClaveProdServ'    => '01010101',
      'NoIdentificacion' => str_pad((string)$i, 6, '0', STR_PAD_LEFT),
      'Cantidad'         => (float)$cant,      // se imprime con 6 decimales
      'ClaveUnidad'      => 'H87',
      'Unidad'           => 'Pieza',
      'Descripcion'      => 'Concepto #'.$i,
      'ValorUnitario'    => (float)$precio,    // se imprime con 2 decimales
      'ObjetoImp'        => '01',              // SIN impuesto (simple)
    ];
  }
  return $out;
}

$conceptos_input = generarConceptosBasicos($N, 5.00, 500.00, 1, 5);

// ===== Construcción XML mínima =====
$xml = new DOMDocument('1.0', 'UTF-8');
$xml->formatOutput = true;

$root = $xml->createElement('cfdi:Comprobante');
$xml->appendChild($root);

cargaAtt($root, [
  'xmlns:cfdi'         => 'http://www.sat.gob.mx/cfd/4',
  'xmlns:xsi'          => 'http://www.w3.org/2001/XMLSchema-instance',
  'xsi:schemaLocation' => 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd',
  'Version'            => '4.0',
  'Serie'              => $datos['Serie'],
  'Folio'              => $datos['Folio'],
  'Fecha'              => date('Y-m-d\TH:i:s'),
  'Sello'              => '',
  'NoCertificado'      => '',
  'Certificado'        => '',
  'SubTotal'           => '0.00',
  'Moneda'             => $datos['Moneda'],
  'Total'              => '0.00',
  'TipoDeComprobante'  => $datos['TipoDeComprobante'],
  'Exportacion'        => $datos['Exportacion'],
  'LugarExpedicion'    => $datos['LugarExpedicion'],
  'FormaPago'          => $datos['FormaPago'],
  'MetodoPago'         => $datos['MetodoPago'],
]);

// InformacionGlobal (antes de Emisor/Receptor)
$ig = $xml->createElement('cfdi:InformacionGlobal');
$root->appendChild($ig);
cargaAtt($ig, [
  'Periodicidad' => $infoGlobal['Periodicidad'],
  'Meses'        => $infoGlobal['Meses'],
  'Año'          => $infoGlobal['Año'],
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

// Conceptos (sin traslados)
$conceptos = $xml->createElement('cfdi:Conceptos');
$root->appendChild($conceptos);

$subtotal = 0.0;

foreach ($conceptos_input as $c) {
  $cantidad      = (float)$c['Cantidad'];
  $valorUnitario = (float)$c['ValorUnitario'];
  $importe       = round($cantidad * $valorUnitario, 2);

  $subtotal += $importe;

  $con = $xml->createElement('cfdi:Concepto');
  $conceptos->appendChild($con);

  cargaAtt($con, [
    'ClaveProdServ'    => $c['ClaveProdServ'],
    'NoIdentificacion' => $c['NoIdentificacion'],
    'Cantidad'         => formato6($cantidad),
    'ClaveUnidad'      => $c['ClaveUnidad'],
    'Unidad'           => $c['Unidad'],
    'Descripcion'      => $c['Descripcion'],
    'ValorUnitario'    => formato2($valorUnitario),
    'Importe'          => formato2($importe),
    'ObjetoImp'        => $c['ObjetoImp'], // 01 = sin impuesto
  ]);
}

// Totales (sin impuestos)
$subtotal = round($subtotal, 2);
$total    = $subtotal;

$root->setAttribute('SubTotal', formato2($subtotal));
$root->setAttribute('Total',    formato2($total));

// Guardar
$nombreArchivo = __DIR__ . DIRECTORY_SEPARATOR . 'cfdi_global40_pre001.xml';
$xml->save($nombreArchivo);
echo "XML GLOBAL generado (básico, sin traslados): $nombreArchivo\n";

// ===== Helpers =====
function cargaAtt(DOMElement $nodo, array $attr) {
  foreach ($attr as $key => $val) {
    if ($val === null || $val === false) continue;
    $val = strval($val);
    $val = preg_replace('/\s\s+/', ' ', $val);
    $val = trim($val);
    if ($val === '') continue;
    $val = str_replace('|', '/', $val);
    $nodo->setAttribute($key, $val);
  }
}
function formato2($n){ return number_format((float)$n, 2, '.', ''); }
function formato6($n){ return number_format((float)$n, 6, '.', ''); }