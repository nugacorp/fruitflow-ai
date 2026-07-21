"""Adaptadores SQLAlchemy de los puertos de repositorio (FASE 4).

Mapean el ORM (infrastructure/db/models.py) hacia y desde las entidades
puras del dominio. Deben pasar exactamente las mismas pruebas que los
adaptadores en memoria (tests/fakes.py).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.domain.cajas.politica import MovimientoCaja, TipoMovimientoCaja
from backend.domain.common.tipos import (
    Dinero,
    EstadoOperacion,
    TipoContraparte,
    UnidadPrecio,
)
from backend.domain.contrapartes.modelo import Contraparte
from backend.domain.finanzas.modelo import DireccionPago, Gasto, Pago
from backend.domain.operaciones.borrador import Borrador, EstadoBorrador
from backend.domain.operaciones.compra import Compra, LineaCompra
from backend.domain.operaciones.costeo import Asignacion, Lote
from backend.domain.operaciones.venta import LineaVenta, Venta
from backend.infrastructure.db import models


class _RepoBase:
    def __init__(self, sesion: AsyncSession, empresa_id: uuid.UUID) -> None:
        self.sesion = sesion
        self.empresa_id = empresa_id


# --- contrapartes ---


def _contraparte_a_dominio(m: models.Contraparte) -> Contraparte:
    return Contraparte(
        nombre=m.nombre,
        tipo=TipoContraparte(m.tipo),
        cajas_retornables=m.cajas_retornables,
        dias_credito=m.dias_credito,
        estado=m.estado,
        id=m.id,
    )


class RepoContrapartesSQL(_RepoBase):
    async def obtener(self, contraparte_id: uuid.UUID) -> Contraparte | None:
        m = await self.sesion.get(models.Contraparte, contraparte_id)
        return _contraparte_a_dominio(m) if m else None

    async def listar(self) -> list[Contraparte]:
        filas = await self.sesion.scalars(
            select(models.Contraparte)
            .where(models.Contraparte.empresa_id == self.empresa_id)
            .order_by(models.Contraparte.nombre)
        )
        return [_contraparte_a_dominio(m) for m in filas]

    async def agregar(self, contraparte: Contraparte) -> None:
        self.sesion.add(
            models.Contraparte(
                id=contraparte.id,
                empresa_id=self.empresa_id,
                nombre=contraparte.nombre,
                tipo=contraparte.tipo.value,
                cajas_retornables=contraparte.cajas_retornables,
                dias_credito=contraparte.dias_credito,
                estado=contraparte.estado,
            )
        )

    async def buscar_por_nombre(self, texto: str) -> list[tuple[uuid.UUID, str]]:
        """Busqueda difusa con pg_trgm (RN-09): nombre o alias, mejor primero."""
        consulta = text(
            """
            SELECT c.id, c.nombre,
                   GREATEST(
                       word_similarity(:txt, c.nombre),
                       COALESCE(MAX(word_similarity(:txt, a.alias)), 0)
                   ) AS puntaje
            FROM contrapartes c
            LEFT JOIN contraparte_alias a ON a.contraparte_id = c.id
            WHERE c.empresa_id = :empresa
            GROUP BY c.id, c.nombre
            ORDER BY puntaje DESC
            LIMIT 10
            """
        )
        filas = await self.sesion.execute(consulta, {"txt": texto, "empresa": str(self.empresa_id)})
        return [(fila.id, fila.nombre) for fila in filas]


# --- compras ---


class RepoComprasSQL(_RepoBase):
    async def obtener(self, compra_id: uuid.UUID) -> Compra | None:
        m = await self.sesion.scalar(
            select(models.Compra)
            .where(models.Compra.id == compra_id)
            .options(selectinload(models.Compra.lineas))
        )
        return await self._a_dominio(m) if m else None

    async def agregar(self, compra: Compra) -> int:
        folio = await self._siguiente_folio()
        self.sesion.add(
            models.Compra(
                id=compra.id,
                empresa_id=self.empresa_id,
                folio=folio,
                proveedor_id=compra.proveedor_id,
                origen_id=compra.origen_id,
                transportista_id=compra.transportista_id,
                fecha=compra.fecha,
                moneda=compra.moneda,
                subtotal=compra.subtotal.monto,
                total=compra.total.monto,
                estado=compra.estado.value,
                documento_folio_externo=compra.folio_externo,
                nota=compra.nota,
                lineas=[
                    models.CompraLinea(
                        id=linea.id,
                        producto_id=linea.producto_id,
                        tipo_caja_id=linea.tipo_caja_id,
                        cajas=linea.cajas,
                        kg_por_caja=linea.kg_por_caja,
                        precio_unitario=linea.precio_unitario.monto,
                        unidad_precio=linea.unidad_precio.value,
                        importe=linea.importe.monto,
                    )
                    for linea in compra.lineas
                ],
            )
        )
        # Los lotes referencian compra_lineas por FK sin relationship(); el
        # flush garantiza que las lineas existan antes de insertar lotes.
        await self.sesion.flush()
        return folio

    async def actualizar_estado(self, compra_id: uuid.UUID, estado: str) -> None:
        await self.sesion.execute(
            update(models.Compra)
            .where(models.Compra.id == compra_id)
            .values(estado=estado, actualizado_en=func.now())
        )

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Compra]:
        filas = await self.sesion.scalars(
            select(models.Compra)
            .where(
                models.Compra.empresa_id == self.empresa_id,
                models.Compra.fecha.between(desde, hasta),
            )
            .options(selectinload(models.Compra.lineas))
            .order_by(models.Compra.fecha, models.Compra.folio)
        )
        return [await self._a_dominio(m) for m in filas]

    async def buscar_por_folio(self, folio: int) -> Compra | None:
        m = await self.sesion.scalar(
            select(models.Compra)
            .where(models.Compra.empresa_id == self.empresa_id, models.Compra.folio == folio)
            .options(selectinload(models.Compra.lineas))
        )
        return await self._a_dominio(m) if m else None

    async def _siguiente_folio(self) -> int:
        actual = await self.sesion.scalar(
            select(func.coalesce(func.max(models.Compra.folio), 0)).where(
                models.Compra.empresa_id == self.empresa_id
            )
        )
        return int(actual or 0) + 1

    async def _a_dominio(self, m: models.Compra) -> Compra:
        lineas = [
            LineaCompra(
                producto_id=lm.producto_id,
                cajas=lm.cajas,
                precio_unitario=Dinero(lm.precio_unitario, m.moneda),
                unidad_precio=UnidadPrecio(lm.unidad_precio),
                importe=Dinero(lm.importe, m.moneda),
                tipo_caja_id=lm.tipo_caja_id,
                kg_por_caja=lm.kg_por_caja,
                id=lm.id,
            )
            for lm in m.lineas
        ]
        lotes_orm = await self.sesion.scalars(
            select(models.Lote).where(
                models.Lote.compra_linea_id.in_([linea.id for linea in lineas])
            )
        )
        lotes = [_lote_a_dominio(lm, m.moneda) for lm in lotes_orm]
        return Compra(
            proveedor_id=m.proveedor_id,
            fecha=m.fecha,
            lineas=lineas,
            lotes=lotes,
            moneda=m.moneda,
            origen_id=m.origen_id,
            transportista_id=m.transportista_id,
            folio_externo=m.documento_folio_externo,
            nota=m.nota,
            estado=EstadoOperacion(m.estado),
            folio=m.folio,
            id=m.id,
        )


# --- ventas ---


class RepoVentasSQL(_RepoBase):
    _CARGA = selectinload(models.Venta.lineas).selectinload(models.VentaLinea.asignaciones)

    async def obtener(self, venta_id: uuid.UUID) -> Venta | None:
        m = await self.sesion.scalar(
            select(models.Venta).where(models.Venta.id == venta_id).options(self._CARGA)
        )
        return _venta_a_dominio(m) if m else None

    async def agregar(self, venta: Venta) -> int:
        folio = await self._siguiente_folio()
        self.sesion.add(
            models.Venta(
                id=venta.id,
                empresa_id=self.empresa_id,
                folio=folio,
                cliente_id=venta.cliente_id,
                destino_id=venta.destino_id,
                transportista_id=venta.transportista_id,
                fecha=venta.fecha,
                moneda=venta.moneda,
                total=venta.total.monto,
                costo_total=venta.costo_total.monto,
                estado=venta.estado.value,
                requiere_revision=venta.requiere_revision,
                nota=venta.nota,
                lineas=[
                    models.VentaLinea(
                        id=linea.id,
                        producto_id=linea.producto_id,
                        tipo_caja_id=linea.tipo_caja_id,
                        cajas=linea.cajas,
                        kg_por_caja=linea.kg_por_caja,
                        precio_unitario=linea.precio_unitario.monto,
                        unidad_precio=linea.unidad_precio.value,
                        importe=linea.importe.monto,
                        asignaciones=[
                            models.AsignacionLote(
                                lote_id=asignacion.lote_id,
                                cajas=asignacion.cajas,
                                costo_unitario=asignacion.costo_unitario.monto,
                            )
                            for asignacion in linea.asignaciones
                        ],
                    )
                    for linea in venta.lineas
                ],
            )
        )
        return folio

    async def actualizar_estado(self, venta_id: uuid.UUID, estado: str) -> None:
        await self.sesion.execute(
            update(models.Venta)
            .where(models.Venta.id == venta_id)
            .values(estado=estado, actualizado_en=func.now())
        )

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Venta]:
        filas = await self.sesion.scalars(
            select(models.Venta)
            .where(
                models.Venta.empresa_id == self.empresa_id,
                models.Venta.fecha.between(desde, hasta),
            )
            .options(self._CARGA)
            .order_by(models.Venta.fecha, models.Venta.folio)
        )
        return [_venta_a_dominio(m) for m in filas]

    async def buscar_por_folio(self, folio: int) -> Venta | None:
        m = await self.sesion.scalar(
            select(models.Venta)
            .where(models.Venta.empresa_id == self.empresa_id, models.Venta.folio == folio)
            .options(self._CARGA)
        )
        return _venta_a_dominio(m) if m else None

    async def _siguiente_folio(self) -> int:
        actual = await self.sesion.scalar(
            select(func.coalesce(func.max(models.Venta.folio), 0)).where(
                models.Venta.empresa_id == self.empresa_id
            )
        )
        return int(actual or 0) + 1


def _venta_a_dominio(m: models.Venta) -> Venta:
    lineas = [
        LineaVenta(
            producto_id=lm.producto_id,
            cajas=lm.cajas,
            precio_unitario=Dinero(lm.precio_unitario, m.moneda),
            unidad_precio=UnidadPrecio(lm.unidad_precio),
            importe=Dinero(lm.importe, m.moneda),
            costo=Dinero(
                sum((a.costo_unitario * a.cajas for a in lm.asignaciones), start=Decimal("0")),
                m.moneda,
            ),
            asignaciones=[
                Asignacion(
                    lote_id=a.lote_id,
                    cajas=a.cajas,
                    costo_unitario=Dinero(a.costo_unitario, m.moneda),
                )
                for a in lm.asignaciones
            ],
            tipo_caja_id=lm.tipo_caja_id,
            kg_por_caja=lm.kg_por_caja,
            id=lm.id,
        )
        for lm in m.lineas
    ]
    return Venta(
        cliente_id=m.cliente_id,
        fecha=m.fecha,
        lineas=lineas,
        moneda=m.moneda,
        destino_id=m.destino_id,
        transportista_id=m.transportista_id,
        nota=m.nota,
        requiere_revision=m.requiere_revision,
        estado=EstadoOperacion(m.estado),
        folio=m.folio,
        id=m.id,
    )


# --- lotes ---


def _lote_a_dominio(m: models.Lote, moneda: str = "MXN") -> Lote:
    return Lote(
        producto_id=m.producto_id,
        cajas_iniciales=m.cajas_iniciales,
        cajas_disponibles=m.cajas_disponibles,
        costo_unitario=Dinero(m.costo_unitario, moneda),
        fecha=m.fecha,
        compra_linea_id=m.compra_linea_id,
        costo_indirecto_unitario=Dinero(m.costo_indirecto_unitario, moneda),
        id=m.id,
    )


class RepoLotesSQL(_RepoBase):
    async def disponibles_de(self, producto_id: uuid.UUID) -> list[Lote]:
        filas = await self.sesion.scalars(
            select(models.Lote)
            .where(
                models.Lote.empresa_id == self.empresa_id,
                models.Lote.producto_id == producto_id,
                models.Lote.cajas_disponibles > 0,
            )
            .order_by(models.Lote.fecha, models.Lote.id)
        )
        return [_lote_a_dominio(m) for m in filas]

    async def agregar(self, *lotes: Lote) -> None:
        for lote in lotes:
            self.sesion.add(
                models.Lote(
                    id=lote.id,
                    empresa_id=self.empresa_id,
                    compra_linea_id=lote.compra_linea_id,
                    producto_id=lote.producto_id,
                    cajas_iniciales=lote.cajas_iniciales,
                    cajas_disponibles=lote.cajas_disponibles,
                    costo_unitario=lote.costo_unitario.monto,
                    costo_indirecto_unitario=lote.costo_indirecto_unitario.monto,
                    fecha=lote.fecha,
                )
            )

    async def guardar(self, *lotes: Lote) -> None:
        for lote in lotes:
            await self.sesion.execute(
                update(models.Lote)
                .where(models.Lote.id == lote.id)
                .values(
                    cajas_disponibles=lote.cajas_disponibles,
                    costo_indirecto_unitario=lote.costo_indirecto_unitario.monto,
                )
            )

    async def obtener(self, lote_id: uuid.UUID) -> Lote | None:
        m = await self.sesion.get(models.Lote, lote_id)
        return _lote_a_dominio(m) if m else None


# --- movimientos de caja ---


class RepoMovimientosCajaSQL(_RepoBase):
    async def agregar(self, *movimientos: MovimientoCaja) -> None:
        for mov in movimientos:
            self.sesion.add(
                models.MovimientoCajaDB(
                    id=mov.id,
                    empresa_id=self.empresa_id,
                    contraparte_id=mov.contraparte_id,
                    tipo_caja_id=mov.tipo_caja_id,
                    fecha=mov.fecha,
                    tipo=mov.tipo.value,
                    cantidad=mov.cantidad,
                    signo=mov.signo,
                    referencia_tipo=mov.referencia_tipo,
                    referencia_id=mov.referencia_id,
                    nota=mov.nota,
                )
            )

    async def saldo(self, contraparte_id: uuid.UUID, tipo_caja_id: uuid.UUID) -> int:
        resultado = await self.sesion.scalar(
            select(
                func.coalesce(
                    func.sum(models.MovimientoCajaDB.cantidad * models.MovimientoCajaDB.signo), 0
                )
            ).where(
                models.MovimientoCajaDB.contraparte_id == contraparte_id,
                models.MovimientoCajaDB.tipo_caja_id == tipo_caja_id,
            )
        )
        return int(resultado or 0)

    async def saldos_de(self, contraparte_id: uuid.UUID) -> dict[uuid.UUID, int]:
        filas = await self.sesion.execute(
            select(
                models.MovimientoCajaDB.tipo_caja_id,
                func.sum(models.MovimientoCajaDB.cantidad * models.MovimientoCajaDB.signo),
            )
            .where(models.MovimientoCajaDB.contraparte_id == contraparte_id)
            .group_by(models.MovimientoCajaDB.tipo_caja_id)
        )
        return {fila[0]: int(fila[1]) for fila in filas}

    async def de_referencia(
        self, referencia_tipo: str, referencia_id: uuid.UUID
    ) -> list[MovimientoCaja]:
        filas = await self.sesion.scalars(
            select(models.MovimientoCajaDB).where(
                models.MovimientoCajaDB.referencia_tipo == referencia_tipo,
                models.MovimientoCajaDB.referencia_id == referencia_id,
            )
        )
        return [
            MovimientoCaja(
                contraparte_id=m.contraparte_id,
                tipo_caja_id=m.tipo_caja_id,
                tipo=TipoMovimientoCaja(m.tipo),
                cantidad=m.cantidad,
                fecha=m.fecha,
                signo=m.signo,
                referencia_tipo=m.referencia_tipo,
                referencia_id=m.referencia_id,
                nota=m.nota,
                id=m.id,
            )
            for m in filas
        ]


# --- pagos y gastos ---


class RepoPagosSQL(_RepoBase):
    async def agregar(self, pago: Pago) -> None:
        self.sesion.add(
            models.Pago(
                id=pago.id,
                empresa_id=self.empresa_id,
                fecha=pago.fecha,
                direccion=pago.direccion.value,
                contraparte_id=pago.contraparte_id,
                monto=pago.monto.monto,
                moneda=pago.monto.moneda,
                metodo=pago.metodo,
                referencia=pago.referencia,
            )
        )

    async def listar_por_contraparte(self, contraparte_id: uuid.UUID) -> list[Pago]:
        filas = await self.sesion.scalars(
            select(models.Pago).where(models.Pago.contraparte_id == contraparte_id)
        )
        return [_pago_a_dominio(m) for m in filas]

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Pago]:
        filas = await self.sesion.scalars(
            select(models.Pago).where(
                models.Pago.empresa_id == self.empresa_id,
                models.Pago.fecha.between(desde, hasta),
            )
        )
        return [_pago_a_dominio(m) for m in filas]


def _pago_a_dominio(m: models.Pago) -> Pago:
    return Pago(
        contraparte_id=m.contraparte_id,
        direccion=DireccionPago(m.direccion),
        monto=Dinero(m.monto, m.moneda),
        fecha=m.fecha,
        metodo=m.metodo,
        referencia=m.referencia,
        id=m.id,
    )


class RepoGastosSQL(_RepoBase):
    async def agregar(self, gasto: Gasto) -> None:
        self.sesion.add(
            models.Gasto(
                id=gasto.id,
                empresa_id=self.empresa_id,
                fecha=gasto.fecha,
                categoria=gasto.categoria,
                descripcion=gasto.descripcion,
                monto=gasto.monto.monto,
                moneda=gasto.monto.moneda,
                contraparte_id=gasto.contraparte_id,
                imputable_tipo=gasto.imputable_tipo,
                imputable_id=gasto.imputable_id,
            )
        )

    async def listar_por_fechas(self, desde: date, hasta: date) -> list[Gasto]:
        filas = await self.sesion.scalars(
            select(models.Gasto).where(
                models.Gasto.empresa_id == self.empresa_id,
                models.Gasto.fecha.between(desde, hasta),
            )
        )
        return [
            Gasto(
                categoria=m.categoria,
                monto=Dinero(m.monto, m.moneda),
                fecha=m.fecha,
                descripcion=m.descripcion,
                contraparte_id=m.contraparte_id,
                imputable_tipo=m.imputable_tipo,
                imputable_id=m.imputable_id,
                id=m.id,
            )
            for m in filas
        ]


# --- borradores ---


class RepoBorradoresSQL(_RepoBase):
    async def obtener(self, borrador_id: uuid.UUID) -> Borrador | None:
        m = await self.sesion.get(models.Borrador, borrador_id)
        return _borrador_a_dominio(m) if m else None

    async def agregar(self, borrador: Borrador) -> None:
        self.sesion.add(
            models.Borrador(
                id=borrador.id,
                empresa_id=self.empresa_id,
                mensaje_id=borrador.mensaje_id,
                intencion=borrador.intencion,
                payload=borrador.payload,
                faltantes=borrador.faltantes,
                preguntas=borrador.preguntas,
                confianza=borrador.confianza,
                estado=borrador.estado.value,
                resultado_tipo=borrador.resultado_tipo,
                resultado_id=borrador.resultado_id,
                expira_en=borrador.expira_en,
                creado_en=borrador.creado_en,
            )
        )

    async def guardar(self, borrador: Borrador) -> None:
        await self.sesion.execute(
            update(models.Borrador)
            .where(models.Borrador.id == borrador.id)
            .values(
                payload=borrador.payload,
                faltantes=borrador.faltantes,
                preguntas=borrador.preguntas,
                estado=borrador.estado.value,
                resultado_tipo=borrador.resultado_tipo,
                resultado_id=borrador.resultado_id,
            )
        )

    async def pendientes(self) -> list[Borrador]:
        filas = await self.sesion.scalars(
            select(models.Borrador)
            .where(
                models.Borrador.empresa_id == self.empresa_id,
                models.Borrador.estado == EstadoBorrador.PENDIENTE.value,
            )
            .order_by(models.Borrador.creado_en)
        )
        return [_borrador_a_dominio(m) for m in filas]

    async def vencidos(self, momento: datetime) -> list[Borrador]:
        filas = await self.sesion.scalars(
            select(models.Borrador).where(
                models.Borrador.empresa_id == self.empresa_id,
                models.Borrador.estado == EstadoBorrador.PENDIENTE.value,
                models.Borrador.expira_en <= momento,
            )
        )
        return [_borrador_a_dominio(m) for m in filas]


def _borrador_a_dominio(m: models.Borrador) -> Borrador:
    return Borrador(
        intencion=m.intencion,
        payload=dict(m.payload),
        faltantes=list(m.faltantes),
        preguntas=list(m.preguntas),
        confianza=float(m.confianza) if m.confianza is not None else None,
        estado=EstadoBorrador(m.estado),
        resultado_tipo=m.resultado_tipo,
        resultado_id=m.resultado_id,
        mensaje_id=m.mensaje_id,
        creado_en=m.creado_en,
        expira_en=m.expira_en,
        id=m.id,
    )


# --- catalogos ---


class RepoCatalogosSQL(_RepoBase):
    async def productos(self) -> list[tuple[uuid.UUID, str]]:
        filas = await self.sesion.execute(
            select(models.Producto.id, models.Producto.nombre, models.Producto.variedad)
            .where(models.Producto.empresa_id == self.empresa_id, models.Producto.activo)
            .order_by(models.Producto.nombre)
        )
        return [
            (fila.id, f"{fila.nombre} {fila.variedad}" if fila.variedad else fila.nombre)
            for fila in filas
        ]

    async def tipos_caja(self) -> list[tuple[uuid.UUID, str]]:
        filas = await self.sesion.execute(
            select(models.TipoCaja.id, models.TipoCaja.nombre)
            .where(models.TipoCaja.empresa_id == self.empresa_id)
            .order_by(models.TipoCaja.nombre)
        )
        return [(fila.id, fila.nombre) for fila in filas]
