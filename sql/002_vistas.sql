-- Vistas de lectura para reportes y consultas del bot.

CREATE OR REPLACE VIEW v_saldo_cajas AS
SELECT empresa_id,
       contraparte_id,
       tipo_caja_id,
       SUM(cantidad * signo) AS saldo,
       MAX(fecha) AS ultimo_movimiento
FROM movimientos_caja
GROUP BY empresa_id, contraparte_id, tipo_caja_id;

CREATE OR REPLACE VIEW v_cxc AS
SELECT v.empresa_id, v.cliente_id, v.id AS venta_id, v.folio, v.fecha, v.total,
       COALESCE(SUM(ap.monto), 0) AS pagado,
       v.total - COALESCE(SUM(ap.monto), 0) AS saldo
FROM ventas v
LEFT JOIN aplicaciones_pago ap
       ON ap.documento_tipo = 'venta' AND ap.documento_id = v.id
WHERE v.estado = 'confirmado'
GROUP BY v.id;

CREATE OR REPLACE VIEW v_cxp AS
SELECT c.empresa_id, c.proveedor_id, c.id AS compra_id, c.folio, c.fecha, c.total,
       COALESCE(SUM(ap.monto), 0) AS pagado,
       c.total - COALESCE(SUM(ap.monto), 0) AS saldo
FROM compras c
LEFT JOIN aplicaciones_pago ap
       ON ap.documento_tipo = 'compra' AND ap.documento_id = c.id
WHERE c.estado = 'confirmado'
GROUP BY c.id;

CREATE OR REPLACE VIEW v_margen_por_proveedor AS
SELECT c.empresa_id,
       c.proveedor_id,
       COUNT(DISTINCT v.id) AS ventas,
       SUM(vl.importe) AS ingreso,
       SUM(al.cajas * al.costo_unitario) AS costo,
       SUM(vl.importe) - SUM(al.cajas * al.costo_unitario) AS utilidad
FROM asignaciones_lote al
JOIN lotes l ON l.id = al.lote_id
JOIN compra_lineas cl ON cl.id = l.compra_linea_id
JOIN compras c ON c.id = cl.compra_id
JOIN venta_lineas vl ON vl.id = al.venta_linea_id
JOIN ventas v ON v.id = vl.venta_id AND v.estado = 'confirmado'
GROUP BY c.empresa_id, c.proveedor_id;

CREATE OR REPLACE VIEW v_inventario_actual AS
SELECT l.empresa_id, l.producto_id,
       SUM(l.cajas_disponibles) AS cajas_disponibles,
       SUM(l.cajas_disponibles * (l.costo_unitario + l.costo_indirecto_unitario)) AS valor
FROM lotes l
WHERE l.cajas_disponibles > 0
GROUP BY l.empresa_id, l.producto_id;
