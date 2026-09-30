import csv
from pathlib import Path

# Verificado contra el mayor real de SOS Contador (cta 01.01.01.003.001 Banco) el
# 2026-08-25: de todo lo identificado en la conciliacion, solo estos 2 movimientos
# de julio no tienen asiento cargado. Todo lo demas (transferencias, comisiones/IVA
# via compra Banco Santander, e Impuesto 25.413 via movimiento de fondos mensual,
# tanto junio como julio) ya esta cargado y verificado exacto contra el extracto.
individuales = [
    ("2026-07-13", "Debito transf online banking emp 00720199007000163309ars", 27000.00, "D"),
    ("2026-07-17", "Debito transf online banking - Maria Eugenia Carabelos (honorarios)", 185000.00, "D"),
]

out_dir = Path(__file__).parent
out_path = out_dir / "pendientes_detfa_junio_julio.csv"
with out_path.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["fecha", "concepto", "importe", "tipo", "estado"])
    for fecha, concepto, importe, tipo in individuales:
        w.writerow([fecha, concepto, f"{importe:.2f}", tipo, "PENDIENTE - cargar"])

total = sum((m if t == "C" else -m) for _, _, m, t in individuales)
print(f"Pendientes reales (verificado contra el mayor): {len(individuales)} | neto {total:,.2f}")
print(f"CSV: {out_path}")
