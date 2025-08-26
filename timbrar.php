<?php
// timbrar.php — versión Ubuntu
date_default_timezone_set('America/Mexico_City');

$username = 'ricascor080@gmail.com'; // Usuario de Finkok
$password = 'Ricas002385.';          // Contraseña de Finkok

// 1) Leer el XML previo (sin sello)
$invoice_path = "/home/rcornejo/Actividades Proyecto/cfdi_global40_pre00.xml";
if (!file_exists($invoice_path)) {
    die("No se encontró el XML previo: $invoice_path\n");
}
$xml_content = file_get_contents($invoice_path);

// 2) Parámetros para sign_stamp
$params = array(
  "xml"      => $xml_content,
  "username" => $username,
  "password" => $password
);

// 3) Llamada al web service
$client = new SoapClient(
  "https://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl",
  array('trace' => 1, 'exceptions' => true, 'cache_wsdl' => WSDL_CACHE_NONE)
);

try {
  $result = $client->__soapCall("sign_stamp", array($params));

  // 4) Guardar Request/Response
  $requestPath  = "/home/rcornejo/Descargas/CFDI PRACTICA php/CFDI PRACTICA/SoapRequest.xml";
  $responsePath = "/home/rcornejo/Descargas/CFDI PRACTICA php/CFDI PRACTICA/SoapResponse.xml";
  file_put_contents($requestPath,  $client->__getLastRequest()  . PHP_EOL);
  file_put_contents($responsePath, $client->__getLastResponse() . PHP_EOL);

  // 5) Guardar el CFDI timbrado
  $signRes = isset($result->sign_stampResult) ? $result->sign_stampResult : $result;
  $raw     = $signRes->xml ?? null;

  $outTimbrado = "/home/rcornejo/Descargas/CFDI PRACTICA php/CFDI PRACTICA/Caso2_1.xml";

  if (!$raw) {
      echo "La respuesta no incluye 'xml' timbrado.\n";
      if (!empty($signRes->Incidencias)) { print_r($signRes->Incidencias); }
      exit(1);
  }

  $maybe = base64_decode($raw, true);
  if ($maybe !== false && strpos($maybe, '<cfdi:Comprobante') !== false) {
      file_put_contents($outTimbrado, $maybe);
  } else {
      $xmlString = html_entity_decode($raw, ENT_QUOTES | ENT_XML1, 'UTF-8');
      file_put_contents($outTimbrado, $xmlString);
  }
  echo "XML timbrado guardado en: $outTimbrado\n";

  // 6) (Opcional) sobrescribir el previo con el timbrado
  copy($outTimbrado, $invoice_path);

  // 7) Mostrar datos clave
  $doc = new DOMDocument();
  $doc->load($outTimbrado);
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
  file_put_contents("/home/rcornejo/Descargas/CFDI PRACTICA php/CFDI PRACTICA/timbres/SoapFault_Request.xml",  $client->__getLastRequest()  ?? '');
  file_put_contents("/home/rcornejo/Descargas/CFDI PRACTICA php/CFDI PRACTICA//SoapFault_Response.xml", $client->__getLastResponse() ?? '');
  exit(1);
}
