"""
Trae productos/stock desde SOS Contador y los vuelca a un JSON local.

Reemplazá el bloque "TODO: enviar a tu sistema" por la llamada real a tu
base de datos / API interna.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sos_contador import client_from_env  # noqa: E402


def main(empresa: str):
    client = client_from_env()
    cuit_id = client.resolver_empresa(empresa)["id"]

    todos = []
    pagina = 1
    while True:
        resp = client.listar_productos(cuit_id, pagina=pagina, registros=100)
        if isinstance(resp, list):
            registros = resp
        else:
            registros = resp.get("items") or resp.get("data") or resp.get("registros") or []
        if not registros:
            break
        todos.extend(registros)
        if len(registros) < 100:
            break
        pagina += 1

    print(f"Productos traídos de SOS Contador: {len(todos)}")

    # TODO: enviar a tu sistema (ejemplo: guardarlo local mientras tanto)
    out_path = Path(__file__).parent / "productos_sos.json"
    out_path.write_text(json.dumps(todos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado en {out_path}")

    # Ejemplo de creación/actualización de stock en SOS Contador:
    # client.crear_producto(cuit_id, {
    #     "codigo": "1234",
    #     "producto": "Producto nuevo",
    #     "idproductoservicio": 1,
    #     "idunidad": 1,
    #     "idcentrocosto": 3348,
    #     "tasaiva": 21.00,
    #     "precio1": 10.00,
    #     "costo": 5.00,
    #     "visible": True,
    # })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Uso: python sync_productos.py <nombre, CUIT o id de la empresa>")
    main(sys.argv[1])
