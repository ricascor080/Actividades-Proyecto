#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import io
import os
import json
import time
import base64
import zipfile
import argparse
from datetime import datetime
from pathlib import Path

from suds.client import Client
from suds.plugin import MessagePlugin

DEFAULT_WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

# ======= CREDENCIALES (puedes cambiarlas aquí o via variables de entorno) =======
FINKOK_USER = os.getenv("FINKOK_USER", "ricascor080@gmail.com")
FINKOK_PASS = os.getenv("FINKOK_PASS", "Ricas002385.")

# ----------------------- SOAP logger -----------------------
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

# ----------------------- helpers -----------------------
def suds_to_builtin(obj):
    try:
        from suds.sudsobject import asdict
    except Exception:
        return obj
    if hasattr(obj, "__keylist__"):
        from suds.sudsobject import asdict
        return {k: suds_to_builtin(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [suds_to_builtin(x) for x in obj]
    return obj

def pick_base64_field(result_obj):
    for c in ("file", "zip", "application_zipped", "application_zip", "data"):
        if hasattr(result_obj, c):
            val = getattr(result_obj, c)
            if val:
                return val
    d = suds_to_builtin(result_obj)
    if isinstance(d, dict):
        for k in ("file", "zip", "application_zipped", "application_zip", "data"):
            if isinstance(d.get(k), str) and len(d[k]) > 100:
                return d[k]
        for v in d.values():
            if isinstance(v, str) and len(v) > 100:
                return v
            if isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, str) and len(vv) > 100:
                        return vv
    return None

def pick_status_incidence(result_obj):
    try:
        incs = getattr(result_obj, "Incidencias", None)
        if not incs:
            return None, None
        inc = getattr(incs, "Incidencia", None)
        if isinstance(inc, list) and inc:
            inc = inc[0]
        code = getattr(inc, "CodigoError", None)
        msg  = getattr(inc, "MensajeIncidencia", None)
        return str(code) if code is not None else None, msg
    except Exception:
        return None, None

def extract_zip_bytes(zip_bytes: bytes, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        zf.extractall(target_dir)
    return target_dir

def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)

def read_id_from_txt(path: Path) -> str:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"(multistamp_[0-9a-fA-F\-]+)", txt)
    if m:
        return m.group(1)
    for token in re.split(r"\s+", txt):
        tok = token.strip().strip("'").strip('"')
        if tok:
            return tok
    raise ValueError(f"No se encontró un id válido en {path}")

# ----------------------- main -----------------------
def main():
    ap = argparse.ArgumentParser(description="Lee id de TXT, consulta get_result_multistamp y extrae ZIP si está listo.")
    ap.add_argument("--wsdl", default=DEFAULT_WSDL, help="URL WSDL async (demo/productivo)")
    ap.add_argument("--id-file", default="./out/workprocessid.txt", help="Ruta del .txt que contiene el id")
    ap.add_argument("--out-dir", default="./out", help="Carpeta de salida")
    ap.add_argument("--soap-dir", default="./soap_logs", help="Carpeta de logs SOAP")
    ap.add_argument("--poll", action="store_true", help="Hacer polling hasta que esté listo")
    ap.add_argument("--every", type=int, default=30, help="Segundos entre intentos (con --poll)")
    ap.add_argument("--max", type=int, default=20, help="Intentos máximos (con --poll)")
    ap.add_argument("--user", default=FINKOK_USER, help="Usuario Finkok (si no, usa env FINKOK_USER)")
    ap.add_argument("--password", default=FINKOK_PASS, help="Contraseña Finkok (si no, usa env FINKOK_PASS)")
    ap.add_argument("--print-b64", action="store_true", help="Imprimir el Base64 en stdout cuando esté listo")
    args = ap.parse_args()

    out_dir  = Path(args.out_dir);  out_dir.mkdir(exist_ok=True, parents=True)
    soap_dir = Path(args.soap_dir); soap_dir.mkdir(exist_ok=True, parents=True)

    id_path = Path(args.id_file)
    if not id_path.exists():
        raise FileNotFoundError(f"No existe el archivo con el id: {id_path}")

    rid = read_id_from_txt(id_path).strip()
    rid_safe = safe_name(rid)

    client = Client(args.wsdl, cache=None, plugins=[SoapFileLogger(soap_dir)])

    attempt = 0
    while True:
        attempt += 1
        print(f"📥 get_result_multistamp (id={rid}, intento {attempt}) ...")

        # >>>>>>>>>>>>>>>>>> ENVÍA id + username + password <<<<<<<<<<<<<<<<<
        res = client.service.get_result_multistamp(id=rid, username=args.user, password=args.password)

        # guardar JSON legible
        res_builtin = suds_to_builtin(res)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"get_result_{rid_safe}_{ts}.json"
        json_path.write_text(json.dumps(res_builtin, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"🧾 Respuesta guardada: {json_path}")

        # ¿ya viene el ZIP?
        b64_zip = pick_base64_field(res)
        if b64_zip:
            b64_bytes = b64_zip.encode("ascii") if isinstance(b64_zip, str) else b64_zip

            # guardar base64 y zip
            b64_path = out_dir / f"resultado_{rid_safe}.b64"
            b64_path.write_bytes(b64_bytes)

            zip_bytes = base64.b64decode(b64_bytes)
            zip_path  = out_dir / f"resultado_{rid_safe}.zip"
            zip_path.write_bytes(zip_bytes)

            # extraer
            extract_dir = out_dir / f"extract_{rid_safe}"
            extract_zip_bytes(zip_bytes, extract_dir)

            print(f"✅ ZIP recibido: {zip_path} ({len(zip_bytes)} bytes)")
            print(f"📂 Archivos extraídos en: {extract_dir}")

            if args.print_b64:
                print(b64_bytes.decode("ascii"))

            print("🎉 Listo.")
            return

        code, msg = pick_status_incidence(res)
        if code or msg:
            print(f"ℹ️ Estado: {code or '-'} - {msg or '-'}")
            # Tip rápido si es 300 (credenciales)
            if str(code) == "300":
                print("❗ Verifica usuario/contraseña (argumentos --user/--password o variables FINKOK_USER/FINKOK_PASS).")
        else:
            print("ℹ️ Aún sin archivo y sin incidencia clara en la respuesta.")

        if not args.poll or attempt >= args.max:
            print("⛔ No hay archivo disponible en este momento. Vuelve a intentar más tarde.")
            return

        time.sleep(args.every)

if __name__ == "__main__":
    main()
