"""
Trae facturas de venta ya emitidas en SOS Contador (listado, detalle y PDF)
y las vuelca a un JSON local + descarga los PDFs.

Importante: la API de SOS Contador no permite EMITIR facturas nuevas, solo
leer/buscar/archivar/editar/borrar las que ya existen.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sos_contador import client_from_env  # noqa: E402


def main(empresa: str, periodo: str = "2026"):
    client = client_from_env()
    cuit_id = client.resolver_empresa(empresa)["id"]

    resp = client.listar_ventas(cuit_id, periodo=periodo, registros=100)
    ventas = resp if isinstance(resp, list) else (resp.get("items") or resp.get("data") or resp.get("registros") or [])
    print(f"Ventas del período {periodo}: {len(ventas)}")

    out_dir = Path(__file__).parent / "ventas_sos"
    out_dir.mkdir(exist_ok=True)

    detalles = []
    for venta in ventas:
        id_venta = venta.get("id") or venta.get("idventa")
        if id_venta is None:
            continue
        detalle = client.detalle_venta(cuit_id, id_venta)
        detalles.append(detalle)

        pdf_bytes = client.pdf_venta(cuit_id, id_venta)
        (out_dir / f"venta_{id_venta}.pdf").write_bytes(pdf_bytes)

    (out_dir / "detalles.json").write_text(
        json.dumps(detalles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Detalles y PDFs guardados en {out_dir}")

    # Ejemplo de búsqueda filtrada:
    # resultado = client.buscar_ventas(cuit_id, {
    #     "fecha_desde": "2026-01-01",
    #     "fecha_hasta": "2026-08-19",
    #     "tipo_factura": ["F"],
    # })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python sync_ventas.py <nombre, CUIT o id de la empresa> [periodo]")
    empresa_arg = sys.argv[1]
    periodo_arg = sys.argv[2] if len(sys.argv) > 2 else "2026"
    main(empresa_arg, periodo_arg)
