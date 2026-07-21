"""Adaptadores en memoria de los puertos de repositorio.

Permiten probar los casos de uso completos sin PostgreSQL. La version
SQLAlchemy debe pasar exactamente las mismas pruebas (Fase 4).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from types import TracebackType

from backend.domain.cajas.politica import MovimientoCaja
from backend.domain.common.tipos import EstadoOperacion, EventoDominio
from backend.domain.contrapartes.modelo import Contraparte
from backend.domain.finanzas.modelo import Gasto, Pago
from backend.domain.operaciones.borrador import Borrador
from backend.domain.operaciones.compra import Compra
from backend.domain.operaciones.costeo import Lote
from backend.domain.operaciones.venta import Venta


class RepoContrapartesMem:
    def __init__(self) -> None:
        self.datos: dict[uuid.UUID, Contraparte] = {}

    async def obtener(self, contraparte_id: uuid.UUID) -> Contraparte | None:
        return self.datos.get(contraparte_id)

    async def listar(self) -> list[Contraparte]:
        return list(self.datos.values())

    async def agregar(self, contraparte: Contraparte) -> None:
        self.datos[contraparte.id] = contraparte

    async def buscar_por_nombre(self, texto: str) -> list[tuple[uuid.UUID, str]]:
        return [(c.id, c.nombre) for c in self.datos.values()]


class RepoComprasMem:
    def __init__(self) -> None:
        self.datos: dict[uuid.UUID, Compra] = {}
        self._folio = 0

    async def obtener(self, compra_id: uuid.UUID) -> Compra | None:
        return self.datos.get(compra_id)

    async def agregar(self, compra: Compra) -> int:
        self._folio += 1
        self.datos[compra.id] = compra
        return self._folio

    async def actualizar_estado(self, compra_id: uuid.UUID, estado: str) -> None:
        self.datos[compra_id].estado = EstadoOperacion(estado)

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Compra]:
        return [c for c in self.datos.values() if desde <= c.fecha <= hasta]

    async def buscar_por_folio(self, folio: int) -> Compra | None:
        return next((c for c in self.datos.values() if c.folio == folio), None)


class RepoVentasMem:
    def __init__(self) -> None:
        self.datos: dict[uuid.UUID, Venta] = {}
        self._folio = 0

    async def obtener(self, venta_id: uuid.UUID) -> Venta | None:
        return self.datos.get(venta_id)

    async def agregar(self, venta: Venta) -> int:
        self._folio += 1
        self.datos[venta.id] = venta
        return self._folio

    async def actualizar_estado(self, venta_id: uuid.UUID, estado: str) -> None:
        self.datos[venta_id].estado = EstadoOperacion(estado)

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Venta]:
        return [v for v in self.datos.values() if desde <= v.fecha <= hasta]

    async def buscar_por_folio(self, folio: int) -> Venta | None:
        return next((v for v in self.datos.values() if v.folio == folio), None)


class RepoLotesMem:
    def __init__(self) -> None:
        self.datos: dict[uuid.UUID, Lote] = {}

    async def disponibles_de(self, producto_id: uuid.UUID) -> list[Lote]:
        lotes = [
            lote
            for lote in self.datos.values()
            if lote.producto_id == producto_id and lote.cajas_disponibles > 0
        ]
        return sorted(lotes, key=lambda lote: (lote.fecha, str(lote.id)))

    async def agregar(self, *lotes: Lote) -> None:
        for lote in lotes:
            self.datos[lote.id] = lote

    async def guardar(self, *lotes: Lote) -> None:
        for lote in lotes:
            self.datos[lote.id] = lote

    async def obtener(self, lote_id: uuid.UUID) -> Lote | None:
        return self.datos.get(lote_id)


class RepoMovimientosCajaMem:
    def __init__(self) -> None:
        self.datos: list[MovimientoCaja] = []

    async def agregar(self, *movimientos: MovimientoCaja) -> None:
        self.datos.extend(movimientos)

    async def saldo(self, contraparte_id: uuid.UUID, tipo_caja_id: uuid.UUID) -> int:
        return sum(
            m.efecto
            for m in self.datos
            if m.contraparte_id == contraparte_id and m.tipo_caja_id == tipo_caja_id
        )

    async def saldos_de(self, contraparte_id: uuid.UUID) -> dict[uuid.UUID, int]:
        saldos: dict[uuid.UUID, int] = {}
        for m in self.datos:
            if m.contraparte_id == contraparte_id:
                saldos[m.tipo_caja_id] = saldos.get(m.tipo_caja_id, 0) + m.efecto
        return saldos

    async def de_referencia(
        self, referencia_tipo: str, referencia_id: uuid.UUID
    ) -> list[MovimientoCaja]:
        return [
            m
            for m in self.datos
            if m.referencia_tipo == referencia_tipo and m.referencia_id == referencia_id
        ]


class RepoPagosMem:
    def __init__(self) -> None:
        self.datos: list[Pago] = []

    async def agregar(self, pago: Pago) -> None:
        self.datos.append(pago)

    async def listar_por_contraparte(self, contraparte_id: uuid.UUID) -> list[Pago]:
        return [p for p in self.datos if p.contraparte_id == contraparte_id]

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Pago]:
        return [p for p in self.datos if desde <= p.fecha <= hasta]


class RepoBorradoresMem:
    def __init__(self) -> None:
        self.datos: dict[uuid.UUID, Borrador] = {}

    async def obtener(self, borrador_id: uuid.UUID) -> Borrador | None:
        return self.datos.get(borrador_id)

    async def agregar(self, borrador: Borrador) -> None:
        self.datos[borrador.id] = borrador

    async def guardar(self, borrador: Borrador) -> None:
        self.datos[borrador.id] = borrador

    async def pendientes(self) -> list[Borrador]:
        return [b for b in self.datos.values() if b.esta_pendiente]

    async def vencidos(self, momento: datetime) -> list[Borrador]:
        return [b for b in self.datos.values() if b.esta_pendiente and b.esta_vencido(momento)]


class RepoGastosMem:
    def __init__(self) -> None:
        self.datos: list[Gasto] = []

    async def agregar(self, gasto: Gasto) -> None:
        self.datos.append(gasto)

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Gasto]:
        return [g for g in self.datos if desde <= g.fecha <= hasta]


class RepoCatalogosMem:
    def __init__(self) -> None:
        self.productos_datos: dict[uuid.UUID, str] = {}
        self.tipos_caja_datos: dict[uuid.UUID, str] = {}

    async def productos(self) -> list[tuple[uuid.UUID, str]]:
        return list(self.productos_datos.items())

    async def tipos_caja(self) -> list[tuple[uuid.UUID, str]]:
        return list(self.tipos_caja_datos.items())


class UnidadDeTrabajoMem:
    """Cumple el puerto UnidadDeTrabajo. Los eventos confirmados quedan en
    `auditoria`, como quedarian en eventos_auditoria."""

    def __init__(self) -> None:
        self.contrapartes = RepoContrapartesMem()
        self.compras = RepoComprasMem()
        self.ventas = RepoVentasMem()
        self.lotes = RepoLotesMem()
        self.movimientos_caja = RepoMovimientosCajaMem()
        self.pagos = RepoPagosMem()
        self.gastos = RepoGastosMem()
        self.borradores = RepoBorradoresMem()
        self.catalogos = RepoCatalogosMem()
        self.eventos: list[EventoDominio] = []
        self.auditoria: list[EventoDominio] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> UnidadDeTrabajoMem:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        valor: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        if tipo is not None:
            await self.rollback()
        else:
            await self.commit()

    def registrar(self, *eventos: EventoDominio) -> None:
        self.eventos.extend(eventos)

    async def commit(self) -> None:
        self.auditoria.extend(self.eventos)
        self.eventos.clear()
        self.commits += 1

    async def rollback(self) -> None:
        self.eventos.clear()
        self.rollbacks += 1
