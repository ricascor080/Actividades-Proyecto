#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Runner integral para Finkok sign_multistamp + get_result_multistamp (async)
- Toma todos los .xml en ./mis_xmls (no recursivo), crea un ZIP
- Envía ZIP (Base64) con credenciales fijas
- Guarda request/response SOAP en ./soap_logs
- Hace polling automático de get_result_multistamp
- Descarga ZIP de resultados y lo extrae en ./out/extract_<WorkProcessId>

Uso:  python multistamp_runner.py
Requisitos: pip install suds-community
"""

import io
import os
import time
import json
import base64
import zipfile
from datetime import datetime
from pathlib import Path

from suds.client import Client
from suds.plugin import MessagePlugin

# ==========================
# CONFIG FIJA DEL DOCUMENTO
# ==========================
# WSDL DEMO (cámbialo por productivo cuando aplique)
WSDL_ASYNC = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"
# WSDL_ASYNC = "https://facturacion.finkok.com/servicios/soap/async.wsdl"  # productivo

# Credenciales FIJAS en el script (a petición del usuario)
FINKOK_USER = "ricascor080@gmail.com"
FINKOK_PASS = "Ricas002385."

# Carpeta con los XML a timbrar (junto al script)
XMLS_DIR = Path(__file__).resolve().parent / "mis_xmls"

# Polling
POLL_EVERY_SECONDS = 60   # segundos entre consultas
POLL_MAX_ATTEMPTS  = 10   # intentos máximos

# Salidas
BASE_DIR = Path(__file__).resolve().parent
OUT_DIR  = BASE_DIR / "out"
LOG_DIR  = BASE_DIR / "soap_logs"
OUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


# ===============
# Utilidades SOAP
# ===============
class SoapFileLogger(MessagePlugin):
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)

    def _method(self, ctx):
        try:
            return getattr(getattr(ctx, "method", None), "name", "unknown")
        except Exception:
            return "unknown"

    def sending(self, context):
        m = self._method(context)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = context.envelope
        if not isinstance(data, (bytes, bytearray)):
            data = str(data).encode("utf-8")
        (self.log_dir / f"soap_{m}_request_{ts}.xml").write_bytes(data)

    def received(self, context):
        m = self._method(context)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = context.reply
        if not isinstance(data, (bytes, bytearray)):
            data = str(data).encode("utf-8")
        (self.log_dir / f"soap_{m}_response_{ts}.xml").write_bytes(data)



def suds_to_builtin(obj):
    """Convierte suds objects a dict/list/str para guardar JSON."""
    try:
        from suds.sudsobject import asdict
    except Exception:
        return obj
    if hasattr(obj, "__keylist__"):
        out = {}
        for k, v in asdict(obj).items():
            out[k] = suds_to_builtin(v)
        return out
    if isinstance(obj, list):
        return [suds_to_builtin(x) for x in obj]
    return obj


# ===================
# Empaquetado de XMLs
# ===================
def make_zip_from_dir(xmls_dir: Path) -> bytes:
    xmls = sorted([p for p in Path(xmls_dir).glob("*.xml") if p.is_file()])
    if not xmls:
        raise FileNotFoundError(f"No se encontraron .xml en: {xmls_dir}")
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in xmls:
            zf.write(p, arcname=p.name)
    return bio.getvalue()


def to_b64str(data: bytes) -> str:
    """bytes -> base64 str (utf-8)."""
    return base64.b64encode(data).decode("utf-8")


def extract_base64_zip_from_result(result_obj):
    """Localiza el campo base64 con el ZIP de salida (nombres varían por versión)."""
    for key in ("file", "zip", "application_zipped", "application_zip", "data"):
        if hasattr(result_obj, key) and getattr(result_obj, key):
            return getattr(result_obj, key)
    # búsqueda laxa
    try:
        d = suds_to_builtin(result_obj)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, str) and len(v) > 100:
                    return v
    except Exception:
        pass
    return None


def save_json(data, path: Path):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# =================
# Llamadas al WS
# =================
def get_client(wsdl: str) -> Client:
    return Client(wsdl, cache=None, plugins=[SoapFileLogger(LOG_DIR)])


def _pick_work_process_id(obj) -> str | None:
    """Busca WorkProcessId en diferentes rutas conocidas."""
    # directo
    if hasattr(obj, "WorkProcessId") and getattr(obj, "WorkProcessId"):
        return getattr(obj, "WorkProcessId")
    # dentro de Incidencias/Incidencia
    try:
        incs = getattr(obj, "Incidencias", None)
        if incs:
            inc_list = getattr(incs, "Incidencia", None)
            if isinstance(inc_list, list):
                for inc in inc_list:
                    if hasattr(inc, "WorkProcessId") and inc.WorkProcessId:
                        return inc.WorkProcessId
            elif inc_list and hasattr(inc_list, "WorkProcessId"):
                return inc_list.WorkProcessId
    except Exception:
        pass
    # búsqueda laxa
    d = suds_to_builtin(obj)
    if isinstance(d, dict):
        for k, v in d.items():
            if k.lower() in ("workprocessid", "work_process_id") and isinstance(v, str) and v:
                return v
    return None


def call_sign_multistamp(client: Client, zip_b64_str: str, username: str, password: str):
    """
    Llama sign_multistamp con parámetros estándar.
    Retorna: (acuse_dict, work_process_id | None)
    """
    # ¡OJO! Aquí estaba tu error de paréntesis: construimos el dict completo y cerramos bien.
    params = dict(file=zip_b64_str, username=username, password=password)
    res = client.service.sign_multistamp(**params)
    res_dict = suds_to_builtin(res)
    wpid = _pick_work_process_id(res)
    return res_dict, wpid


def call_get_result_multistamp(client: Client, work_process_id: str):
    """
    Llama get_result_multistamp y retorna (result_dict, base64_zip_str | None, status_code | None)
    - base64_zip_str será None si aún no está listo
    - status_code puede traer 731/733 (en ejecución/fallo), etc.
    """
    res = client.service.get_result_multistamp(work_process_id=work_process_id)
    res_dict = suds_to_builtin(res)

    # Códigos en Incidencias (si los hay)
    status_code = None
    try:
        incs = res.Incidencias
        if incs:
            inc_list = getattr(incs, "Incidencia", None)
            if isinstance(inc_list, list) and inc_list:
                status_code = getattr(inc_list[0], "CodigoError", None)
            elif inc_list:
                status_code = getattr(inc_list, "CodigoError", None)
    except Exception:
        pass

    # Intentar extraer el archivo
    b64_zip = extract_base64_zip_from_result(res)
    return res_dict, b64_zip, status_code


def write_and_extract_zip(base64_zip_str: str, target_dir: Path) -> Path:
    """
    Guarda el ZIP (base64) en out/ y lo extrae a target_dir.
    Retorna la ruta del zip guardado.
    """
    raw = base64.b64decode(base64_zip_str)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = OUT_DIR / f"result_{ts}.zip"
    zip_path.write_bytes(raw)

    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        zf.extractall(target_dir)
    return zip_path


def poll_and_fetch_results(client: Client, work_process_id: str):
    """Hace polling a get_result_multistamp hasta que haya archivo o se agoten intentos."""
    print(f"📡 Polling get_result_multistamp para WorkProcessId={work_process_id} ...")
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        print(f"  Intento {attempt}/{POLL_MAX_ATTEMPTS} ...")
        res_dict, b64_zip, status = call_get_result_multistamp(client, work_process_id)

        # Guardar json de cada intento (útil para auditoría)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_json(res_dict, OUT_DIR / f"get_result_attempt_{attempt}_{ts}.json")

        if b64_zip:
            print("✅ Resultados listos. Descargando ZIP y extrayendo...")
            extract_dir = OUT_DIR / f"extract_{work_process_id}"
            zip_path = write_and_extract_zip(b64_zip, extract_dir)
            print(f"   ZIP guardado en: {zip_path}")
            print(f"   Archivos extraídos en: {extract_dir}")
            return True

        # Si hay códigos conocidos de “en ejecución”, informamos
        if status in ("731", 731, "733", 733):
            # 731: en ejecución, 733: failure interno (informativo)
            print(f"   Estado del proceso: {status} (aún sin archivo).")
        else:
            # Puede no haber status; seguimos intentando hasta agotar
            print("   Aún sin archivo. Reintentando...")

        time.sleep(POLL_EVERY_SECONDS)

    print("⛔ Sin archivo tras los reintentos. Revisa incidencias y SOAP logs.")
    return False


# =========
# MAIN RUN
# =========
def main():
    print("🚀 Iniciando multistamp_runner...")
    print(f"   WSDL: {WSDL_ASYNC}")
    print(f"   XMLS_DIR: {XMLS_DIR}")

    if not XMLS_DIR.exists():
        raise FileNotFoundError(f"No existe la carpeta: {XMLS_DIR}")

    # 1) Crear ZIP desde ./mis_xmls
    zip_bytes = make_zip_from_dir(XMLS_DIR)
    zip_b64_str = to_b64str(zip_bytes)
    print(f"📦 ZIP construido con {len(zip_bytes)} bytes (BASE64 len={len(zip_b64_str)})")

    # 2) Cliente SOAP
    client = get_client(WSDL_ASYNC)

    # 3) sign_multistamp
    print("📝 Llamando sign_multistamp ...")
    acuse_dict, wpid = call_sign_multistamp(client, zip_b64_str, FINKOK_USER, FINKOK_PASS)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(acuse_dict, OUT_DIR / f"sign_multistamp_{ts}.json")
    print(f"   Respuesta guardada en out/sign_multistamp_{ts}.json")

    if not wpid:
        print("⚠️ No se pudo determinar WorkProcessId en la respuesta de sign_multistamp.")
        print("   Revisa el JSON y los SOAP logs para más detalle.")
        return

    print(f"🆔 WorkProcessId: {wpid}")

    # 4) Polling a get_result_multistamp
    ok = poll_and_fetch_results(client, wpid)
    if ok:
        print("🎉 Proceso completado.")
    else:
        print("❗ Proceso finalizado sin archivo de resultados.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 Error no controlado: {e}")
