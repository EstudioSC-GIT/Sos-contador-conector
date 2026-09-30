"""
Cliente para la API "api-comunidad" de SOS Contador.

Documentación oficial: https://ayuda.sos-contador.com.ar/mas-funcionalidades-de-sos/SOS-Contador-tiene-API
Colección Postman:     https://documenter.getpostman.com/view/1566360/SWTD6vnC

Importante:
- Esta es una cuenta de estudio/contador: un mismo usuario tiene acceso a
  varias empresas (CUITs). Cada operación de datos recibe qué empresa
  usar (por nombre, CUIT o id interno) y el cliente resuelve/cachea el
  token correspondiente a esa empresa.
- La API permite leer, buscar, archivar, editar y borrar comprobantes de
  venta/compra ya existentes, pero NO permite crearlos (no confirmado lo
  contrario en la documentación). La emisión de facturas se hace desde la
  aplicación de SOS Contador.
- Asiento, pago y cobro SÍ permiten crear registros nuevos: la documentación
  aclara que el mismo PUT usado para editar (sin id en la URL / sin
  idcomprobante en el body) sirve para crear. Confirmado en vivo para
  asiento (crear + verificar + borrar exitoso).
"""

from __future__ import annotations

import requests

from .exceptions import APIError, AuthenticationError, SOSContadorError

DEFAULT_BASE_URL = "https://api.sos-contador.com/api-comunidad"

# Nombres de campo observados en la respuesta real de /login: {"jwt": "...", "cuits": [...]}.
# Se dejan alternativas por si otra cuenta devuelve un nombre distinto.
_TOKEN_KEYS = ("jwt", "token", "access_token", "accessToken")


def _extract_token(data: dict) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in _TOKEN_KEYS:
        if data.get(key):
            return data[key]
    return None


class SOSContadorClient:
    def __init__(
        self,
        usuario: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
    ):
        self.usuario = usuario
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self._session = requests.Session()
        self._user_token: str | None = None
        self._empresas: list[dict] | None = None
        self._cuit_tokens: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Autenticación
    # ------------------------------------------------------------------ #
    def login(self) -> str:
        """POST /login -> token de usuario + listado de empresas (CUITs) accesibles."""
        resp = self._session.post(
            f"{self.base_url}/login",
            json={"usuario": self.usuario, "password": self.password},
            timeout=self.timeout,
        )
        if not resp.ok:
            raise AuthenticationError(f"Login falló ({resp.status_code}): {resp.text}")
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            raise AuthenticationError(
                f"Login rechazado por SOS Contador: {data['error']}. "
                f"Revisá SOS_USUARIO/SOS_PASSWORD en el .env."
            )
        token = _extract_token(data)
        if not token:
            raise AuthenticationError(
                f"Login OK pero no reconozco el campo del token en la respuesta: {data}. "
                f"Agregá el nombre correcto a _TOKEN_KEYS en client.py."
            )
        self._user_token = token
        self._empresas = data.get("cuits", [])
        return token

    def listar_empresas(self) -> list[dict]:
        """Devuelve [{id, cuit, razonsocial}, ...] de las empresas accesibles."""
        if self._empresas is None:
            self.login()
        return self._empresas

    def resolver_empresa(self, query: str | int) -> dict:
        """Encuentra una empresa por id interno, CUIT o nombre (coincidencia parcial,
        sin importar mayúsculas/minúsculas). Lanza error si no matchea o si es ambiguo."""
        empresas = self.listar_empresas()
        q = str(query).strip().lower()

        for e in empresas:
            if str(e["id"]) == q or str(e["cuit"]) == q:
                return e

        matches = [e for e in empresas if q in e["razonsocial"].lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise SOSContadorError(f"No encontré ninguna empresa que coincida con '{query}'.")
        listado = ", ".join(f"{e['razonsocial']} (id={e['id']})" for e in matches[:10])
        raise SOSContadorError(
            f"'{query}' coincide con {len(matches)} empresas: {listado}. "
            f"Especificá mejor el nombre, el CUIT o el id."
        )

    def _cuit_token(self, cuit_id) -> str:
        cuit_id = str(cuit_id)
        if cuit_id in self._cuit_tokens:
            return self._cuit_tokens[cuit_id]
        if not self._user_token:
            self.login()
        resp = self._session.get(
            f"{self.base_url}/cuit/credentials/{cuit_id}",
            headers={"Authorization": f"Bearer {self._user_token}"},
            timeout=self.timeout,
        )
        if not resp.ok:
            raise AuthenticationError(
                f"No se pudo obtener token de CUIT {cuit_id} ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        token = _extract_token(data)
        if not token:
            raise AuthenticationError(
                f"cuit/credentials OK pero no reconozco el campo del token en la "
                f"respuesta: {data}. Agregá el nombre correcto a _TOKEN_KEYS en client.py."
            )
        self._cuit_tokens[cuit_id] = token
        return token

    # ------------------------------------------------------------------ #
    # Request helper
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, *, cuit_id, retry_on_401: bool = True, **kwargs):
        token = self._cuit_token(cuit_id)
        headers = kwargs.pop("headers", {}) or {}
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")

        resp = self._session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )

        if resp.status_code == 401 and retry_on_401:
            # Token vencido: invalidar cache de esa empresa (y del usuario) y reintentar una vez.
            self._cuit_tokens.pop(str(cuit_id), None)
            self._user_token = None
            return self._request(method, path, cuit_id=cuit_id, retry_on_401=False, **kwargs)

        if not resp.ok:
            try:
                payload = resp.json()
            except ValueError:
                payload = resp.text
            raise APIError(resp.status_code, str(payload), payload)

        if resp.content and "application/json" in resp.headers.get("Content-Type", ""):
            return resp.json()
        return resp.content

    # ------------------------------------------------------------------ #
    # Clientes / Proveedores
    # ------------------------------------------------------------------ #
    def listar_clientes(
        self, cuit_id, *, cliente: bool = True, proveedor: bool = True, pagina: int = 1, registros: int = 50
    ):
        return self._request(
            "GET",
            "/cliente/listado",
            cuit_id=cuit_id,
            params={
                "cliente": str(cliente).lower(),
                "proveedor": str(proveedor).lower(),
                "pagina": pagina,
                "registros": registros,
            },
        )

    def crear_cliente(self, cuit_id, datos: dict):
        """datos: cuit, clipro, idprovincia, idtipocondicioniva, email, ..."""
        return self._request("POST", "/cliente", cuit_id=cuit_id, json=datos)

    def actualizar_cliente(self, cuit_id, id_cliente: int, datos: dict):
        return self._request("PUT", f"/cliente/{id_cliente}", cuit_id=cuit_id, json=datos)

    def eliminar_cliente(self, cuit_id, id_cliente: int):
        return self._request("DELETE", f"/cliente/{id_cliente}", cuit_id=cuit_id)

    # ------------------------------------------------------------------ #
    # Productos / Stock
    # ------------------------------------------------------------------ #
    def listar_productos(self, cuit_id, *, pagina: int = 1, registros: int = 50):
        return self._request(
            "GET", "/producto/listado", cuit_id=cuit_id, params={"pagina": pagina, "registros": registros}
        )

    def crear_producto(self, cuit_id, datos: dict):
        """datos: codigo, producto, idproductoservicio, idunidad, idcentrocosto,
        idgrupomodi, tasaiva, precio1..5, costo, excluirIIBB, memo, visible."""
        return self._request("POST", "/producto", cuit_id=cuit_id, json=datos)

    def actualizar_producto(self, cuit_id, id_producto: int, datos: dict):
        return self._request("PUT", f"/producto/{id_producto}", cuit_id=cuit_id, json=datos)

    def eliminar_producto(self, cuit_id, id_producto: int):
        return self._request("DELETE", f"/producto/{id_producto}", cuit_id=cuit_id)

    # ------------------------------------------------------------------ #
    # Puntos de venta
    # ------------------------------------------------------------------ #
    def listar_puntos_venta(self, cuit_id):
        return self._request("GET", "/puntoventa/listado", cuit_id=cuit_id)

    def crear_punto_venta(self, cuit_id, datos: dict):
        return self._request("POST", "/puntoventa", cuit_id=cuit_id, json=datos)

    def actualizar_punto_venta(self, cuit_id, id_punto_venta: int, datos: dict):
        return self._request("PUT", f"/puntoventa/{id_punto_venta}", cuit_id=cuit_id, json=datos)

    def eliminar_punto_venta(self, cuit_id, id_punto_venta: int):
        return self._request("DELETE", f"/puntoventa/{id_punto_venta}", cuit_id=cuit_id)

    # ------------------------------------------------------------------ #
    # Ventas / Facturas (solo lectura: la API no permite crearlas)
    # ------------------------------------------------------------------ #
    def listar_ventas(
        self,
        cuit_id,
        *,
        periodo: str,
        modo: str = "todos",
        cae: str = "todos",
        pagina: int = 1,
        registros: int = 50,
        fecha_desde: str | None = None,
        fecha_hasta: str | None = None,
    ):
        """periodo con formato del ejercicio contable, p.ej. '2026'."""
        params = {"pagina": pagina, "registros": registros}
        if fecha_desde:
            params["fecha_desde"] = fecha_desde
        if fecha_hasta:
            params["fecha_hasta"] = fecha_hasta
        return self._request(
            "GET", f"/venta/listado/{modo}/{periodo}/{cae}", cuit_id=cuit_id, params=params
        )

    def detalle_venta(self, cuit_id, id_venta: int):
        return self._request("GET", f"/venta/detalle/{id_venta}", cuit_id=cuit_id)

    def pdf_venta(self, cuit_id, id_venta: int) -> bytes:
        return self._request("GET", f"/venta/pdf/{id_venta}", cuit_id=cuit_id)

    def buscar_ventas(self, cuit_id, filtros: dict, *, pagina: int = 1, registros: int = 50):
        """filtros: fecha_desde, fecha_hasta, numero_desde, numero_hasta,
        sucursal (lista), tipo_factura (lista), idclipro (lista)."""
        return self._request(
            "POST",
            "/venta/consulta",
            cuit_id=cuit_id,
            params={"pagina": pagina, "registros": registros},
            json=filtros,
        )

    def archivar_venta(self, cuit_id, id_venta: int):
        return self._request("PUT", f"/venta/archivar/{id_venta}", cuit_id=cuit_id)

    # ------------------------------------------------------------------ #
    # Asientos contables
    #
    # PUT /asiento (sin id) CREA un asiento nuevo. PUT /asiento/:id (con
    # idcomprobante en el body) MODIFICA uno existente. Confirmado contra la
    # documentación oficial y probado en vivo (crear + verificar + borrar).
    # ------------------------------------------------------------------ #
    def listar_asientos(self, cuit_id, *, periodo: str, pagina: int = 1, registros: int = 50):
        return self._request(
            "GET", f"/asiento/listado/{periodo}", cuit_id=cuit_id,
            params={"pagina": pagina, "registros": registros},
        )

    def detalle_asiento(self, cuit_id, id_asiento: int):
        return self._request("GET", f"/asiento/detalle/{id_asiento}", cuit_id=cuit_id)

    def crear_asiento(
        self,
        cuit_id,
        *,
        fecha: str,
        idcentrocosto: int,
        idprovinciaiibb: int,
        imputaciones: list[dict],
        memo: str = "",
    ):
        """Crea un asiento contable nuevo.

        imputaciones: lista de {"cuid": id_cuenta_contable, "fd": monto_debe,
        "fh": monto_haber, "memo": opcional}. El asiento debe balancear
        (suma de fd == suma de fh).
        """
        datos = {
            "fecha": fecha,
            "memo": memo,
            "idcentrocosto": idcentrocosto,
            "idprovinciaiibb": idprovinciaiibb,
            "imputaciones": imputaciones,
        }
        return self._request("PUT", "/asiento", cuit_id=cuit_id, json=datos)

    def actualizar_asiento(self, cuit_id, id_asiento: int, datos: dict):
        return self._request("PUT", f"/asiento/{id_asiento}", cuit_id=cuit_id, json=datos)

    def eliminar_asiento(self, cuit_id, id_asiento: int):
        return self._request("DELETE", f"/asiento/{id_asiento}", cuit_id=cuit_id)

    def mayor(self, cuit_id, *, ejercicio: str, arbol: str, pagina: int = 1, registros: int = 500):
        """Mayor contable de una cuenta para un ejercicio (año calendario,
        p.ej. '2026'). `arbol` es el código jerárquico de la cuenta (p.ej.
        '01.01.01.003.001'), no el id numérico. A diferencia de
        listar_asientos (limitado a hoy/ayer/semana/mes/mes_anterior/anio,
        y 'anio' no siempre alcanza todo el año en la práctica), este
        endpoint sí trae el movimiento completo del ejercicio pedido - es
        la fuente confiable para conciliaciones. No expone el id numérico
        de la cuenta en la respuesta (para eso, ver buscar_cuenta)."""
        return self._request(
            "GET", f"/mayor/listado/{ejercicio}", cuit_id=cuit_id,
            params={"arbol": arbol, "pagina": pagina, "registros": registros},
        )

    # ------------------------------------------------------------------ #
    # Pagos y cobros (mismo patrón que asiento: PUT sin id crea nuevo)
    # ------------------------------------------------------------------ #
    def crear_pago(
        self,
        cuit_id,
        *,
        fecha: str,
        idclipro: int,
        idcuenta: int,
        idcentrocosto: int,
        idprovinciaiibb: int,
        imputaciones: list[dict],
        memo: str = "",
        referencia: str = "",
    ):
        """Registra un pago. idclipro: proveedor (su cuenta corriente de
        Proveedores se cancela automáticamente por el total). idcuenta:
        cuenta de fondos (banco/caja) usada, debe coincidir con el cuid
        usado en imputaciones: [{"cuid": id_cuenta_de_fondos, "fv":
        monto}, ...]."""
        datos = {
            "fecha": fecha,
            "idclipro": idclipro,
            "idcuenta": idcuenta,
            "idcentrocosto": idcentrocosto,
            "idprovinciaiibb": idprovinciaiibb,
            "memo": memo,
            "referencia": referencia,
            "imputaciones": imputaciones,
        }
        return self._request("PUT", "/pago", cuit_id=cuit_id, json=datos)

    def actualizar_pago(self, cuit_id, id_pago: int, datos: dict):
        return self._request("PUT", f"/pago/{id_pago}", cuit_id=cuit_id, json=datos)

    def eliminar_pago(self, cuit_id, id_pago: int):
        return self._request("DELETE", f"/pago/{id_pago}", cuit_id=cuit_id)

    def listar_pagos(self, cuit_id, *, periodo: str, pagina: int = 1, registros: int = 50):
        return self._request(
            "GET", f"/pago/listado/{periodo}", cuit_id=cuit_id,
            params={"pagina": pagina, "registros": registros},
        )

    def detalle_pago(self, cuit_id, id_pago: int):
        return self._request("GET", f"/pago/detalle/{id_pago}", cuit_id=cuit_id)

    def crear_cobro(
        self,
        cuit_id,
        *,
        fecha: str,
        idclipro: int,
        idcuenta: int,
        idcentrocosto: int,
        idprovinciaiibb: int,
        imputaciones: list[dict],
        memo: str = "",
        referencia: str = "",
    ):
        """Registra un cobro. idclipro: cliente (su cuenta corriente de
        Deudores Por Ventas se cancela automáticamente por el total).
        idcuenta: cuenta de fondos (banco/caja) que recibe el dinero, debe
        coincidir con el cuid usado en imputaciones: [{"cuid":
        id_cuenta_de_fondos, "fv": monto}, ...]."""
        datos = {
            "fecha": fecha,
            "idclipro": idclipro,
            "idcuenta": idcuenta,
            "idcentrocosto": idcentrocosto,
            "idprovinciaiibb": idprovinciaiibb,
            "memo": memo,
            "referencia": referencia,
            "imputaciones": imputaciones,
        }
        return self._request("PUT", "/cobro", cuit_id=cuit_id, json=datos)

    def actualizar_cobro(self, cuit_id, id_cobro: int, datos: dict):
        return self._request("PUT", f"/cobro/{id_cobro}", cuit_id=cuit_id, json=datos)

    def eliminar_cobro(self, cuit_id, id_cobro: int):
        return self._request("DELETE", f"/cobro/{id_cobro}", cuit_id=cuit_id)

    def listar_cobros(self, cuit_id, *, periodo: str, pagina: int = 1, registros: int = 50):
        return self._request(
            "GET", f"/cobro/listado/{periodo}", cuit_id=cuit_id,
            params={"pagina": pagina, "registros": registros},
        )

    def detalle_cobro(self, cuit_id, id_cobro: int):
        return self._request("GET", f"/cobro/detalle/{id_cobro}", cuit_id=cuit_id)

    # ------------------------------------------------------------------ #
    # Búsqueda de cuentas contables por nombre
    # ------------------------------------------------------------------ #
    def buscar_cuenta(self, cuit_id, nombre: str, *, max_revisadas: int = 150):
        """Busca el id numérico de una o más cuentas contables por nombre
        (coincidencia parcial, sin distinguir mayúsculas). No existe ningún
        endpoint de "plan de cuentas" en la API (ni tampoco en la web de SOS
        Contador, que solo muestra nombre/código de árbol, nunca el id
        numérico), así que esto recorre asientos, cobros y pagos ya
        cargados, alcanzables por API, hasta encontrar una cuenta cuyo
        nombre coincida. Si la cuenta nunca fue usada en ninguna de esas
        transacciones, no hay forma de encontrar su id por esta vía.

        Devuelve {idcuenta: nombre_cuenta} con las coincidencias encontradas.
        """
        objetivo = nombre.strip().lower()
        encontradas: dict[int, str] = {}
        revisadas = 0

        def _scan(imputaciones):
            nonlocal revisadas
            for imp in imputaciones or []:
                idcuenta = imp.get("idcuenta")
                cuenta = imp.get("cuenta") or ""
                if idcuenta and objetivo in cuenta.lower():
                    encontradas[idcuenta] = cuenta

        fuentes = [
            ("asiento", ("hoy", "ayer", "semana", "mes", "mes_anterior", "anio"),
             self.listar_asientos, self.detalle_asiento),
            ("cobro", ("hoy", "ayer", "semana", "mes", "mes_anterior", "anio"),
             self.listar_cobros, self.detalle_cobro),
            ("pago", ("hoy", "ayer", "semana", "mes", "mes_anterior"),
             self.listar_pagos, self.detalle_pago),
        ]

        for _tipo, periodos, listar, detalle in fuentes:
            for periodo in periodos:
                if revisadas >= max_revisadas or len(encontradas) >= 8:
                    break
                try:
                    resp = listar(cuit_id, periodo=periodo, pagina=1, registros=100)
                except Exception:
                    continue
                items = resp.get("items", []) if isinstance(resp, dict) else []
                for it in items:
                    idmov = it.get("id")
                    if not idmov or revisadas >= max_revisadas:
                        continue
                    try:
                        d = detalle(cuit_id, idmov)
                    except Exception:
                        continue
                    revisadas += 1
                    if isinstance(d, dict) and "imputaciones" in d:
                        _scan(d["imputaciones"])
                    if len(encontradas) >= 8:
                        break
            if revisadas >= max_revisadas or len(encontradas) >= 8:
                break

        return encontradas
