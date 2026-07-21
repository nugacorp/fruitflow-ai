"""Puertos de repositorio. El dominio y los casos de uso dependen de estos
Protocols; la infraestructura (SQLAlchemy, memoria) los implementa."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Protocol

from backend.domain.cajas.politica import MovimientoCaja
from backend.domain.contrapartes.modelo import Contraparte
from backend.domain.finanzas.modelo import Gasto, Pago
from backend.domain.operaciones.borrador import Borrador
from backend.domain.operaciones.compra import Compra
from backend.domain.operaciones.costeo import Lote
from backend.domain.operaciones.venta import Venta


class RepositorioContrapartes(Protocol):
    async def obtener(self, contraparte_id: uuid.UUID) -> Contraparte | None: ...

    async def listar(self) -> list[Contraparte]: ...

    async def agregar(self, contraparte: Contraparte) -> None: ...

    async def buscar_por_nombre(self, texto: str) -> list[tuple[uuid.UUID, str]]:
        """Catalogo (id, nombre) para el resolutor de alias. En produccion
        usa pg_trgm; el orden de mejor a peor similitud."""
        ...


class RepositorioCompras(Protocol):
    async def obtener(self, compra_id: uuid.UUID) -> Compra | None: ...

    async def agregar(self, compra: Compra) -> int:
        """Persiste y devuelve el folio asignado."""
        ...

    async def actualizar_estado(self, compra_id: uuid.UUID, estado: str) -> None: ...

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Compra]: ...

    async def buscar_por_folio(self, folio: int) -> Compra | None: ...


class RepositorioVentas(Protocol):
    async def obtener(self, venta_id: uuid.UUID) -> Venta | None: ...

    async def agregar(self, venta: Venta) -> int:
        """Persiste y devuelve el folio asignado."""
        ...

    async def actualizar_estado(self, venta_id: uuid.UUID, estado: str) -> None: ...

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Venta]: ...

    async def buscar_por_folio(self, folio: int) -> Venta | None: ...


class RepositorioLotes(Protocol):
    async def disponibles_de(self, producto_id: uuid.UUID) -> list[Lote]:
        """Lotes con cajas_disponibles > 0, ordenados por fecha (FIFO)."""
        ...

    async def agregar(self, *lotes: Lote) -> None: ...

    async def guardar(self, *lotes: Lote) -> None:
        """Persiste el nuevo cajas_disponibles tras consumir o liberar."""
        ...

    async def obtener(self, lote_id: uuid.UUID) -> Lote | None: ...


class RepositorioMovimientosCaja(Protocol):
    async def agregar(self, *movimientos: MovimientoCaja) -> None: ...

    async def saldo(self, contraparte_id: uuid.UUID, tipo_caja_id: uuid.UUID) -> int: ...

    async def saldos_de(self, contraparte_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """Saldo por tipo de caja de una contraparte."""
        ...

    async def de_referencia(
        self, referencia_tipo: str, referencia_id: uuid.UUID
    ) -> list[MovimientoCaja]: ...


class RepositorioPagos(Protocol):
    async def agregar(self, pago: Pago) -> None: ...

    async def listar_por_contraparte(self, contraparte_id: uuid.UUID) -> list[Pago]: ...

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Pago]: ...


class RepositorioBorradores(Protocol):
    async def obtener(self, borrador_id: uuid.UUID) -> Borrador | None: ...

    async def agregar(self, borrador: Borrador) -> None: ...

    async def guardar(self, borrador: Borrador) -> None:
        """Persiste cambios de estado o payload."""
        ...

    async def pendientes(self) -> list[Borrador]: ...

    async def vencidos(self, momento: datetime) -> list[Borrador]:
        """Pendientes cuyo expira_en ya paso."""
        ...


class RepositorioGastos(Protocol):
    async def agregar(self, gasto: Gasto) -> None: ...

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Gasto]: ...


class RepositorioCatalogos(Protocol):
    """Catalogos de referencia (id, nombre) para resolver texto libre de la
    IA y para poblar teclados y tarjetas. Solo lectura."""

    async def productos(self) -> list[tuple[uuid.UUID, str]]: ...

    async def tipos_caja(self) -> list[tuple[uuid.UUID, str]]: ...
