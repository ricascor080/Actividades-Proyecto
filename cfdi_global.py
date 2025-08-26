import datetime
import random
from lxml import etree as ET

# ===== Configuración rápida =====
N = 3000  # Puedes cambiarlo a 3000 si lo necesitas

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

# InformacionGlobal (obligatoria en factura global)
info_global = {
    'Periodicidad': '04',  # Mensual
    'Meses': '08',  # Agosto
    'Año': '2025',
}

# ===== Genera conceptos básicos (sin impuestos) =====
def generar_conceptos_basicos(n=10, precio_min=5.00, precio_max=500.00, cant_min=1, cant_max=5):
    """
    Genera una lista de conceptos básicos para el CFDI.
    """
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
            'ObjetoImp': '01',
        })
    return out

conceptos_input = generar_conceptos_basicos(N, 5.00, 500.00, 1, 5)

# ===== Construcción XML mínima =====
# Se usan los namespaces y el schemaLocation para la validación del CFDI.
nsmap = {
    'cfdi': 'http://www.sat.gob.mx/cfd/4',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}
schemaLocation = 'http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd'

# Elemento raíz
root = ET.Element(
    '{http://www.sat.gob.mx/cfd/4}Comprobante',
    nsmap=nsmap,
    attrib={
        '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': schemaLocation,
        'Version': '4.0',
        'Serie': datos['Serie'],
        'Folio': datos['Folio'],
        'Fecha': datetime.datetime.now().isoformat(),
        'Sello': '',
        'NoCertificado': '',
        'Certificado': '',
        'Moneda': datos['Moneda'],
        'TipoDeComprobante': datos['TipoDeComprobante'],
        'Exportacion': datos['Exportacion'],
        'LugarExpedicion': datos['LugarExpedicion'],
        'FormaPago': datos['FormaPago'],
        'MetodoPago': datos['MetodoPago'],
    }
)

# InformacionGlobal
ig = ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}InformacionGlobal', attrib={
    'Periodicidad': info_global['Periodicidad'],
    'Meses': info_global['Meses'],
    'Año': info_global['Año'],
})

# Emisor
emisor = ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Emisor', attrib={
    'Rfc': datos['EmisorRfc'],
    'Nombre': datos['EmisorNombre'],
    'RegimenFiscal': datos['EmisorRegimen'],
})

# Receptor
receptor = ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Receptor', attrib={
    'Rfc': datos['ReceptorRfc'],
    'Nombre': datos['ReceptorNombre'],
    'UsoCFDI': datos['ReceptorUsoCFDI'],
    'RegimenFiscalReceptor': datos['ReceptorRegimen'],
    'DomicilioFiscalReceptor': datos['ReceptorCP'],
})

# Conceptos
conceptos = ET.SubElement(root, '{http://www.sat.gob.mx/cfd/4}Conceptos')
subtotal = 0.0

for c in conceptos_input:
    cantidad = c['Cantidad']
    valor_unitario = c['ValorUnitario']
    importe = round(cantidad * valor_unitario, 2)
    subtotal += importe

    con = ET.SubElement(conceptos, '{http://www.sat.gob.mx/cfd/4}Concepto', attrib={
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

# Totales (sin impuestos)
subtotal = round(subtotal, 2)
total = subtotal

root.set('SubTotal', f'{subtotal:.2f}')
root.set('Total', f'{total:.2f}')

# Guardar
nombre_archivo = 'cfdi_global40_prepy.xml'
tree = ET.ElementTree(root)
tree.write(nombre_archivo, pretty_print=True, xml_declaration=True, encoding='UTF-8')

print(f"XML GLOBAL generado (básico, sin traslados): {nombre_archivo}")