import base64
import zipfile

# Leer Base64 y convertirlo a ZIP
with open("cfdi_global40_bueno1.b64", "r") as f:
    contenido_b64 = f.read()

zip_bytes = base64.b64decode(contenido_b64)

with open("cfdi_global40_bueno_out.zip", "wb") as f:
    f.write(zip_bytes)

# Descomprimir ZIP
with zipfile.ZipFile("cfdi_global40_bueno_out.zip", "r") as zipf:
    zipf.extractall(".")

print("✅ ZIP generado y descomprimido en la carpeta actual")
