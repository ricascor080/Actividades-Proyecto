# poll_multistamp.py
from pathlib import Path
import base64, time, zipfile, io
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session

WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"
USER = "ricascor080@gmail.com"
PASS = "Ricas002385."

# Pon aquí el id que te devolvió multistamp, por ejemplo:
PROCESS_ID = "multistamp_f95fcb0f-b89f-4010-8c6f-d7077b762786"

def build_client():
    session = Session()
    transport = Transport(session=session, timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)
    return Client(wsdl=WSDL, transport=transport, settings=settings)

def save_zip_and_extract(b64_data: str, zip_name="resultado_multistamp.zip", out_dir="resultado_multistamp"):
    raw = base64.b64decode(b64_data)
    Path(zip_name).write_bytes(raw)
    print(f"ZIP guardado: {zip_name} ({len(raw)} bytes)")
    # extraer
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        zf.extractall(out)
        print(f"Archivos extraídos en: {out.resolve()}")
        for n in zf.namelist():
            print(" -", n)

def print_incidencias(obj):
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
            print("Incidencias:")
            for i, inc in enumerate(items, 1):
                cod = getattr(inc, "CodigoError", None)
                msg = getattr(inc, "MensajeIncidencia", None)
                print(f"  #{i} CodigoError={cod}  Mensaje={msg}")
    except Exception:
        pass

def main():
    client = build_client()

    # política de reintentos: 10s, 15s, 20s, ... (máx ~10 min)
    delays = [10,15,20,30,30,45,60,60,60,60,60,60]
    for i, delay in enumerate(delays, 1):
        print(f"\nConsulta #{i} → get_result_multistamp(id={PROCESS_ID})")
        resp = client.service.get_result_multistamp(id=PROCESS_ID, username=USER, password=PASS)

        # imprime campos útiles
        print_incidencias(resp)

        # si ya entregó archivo, guardar y terminar
        file_b64 = getattr(resp, "file", None)
        if file_b64:
            save_zip_and_extract(file_b64)
            print("✅ Proceso finalizado con archivo recibido.")
            return

        # si sigue en ejecución (731), esperamos y volvemos a consultar
        # si hay otros códigos, igual puedes seguir consultando o abortar según tu criterio
        # aquí seguimos a menos que venga algo más grave conocido (705 XML inválido, etc.)
        print(f"Aún sin archivo. Reintentando en {delay} s ...")
        time.sleep(delay)

    print("⛔ Se agotaron los intentos de consulta sin recibir archivo. Intenta más tarde o revisa en el panel.")

if __name__ == "__main__":
    main()
