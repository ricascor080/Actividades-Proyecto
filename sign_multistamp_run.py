# sign_multistamp_run.py
# Envia ZIP (base64) con CFDI SIN sello a Finkok (sign_multistamp),
# guarda/visualiza envolturas SOAP, detecta id o file directo, y hace polling con get_result_multistamp.

from pathlib import Path
import base64, time, zipfile, io, datetime
from typing import Optional, List
from requests import Session
from zeep import Client, Settings
from zeep.transports import Transport
from zeep.plugins import HistoryPlugin
from zeep.exceptions import Fault
from lxml import etree

# =========== CONFIG ===========
WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"
USER = "ricascor080@gmail.com"        # <--- coloca tus credenciales
PASS = "Ricas002385."
ZIP_PATH = Path("cfdi_global40_pre.zip")  # ZIP con XML sin sello (uno o varios)
USE_WEBHOOK = False  # True si tu cuenta exige webhook

# Si necesitas webhook, ajusta namespace y campos:
WEBHOOK_NAMESPACE = "ns2:sign_multistamp_webhookType"  # revisa tu WSDL por el nombre exacto
WEBHOOK_DATA = {
    # ejemplo si tu tipo lo requiere:
    # "url": "https://tu-servidor/callback",
    # "method": "POST",
}

# Nombres alternos donde algunos despliegues devuelven el identificador
ALT_ID_FIELDS: List[str] = ["id", "Id", "process_id", "processId", "ticket", "work_id", "WorkProcessId"]

# =========== UTIL: LOG DE ENVOLTURAS SOAP ===========
def _as_last(entry):
    if entry is None:
        return None
    if isinstance(entry, (list, tuple)):
        return entry[-1] if entry else None
    return entry

def _env(obj):
    if obj is None:
        return None
    try:
        return obj["envelope"]
    except Exception:
        try:
            return obj.envelope
        except Exception:
            return None

def _hdrs(obj):
    if obj is None:
        return None
    try:
        return obj["http_headers"]
    except Exception:
        try:
            return obj.http_headers
        except Exception:
            return None

def dump_soap(history: HistoryPlugin, op: str, phase: str):
    """
    Guarda e imprime última request/response SOAP capturada por HistoryPlugin.
    phase: 'request' o 'response'
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sent = _as_last(history.last_sent)
    recv = _as_last(history.last_received)
    obj = sent if phase == "request" else recv
    env = _env(obj)
    hdr = _hdrs(obj)
    if env is None:
        print(f"[soaplog] Sin envelope {phase} para {op}")
        return
    xml_bytes = etree.tostring(env, pretty_print=True, encoding="utf-8", xml_declaration=True)
    fname = f"soap_{op}_{phase}_{ts}.xml"
    Path(fname).write_bytes(xml_bytes)

    print(f"\n===== SOAP {phase.upper()} :: {op} =====")
    if hdr:
        try:
            print("HTTP headers:", dict(hdr))
        except Exception:
            pass
    print(xml_bytes.decode("utf-8"))
    print(f"[soaplog] Guardado: {fname}")

# =========== CLIENTE, CARGA Y UTILIDADES ===========
def build_client():
    session = Session()
    transport = Transport(session=session, timeout=120)
    settings = Settings(strict=False, xml_huge_tree=True)
    history = HistoryPlugin()
    client = Client(wsdl=WSDL, transport=transport, settings=settings, plugins=[history])
    return client, history

def load_zip_b64() -> str:
    return base64.b64encode(ZIP_PATH.read_bytes()).decode("ascii")

def build_webhook(client: Client):
    webhook_type = client.get_type(WEBHOOK_NAMESPACE)
    return webhook_type(**WEBHOOK_DATA)

def print_incidencias(obj, title="Incidencias"):
    try:
        incs = getattr(obj, "Incidencias", None)
        if not incs:
            return
        items = []
        if isinstance(incs, list):
            items = incs
        elif hasattr(incs, "Incidencia"):
            items = incs.Incidencia or []
        if items:
            print(title + ":")
            for i, inc in enumerate(items, 1):
                cod = getattr(inc, "CodigoError", None)
                msg = getattr(inc, "MensajeIncidencia", None)
                print(f"  #{i} CodigoError={cod}  Mensaje={msg}")
    except Exception:
        pass

def save_zip_and_extract(b64_data: str, zip_name="resultado_sign_multistamp.zip", out_dir="resultado_sign_multistamp"):
    raw = base64.b64decode(b64_data)
    Path(zip_name).write_bytes(raw)
    print(f"ZIP guardado: {zip_name} ({len(raw)} bytes)")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        zf.extractall(out)
        print(f"Archivos extraídos en: {out.resolve()}")
        for n in zf.namelist():
            print(" -", n)

def first_attr(obj, names: List[str]):
    for n in names:
        try:
            v = getattr(obj, n)
            if v:
                return v
        except Exception:
            pass
    return None

def extract_id_from_last_response_envelope(history: HistoryPlugin) -> Optional[str]:
    """
    Lee la última SOAP response y busca <id> en cualquier namespace.
    Útil si el PAC no expone el campo 'id' como atributo del objeto.
    """
    last = _as_last(history.last_received)
    if not last:
        return None
    env = _env(last)
    if env is None:
        return None
    try:
        elems = env.xpath("//*[local-name()='id']")
        if elems and elems[0].text and elems[0].text.strip():
            return elems[0].text.strip()
    except Exception:
        pass
    return None

# =========== FLUJO sign_multistamp + POLLING ===========
def enviar_sign_multistamp(client: Client, history: HistoryPlugin, file_b64: str) -> Optional[str]:
    """
    Envía el lote y devuelve el id de proceso si aplica. Si el acuse trae file directo,
    lo guarda y retorna None (no requiere polling).
    """
    webhook = None
    if USE_WEBHOOK:
        webhook = build_webhook(client)

    try:
        resp = client.service.sign_multistamp(file=file_b64, username=USER, password=PASS, webhook=webhook)
        dump_soap(history, "sign_multistamp", "request")
        dump_soap(history, "sign_multistamp", "response")

        print("\n=== ACUSE sign_multistamp ===")
        print_incidencias(resp, "Incidencias (acuse)")

        # Caso A: el PAC devolvió archivo final en el acuse (sin polling)
        file_b64_resp = first_attr(resp, ["file", "File", "zip", "Zip", "resultFile"])
        if file_b64_resp:
            print("El PAC devolvió el archivo en el ACUSE (sin polling).")
            save_zip_and_extract(file_b64_resp, zip_name="resultado_sign_multistamp.zip", out_dir="resultado_sign_multistamp")
            return None

        # Caso B: devuelve un id con nombre típico o alterno
        pid = first_attr(resp, ALT_ID_FIELDS)
        if pid:
            print("id:", pid)
            status = first_attr(resp, ["status", "Status"])
            if status:
                print("status:", status)
            return pid

        # Caso C: no vino como atributo; raspar desde SOAP
        pid = extract_id_from_last_response_envelope(history)
        if pid:
            print("id (desde SOAP response):", pid)
            return pid

        # Caso D: no hubo id ni file -> listar campos para diagnóstico
        print("⛔ No se encontró 'id' ni 'file' en el acuse. Campos devueltos:")
        for k in dir(resp):
            if k.startswith("_"):
                continue
            try:
                v = getattr(resp, k)
                if not callable(v):
                    print(f" - {k}: {v}")
            except Exception:
                pass
        return None

    except Fault as f:
        print(f"Zeep Fault en sign_multistamp: {f}")
        dump_soap(history, "sign_multistamp", "request")
        dump_soap(history, "sign_multistamp", "response")
        return None
    except Exception as e:
        print(f"Error en sign_multistamp: {e}")
        dump_soap(history, "sign_multistamp", "request")
        dump_soap(history, "sign_multistamp", "response")
        return None

def poll_get_result(client: Client, history: HistoryPlugin, process_id: str):
    """
    Polling con get_result_multistamp hasta recibir file o agotar reintentos.
    Maneja estados 731 (en ejecución), 733 (FAILURE), 730 (id no encontrado).
    """
    delays = [20,30,45,60,60,60,60,60,60,60,60,60,60,60,60]  # ~15 min
    for i, dly in enumerate(delays, 1):
        print(f"\nConsulta #{i} → get_result_multistamp(id={process_id})")
        try:
            r = client.service.get_result_multistamp(id=process_id, username=USER, password=PASS)

            dump_soap(history, "get_result_multistamp", "request")
            dump_soap(history, "get_result_multistamp", "response")

            print_incidencias(r)

            file_b64 = first_attr(r, ["file", "File", "zip", "Zip", "resultFile"])
            if file_b64:
                save_zip_and_extract(file_b64, zip_name="resultado_sign_multistamp.zip", out_dir="resultado_sign_multistamp")
                print("✅ Proceso finalizado con archivo recibido.")
                return True

            print(f"Aún sin archivo. Reintentando en {dly} s ...")
            time.sleep(dly)

        except Fault as f:
            print(f"Zeep Fault en get_result_multistamp: {f}")
            dump_soap(history, "get_result_multistamp", "request")
            dump_soap(history, "get_result_multistamp", "response")
            time.sleep(dly)
        except Exception as e:
            print(f"Error en get_result_multistamp: {e}")
            dump_soap(history, "get_result_multistamp", "request")
            dump_soap(history, "get_result_multistamp", "response")
            time.sleep(dly)

    print("⛔ Sin archivo tras los reintentos.")
    return False

def main():
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"No encuentro {ZIP_PATH.resolve()}")

    client, history = build_client()
    file_b64 = load_zip_b64()

    pid = enviar_sign_multistamp(client, history, file_b64)
    # Si pid es None, o ya guardamos el ZIP (acuse con file), o no hubo id.
    if pid:
        ok = poll_get_result(client, history, pid)
        if not ok:
            print("Revisa incidencias y archivos soap_*.xml para diagnóstico.")
    else:
        print("No se requiere polling (ya se guardó el ZIP) o no se obtuvo id.")

if __name__ == "__main__":
    main()
