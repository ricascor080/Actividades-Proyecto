import datetime
import random
from lxml import etree as ET
import zipfile
import base64
import os

# ===== Configuración rápida =====
N = 3000  # número de conceptos

datos = {
    'Serie': 'FG',
    'Folio': '10001',
    'LugarExpedicion': '61652',
    'Moneda': 'MXN',
    'TipoDeComprobante': 'I',
    'Exportacion': '01',
    'FormaPago': '01',
    'MetodoPago': 'PUE',
    'EmisorRfc': 'EKU9003173C9',
    'EmisorNombre': 'ESCUELA KEMPER URGATE',
    'EmisorRegimen': '601',
    'ReceptorRfc': 'XAXX010101000',
    'ReceptorNombre': 'PUBLICO EN GENERAL',
    'ReceptorUsoCFDI': 'S01',
    'ReceptorRegimen': '616',
    'ReceptorCP': '61652',
}

# InformacionGlobal
info_global = {
    'Periodicidad': '04',
    'Meses': '08',
    'Año': '2025',
}

# ===== Genera conceptos básicos (sin impuestos) =====
def generar_conceptos_basicos(n=10, precio_min=5.00, precio_max=500.00, cant_min=1, cant_max=5):
    random.seed(20250822)
    out = []
    for i in range(1, n + 1):
        cantidad = random.randint(cant_min, cant_max)
        precio = round(random.uniform(precio_min, precio_max), 2)
        out.append({
            'ClaveProdServ': '01010101',
            'NoIdentificacion': str(i).zfill(6),
            'Cantidad': float(cantidad),
            'ClaveUnidad': 'H87',
            'Unidad': 'Pieza',
            'Descripcion': f'Concepto #{i}',
            'ValorUnitario': float(precio),
            'ObjetoImp': '01',  # sin impuestos
        })
    return out

conceptos_input = generar_conceptos_basicos(N, 5.00, 500.00, 1, 5)

# ===== Construcción XML =====
nsmap = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}
schemaLocation = 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd'

# ⚠️ Fecha en formato exigido por SAT: AAAA-MM-DDThh:mm:ss (sin microsegundos ni zona horaria)
fecha_sat = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

root = ET.Element(
    '{http://www.sat.gob.mx/cfd/4}Comprobante',
    nsmap=nsmap,
    attrib={
        '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': schemaLocation,
        'Version': '4.0',
        'Serie': datos['Serie'],
        'Folio': datos['Folio'],
        'Fecha': fecha_sat,                 # ← corregido
        'Sello': '',                        # lo llenará el PAC
        'NoCertificado': '',                # lo llenará el PAC
        'Certificado': '',                  # lo llenará el PAC
        'Moneda': datos['Moneda'],
        'TipoDeComprobante': datos['TipoDeComprobante'],
        'Exportacion': datos['Exportacion'],
        'LugarExpedicion': datos['LugarExpedicion'],
        'FormaPago': datos['FormaPago'],
        'MetodoPago': datos['MetodoPago'],
    }
)

ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}InformacionGlobal', attrib=info_global)

ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Emisor', attrib={
    'Rfc': datos['EmisorRfc'],
    'Nombre': datos['EmisorNombre'],
    'RegimenFiscal': datos['EmisorRegimen'],
})

ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Receptor', attrib={
    'Rfc': datos['ReceptorRfc'],
    'Nombre': datos['ReceptorNombre'],
    'UsoCFDI': datos['ReceptorUsoCFDI'],
    'RegimenFiscalReceptor': datos['ReceptorRegimen'],
    'DomicilioFiscalReceptor': datos['ReceptorCP'],
})

conceptos = ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Conceptos')
subtotal = 0.0

for c in conceptos_input:
    cantidad = c['Cantidad']
    valor_unitario = c['ValorUnitario']
    importe = round(cantidad * valor_unitario, 2)
    subtotal += importe

    ET.SubElement(conceptos, '{http://www.sat.gob.mx/cfd/4}Concepto', attrib={
        'ClaveProdServ': c['ClaveProdServ'],
        'NoIdentificacion': c['NoIdentificacion'],
        'Cantidad': f'{cantidad:.6f}',
        'ClaveUnidad': c['ClaveUnidad'],
        'Unidad': c['Unidad'],
        'Descripcion': c['Descripcion'],
        'ValorUnitario': f'{valor_unitario:.2f}',
        'Importe': f'{importe:.2f}',
        'ObjetoImp': c['ObjetoImp'],
    })

# Totales
subtotal = round(subtotal, 2)
root.set('SubTotal', f'{subtotal:.2f}')
root.set('Total', f'{subtotal:.2f}')

# Guardar XML
xml_filename = 'cfdi_global40_bueno.xml'
tree = ET.ElementTree(root)
tree.write(xml_filename, pretty_print=True, xml_declaration=True, encoding='UTF-8')
print(f"✅ XML GLOBAL generado: {xml_filename}")

# ===== Crear ZIP =====
zip_filename = "cfdi_global40_bueno.zip"
with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    zipf.write(xml_filename, arcname=os.path.basename(xml_filename))
print(f"✅ ZIP creado: {zip_filename}")

# ===== Convertir ZIP a Base64 =====
with open(zip_filename, "rb") as f:
    zip_b64 = base64.b64encode(f.read()).decode('utf-8')

# Guardar Base64 en archivo
b64_filename = "cfdi_global40_bueno.b64"
with open(b64_filename, "w", encoding="utf-8") as f:
    f.write(zip_b64)

print(f"✅ Base64 guardado en: {b64_filename}")
print("🔎 Vista previa (primeros 200 caracteres):")
print(zip_b64[:200] + "...")
