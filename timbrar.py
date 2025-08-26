import os
import base64
import zipfile
import io
from zeep import Client, exceptions as zeep_exceptions

# ===== Configuración de Finkok =====
username = 'ricascor080@gmail.com'
password = 'Ricas002385.'

# URL del servicio asíncrono de Finkok
wsdl_url = "https://demo-facturacion.finkok.com/servicios/soap/async.wsdl"

# ===== Rutas de trabajo =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
XML_BATCH_DIR = os.path.join(BASE_DIR, 'lote_xml')
OUT_DIR = os.path.join(BASE_DIR, 'salida_async')

os.makedirs(XML_BATCH_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

# ===== Preparación del Lote de XMLs en un ZIP =====
xml_files = [os.path.join(XML_BATCH_DIR, f) for f in os.listdir(XML_BATCH_DIR) if f.endswith('.xml')]

if not xml_files:
    print(f"No se encontraron archivos XML en la carpeta: {XML_BATCH_DIR}")
    print("Por favor, coloca los XMLs que deseas timbrar en esa carpeta.")
    exit(1)

# Crea un ZIP en memoria sin guardarlo en el disco
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
    for file_path in xml_files:
        zip_file.write(file_path, os.path.basename(file_path))

# Obtiene el contenido binario del ZIP y lo codifica en Base64
zip_content = zip_buffer.getvalue()
encoded_zip = base64.b64encode(zip_content).decode('utf-8')

# ===== Llamada al servicio asíncrono de Finkok =====
try:
    print("Conectando al servicio asíncrono...")
    client = Client(wsdl_url)

    # Parámetros para la llamada
    params = {
        "file": encoded_zip,  # Envía el ZIP completo en una sola cadena Base64
        "username": username,
        "password": password
    }

    print(f"Enviando un archivo ZIP con {len(xml_files)} XMLs para timbrado asíncrono...")
    result = client.service.sign_multistamp(**params)

    async_res = result
    stamp_id = getattr(async_res, 'stamp_id', None)

    if stamp_id:
        print(f"Lote enviado con éxito. Folio de acuse (stamp_id): {stamp_id}")
        print("Puedes usar este folio para consultar el estado del timbrado más tarde.")
        with open(os.path.join(OUT_DIR, 'stamp_id.txt'), 'w') as f:
            f.write(stamp_id)
    else:
        print("El servicio no devolvió un stamp_id válido.")
        print(f"Mensaje de error: {getattr(async_res, 'incidents', 'N/D')}")

except zeep_exceptions.Fault as e:
    print(f"SOAP Fault al enviar el lote: ({e.code}) {e.message}")
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")