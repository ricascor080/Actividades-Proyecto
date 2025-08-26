#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
from suds.client import Client
import logging
import base64

logging.basicConfig(level=logging.INFO)
logging.getLogger('suds.client').setLevel(logging.DEBUG)

def encode_file_to_base64(filepath):
    """Lee un archivo en modo binario y lo codifica en Base64."""
    try:
        with open(filepath, "rb") as file:
            file_content = file.read()
            encoded_content = base64.b64encode(file_content)
            return encoded_content.decode('utf-8')
    except FileNotFoundError:
        print(f"Error: El archivo no fue encontrado en la ruta: {filepath}")
        return None
    except Exception as e:
        print(f"Ocurrió un error al leer el archivo: {e}")
        return None


# --- Rutas relativas al directorio donde está este script ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))     # carpeta donde está el .py
CANCEL_DIR = os.path.join(BASE_DIR, "cancel")             # subcarpeta "cancel"

# Crear carpeta si no existe
os.makedirs(CANCEL_DIR, exist_ok=True)

cer_path = os.path.join(BASE_DIR, "cer.pem")
key_path = os.path.join(BASE_DIR, "key.pem")

# --- Credenciales ---
username = 'ricascor080@gmail.com'
password = 'Ricas002385.'
taxpayer_id = 'EKU9003173C9'

# Leer y codificar archivos
cer_file = encode_file_to_base64(cer_path)
key_file = encode_file_to_base64(key_path)

if not cer_file or not key_file:
    exit()

# --- Cliente SOAP ---
url = "https://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl"
client = Client(url, cache=None)

# Crear objeto para cancelación
invoices_obj = client.factory.create("ns0:UUID")
invoices_obj._UUID = 'C80C269F-1BF9-5E8D-9F1A-9A40374D6A17'
invoices_obj._Motivo = '02'

UUIDS_list = client.factory.create("ns0:UUIDArray")
UUIDS_list.UUID.append(invoices_obj)

try:
    result = client.service.cancel(UUIDS_list, username, password, taxpayer_id, cer_file, key_file)
    print("Solicitud enviada con éxito. Verifique el resultado:")
    print(result)

    # Guardar request y response en la carpeta "cancel"
    req_path = os.path.join(CANCEL_DIR, "request.xml")
    res_path = os.path.join(CANCEL_DIR, "response.xml")

    with open(req_path, "w", encoding="utf-8") as req_file:
        req_file.write(str(client.last_sent()))

    with open(res_path, "w", encoding="utf-8") as res_file:
        res_file.write(str(client.last_received()))

    print(f"Archivos guardados en: {CANCEL_DIR}")

except Exception as e:
    print("Ocurrió un error al intentar la cancelación:")
    print(e)
    last_response = client.last_received()
    if last_response:
        print("\nÚltima respuesta del servidor:")
        print(last_response)
