-- FruitFlow AI :: esquema inicial
-- Convenciones: UUID v7 generado en aplicacion, dinero NUMERIC(18,2),
-- peso NUMERIC(10,3), timestamps en UTC, sin borrado fisico.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ============ Organizacion ============
CREATE TABLE empresas (
  id UUID PRIMARY KEY,
  nombre TEXT NOT NULL,
  moneda_base CHAR(3) NOT NULL DEFAULT 'MXN',
  zona_horaria TEXT NOT NULL DEFAULT 'America/Tijuana',
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usuarios (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  telegram_user_id BIGINT UNIQUE NOT NULL,
  nombre TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('admin','operador','contador')),
  activo BOOLEAN NOT NULL DEFAULT true,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ Catalogos ============
CREATE TABLE productos (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  nombre TEXT NOT NULL,
  variedad TEXT,
  unidad_base TEXT NOT NULL DEFAULT 'caja',
  kg_por_caja_default NUMERIC(10,3),
  activo BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (empresa_id, nombre, variedad)
);

CREATE TABLE tipos_caja (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  nombre TEXT NOT NULL,
  retornable BOOLEAN NOT NULL DEFAULT true,
  costo_reposicion NUMERIC(18,2),
  UNIQUE (empresa_id, nombre)
);

CREATE TABLE ubicaciones (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  nombre TEXT NOT NULL,
  ciudad TEXT,
  estado TEXT,
  pais TEXT NOT NULL DEFAULT 'MX',
  es_propia BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (empresa_id, nombre)
);

-- ============ Contrapartes ============
CREATE TABLE contrapartes (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  nombre TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('proveedor','cliente','ambos','transportista')),
  rfc TEXT,
  telefono TEXT,
  correo TEXT,
  ubicacion_id UUID REFERENCES ubicaciones(id),
  dias_credito INT NOT NULL DEFAULT 0,
  cajas_retornables BOOLEAN NOT NULL DEFAULT true,
  notas TEXT,
  estado TEXT NOT NULL DEFAULT 'activo',
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  version INT NOT NULL DEFAULT 1,
  UNIQUE (empresa_id, nombre)
);
CREATE INDEX idx_contraparte_nombre_trgm ON contrapartes USING gin (nombre gin_trgm_ops);

CREATE TABLE contraparte_alias (
  id UUID PRIMARY KEY,
  contraparte_id UUID NOT NULL REFERENCES contrapartes(id),
  alias TEXT NOT NULL,
  alias_norm TEXT NOT NULL,
  origen TEXT NOT NULL DEFAULT 'usuario' CHECK (origen IN ('usuario','ia')),
  confirmado BOOLEAN NOT NULL DEFAULT false,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (contraparte_id, alias_norm)
);
CREATE INDEX idx_alias_trgm ON contraparte_alias USING gin (alias_norm gin_trgm_ops);

-- ============ Compras ============
CREATE TABLE compras (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  folio SERIAL,
  proveedor_id UUID NOT NULL REFERENCES contrapartes(id),
  origen_id UUID REFERENCES ubicaciones(id),
  transportista_id UUID REFERENCES contrapartes(id),
  fecha DATE NOT NULL,
  moneda CHAR(3) NOT NULL DEFAULT 'MXN',
  subtotal NUMERIC(18,2) NOT NULL DEFAULT 0,
  total NUMERIC(18,2) NOT NULL DEFAULT 0,
  estado TEXT NOT NULL DEFAULT 'borrador'
    CHECK (estado IN ('borrador','confirmado','anulado')),
  requiere_revision BOOLEAN NOT NULL DEFAULT false,
  documento_folio_externo TEXT,
  mensaje_origen_id UUID,
  nota TEXT,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  actualizado_en TIMESTAMPTZ,
  version INT NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX ux_compra_folio_externo
  ON compras (empresa_id, proveedor_id, documento_folio_externo)
  WHERE documento_folio_externo IS NOT NULL AND estado <> 'anulado';
CREATE INDEX idx_compras_fecha ON compras (empresa_id, fecha DESC);

CREATE TABLE compra_lineas (
  id UUID PRIMARY KEY,
  compra_id UUID NOT NULL REFERENCES compras(id) ON DELETE CASCADE,
  producto_id UUID NOT NULL REFERENCES productos(id),
  tipo_caja_id UUID REFERENCES tipos_caja(id),
  cajas INT NOT NULL CHECK (cajas > 0),
  kg_por_caja NUMERIC(10,3),
  precio_unitario NUMERIC(18,2) NOT NULL CHECK (precio_unitario >= 0),
  unidad_precio TEXT NOT NULL DEFAULT 'caja' CHECK (unidad_precio IN ('caja','kg')),
  importe NUMERIC(18,2) NOT NULL
);

CREATE TABLE lotes (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  compra_linea_id UUID NOT NULL REFERENCES compra_lineas(id),
  producto_id UUID NOT NULL REFERENCES productos(id),
  cajas_iniciales INT NOT NULL CHECK (cajas_iniciales > 0),
  cajas_disponibles INT NOT NULL CHECK (cajas_disponibles >= 0),
  costo_unitario NUMERIC(18,2) NOT NULL,
  costo_indirecto_unitario NUMERIC(18,2) NOT NULL DEFAULT 0,
  fecha DATE NOT NULL,
  CHECK (cajas_disponibles <= cajas_iniciales)
);
CREATE INDEX idx_lotes_disponibles ON lotes (empresa_id, producto_id, fecha)
  WHERE cajas_disponibles > 0;

-- ============ Ventas ============
CREATE TABLE ventas (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  folio SERIAL,
  cliente_id UUID NOT NULL REFERENCES contrapartes(id),
  destino_id UUID REFERENCES ubicaciones(id),
  transportista_id UUID REFERENCES contrapartes(id),
  fecha DATE NOT NULL,
  moneda CHAR(3) NOT NULL DEFAULT 'MXN',
  total NUMERIC(18,2) NOT NULL DEFAULT 0,
  costo_total NUMERIC(18,2) NOT NULL DEFAULT 0,
  utilidad NUMERIC(18,2) GENERATED ALWAYS AS (total - costo_total) STORED,
  estado TEXT NOT NULL DEFAULT 'borrador'
    CHECK (estado IN ('borrador','confirmado','anulado')),
  requiere_revision BOOLEAN NOT NULL DEFAULT false,
  mensaje_origen_id UUID,
  nota TEXT,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  actualizado_en TIMESTAMPTZ,
  version INT NOT NULL DEFAULT 1
);
CREATE INDEX idx_ventas_fecha ON ventas (empresa_id, fecha DESC);

CREATE TABLE venta_lineas (
  id UUID PRIMARY KEY,
  venta_id UUID NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
  producto_id UUID NOT NULL REFERENCES productos(id),
  tipo_caja_id UUID REFERENCES tipos_caja(id),
  cajas INT NOT NULL CHECK (cajas > 0),
  kg_por_caja NUMERIC(10,3),
  precio_unitario NUMERIC(18,2) NOT NULL CHECK (precio_unitario >= 0),
  unidad_precio TEXT NOT NULL DEFAULT 'caja' CHECK (unidad_precio IN ('caja','kg')),
  importe NUMERIC(18,2) NOT NULL
);

CREATE TABLE asignaciones_lote (
  id UUID PRIMARY KEY,
  venta_linea_id UUID NOT NULL REFERENCES venta_lineas(id) ON DELETE CASCADE,
  lote_id UUID NOT NULL REFERENCES lotes(id),
  cajas INT NOT NULL CHECK (cajas > 0),
  costo_unitario NUMERIC(18,2) NOT NULL
);
CREATE INDEX idx_asignaciones_lote ON asignaciones_lote (lote_id);

-- ============ Cajas retornables ============
CREATE TABLE movimientos_caja (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  contraparte_id UUID NOT NULL REFERENCES contrapartes(id),
  tipo_caja_id UUID NOT NULL REFERENCES tipos_caja(id),
  fecha DATE NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN (
    'entrega_llena','recepcion_llena','devolucion_recibida',
    'devolucion_entregada','ajuste','merma')),
  cantidad INT NOT NULL CHECK (cantidad > 0),
  signo SMALLINT NOT NULL CHECK (signo IN (-1,1)),
  referencia_tipo TEXT,
  referencia_id UUID,
  nota TEXT,
  mensaje_origen_id UUID,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mov_caja_saldo
  ON movimientos_caja (empresa_id, contraparte_id, tipo_caja_id, fecha);

-- ============ Finanzas ============
CREATE TABLE gastos (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  fecha DATE NOT NULL,
  categoria TEXT NOT NULL CHECK (categoria IN
    ('flete','hielo','maniobras','comision','peaje','empaque','otro')),
  descripcion TEXT,
  monto NUMERIC(18,2) NOT NULL CHECK (monto >= 0),
  moneda CHAR(3) NOT NULL DEFAULT 'MXN',
  contraparte_id UUID REFERENCES contrapartes(id),
  imputable_tipo TEXT CHECK (imputable_tipo IN ('compra','venta','lote','general')),
  imputable_id UUID,
  estado TEXT NOT NULL DEFAULT 'confirmado',
  mensaje_origen_id UUID,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pagos (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  fecha DATE NOT NULL,
  direccion TEXT NOT NULL CHECK (direccion IN ('cobro','pago')),
  contraparte_id UUID NOT NULL REFERENCES contrapartes(id),
  monto NUMERIC(18,2) NOT NULL CHECK (monto > 0),
  moneda CHAR(3) NOT NULL DEFAULT 'MXN',
  metodo TEXT CHECK (metodo IN ('efectivo','transferencia','cheque','otro')),
  referencia TEXT,
  estado TEXT NOT NULL DEFAULT 'confirmado',
  mensaje_origen_id UUID,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE aplicaciones_pago (
  id UUID PRIMARY KEY,
  pago_id UUID NOT NULL REFERENCES pagos(id),
  documento_tipo TEXT NOT NULL CHECK (documento_tipo IN ('compra','venta')),
  documento_id UUID NOT NULL,
  monto NUMERIC(18,2) NOT NULL CHECK (monto > 0)
);

-- ============ Documentos y mensajes ============
CREATE TABLE documentos (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  tipo TEXT NOT NULL CHECK (tipo IN ('foto','pdf','audio','otro')),
  storage_key TEXT NOT NULL,
  mime TEXT NOT NULL,
  bytes BIGINT NOT NULL,
  sha256 TEXT NOT NULL,
  telegram_file_id TEXT,
  texto_extraido TEXT,
  metadatos JSONB NOT NULL DEFAULT '{}',
  vinculado_tipo TEXT,
  vinculado_id UUID,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (empresa_id, sha256)
);

CREATE TABLE mensajes_entrantes (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  telegram_update_id BIGINT UNIQUE NOT NULL,
  telegram_chat_id BIGINT NOT NULL,
  usuario_id UUID REFERENCES usuarios(id),
  tipo TEXT NOT NULL CHECK (tipo IN ('texto','voz','foto','documento','otro')),
  payload JSONB NOT NULL,
  texto_normalizado TEXT,
  estado TEXT NOT NULL DEFAULT 'recibido',
  error TEXT,
  recibido_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  procesado_en TIMESTAMPTZ
);

CREATE TABLE borradores (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  mensaje_id UUID REFERENCES mensajes_entrantes(id),
  intencion TEXT NOT NULL,
  payload JSONB NOT NULL,
  faltantes JSONB NOT NULL DEFAULT '[]',
  preguntas JSONB NOT NULL DEFAULT '[]',
  confianza NUMERIC(4,3),
  estado TEXT NOT NULL DEFAULT 'pendiente'
    CHECK (estado IN ('pendiente','confirmado','editando','cancelado','expirado')),
  resultado_tipo TEXT,
  resultado_id UUID,
  expira_en TIMESTAMPTZ NOT NULL,
  creado_por UUID REFERENCES usuarios(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_borradores_pendientes ON borradores (empresa_id, estado, creado_en DESC);

-- ============ Auditoria e IA ============
CREATE TABLE eventos_auditoria (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  agregado_tipo TEXT NOT NULL,
  agregado_id UUID NOT NULL,
  tipo_evento TEXT NOT NULL,
  datos_antes JSONB,
  datos_despues JSONB,
  actor_usuario_id UUID REFERENCES usuarios(id),
  origen TEXT NOT NULL DEFAULT 'telegram',
  ocurrido_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_auditoria_agregado
  ON eventos_auditoria (agregado_tipo, agregado_id, ocurrido_en DESC);

CREATE TABLE ia_llamadas (
  id UUID PRIMARY KEY,
  empresa_id UUID NOT NULL REFERENCES empresas(id),
  mensaje_id UUID REFERENCES mensajes_entrantes(id),
  proposito TEXT NOT NULL,
  modelo TEXT NOT NULL,
  tokens_entrada INT NOT NULL DEFAULT 0,
  tokens_salida INT NOT NULL DEFAULT 0,
  costo_mxn NUMERIC(18,4) NOT NULL DEFAULT 0,
  latencia_ms INT,
  exito BOOLEAN NOT NULL DEFAULT true,
  error TEXT,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_ia_costo_dia ON ia_llamadas (empresa_id, creado_en);
