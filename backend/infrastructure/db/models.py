"""Modelos SQLAlchemy 2.0. Espejo del esquema en sql/001_schema.sql."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.domain.common.tipos import nuevo_id

DINERO = Numeric(18, 2)
PESO = Numeric(10, 3)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Empresa(Base, TimestampMixin):
    __tablename__ = "empresas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    moneda_base: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    zona_horaria: Mapped[str] = mapped_column(Text, default="America/Tijuana", nullable=False)


class Usuario(Base, TimestampMixin):
    __tablename__ = "usuarios"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (CheckConstraint("rol IN ('admin','operador','contador')"),)


class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    variedad: Mapped[str | None] = mapped_column(Text)
    unidad_base: Mapped[str] = mapped_column(Text, default="caja", nullable=False)
    kg_por_caja_default: Mapped[Decimal | None] = mapped_column(PESO)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (UniqueConstraint("empresa_id", "nombre", "variedad"),)


class TipoCaja(Base):
    __tablename__ = "tipos_caja"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    retornable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    costo_reposicion: Mapped[Decimal | None] = mapped_column(DINERO)
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)


class Ubicacion(Base):
    __tablename__ = "ubicaciones"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    ciudad: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str | None] = mapped_column(Text)
    pais: Mapped[str] = mapped_column(Text, default="MX", nullable=False)
    es_propia: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)


class Contraparte(Base, TimestampMixin):
    __tablename__ = "contrapartes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    rfc: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    correo: Mapped[str | None] = mapped_column(Text)
    ubicacion_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ubicaciones.id"))
    dias_credito: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cajas_retornables: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notas: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, default="activo", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    alias: Mapped[list[ContraparteAlias]] = relationship(back_populates="contraparte")
    __table_args__ = (
        UniqueConstraint("empresa_id", "nombre"),
        CheckConstraint("tipo IN ('proveedor','cliente','ambos','transportista')"),
    )
    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": version}


class ContraparteAlias(Base, TimestampMixin):
    __tablename__ = "contraparte_alias"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    contraparte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrapartes.id"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_norm: Mapped[str] = mapped_column(Text, nullable=False)
    origen: Mapped[str] = mapped_column(Text, default="usuario", nullable=False)
    confirmado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contraparte: Mapped[Contraparte] = relationship(back_populates="alias")
    __table_args__ = (UniqueConstraint("contraparte_id", "alias_norm"),)


class Compra(Base, TimestampMixin):
    __tablename__ = "compras"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    folio: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=True)
    proveedor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrapartes.id"), nullable=False)
    origen_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ubicaciones.id"))
    transportista_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contrapartes.id"))
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"), nullable=False)
    estado: Mapped[str] = mapped_column(Text, default="borrador", nullable=False)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    documento_folio_externo: Mapped[str | None] = mapped_column(Text)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nota: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lineas: Mapped[list[CompraLinea]] = relationship(
        back_populates="compra", cascade="all, delete-orphan"
    )
    __table_args__ = (
        CheckConstraint("estado IN ('borrador','confirmado','anulado')"),
        Index("idx_compras_fecha", "empresa_id", "fecha"),
    )
    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": version}


class CompraLinea(Base):
    __tablename__ = "compra_lineas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    compra_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compras.id", ondelete="CASCADE"), nullable=False
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), nullable=False)
    tipo_caja_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tipos_caja.id"))
    cajas: Mapped[int] = mapped_column(Integer, nullable=False)
    kg_por_caja: Mapped[Decimal | None] = mapped_column(PESO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    unidad_precio: Mapped[str] = mapped_column(Text, default="caja", nullable=False)
    importe: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    compra: Mapped[Compra] = relationship(back_populates="lineas")
    __table_args__ = (CheckConstraint("cajas > 0"),)


class Lote(Base):
    __tablename__ = "lotes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    compra_linea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compra_lineas.id"), nullable=False
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), nullable=False)
    cajas_iniciales: Mapped[int] = mapped_column(Integer, nullable=False)
    cajas_disponibles: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    costo_indirecto_unitario: Mapped[Decimal] = mapped_column(
        DINERO, default=Decimal("0"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    __table_args__ = (
        CheckConstraint("cajas_disponibles >= 0"),
        CheckConstraint("cajas_disponibles <= cajas_iniciales"),
    )


class Venta(Base, TimestampMixin):
    __tablename__ = "ventas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    folio: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=True)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrapartes.id"), nullable=False)
    destino_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ubicaciones.id"))
    transportista_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contrapartes.id"))
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"), nullable=False)
    costo_total: Mapped[Decimal] = mapped_column(DINERO, default=Decimal("0"), nullable=False)
    estado: Mapped[str] = mapped_column(Text, default="borrador", nullable=False)
    requiere_revision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nota: Mapped[str | None] = mapped_column(Text)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    actualizado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lineas: Mapped[list[VentaLinea]] = relationship(
        back_populates="venta", cascade="all, delete-orphan"
    )
    __table_args__ = (
        CheckConstraint("estado IN ('borrador','confirmado','anulado')"),
        Index("idx_ventas_fecha", "empresa_id", "fecha"),
    )
    __mapper_args__: ClassVar[dict[str, Any]] = {"version_id_col": version}


class VentaLinea(Base):
    __tablename__ = "venta_lineas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    venta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("productos.id"), nullable=False)
    tipo_caja_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tipos_caja.id"))
    cajas: Mapped[int] = mapped_column(Integer, nullable=False)
    kg_por_caja: Mapped[Decimal | None] = mapped_column(PESO)
    precio_unitario: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    unidad_precio: Mapped[str] = mapped_column(Text, default="caja", nullable=False)
    importe: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    venta: Mapped[Venta] = relationship(back_populates="lineas")
    asignaciones: Mapped[list[AsignacionLote]] = relationship(
        back_populates="venta_linea", cascade="all, delete-orphan"
    )
    __table_args__ = (CheckConstraint("cajas > 0"),)


class AsignacionLote(Base):
    __tablename__ = "asignaciones_lote"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    venta_linea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venta_lineas.id", ondelete="CASCADE"), nullable=False
    )
    lote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lotes.id"), nullable=False)
    cajas: Mapped[int] = mapped_column(Integer, nullable=False)
    costo_unitario: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    venta_linea: Mapped[VentaLinea] = relationship(back_populates="asignaciones")


class MovimientoCajaDB(Base, TimestampMixin):
    __tablename__ = "movimientos_caja"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    contraparte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrapartes.id"), nullable=False)
    tipo_caja_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tipos_caja.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    signo: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    referencia_tipo: Mapped[str | None] = mapped_column(Text)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    nota: Mapped[str | None] = mapped_column(Text)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    __table_args__ = (
        CheckConstraint("cantidad > 0"),
        CheckConstraint("signo IN (-1,1)"),
        Index("idx_mov_caja_saldo", "empresa_id", "contraparte_id", "tipo_caja_id", "fecha"),
    )


class Gasto(Base, TimestampMixin):
    __tablename__ = "gastos"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    categoria: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    monto: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    contraparte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contrapartes.id"))
    imputable_tipo: Mapped[str | None] = mapped_column(Text)
    imputable_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    estado: Mapped[str] = mapped_column(Text, default="confirmado", nullable=False)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))


class Pago(Base, TimestampMixin):
    __tablename__ = "pagos"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    direccion: Mapped[str] = mapped_column(Text, nullable=False)
    contraparte_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contrapartes.id"), nullable=False)
    monto: Mapped[Decimal] = mapped_column(DINERO, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    metodo: Mapped[str | None] = mapped_column(Text)
    referencia: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, default="confirmado", nullable=False)
    mensaje_origen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    __table_args__ = (CheckConstraint("direccion IN ('cobro','pago')"),)


class AplicacionPago(Base):
    __tablename__ = "aplicaciones_pago"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    pago_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pagos.id"), nullable=False)
    documento_tipo: Mapped[str] = mapped_column(Text, nullable=False)
    documento_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    monto: Mapped[Decimal] = mapped_column(DINERO, nullable=False)


class Documento(Base, TimestampMixin):
    __tablename__ = "documentos"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_file_id: Mapped[str | None] = mapped_column(Text)
    texto_extraido: Mapped[str | None] = mapped_column(Text)
    metadatos: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    vinculado_tipo: Mapped[str | None] = mapped_column(Text)
    vinculado_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    __table_args__ = (UniqueConstraint("empresa_id", "sha256"),)


class MensajeEntrante(Base):
    __tablename__ = "mensajes_entrantes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    telegram_update_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    texto_normalizado: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(Text, default="recibido", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    procesado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Borrador(Base, TimestampMixin):
    __tablename__ = "borradores"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    mensaje_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mensajes_entrantes.id"))
    intencion: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    faltantes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    preguntas: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    estado: Mapped[str] = mapped_column(Text, default="pendiente", nullable=False)
    resultado_tipo: Mapped[str | None] = mapped_column(Text)
    resultado_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))


class EventoAuditoria(Base):
    __tablename__ = "eventos_auditoria"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    agregado_tipo: Mapped[str] = mapped_column(Text, nullable=False)
    agregado_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tipo_evento: Mapped[str] = mapped_column(Text, nullable=False)
    datos_antes: Mapped[dict | None] = mapped_column(JSONB)
    datos_despues: Mapped[dict | None] = mapped_column(JSONB)
    actor_usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    origen: Mapped[str] = mapped_column(Text, default="telegram", nullable=False)
    ocurrido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IALlamada(Base, TimestampMixin):
    __tablename__ = "ia_llamadas"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=nuevo_id)
    empresa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    mensaje_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mensajes_entrantes.id"))
    proposito: Mapped[str] = mapped_column(Text, nullable=False)
    modelo: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    costo_mxn: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    exito: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
