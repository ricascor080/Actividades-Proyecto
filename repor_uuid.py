#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import csv
import sys
import logging
from datetime import datetime
from pathlib import Path
from lxml import etree
from zeep import Client, Settings
from zeep.plugins import HistoryPlugin
from zeep.transports import Transport
from requests import Session

# ======== CONFIGURA AQUÍ ========
USERNAME = "ricascor080@gmail.com"   # <-- CAMBIA
PASSWORD = "Ricas002385."              # <-- CAMBIA
RFC       = "EKU9003173C9"
DATE_FROM = "2025-08-01T00:00:00"
DATE_TO   = "2025-09-01T00:00:00"
INVOICE_TYPE = "I"  # Algunas instalaciones requieren este parámetro, otras no
WSDL_URL = "https://demo-facturacion.finkok.com/servicios/soap/utilities.wsdl"
OUTDIR = Path("./salidas_report_uuid")  # Carpeta destino
# ================================

# Logging detallado
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
for lg in ("zeep.client", "zeep.transports", "zeep.xsd.schema", "zeep.wsdl"):
    logging.getLogger(lg).setLevel(logging.WARNING)

def ensure_outdir():
    OUTDIR.mkdir(parents=True, exist_ok=True)

def save_xml(filename: Path, envelope):
    """Guarda un envelope SOAP (bytes o XML Element) en disco con pretty print."""
    try:
        if isinstance(envelope, bytes):
            root = etree.fromstring(envelope)
        else:
            root = envelope
        xml_bytes = etree.tostring(root, encoding="utf-8", pretty_print=True, xml_declaration=True)
        filename.write_bytes(xml_bytes)
        logging.info(f"📝 Guardado: {filename}")
    except Exception as e:
        logging.warning(f"No se pudo guardar {filename.name}: {e}")

def main():
    ensure_outdir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Preparar cliente Zeep con historial para capturar SOAP crudo
    history = HistoryPlugin()
    session = Session()
    session.verify = True  # Cambia a False solo para depurar (no recomendado en prod)
    transport = Transport(session=session, timeout=60)
    settings = Settings(strict=False, xml_huge_tree=True)

    client = Client(WSDL_URL, transport=transport, settings=settings, plugins=[history])

    # Intentar con y sin invoice_type automáticamente
    respuesta = None
    tried_signatures = []

    try:
        logging.info("Intentando firma: report_uuid(username, password, rfc, date_from, date_to, invoice_type)")
        respuesta = client.service.report_uuid(USERNAME, PASSWORD, RFC, DATE_FROM, DATE_TO, INVOICE_TYPE)
        tried_signatures.append("con_invoice_type")
    except Exception as e1:
        logging.warning(f"No funcionó con invoice_type ({e1}). Probando sin invoice_type…")
        try:
            logging.info("Intentando firma: report_uuid(username, password, rfc, date_from, date_to)")
            respuesta = client.service.report_uuid(USERNAME, PASSWORD, RFC, DATE_FROM, DATE_TO)
            tried_signatures.append("sin_invoice_type")
        except Exception as e2:
            logging.error("Fallo ambas firmas de report_uuid.")
            logging.error(f"Error con invoice_type: {e1}")
            logging.error(f"Error sin invoice_type: {e2}")
            # Guardar igual el último request/response si existen, para diagnóstico
            if history.last_sent:
                save_xml(OUTDIR / f"soap_request_error_{ts}.xml", history.last_sent["envelope"])
            if history.last_received:
                save_xml(OUTDIR / f"soap_response_error_{ts}.xml", history.last_received["envelope"])
            sys.exit(1)

    # Guardar SOAP crudo (request/response)
    if history.last_sent:
        save_xml(OUTDIR / f"soap_report_uuid_request_{ts}.xml", history.last_sent["envelope"])
    if history.last_received:
        save_xml(OUTDIR / f"soap_report_uuid_response_{ts}.xml", history.last_received["envelope"])

    # Rutas de salida de datos
    txt_path = OUTDIR / f"Report_uuid_{ts}.txt"
    csv_path = OUTDIR / f"Report_uuid_{ts}.csv"

    # Extraer datos
    invoices = []
    try:
        # Estructura esperada: respuesta.invoices.ReportUUID (puede ser lista o un solo objeto)
        inv_container = getattr(respuesta, "invoices", None)
        if inv_container is None:
            logging.info("Sin nodo 'invoices' en la respuesta. No hay resultados.")
        else:
            report_list = getattr(inv_container, "ReportUUID", None)
            if report_list:
                # Normalizar a lista
                if not isinstance(report_list, (list, tuple)):
                    report_list = [report_list]
                for it in report_list:
                    invoices.append({
                        "uuid": getattr(it, "uuid", ""),
                        "taxpayer_id": getattr(it, "taxpayer_id", ""),
                        "rtaxpayer_id": getattr(it, "rtaxpayer_id", ""),
                        "date": getattr(it, "date", ""),
                        "total": getattr(it, "total", ""),
                    })
    except Exception as e:
        logging.warning(f"No se pudieron parsear las facturas: {e}")

    # Guardar TXT (formato solicitado)
    with open(txt_path, "w", encoding="utf-8") as f:
        if not invoices:
            f.write("SIN RESULTADOS\n")
        else:
            for it in invoices:
                f.write(f"FECHA: {it['date']}\n")
                f.write(f"UUID: {it['uuid']}\n\n")
    logging.info(f"✅ TXT generado: {txt_path}")

    # Guardar CSV (útil para Excel)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["uuid", "taxpayer_id", "rtaxpayer_id", "date", "total"])
        writer.writeheader()
        writer.writerows(invoices)
    logging.info(f"✅ CSV generado: {csv_path}")

    # Resumen rápido
    logging.info(f"Intentos de firma: {', '.join(tried_signatures)}")
    logging.info(f"Total de UUIDs: {len(invoices)}")

if __name__ == "__main__":
    main()
