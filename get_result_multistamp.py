#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import json
import base64
import zipfile
import argparse
from datetime import datetime
from pathlib import Path

from suds.client import Client
from suds.plugin import MessagePlugin

DEFAULT_WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

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
        (self.log_dir / f"soap_{m}_request_{ts}.xml").write_bytes(
            context.envelope.encode("utf-8")
        )

    def received(self, context):
        m = self._method(context)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (self.log_dir / f"soap_{m}_response_{ts}.xml").write_bytes(context.reply)

def suds_to_builtin(obj):
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

def extract_zip_bytes(zip_bytes: bytes, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(target_dir)
    return target_dir

def pick_base64_field(result_obj):
    """
    Localiza el campo base64 con el ZIP en la respuesta (nombres varían).
    """
    candidates = ("file", "zip", "application_zipped", "application_zip", "data")
    for c in candidates:
        if hasattr(result_obj, c):
            val = getattr(result_obj, c)
            if val:
                return val
    # búsqueda laxa
    d = suds_to_builtin(result_obj)
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 100:
                return v
    return None

def read_workprocessid_from_acuse(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("WorkProcessId", "work_process_id", "Id", "id", "WorkProcessID"):
        if key in data and data[key]:
            return data[key]
    # algunos acuses lo anidan
    def dfs(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("WorkProcessId", "work_process_id", "Id", "id", "WorkProcessID") and v:
                    return v
                r = dfs(v)
                if r:
                    return r
        elif isinstance(x, list):
            for it in x:
                r = dfs(it)
                if r:
                    return r
        return None
    wpid = dfs(data)
    if not wpid:
        raise ValueError("No se encontró WorkProcessId en el acuse.")
    return wpid

def main():
    ap = argparse.ArgumentParser(description="Finkok get_result_multistamp")
    ap.add_argument("--wsdl", default=DEFAULT_WSDL, help="URL WSDL async (demo/productivo)")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--work-process-id", help="WorkProcessId del proceso async")
    group.add_argument("--acuse", help="Ruta al JSON del acuse de sign_multistamp")
    ap.add_argument("--out-dir", default="./out", help="Carpeta de salida")
    ap.add_argument("--soap-dir", default="./soap_logs", help="Carpeta de logs SOAP")
    ap.add_argument("--extract", action="store_true", help="Extraer ZIP de resultados al recibirlo")
    args = ap.parse_args()

    out_dir = Path(args.out_dir); out_dir.mkdir(exist_ok=True, parents=True)
    soap_dir = Path(args.soap_dir); soap_dir.mkdir(exist_ok=True, parents=True)

    # 1) Obtener WorkProcessId
    if args.acuse:
        wpid = read_workprocessid_from_acuse(Path(args.acuse))
    else:
        wpid = args.work_process_id

    print(f"🆔 WorkProcessId: {wpid}")
    print(f"🔗 WSDL: {args.wsdl}")

    # 2) Cliente SOAP
    client = Client(args.wsdl, cache=None, plugins=[SoapFileLogger(soap_dir)])

    # 3) Llamar get_result_multistamp
    print("📥 Consultando get_result_multistamp ...")
    res = client.service.get_result_multistamp(wpid)

    # 4) Guardar JSON con toda la respuesta
    res_builtin = suds_to_builtin(res)
    json_path = out_dir / f"get_result_{wpid}.json"
    json_path.write_text(json.dumps(res_builtin, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🧾 Resultado JSON: {json_path}")

    # 5) Intentar extraer el ZIP base64 del resultado
    b64_zip = pick_base64_field(res)
    if not b64_zip:
        print("ℹ️ Aún no hay archivo ZIP en la respuesta (posible estado: en ejecución/en cola).")
        return

    if isinstance(b64_zip, str):
        b64_zip = b64_zip.encode("ascii")

    zip_bytes = base64.b64decode(b64_zip)
    zip_path = out_dir / f"resultado_{wpid}.zip"
    zip_path.write_bytes(zip_bytes)
    print(f"✅ ZIP recibido: {zip_path} ({len(zip_bytes)} bytes)")

    # 6) Extraer si se pidió
    if args.extract:
        extract_dir = out_dir / f"extract_{wpid}"
        extract_zip_bytes(zip_bytes, extract_dir)
        print(f"📂 Archivos extraídos en: {extract_dir}")

    print("🎉 Listo.")

if __name__ == "__main__":
    main()
