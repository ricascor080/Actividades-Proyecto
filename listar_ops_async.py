# listar_ops_async.py
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session

WSDL = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

def main():
    session = Session()
    transport = Transport(session=session, timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)
    client = Client(wsdl=WSDL, transport=transport, settings=settings)

    for svc_name, svc in client.wsdl.services.items():
        print(f"[Service] {svc_name}")
        for port_name, port in svc.ports.items():
            print(f"  [Port] {port_name}")
            for op_name, op in port.binding._operations.items():
                sig = op.input.signature(as_output=False)
                print(f"     - {op_name}({sig})")

if __name__ == "__main__":
    main()
