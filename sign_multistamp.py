#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Envía un ZIP en Base64 a sign_multistamp y regresa SOLO el id.
- Lee ./cfdi_global40_bueno.b64 (o usa --b64 para indicar otro archivo)
- Imprime en stdout únicamente el id (p.ej. multistamp_abc123...)
- Guarda el id en ./out/workprocessid.txt

Uso:
  python send_b64_return_id.py --b64 ./cfdi_global40_bueno.b64
Variables opcionales:
  export FINKOK_USER="tu_usuario"; export FINKOK_PASS="tu_password"
"""

import argparse
import os
from pathlib import Path
from suds.client import Client

WSDL_ASYNC = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

# Fallback a constantes si no hay variables de entorno
FINKOK_USER = os.getenv("FINKOK_USER", "ricascor080@gmail.com")
FINKOK_PASS = os.getenv("FINKOK_PASS", "Ricas002385.")

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

def suds_to_builtin(obj):
    try:
        from suds.sudsobject import asdict
    except Exception:
        return obj
    if hasattr(obj, "__keylist__"):
        return {k: suds_to_builtin(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [suds_to_builtin(x) for x in obj]
    return obj

def extract_first_id(res_obj):
    """Obtiene el primer 'id' (p.ej. multistamp_...) de la respuesta."""
    # Caso directo (lo más común)
    wpid = getattr(res_obj, "id", None)
    if isinstance(wpid, str) and wpid:
        return wpid

    # Conversión a dict por seguridad
    d = suds_to_builtin(res_obj)
    if isinstance(d, dict):
        if isinstance(d.get("id"), str) and d["id"]:
            return d["id"]
        for v in d.values():
            if isinstance(v, dict) and isinstance(v.get("id"), str) and v["id"]:
                return v["id"]
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]:
                        return item["id"]

    # Último recurso: buscar patrón en string
    s = str(d)
    marker = "id': "
    idx = s.find(marker)
    if idx != -1:
        tail = s[idx + len(marker):].strip()
        for sep in [",", "}", "]", " "]:
            pos = tail.find(sep)
            if pos != -1:
                candidate = tail[:pos].strip().strip("'").strip('"')
                if candidate:
                    return candidate
        return tail.strip().strip("'").strip('"')
    return None

def main():
    parser = argparse.ArgumentParser(description="Enviar .b64 a sign_multistamp y regresar SOLO el id.")
    parser.add_argument("--b64", default=str(BASE_DIR / "cfdi_global40_bueno.b64"),
                        help="Ruta del archivo .b64 (default: ./cfdi_global40_bueno.b64)")
    args = parser.parse_args()

    b64_path = Path(args.b64)
    if not b64_path.exists():
        raise FileNotFoundError(f"No existe el archivo .b64: {b64_path}")

    zip_b64 = b64_path.read_text(encoding="utf-8").strip()

    client = Client(WSDL_ASYNC, cache=None)
    res = client.service.sign_multistamp(file=zip_b64, username=FINKOK_USER, password=FINKOK_PASS)

    wpid = extract_first_id(res)
    if not wpid:
        # Si no hay id, imprime error legible y sale con código ≠ 0
        import sys, json
        sys.stderr.write("No se pudo obtener el id. Respuesta:\n")
        sys.stderr.write(json.dumps(suds_to_builtin(res), ensure_ascii=False, indent=2))
        sys.stderr.write("\n")
        sys.exit(1)

    # Guardar en archivo (por si lo necesitas después)
    (OUT_DIR / "workprocessid.txt").write_text(wpid, encoding="utf-8")

    # IMPORTANTÍSIMO: imprimir SOLO el id en stdout (para pipeo/consumo)
    print(wpid)

if __name__ == "__main__":
    main()
