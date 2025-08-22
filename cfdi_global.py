# generar_cfdi_global40_pre.py
# FACTURA GLOBAL CFDI 4.0 (Tipo I) — SOLO XML (sin sello/cert)
# + ZIP del XML
# + Base64 del XML y del ZIP
# Python 3.9+ (usa zoneinfo). Sin dependencias externas.

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import datetime
from zoneinfo import ZoneInfo
import random
import os
import base64
import zipfile
import xml.etree.ElementTree as ET

# ====== Utilidades de formato con Decimal ======
getcontext().prec = 28
Q2 = Decimal("0.01")
Q6 = Decimal("0.000001")

def d(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))

def fmt2(x) -> str:
    return str(d(x).quantize(Q2, rounding=ROUND_HALF_UP))

def fmt6(x) -> str:
    return str(d(x).quantize(Q6, rounding=ROUND_HALF_UP))

def clean_val(s: str) -> str:
    s = " ".join(str(s).split())
    return s.replace("|", "/").strip()

# ====== Parámetros del comprobante ======
datos = {
    "Serie":             "FG",
    "Folio":             "10001",
    "LugarExpedicion":   "61652",
    "Moneda":            "MXN",
    "TipoDeComprobante": "I",
    "Exportacion":       "01",
    "FormaPago":         "01",
    "MetodoPago":        "PUE",
    "EmisorRfc":         "EKU9003173C9",
    "EmisorNombre":      "ESCUELA KEMPER URGATE",
    "EmisorRegimen":     "601",
    "ReceptorRfc":       "XAXX010101000",
    "ReceptorNombre":    "PUBLICO EN GENERAL",
    "ReceptorUsoCFDI":   "S01",
    "ReceptorRegimen":   "616",
    "ReceptorCP":        "61652",
}

# ====== Generador de conceptos aleatorios ======
def generar_conceptos_aleatorios(n=3000, precio_min=Decimal("5.00"),
                                 precio_max=Decimal("500.00"),
                                 cant_min=1, cant_max=5):
    random.seed(20250822)           # misma semilla que en PHP
    tasa = Decimal("0.160000")      # IVA 16% con 6 decimales

    out = []
    cents_min = int((precio_min * 100).to_integral_value())
    cents_max = int((precio_max * 100).to_integral_value())

    for i in range(1, n + 1):
        cant_entera = Decimal(random.randint(cant_min, cant_max))
        precio_cents = Decimal(random.randint(cents_min, cents_max))
        precio = (precio_cents / Decimal(100)).quantize(Q2, rounding=ROUND_HALF_UP)

        out.append({
            "ClaveProdServ":    "01010101",
            "NoIdentificacion": str(i).zfill(6),
            "Cantidad":         cant_entera,
            "ClaveUnidad":      "H87",
            "Unidad":           "Pieza",
            "Descripcion":      f"Concepto aleatorio #{i}",
            "ValorUnitario":    precio,
            "ObjetoImp":        "02",
            "Impuesto":         "002",
            "TipoFactor":       "Tasa",
            "TasaOCuota":       tasa,
        })
    return out

conceptos_input = generar_conceptos_aleatorios()

# ====== Construcción del XML ======
NS_CFDI = "http://www.sat.gob.mx/cfd/4"
NS_XSI  = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("cfdi", NS_CFDI)
ET.register_namespace("xsi", NS_XSI)

def carga_att(elem: ET.Element, attrs: dict):
    for k, v in attrs.items():
        if v is None or v is False:
            continue
        sv = clean_val(v)
        if not sv:
            continue
        elem.set(k, sv)

root = ET.Element(
    ET.QName(NS_CFDI, "Comprobante"),
    {
        "Version":            "4.0",
        "Serie":              datos["Serie"],
        "Folio":              datos["Folio"],
        "Fecha":              datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%dT%H:%M:%S"),
        "Sello":              "",
        "NoCertificado":      "",
        "Certificado":        "",
        "SubTotal":           "0.00",
        "Moneda":             datos["Moneda"],
        "Total":              "0.00",
        "TipoDeComprobante":  datos["TipoDeComprobante"],
        "Exportacion":        datos["Exportacion"],
        "LugarExpedicion":    datos["LugarExpedicion"],
        "FormaPago":          datos["FormaPago"],
        "MetodoPago":         datos["MetodoPago"],
        ET.QName(NS_XSI, "schemaLocation"): (
            "http://www.sat.gob.mx/cfd/4 "
            "http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"
        ),
    }
)

# Emisor
emisor = ET.SubElement(root, ET.QName(NS_CFDI, "Emisor"))
carga_att(emisor, {
    "Rfc":           datos["EmisorRfc"],
    "Nombre":        datos["EmisorNombre"],
    "RegimenFiscal": datos["EmisorRegimen"],
})

# Receptor
receptor = ET.SubElement(root, ET.QName(NS_CFDI, "Receptor"))
carga_att(receptor, {
    "Rfc":                     datos["ReceptorRfc"],
    "Nombre":                  datos["ReceptorNombre"],
    "UsoCFDI":                 datos["ReceptorUsoCFDI"],
    "RegimenFiscalReceptor":   datos["ReceptorRegimen"],
    "DomicilioFiscalReceptor": datos["ReceptorCP"],
})

# Conceptos
conceptos = ET.SubElement(root, ET.QName(NS_CFDI, "Conceptos"))

subtotal = Decimal("0.00")
traslados_totales = {}
traslados_sum = Decimal("0.00")

for c in conceptos_input:
    cantidad = d(c["Cantidad"])
    valor_unit = d(c["ValorUnitario"])
    importe = (cantidad * valor_unit).quantize(Q2, rounding=ROUND_HALF_UP)

    subtotal += importe

    con = ET.SubElement(conceptos, ET.QName(NS_CFDI, "Concepto"))
    carga_att(con, {
        "ClaveProdServ":    c["ClaveProdServ"],
        "NoIdentificacion": c["NoIdentificacion"],
        "Cantidad":         fmt2(cantidad),
        "ClaveUnidad":      c["ClaveUnidad"],
        "Unidad":           c["Unidad"],
        "Descripcion":      c["Descripcion"],
        "ValorUnitario":    fmt2(valor_unit),
        "Importe":          fmt2(importe),
        "ObjetoImp":        c["ObjetoImp"],
    })

    if c["ObjetoImp"] == "02":
        impuestos = ET.SubElement(con, ET.QName(NS_CFDI, "Impuestos"))
        traslados = ET.SubElement(impuestos, ET.QName(NS_CFDI, "Traslados"))
        tras = ET.SubElement(traslados, ET.QName(NS_CFDI, "Traslado"))

        tasa6 = d(c["TasaOCuota"])
        iva_importe = (importe * tasa6).quantize(Q2, rounding=ROUND_HALF_UP)

        carga_att(tras, {
            "Base":       fmt2(importe),
            "Impuesto":   c["Impuesto"],
            "TipoFactor": c["TipoFactor"],
            "TasaOCuota": fmt6(tasa6),
            "Importe":    fmt2(iva_importe),
        })

        key = (c["Impuesto"], c["TipoFactor"], fmt6(tasa6))
        traslados_totales[key] = traslados_totales.get(key, Decimal("0.00")) + iva_importe
        traslados_sum += iva_importe

# Impuestos globales
impuestos_global = ET.SubElement(root, ET.QName(NS_CFDI, "Impuestos"))
if traslados_sum > 0:
    traslados_glob = ET.SubElement(impuestos_global, ET.QName(NS_CFDI, "Traslados"))
    for (imp, tipo, tasa), importe_total in traslados_totales.items():
        t_tras = ET.SubElement(traslados_glob, ET.QName(NS_CFDI, "Traslado"))
        carga_att(t_tras, {
            "Impuesto":   imp,
            "TipoFactor": tipo,
            "TasaOCuota": tasa,
            "Importe":    fmt2(importe_total),
        })
    carga_att(impuestos_global, {
        "TotalImpuestosTrasladados": fmt2(traslados_sum),
    })

# Totales
subtotal = subtotal.quantize(Q2, rounding=ROUND_HALF_UP)
total = (subtotal + traslados_sum).quantize(Q2, rounding=ROUND_HALF_UP)
root.set("SubTotal", fmt2(subtotal))
root.set("Total", fmt2(total))

# ====== Guardar XML ======
base_dir = os.path.dirname(__file__)
xml_path = os.path.join(base_dir, "cfdi_global40_pre.xml")
tree = ET.ElementTree(root)
tree.write(xml_path, encoding="UTF-8", xml_declaration=True, short_empty_elements=False)
print(f"XML GLOBAL generado (sin sello): {xml_path}")

# ====== Crear ZIP con el XML ======
zip_path = os.path.join(base_dir, "cfdi_global40_pre.zip")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    # El archivo se guardará en el zip con el mismo nombre base (sin ruta)
    zf.write(xml_path, arcname=os.path.basename(xml_path))
print(f"ZIP generado: {zip_path}")

# ====== Base64 del XML y del ZIP ======
def to_b64_file(input_path: str, out_suffix: str):
    with open(input_path, "rb") as f:
        content = f.read()
    b64 = base64.b64encode(content).decode("ascii")
    out_path = input_path + out_suffix
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(b64)
    print(f"Base64 guardado: {out_path}  (longitud: {len(b64)} chars)")
    # Muestra un preview corto en consola:
    print(f"Preview: {b64[:80]}...")

xml_b64_path = to_b64_file(xml_path, ".b64")   # cfdi_global40_pre.xml.b64
zip_b64_path = to_b64_file(zip_path, ".b64")   # cfdi_global40_pre.zip.b64
