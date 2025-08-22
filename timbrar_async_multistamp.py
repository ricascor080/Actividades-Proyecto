from pathlib import Path
import base64
from typing import Optional
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session

WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

# <<< PON AQUÍ TUS CREDENCIALES >>>
USER = "ricascor080@gmail.com"
PASS = "Ricas002385."

ZIP_PATH = Path("cfdi_global40_pre.zip")  # Debe existir en este directorio


def load_zip_b64() -> str:
    return base64.b64encode(ZIP_PATH.read_bytes()).decode("ascii")


def build_client() -> Client:
    session = Session()
    transport = Transport(session=session, timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)
    return Client(wsdl=WSDL, transport=transport, settings=settings)


def try_multistamp(client: Client, file_b64: str, webhook_obj: Optional[object] = None):
    """
    Intenta multistamp (y luego sign_multistamp) con webhook=None por defecto.
    Si tu WSDL exige webhook con campos, más abajo hay una función para inspeccionar su tipo.
    """
    # 1) Intentar multistamp
    try:
        resp = client.service.multistamp(file=file_b64, username=USER, password=PASS, webhook=webhook_obj)
        print("Usé operación: multistamp")
        return resp
    except Exception as e:
        print(f"multistamp falló: {e}")

    # 2) Intentar sign_multistamp
    try:
        resp = client.service.sign_multistamp(file=file_b64, username=USER, password=PASS, webhook=webhook_obj)
        print("Usé operación: sign_multistamp")
        return resp
    except Exception as e:
        print(f"sign_multistamp también falló: {e}")
        raise


def pretty_print_response(resp):
    print("\n=== RESPUESTA ===")
    for k in dir(resp):
        if k.startswith("_"):
            continue
        try:
            v = getattr(resp, k)
            if not callable(v):
                print(f"{k}: {v}")
        except Exception:
            pass

    # Intenta extraer 'id' del acuse (suele venir como 'id' para luego consultar get_result_multistamp)
    try:
        rid = getattr(resp, "id", None)
        if rid:
            print("\nID de proceso:", rid)
    except Exception:
        pass

    # Imprime incidencias si existen
    try:
        incs = getattr(resp, "Incidencias", None)
        if incs:
            items = []
            if isinstance(incs, list):
                items = incs
            elif hasattr(incs, "Incidencia"):
                items = incs.Incidencia or []
            if items:
                print("\nIncidencias:")
                for i, inc in enumerate(items, 1):
                    try:
                        cod = getattr(inc, "CodigoError", None)
                        msg = getattr(inc, "MensajeIncidencia", None)
                        print(f"  - #{i} CodigoError={cod} Mensaje={msg}")
                    except Exception:
                        print(f"  - #{i} {inc}")
    except Exception:
        pass


def get_result(client: Client, process_id: str):
    """
    Consulta el resultado con get_result_multistamp.
    """
    print(f"\nConsultando resultado para id={process_id} ...")
    resp = client.service.get_result_multistamp(id=process_id, username=USER, password=PASS)
    print("\n=== RESULTADO ===")
    for k in dir(resp):
        if k.startswith("_"):
            continue
        try:
            v = getattr(resp, k)
            if not callable(v):
                print(f"{k}: {v}")
        except Exception:
            pass
    return resp


def inspect_webhook_type(client: Client):
    """
    Si el servidor te exige 'webhook' obligatorio, inspecciona el tipo para ver sus campos.
    Imprime los tipos disponibles que contienen 'webhook' en su nombre y sus atributos.
    """
    print("\n=== TIPOS RELACIONADOS CON 'webhook' ===")
    for qname, xsd_type in client.wsdl.types.types.items():
        name = str(qname.localname).lower()
        if "webhook" in name:
            print(f"\nTipo: {qname}")
            try:
                # Para complexTypes, zeep suele exponer elementos/atributos
                if hasattr(xsd_type, "elements"):
                    for el in xsd_type.elements:
                        print(f"  - campo: {el.attr_name}  xsd: {el.type}")
            except Exception as e:
                print("  (no se pudieron listar campos)", e)


def main():
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"No encuentro {ZIP_PATH.resolve()}")

    client = build_client()
    file_b64 = load_zip_b64()

    # --- Si tu primer intento con webhook=None falla por "webhook requerido",
    # usa inspect_webhook_type(client) para ver los campos y arma uno.
    # Por ejemplo, si imprime un tipo como ns2:multistamp_webhookType con campos 'url' y 'method':
    #
    #   webhook_type = client.get_type("ns2:multistamp_webhookType")
    #   webhook = webhook_type(url="https://tu-callback.tld/finkok", method="POST")
    #
    # y luego pásalo como 'webhook=webhook' en try_multistamp(...)

    # 1) Timbrado async
    resp = try_multistamp(client, file_b64, webhook_obj=None)
    pretty_print_response(resp)

    # 2) Si obtuviste 'id', consulta el resultado
    process_id = getattr(resp, "id", None)
    if process_id:
        get_result(client, process_id)
    else:
        print("\nNo se encontró 'id' en la respuesta. "
              "Si el WSDL exige webhook, ejecuta primero:")
        print("  python3 -c 'import timbrar_async_multistamp as m; "
              "c=m.build_client(); m.inspect_webhook_type(c)'")
        print("y arma el objeto 'webhook' con los campos que imprima.")


if __name__ == "__main__":
    main()
