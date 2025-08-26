# consumir_async_finkok.py
from pathlib import Path
import base64
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session

# --- CONFIG ---
WSDL_ASYNC = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"
USER = "ricascor080@gmail.com"
PASS = "Ricas002385."

# Ruta del ZIP (si ya tienes el .b64, puedes leerlo directo)
ZIP_PATH = Path("cfdi_global40_pre.zip")
# Si prefieres desde .b64: B64_PATH = Path("cfdi_global40_pre.zip.b64")

def cargar_zip_b64():
    # Opción A: leer bytes y convertir aquí
    data = ZIP_PATH.read_bytes()
    return base64.b64encode(data).decode("ascii")

    # Opción B: si ya tienes el archivo .b64
    # return B64_PATH.read_text(encoding="utf-8").strip()

def main():
    # Sugerido para SOAP
    session = Session()
    transport = Transport(session=session, timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)

    client = Client(wsdl=WSDL_ASYNC, transport=transport, settings=settings)

    # ---- (Opcional) inspecciona operaciones disponibles ----
    # for name, op in client.wsdl.services[0].ports.values().__iter__().__next__().binding._operations.items():
    #     print("OP:", name)

    file_b64 = cargar_zip_b64()

    # Algunos tenants exponen el método como uno de estos nombres.
    posibles = [
        "stamp_multi_async",
        "stamps_multi_async",
        "stampMultiAsync",
        "stampsMultiAsync",
        "async_stamp",
        "asyncStamps",
    ]

    respuesta = None
    last_err = None
    for nombre in posibles:
        try:
            metodo = getattr(client.service, nombre)
            # Firma típica: (file, username, password)
            respuesta = metodo(file_b64, USER, PASS)
            print(f"Usando método: {nombre}")
            break
        except AttributeError as e:
            last_err = e
        except Exception as e:
            # Si el método existe pero la firma difiere, imprime y sigue probando
            print(f"Intento con {nombre} falló: {e}")
            last_err = e

    if respuesta is None:
        raise RuntimeError(
            f"No encontré el método asíncrono esperado en {WSDL_ASYNC}. "
            f"Imprime las operaciones disponibles (ver bloque comentado) y elige el correcto. "
            f"Último error: {last_err}"
        )

    # --- Parseo de acuse / incidencias (estructura típica) ---
    # Muchos WSDL de Finkok devuelven objetos tipo "AcuseRecepcionMultiAsync" con:
    #   - Incidencias (arreglo)
    #   - WorkProcessId (GUID)
    #   - FechaRegistro, etc.
    print("=== RESPUESTA ===")
    for k in dir(respuesta):
        if k.startswith("_"):
            continue
        try:
            v = getattr(respuesta, k)
            print(f"{k}: {v}")
        except Exception:
            pass

    # Ejemplo más amigable si existen esos campos:
    try:
        print("\nWorkProcessId:", getattr(respuesta, "WorkProcessId", None))
        incidencias = getattr(respuesta, "Incidencias", None)
        if incidencias:
            print("\nIncidencias:")
            # Puede venir como lista o como objeto con .Incidencia (lista)
            items = []
            if isinstance(incidencias, list):
                items = incidencias
            elif hasattr(incidencias, "Incidencia"):
                items = incidencias.Incidencia or []
            for i, inc in enumerate(items, 1):
                try:
                    print(f"- #{i} CodigoError={inc.CodigoError} Mensaje={inc.MensajeIncidencia}")
                except Exception:
                    print(f"- #{i} {inc}")
    except Exception:
        pass

if __name__ == "__main__":
    main()
