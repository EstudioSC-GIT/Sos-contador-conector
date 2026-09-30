"""
Servidor MCP que expone el conector de SOS Contador como herramientas
invocables por Claude (Claude Code / Claude Desktop).

Uso:
    python mcp_server.py

Se registra en Claude vía .mcp.json (ver ese archivo en esta misma carpeta).
Requiere un .env con SOS_USUARIO y SOS_PASSWORD (ver .env.example).

Multi-empresa: esta es una cuenta de estudio/contador, con acceso a varias
empresas (CUITs). Todas las herramientas de datos reciben `empresa`, que
puede ser el nombre (o parte del nombre) de la razón social, el CUIT o el
id interno. Usá sos_listar_empresas() para ver las opciones disponibles.

Alcance (igual que sos_contador/client.py):
- clientes/proveedores: leer, crear, actualizar, borrar
- productos/stock: leer, crear, actualizar, borrar
- puntos de venta: leer, crear, actualizar, borrar
- ventas/facturas: SOLO lectura (listar, detalle, PDF, búsqueda, archivar).
  La API de SOS Contador no permite emitir facturas nuevas.
"""

import base64
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from sos_contador import APIError, AuthenticationError, SOSContadorError, client_from_env  # noqa: E402

mcp = MCPServer("sos-contador")

_client = None


def get_client():
    global _client
    if _client is None:
        _client = client_from_env(Path(__file__).resolve().parent / ".env")
    return _client


def _resolve(empresa: str) -> int:
    return get_client().resolver_empresa(empresa)["id"]


def _safe_call(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except (APIError, AuthenticationError, SOSContadorError) as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------- #
# Empresas
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_listar_empresas() -> Any:
    """Lista todas las empresas (CUITs) a las que tiene acceso esta cuenta de
    SOS Contador. Usá el nombre (o CUIT, o id) devuelto acá como `empresa`
    en el resto de las herramientas."""
    return _safe_call(get_client().listar_empresas)


# ---------------------------------------------------------------------- #
# Clientes / Proveedores
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_listar_clientes(
    empresa: str, cliente: bool = True, proveedor: bool = True, pagina: int = 1, registros: int = 50
) -> Any:
    """Lista clientes y/o proveedores dados de alta en SOS Contador para una empresa."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(
        get_client().listar_clientes,
        cuit_id,
        cliente=cliente,
        proveedor=proveedor,
        pagina=pagina,
        registros=registros,
    )


@mcp.tool()
def sos_crear_cliente(
    empresa: str,
    cuit: str,
    nombre: str,
    idprovincia: int,
    idtipocondicioniva: int,
    email: str = "",
) -> Any:
    """Crea un cliente/proveedor nuevo en SOS Contador, dentro de una empresa."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    datos = {
        "cuit": cuit,
        "clipro": nombre,
        "idprovincia": idprovincia,
        "idtipocondicioniva": idtipocondicioniva,
        "email": email,
    }
    return _safe_call(get_client().crear_cliente, cuit_id, datos)


@mcp.tool()
def sos_actualizar_cliente(empresa: str, id_cliente: int, datos: dict) -> Any:
    """Actualiza un cliente/proveedor existente. `datos` son los campos a modificar
    (cuit, clipro, idprovincia, idtipocondicioniva, email, ...)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().actualizar_cliente, cuit_id, id_cliente, datos)


@mcp.tool()
def sos_eliminar_cliente(empresa: str, id_cliente: int) -> Any:
    """Elimina un cliente/proveedor de SOS Contador. Acción irreversible."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().eliminar_cliente, cuit_id, id_cliente)


# ---------------------------------------------------------------------- #
# Productos / Stock
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_listar_productos(empresa: str, pagina: int = 1, registros: int = 50) -> Any:
    """Lista productos/servicios y su stock en SOS Contador para una empresa."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().listar_productos, cuit_id, pagina=pagina, registros=registros)


@mcp.tool()
def sos_crear_producto(
    empresa: str,
    codigo: str,
    nombre: str,
    idunidad: int,
    idcentrocosto: int,
    tasaiva: float = 21.0,
    precio1: float = 0.0,
    costo: float = 0.0,
    idproductoservicio: int = 1,
    visible: bool = True,
) -> Any:
    """Crea un producto/servicio nuevo en SOS Contador dentro de una empresa."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    datos = {
        "codigo": codigo,
        "producto": nombre,
        "idproductoservicio": idproductoservicio,
        "idunidad": idunidad,
        "idcentrocosto": idcentrocosto,
        "tasaiva": tasaiva,
        "precio1": precio1,
        "costo": costo,
        "visible": visible,
    }
    return _safe_call(get_client().crear_producto, cuit_id, datos)


@mcp.tool()
def sos_actualizar_producto(empresa: str, id_producto: int, datos: dict) -> Any:
    """Actualiza un producto existente. `datos` son los campos a modificar."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().actualizar_producto, cuit_id, id_producto, datos)


@mcp.tool()
def sos_eliminar_producto(empresa: str, id_producto: int) -> Any:
    """Elimina un producto de SOS Contador. Acción irreversible."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().eliminar_producto, cuit_id, id_producto)


# ---------------------------------------------------------------------- #
# Puntos de venta
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_listar_puntos_venta(empresa: str) -> Any:
    """Lista los puntos de venta configurados en SOS Contador para una empresa."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().listar_puntos_venta, cuit_id)


# ---------------------------------------------------------------------- #
# Ventas / Facturas (solo lectura)
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_listar_ventas(
    empresa: str,
    periodo: str,
    modo: str = "todos",
    cae: str = "todos",
    pagina: int = 1,
    registros: int = 50,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
) -> Any:
    """Lista facturas de venta ya emitidas en SOS Contador para una empresa y un
    período (ejercicio contable, ej. '2026'). No permite crear facturas nuevas."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(
        get_client().listar_ventas,
        cuit_id,
        periodo=periodo,
        modo=modo,
        cae=cae,
        pagina=pagina,
        registros=registros,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )


@mcp.tool()
def sos_detalle_venta(empresa: str, id_venta: int) -> Any:
    """Trae el detalle completo de una factura de venta por su id."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().detalle_venta, cuit_id, id_venta)


@mcp.tool()
def sos_buscar_ventas(
    empresa: str,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    numero_desde: int | None = None,
    numero_hasta: int | None = None,
    tipo_factura: list[str] | None = None,
    idclipro: list[int] | None = None,
    pagina: int = 1,
    registros: int = 50,
) -> Any:
    """Busca facturas de venta por filtros (fechas, rango de número,
    tipo de comprobante, cliente)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    filtros = {
        k: v
        for k, v in {
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "numero_desde": numero_desde,
            "numero_hasta": numero_hasta,
            "tipo_factura": tipo_factura,
            "idclipro": idclipro,
        }.items()
        if v is not None
    }
    return _safe_call(get_client().buscar_ventas, cuit_id, filtros, pagina=pagina, registros=registros)


@mcp.tool()
def sos_pdf_venta_base64(empresa: str, id_venta: int) -> Any:
    """Descarga el PDF de una factura de venta y lo devuelve codificado en
    base64 (para guardarlo o mostrarlo del lado de Claude)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    result = _safe_call(get_client().pdf_venta, cuit_id, id_venta)
    if isinstance(result, dict) and "error" in result:
        return result
    return {"filename": f"venta_{id_venta}.pdf", "base64": base64.b64encode(result).decode("ascii")}


@mcp.tool()
def sos_archivar_venta(empresa: str, id_venta: int) -> Any:
    """Archiva una factura de venta existente en SOS Contador."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().archivar_venta, cuit_id, id_venta)


# ---------------------------------------------------------------------- #
# Asientos contables
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_crear_asiento(
    empresa: str,
    fecha: str,
    idcentrocosto: int,
    idprovinciaiibb: int,
    imputaciones: list[dict],
    memo: str = "",
) -> Any:
    """Crea un asiento contable nuevo en SOS Contador. `imputaciones` es una
    lista de {"cuid": id_cuenta_contable, "fd": monto_debe, "fh": monto_haber,
    "memo": opcional (str)} - el asiento debe balancear (suma fd == suma fh)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(
        get_client().crear_asiento,
        cuit_id,
        fecha=fecha,
        idcentrocosto=idcentrocosto,
        idprovinciaiibb=idprovinciaiibb,
        imputaciones=imputaciones,
        memo=memo,
    )


@mcp.tool()
def sos_listar_asientos(empresa: str, periodo: str, pagina: int = 1, registros: int = 50) -> Any:
    """Lista los asientos contables ya cargados en SOS Contador para una
    empresa y un período (ejercicio, ej. '2026')."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().listar_asientos, cuit_id, periodo=periodo, pagina=pagina, registros=registros)


@mcp.tool()
def sos_detalle_asiento(empresa: str, id_asiento: int) -> Any:
    """Trae el detalle completo (líneas, cuentas, importes) de un asiento contable."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().detalle_asiento, cuit_id, id_asiento)


@mcp.tool()
def sos_actualizar_asiento(empresa: str, id_asiento: int, datos: dict) -> Any:
    """Actualiza un asiento contable existente. `datos` son los campos/líneas
    a modificar. Para crear uno nuevo usá sos_crear_asiento."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().actualizar_asiento, cuit_id, id_asiento, datos)


@mcp.tool()
def sos_eliminar_asiento(empresa: str, id_asiento: int) -> Any:
    """Elimina (anula) un asiento contable existente. Es un borrado lógico:
    se puede desanular manualmente desde la web de SOS Contador."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().eliminar_asiento, cuit_id, id_asiento)


# ---------------------------------------------------------------------- #
# Cobros (a clientes)
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_crear_cobro(
    empresa: str,
    fecha: str,
    idclipro: int,
    idcuenta: int,
    idcentrocosto: int,
    idprovinciaiibb: int,
    imputaciones: list[dict],
    memo: str = "",
    referencia: str = "",
) -> Any:
    """Registra un cobro a un cliente en SOS Contador. `idclipro` es el
    cliente (su cuenta corriente de Deudores por Ventas se cancela
    automáticamente por el total). `idcuenta` es la cuenta de fondos (banco
    o caja) que recibe el dinero, y debe coincidir con el `cuid` usado en
    `imputaciones`: [{"cuid": id_cuenta_de_fondos, "fv": monto}, ...]."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(
        get_client().crear_cobro,
        cuit_id,
        fecha=fecha,
        idclipro=idclipro,
        idcuenta=idcuenta,
        idcentrocosto=idcentrocosto,
        idprovinciaiibb=idprovinciaiibb,
        imputaciones=imputaciones,
        memo=memo,
        referencia=referencia,
    )


@mcp.tool()
def sos_listar_cobros(empresa: str, periodo: str, pagina: int = 1, registros: int = 50) -> Any:
    """Lista los cobros ya cargados en SOS Contador para una empresa y un
    período (hoy, ayer, semana, mes, mes_anterior o anio)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().listar_cobros, cuit_id, periodo=periodo, pagina=pagina, registros=registros)


@mcp.tool()
def sos_detalle_cobro(empresa: str, id_cobro: int) -> Any:
    """Trae el detalle completo de un cobro (cliente, cuenta de fondos, importe)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().detalle_cobro, cuit_id, id_cobro)


@mcp.tool()
def sos_actualizar_cobro(empresa: str, id_cobro: int, datos: dict) -> Any:
    """Actualiza un cobro existente. `datos` son los campos a modificar.
    Para crear uno nuevo usá sos_crear_cobro."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().actualizar_cobro, cuit_id, id_cobro, datos)


@mcp.tool()
def sos_eliminar_cobro(empresa: str, id_cobro: int) -> Any:
    """Elimina (anula) un cobro existente. Es un borrado lógico: se puede
    desanular manualmente desde la web de SOS Contador."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().eliminar_cobro, cuit_id, id_cobro)


# ---------------------------------------------------------------------- #
# Pagos (a proveedores)
# ---------------------------------------------------------------------- #
@mcp.tool()
def sos_crear_pago(
    empresa: str,
    fecha: str,
    idclipro: int,
    idcuenta: int,
    idcentrocosto: int,
    idprovinciaiibb: int,
    imputaciones: list[dict],
    memo: str = "",
    referencia: str = "",
) -> Any:
    """Registra un pago a un proveedor (o a un impuesto/tributo, usando su
    cuenta de pasivo) en SOS Contador. `idclipro` es el proveedor. `idcuenta`
    es la cuenta de fondos (banco o caja) usada para pagar, y debe coincidir
    con el `cuid` usado en `imputaciones`: [{"cuid": id_cuenta_de_fondos,
    "fv": monto}, ...]."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(
        get_client().crear_pago,
        cuit_id,
        fecha=fecha,
        idclipro=idclipro,
        idcuenta=idcuenta,
        idcentrocosto=idcentrocosto,
        idprovinciaiibb=idprovinciaiibb,
        imputaciones=imputaciones,
        memo=memo,
        referencia=referencia,
    )


@mcp.tool()
def sos_listar_pagos(empresa: str, periodo: str, pagina: int = 1, registros: int = 50) -> Any:
    """Lista los pagos ya cargados en SOS Contador para una empresa y un
    período (hoy, ayer, semana, mes o mes_anterior)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().listar_pagos, cuit_id, periodo=periodo, pagina=pagina, registros=registros)


@mcp.tool()
def sos_detalle_pago(empresa: str, id_pago: int) -> Any:
    """Trae el detalle completo de un pago (proveedor, cuenta de fondos, importe)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().detalle_pago, cuit_id, id_pago)


@mcp.tool()
def sos_actualizar_pago(empresa: str, id_pago: int, datos: dict) -> Any:
    """Actualiza un pago existente. `datos` son los campos a modificar.
    Para crear uno nuevo usá sos_crear_pago."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().actualizar_pago, cuit_id, id_pago, datos)


@mcp.tool()
def sos_mayor(empresa: str, ejercicio: str, arbol: str, pagina: int = 1, registros: int = 500) -> Any:
    """Trae el mayor contable completo de una cuenta para un ejercicio
    (año calendario, ej. "2026"). `arbol` es el código jerárquico de la
    cuenta (ej. "01.01.01.003.001" para un banco) - se ve en la web de SOS
    Contador al abrir la cuenta, o navegando el plan de cuentas. A
    diferencia de sos_listar_asientos (que en la práctica no siempre
    alcanza todo el año pedido), este es el que hay que usar para
    conciliaciones bancarias y para revisar el movimiento real de una
    cuenta en el período. No trae el id numérico de la cuenta (para eso,
    sos_buscar_cuenta)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().mayor, cuit_id, ejercicio=ejercicio, arbol=arbol, pagina=pagina, registros=registros)


@mcp.tool()
def sos_buscar_cuenta(empresa: str, nombre: str) -> Any:
    """Busca el id numérico de una cuenta contable por nombre (coincidencia
    parcial, ej. "IVA A Pagar" o "Banco Galicia") - necesario para el
    parámetro `cuid` de sos_crear_asiento/sos_crear_cobro/sos_crear_pago.
    No existe un endpoint de "plan de cuentas": esto recorre asientos,
    cobros y pagos ya cargados hasta encontrar la cuenta, así que puede
    tardar unos segundos y solo encuentra cuentas que ya se usaron en algo
    accesible por API. Devuelve {idcuenta: nombre_cuenta} con las
    coincidencias; si no encuentra nada, no hay atajo por API - hay que
    conseguir el id desde la web (herramientas de desarrollador del
    navegador, pestaña Network, al abrir esa cuenta)."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().buscar_cuenta, cuit_id, nombre)


@mcp.tool()
def sos_eliminar_pago(empresa: str, id_pago: int) -> Any:
    """Elimina (anula) un pago existente. Es un borrado lógico: se puede
    desanular manualmente desde la web de SOS Contador."""
    try:
        cuit_id = _resolve(empresa)
    except SOSContadorError as exc:
        return {"error": str(exc)}
    return _safe_call(get_client().eliminar_pago, cuit_id, id_pago)


if __name__ == "__main__":
    mcp.run()
