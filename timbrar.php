<?php
// timbrar.php — versión portable (Windows/Linux)
date_default_timezone_set('America/Mexico_City');

$username = 'ricascor080@gmail.com'; // Usuario de Finkok
$password = 'Ricas002385.';          // Contraseña de Finkok

// ===== Rutas seguras (relativas al script) =====
$BASE_DIR = __DIR__;
$OUT_DIR  = $BASE_DIR . DIRECTORY_SEPARATOR . 'salida';

// Crea carpeta de salida si no existe
if (!is_dir($OUT_DIR)) {
    if (!mkdir($OUT_DIR, 0777, true) && !is_dir($OUT_DIR)) {
        die("No se pudo crear la carpeta: $OUT_DIR\n");
    }
}

// Coloca el XML previo junto a este script con este nombre
$invoice_path = $BASE_DIR . DIRECTORY_SEPARATOR . 'cfdi_global40_pre001.xml';
if (!file_exists($invoice_path)) {
    die("No se encontró el XML previo: $invoice_path\n");
}
$xml_content = file_get_contents($invoice_path);

// ===== Parámetros para sign_stamp =====
$params = array(
  "xml"      => $xml_content,
  "username" => $username,
  "password" => $password
);

// ===== Cliente SOAP =====
$client = new SoapClient(
  "https://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl",
  array('trace' => 1, 'exceptions' => true, 'cache_wsdl' => WSDL_CACHE_NONE)
);

try {
  $result = $client->__soapCall("sign_stamp", array($params));

  // ===== Guardar Request/Response =====
  $requestPath  = $OUT_DIR . DIRECTORY_SEPARATOR . "SoapRequest.xml";
  $responsePath = $OUT_DIR . DIRECTORY_SEPARATOR . "SoapResponse.xml";
  file_put_contents($requestPath,  $client->__getLastRequest()  . PHP_EOL);
  file_put_contents($responsePath, $client->__getLastResponse() . PHP_EOL);

  // ===== Guardar el CFDI timbrado =====
  $signRes = isset($result->sign_stampResult) ? $result->sign_stampResult : $result;
  $raw     = $signRes->xml ?? null;

  $outTimbrado = $OUT_DIR . DIRECTORY_SEPARATOR . "Caso2_1.xml";

  if (!$raw) {
      echo "La respuesta no incluye 'xml' timbrado.\n";
      if (!empty($signRes->Incidencias)) { print_r($signRes->Incidencias); }
      exit(1);
  }

  // Algunas respuestas vienen base64; otras como XML escapado
  $maybe = base64_decode($raw, true);
  if ($maybe !== false && strpos($maybe, '<cfdi:Comprobante') !== false) {
      file_put_contents($outTimbrado, $maybe);
  } else {
      $xmlString = html_entity_decode($raw, ENT_QUOTES | ENT_XML1, 'UTF-8');
      file_put_contents($outTimbrado, $xmlString);
  }
  echo "XML timbrado guardado en: $outTimbrado\n";

  // (Opcional) sobrescribir el previo con el timbrado
  if (!@copy($outTimbrado, $invoice_path)) {
      echo "Aviso: no se pudo sobrescribir el XML previo. Verifica permisos.\n";
  }

  // ===== Mostrar datos clave =====
  $doc = new DOMDocument();
  if (!$doc->load($outTimbrado)) {
      die("No se pudo cargar el XML timbrado para lectura: $outTimbrado\n");
  }
  $xp = new DOMXPath($doc);
  $xp->registerNamespace('cfdi','http://www.sat.gob.mx/cfd/4');
  $xp->registerNamespace('tfd','http://www.sat.gob.mx/TimbreFiscalDigital');

  $sello   = $xp->query('/cfdi:Comprobante/@Sello')->item(0)?->nodeValue ?? 'N/D';
  $nocer   = $xp->query('/cfdi:Comprobante/@NoCertificado')->item(0)?->nodeValue ?? 'N/D';
  $cerB64  = $xp->query('/cfdi:Comprobante/@Certificado')->item(0)?->nodeValue ?? 'N/D';
  $uuid    = $xp->query('//cfdi:Complemento/tfd:TimbreFiscalDigital/@UUID')->item(0)?->nodeValue ?? 'N/D';
  $cod     = $signRes->CodEstatus ?? 'N/D';

  echo "CodEstatus: $cod\n";
  echo "UUID: $uuid\n";
  echo "NoCertificado: $nocer\n";
  echo "Sello (inicio): " . substr($sello, 0, 40) . "...\n";
  echo "Certificado(b64, inicio): " . substr($cerB64, 0, 40) . "...\n";

} catch (SoapFault $e) {
  echo "SOAP Fault: ({$e->faultcode}) {$e->faultstring}\n";
  $faultReq = $OUT_DIR . DIRECTORY_SEPARATOR . "SoapFault_Request.xml";
  $faultRes = $OUT_DIR . DIRECTORY_SEPARATOR . "SoapFault_Response.xml";
  @file_put_contents($faultReq, $client->__getLastRequest()  ?? '');
  @file_put_contents($faultRes, $client->__getLastResponse() ?? '');
  exit(1);
}
