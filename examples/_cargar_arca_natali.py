import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sos_contador import client_from_env

client = client_from_env(Path(__file__).resolve().parent.parent / ".env")
cuit_id = client.resolver_empresa("Natali")["id"]

with open(Path(__file__).parent / "_devengamientos_natali.json", encoding="utf-8") as f:
    dev = json.load(f)

BANCO_GALICIA = 38206737
IDCENTROCOSTO = 102984
IDPROVINCIAIIBB = 9

pagos = [
    ("IVA", "2025-10", 277995.79, "2025-12-26", "1564140940"),
    ("IVA", "2025-09", 558259.37, "2025-11-25", "1549524664"),
    ("IIBB", "2025-10", 55079.99, "2025-11-25", "1547434835"),
    ("IVA", "2025-08", 73272.82, "2025-10-21", "1535311042"),
    ("IVA", "2025-07", 188689.10, "2025-09-19", "1506618253"),
    ("IVA", "2025-06", 496874.39, "2025-08-22", "1492104564"),
    ("IVA", "2025-05", 600517.70, "2025-07-31", "1480643580"),
    ("IVA", "2025-04", 181294.65, "2025-05-29", "1461600017"),
    ("IIBB", "2025-04", 8272.64, "2025-05-29", "1461598130"),
    ("IIBB", "2025-03", 15321.44, "2025-04-25", "1446325286"),
    ("IVA", "2025-02", 362998.25, "2025-04-21", "1431579555"),
    ("IIBB", "2025-02", 8841.99, "2025-03-28", "1429597457"),
    ("IVA", "2025-01", 54302.33, "2025-03-05", "1415995943"),
    ("IIBB", "2025-01", 19290.28, "2025-02-19", "1413213096"),
]

resultados = []
for tipo, periodo, monto, fecha, vep in pagos:
    d = dev[f"{tipo}|{periodo}"]
    imputaciones = [
        {"cuid": d["cuid_a_pagar"], "fd": f"{monto:.2f}", "fh": "0", "memo": f"Pago {tipo} {periodo} - VEP {vep}"},
        {"cuid": BANCO_GALICIA, "fd": "0", "fh": f"{monto:.2f}", "memo": f"Pago {tipo} {periodo} - VEP {vep}"},
    ]
    resp = client.crear_asiento(
        cuit_id,
        fecha=fecha,
        idcentrocosto=IDCENTROCOSTO,
        idprovinciaiibb=IDPROVINCIAIIBB,
        imputaciones=imputaciones,
        memo=f"Pago {tipo} DJ {periodo[5:7]}/{periodo[2:4]} - ARCA/Interbanking VEP {vep}",
    )
    nuevo_id = resp.get("id")
    resultados.append({"tipo": tipo, "periodo": periodo, "monto": monto, "fecha": fecha, "vep": vep, "id_creado": nuevo_id})
    print(f"{tipo:5s} {periodo}  ${monto:>12,.2f}  {fecha}  -> asiento id {nuevo_id}")

with open(Path(__file__).parent / "_resultado_carga_arca_natali.json", "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)

print(f"\nTotal creados: {len(resultados)}")
