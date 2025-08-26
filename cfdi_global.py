# generar_cfdi_global40_pre.py
# FACTURA GLOBAL CFDI 4.0 (Tipo I) — SOLO XML (sin sello/cert)
# + ZIP del XML
# + Base64 del XML y del ZIP
# + Validador local (reglas básicas)
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
import codecs

# ========= CONFIG RÁPIDA =========
N_CONCEPTOS = 1         # cámbialo a 3000 si lo necesitas
SEED = 20250822           # fija aleatoriedad reproducible (opcional)
PRECIO_MIN = Decimal("5.00")
PRECIO_MAX = Decimal("500.00")
CANT_MIN = 1
CANT_MAX = 5

# InformacionGlobal (catálogos: c_Periodicidad 01..05, c_Meses 01..12)
INFO_GLOBAL = {
    "Periodicidad": "04",  # 04 = Mensual
    "Meses":        "08",  # 01..12
    "Año":          "2025" # AAAA
}

# ========= Utilidades de formato con Decimal =========
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

# ========= Parámetros del comprobante =========
datos = {
    "Serie":             "FG",
    "Folio":             "10001",
    "LugarExpedicion":   "61652",
    "Moneda":            "MXN",
    "TipoDeComprobante": "I",
    "Exportacion":       "01",
    "FormaPago":         "01",      # Global típico PUE/01; ajusta si aplica
    "MetodoPago":        "PUE",

    # Emisor demo SAT:
    "EmisorRfc":         "EKU9003173C9",
    "EmisorNombre":      "ESCUELA KEMPER URGATE",
    "EmisorRegimen":     "601",

    # Receptor Público en general:
    "ReceptorRfc":       "XAXX010101000",
    "ReceptorNombre":    "PUBLICO EN GENERAL",
    "ReceptorUsoCFDI":   "S01",
    "ReceptorRegimen":   "616",
    "ReceptorCP":        "61652",
}

# ========= Generador de conceptos aleatorios =========
def generar_conceptos_aleatorios(n=1,
                                 precio_min=Decimal("5.00"),
                                 precio_max=Decimal("500.00"),
                                 cant_min=1, cant_max=5,
                                 seed: int | None = None):
    if seed is not None:
        random.seed(seed)

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
            "ObjetoImp":        "02",        # objeto gravado
            "Impuesto":         "002",       # IVA
            "TipoFactor":       "Tasa",
            "TasaOCuota":       tasa,        # 0.160000
        })
    return out

conceptos_input = generar_conceptos_aleatorios(
    N_CONCEPTOS, PRECIO_MIN, PRECIO_MAX, CANT_MIN, CANT_MAX, seed=SEED
)

# ========= Construcción del XML =========
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

# === Orden correcto: InformacionGlobal antes de Emisor/Receptor ===
info_global = ET.SubElement(root, ET.QName(NS_CFDI, "InformacionGlobal"))
carga_att(info_global, {
    "Periodicidad": INFO_GLOBAL["Periodicidad"],
    "Meses":        INFO_GLOBAL["Meses"],
    "Año":          INFO_GLOBAL["Año"],
})

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
traslados_totales = {}   # clave (Impuesto, TipoFactor, TasaOCuota_str6) -> importe sumado
traslados_sum = Decimal("0.00")

for c in conceptos_input:
    cantidad = d(c["Cantidad"])
    valor_unit = d(c["ValorUnitario"])
    importe = (cantidad * valor_unit).quantize(Q2, rounding=ROUND_HALF_UP)

    subtotal += importe

    con = ET.SubElement(conceptos, ET.QName(NS_CFDI, "Concepto"))
    # Cantidad: hasta 6 decimales; ValorUnitario/Importe: 2 decimales
    carga_att(con, {
        "ClaveProdServ":    c["ClaveProdServ"],
        "NoIdentificacion": c["NoIdentificacion"],
        "Cantidad":         fmt6(cantidad),
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
            "Impuesto":   c["Impuesto"],   # 002 = IVA
            "TipoFactor": c["TipoFactor"], # Tasa
            "TasaOCuota": fmt6(tasa6),     # 0.160000
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

# ========= Guardar XML =========
base_dir = os.path.dirname(__file__)
xml_path = os.path.join(base_dir, "cfdi_global40_pre.xml")
tree = ET.ElementTree(root)
tree.write(xml_path, encoding="UTF-8", xml_declaration=True, short_empty_elements=False)
print(f"XML GLOBAL generado (sin sello): {xml_path}")

# ========= Crear ZIP con el XML =========
zip_path = os.path.join(base_dir, "cfdi_global40_pre.zip")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    # incluir el XML en la raíz del ZIP
    zf.write(xml_path, arcname=os.path.basename(xml_path))
print(f"ZIP generado: {zip_path}")

# ========= Base64 del XML y del ZIP =========
def to_b64_file(input_path: str, out_suffix: str):
    with open(input_path, "rb") as f:
        content = f.read()
    b64 = base64.b64encode(content).decode("ascii")
    out_path = input_path + out_suffix
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(b64)
    print(f"Base64 guardado: {out_path}  (longitud: {len(b64)} chars)")
    print(f"Preview: {b64[:80]}...")

to_b64_file(xml_path, ".b64")   # cfdi_global40_pre.xml.b64
to_b64_file(zip_path, ".b64")   # cfdi_global40_pre.zip.b64

# ========= Validador local de CFDI Global 4.0 (reglas básicas) =========
def validar_cfdi40_global(xml_path: str) -> None:
    errores = []

    # 0) UTF-8 sin BOM
    with open(xml_path, "rb") as f:
        data = f.read()
    if data.startswith(codecs.BOM_UTF8):
        errores.append("El XML tiene BOM UTF-8; debe ser UTF-8 sin BOM.")

    # 1) Parse + namespaces
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {"cfdi": NS_CFDI}

    # 2) Atributos base
    version = root.get("Version")
    if version != "4.0":
        errores.append(f'Version distinta de 4.0: {version}')

    # 3) InformacionGlobal
    ig = root.find("cfdi:InformacionGlobal", ns)
    if ig is None:
        errores.append("Falta cfdi:InformacionGlobal (obligatorio en factura global).")
    else:
        per = ig.get("Periodicidad")
        mes = ig.get("Meses")
        anio = ig.get("Año")
        if per not in {"01", "02", "03", "04", "05"}:
            errores.append(f"Periodicidad inválida: {per} (cat 01..05).")
        if mes not in {f"{i:02d}" for i in range(1, 13)}:
            errores.append(f"Meses inválido: {mes} (debe 01..12).")
        if not (anio and len(anio) == 4 and anio.isdigit()):
            errores.append(f"Año inválido: {anio} (debe AAAA).")

    # 4) Receptor público en general
    rec = root.find("cfdi:Receptor", ns)
    if rec is None:
        errores.append("Falta cfdi:Receptor.")
    else:
        if rec.get("Rfc") != "XAXX010101000":
            errores.append(f'Rfc Receptor debe ser XAXX010101000, recibido: {rec.get("Rfc")}')
        if rec.get("UsoCFDI") != "S01":
            errores.append(f'UsoCFDI debe ser S01, recibido: {rec.get("UsoCFDI")}')
        if rec.get("RegimenFiscalReceptor") != "616":
            errores.append(f'RegimenFiscalReceptor debe ser 616, recibido: {rec.get("RegimenFiscalReceptor")}')

    # 5) Conceptos + traslados
    conceptos = root.find("cfdi:Conceptos", ns)
    if conceptos is None:
        errores.append("Falta cfdi:Conceptos.")
    else:
        subtotal_calc = Decimal("0.00")
        traslados_calc = Decimal("0.00")
        for i, con in enumerate(conceptos.findall("cfdi:Concepto", ns), 1):
            try:
                cant = d(con.get("Cantidad", "0"))
                vunit = d(con.get("ValorUnitario", "0"))
                imp = d(con.get("Importe", "0"))
            except Exception:
                errores.append(f"[Concepto #{i}] Cantidad/ValorUnitario/Importe no numérico.")
                continue

            imp_calc = (cant * vunit).quantize(Q2, rounding=ROUND_HALF_UP)
            if imp != imp_calc:
                errores.append(f"[Concepto #{i}] Importe {imp} != Cantidad*ValorUnitario {imp_calc}")
            subtotal_calc += imp

            if con.get("ObjetoImp") == "02":
                imp_node = con.find("cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", ns)
                if imp_node is None:
                    errores.append(f"[Concepto #{i}] Falta Traslado IVA (ObjetoImp=02).")
                else:
                    base = d(imp_node.get("Base", "0"))
                    impuesto = imp_node.get("Impuesto")
                    tipo = imp_node.get("TipoFactor")
                    tasa = d(imp_node.get("TasaOCuota", "0"))
                    importe_tras = d(imp_node.get("Importe", "0"))

                    if impuesto != "002":
                        errores.append(f"[Concepto #{i}] Impuesto debe ser 002 (IVA), recibido {impuesto}.")
                    if tipo != "Tasa":
                        errores.append(f"[Concepto #{i}] TipoFactor debe ser Tasa, recibido {tipo}.")
                    if fmt6(tasa) != "0.160000":
                        errores.append(f"[Concepto #{i}] TasaOCuota debe 0.160000, recibido {fmt6(tasa)}.")

                    if base != imp:
                        errores.append(f"[Concepto #{i}] Base traslado {base} != Importe concepto {imp}.")
                    importe_calc = (base * tasa).quantize(Q2, rounding=ROUND_HALF_UP)
                    if importe_tras != importe_calc:
                        errores.append(f"[Concepto #{i}] IVA {importe_tras} != Base*0.16 {importe_calc}.")
                    traslados_calc += importe_tras

        # 6) Totales a nivel Comprobante
        try:
            sub_attr = d(root.get("SubTotal", "0"))
            tot_attr = d(root.get("Total", "0"))
        except Exception:
            errores.append("SubTotal/Total del comprobante no numéricos.")
            sub_attr = tot_attr = Decimal("0.00")

        if sub_attr != subtotal_calc.quantize(Q2, rounding=ROUND_HALF_UP):
            errores.append(f"SubTotal {sub_attr} != suma importes {subtotal_calc}.")

        imp_glob = root.find("cfdi:Impuestos", ns)
        tras_total_attr = None
        if imp_glob is not None:
            tras_total_attr = imp_glob.get("TotalImpuestosTrasladados")
            if tras_total_attr is None and traslados_calc > 0:
                errores.append("Falta TotalImpuestosTrasladados en cfdi:Impuestos.")
            elif tras_total_attr is not None:
                try:
                    tras_total_attr = d(tras_total_attr)
                except Exception:
                    errores.append("TotalImpuestosTrasladados no numérico.")
                    tras_total_attr = Decimal("0.00")

        if traslados_calc > 0 and tras_total_attr is not None:
            if tras_total_attr != traslados_calc.quantize(Q2, rounding=ROUND_HALF_UP):
                errores.append(
                    f"TotalImpuestosTrasladados {tras_total_attr} != suma traslados {traslados_calc}."
                )

        total_calc = (subtotal_calc + traslados_calc).quantize(Q2, rounding=ROUND_HALF_UP)
        if tot_attr != total_calc:
            errores.append(f"Total {tot_attr} != SubTotal+Traslados {total_calc}.")

    # 7) Resultado
    if errores:
        print("\n❌ VALIDACIÓN CFDI GLOBAL — ERRORES:")
        for e in errores:
            print(" -", e)
    else:
        print("\n✅ VALIDACIÓN CFDI GLOBAL — OK (reglas básicas).")

# Ejecuta la validación al final
validar_cfdi40_global(xml_path)

# === Mensaje final para timbrado ===
print(
    "\nSiguiente paso:\n"
    " - Si vas a timbrar SIN sello propio, usa async.wsdl -> sign_stamp(xml=<b64 XML>, username, password) y luego get_result_stamp.\n"
    " - Si vas a timbrar CON sello propio, agrega Sello/Cert/NoCert y usa stamp(...).\n"
    " - Si haces 3000 conceptos y falla por tamaño/tiempo (733), divide en varios XML y usa multistamp (ZIP con XML en la raíz)."
)
