"""Cliente HTTP del bot hacia la API interna. El bot nunca toca la BD."""

from __future__ import annotations

from typing import Any

import httpx

from backend.config import get_settings


class ErrorAPI(Exception):
    """Error de dominio devuelto por la API (422). Se muestra al usuario."""

    def __init__(self, codigo: str, detalle: str, sugerencia: str | None = None) -> None:
        super().__init__(detalle)
        self.codigo = codigo
        self.detalle = detalle
        self.sugerencia = sugerencia

    @property
    def texto(self) -> str:
        return f"{self.detalle} {self.sugerencia}" if self.sugerencia else self.detalle


class ApiInterna:
    """Envoltura de httpx con la llave interna. Una instancia por proceso."""

    def __init__(self, base_url: str | None = None, llave: str | None = None) -> None:
        settings = get_settings()
        self._http = httpx.AsyncClient(
            base_url=base_url or settings.api_base_url,
            headers={"X-Internal-Key": llave or settings.internal_api_key},
            timeout=httpx.Timeout(15.0),
        )

    async def cerrar(self) -> None:
        await self._http.aclose()

    async def _pedir(
        self,
        metodo: str,
        ruta: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        respuesta = await self._http.request(metodo, ruta, json=json, params=params)
        if respuesta.status_code == 422:
            datos = respuesta.json()
            raise ErrorAPI(
                codigo=str(datos.get("codigo", "DOM-000")),
                detalle=str(datos.get("detalle", "La operacion no es valida.")),
                sugerencia=datos.get("sugerencia"),
            )
        if respuesta.status_code == 404:
            datos = respuesta.json()
            raise ErrorAPI(codigo="HTTP-404", detalle=str(datos.get("detail", "No encontrado.")))
        respuesta.raise_for_status()
        return respuesta.json()

    # --- borradores (RN-01) ---

    async def crear_borrador(
        self,
        *,
        intencion: str,
        payload: dict[str, Any],
        faltantes: list[str] | None = None,
        preguntas: list[str] | None = None,
        confianza: float | None = None,
    ) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {
            "intencion": intencion,
            "payload": payload,
            "faltantes": faltantes or [],
            "preguntas": preguntas or [],
        }
        if confianza is not None:
            cuerpo["confianza"] = confianza
        resultado: dict[str, Any] = await self._pedir("POST", "/v1/borradores", json=cuerpo)
        return resultado

    async def obtener_borrador(self, borrador_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir("GET", f"/v1/borradores/{borrador_id}")
        return resultado

    async def borradores_pendientes(self) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = await self._pedir("GET", "/v1/borradores/pendientes")
        return resultado

    async def editar_borrador(self, borrador_id: str, cambios: dict[str, Any]) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir(
            "PATCH", f"/v1/borradores/{borrador_id}", json={"cambios": cambios}
        )
        return resultado

    async def confirmar_borrador(self, borrador_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir(
            "POST", f"/v1/borradores/{borrador_id}/confirmar"
        )
        return resultado

    async def cancelar_borrador(self, borrador_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir(
            "POST", f"/v1/borradores/{borrador_id}/cancelar"
        )
        return resultado

    # --- consultas ---

    async def catalogos(self) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir("GET", "/v1/catalogos")
        return resultado

    async def tablero_cajas(self) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = await self._pedir("GET", "/v1/saldos/cajas")
        return resultado

    async def saldo_cajas(self, contraparte_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir("GET", f"/v1/saldos/cajas/{contraparte_id}")
        return resultado

    async def cuentas_por_cobrar(self, cliente_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir("GET", f"/v1/saldos/cxc/{cliente_id}")
        return resultado

    async def cuentas_por_pagar(self, proveedor_id: str) -> dict[str, Any]:
        resultado: dict[str, Any] = await self._pedir("GET", f"/v1/saldos/cxp/{proveedor_id}")
        return resultado


_instancia: ApiInterna | None = None


def api() -> ApiInterna:
    global _instancia
    if _instancia is None:
        _instancia = ApiInterna()
    return _instancia
