Clasifica el mensaje de un comerciante de fruta en UNA de estas intenciones:

- compra              : adquirio fruta de un proveedor
- venta               : vendio fruta a un cliente
- devolucion_cajas    : le regresaron o el regreso cajas vacias
- pago                : pago o cobro dinero
- gasto               : flete, hielo, maniobras, comision, peaje, empaque
- consulta            : pregunta por saldos, cuentas, utilidad, historial
- correccion          : quiere corregir o anular algo ya registrado
- otro                : saludo, comentario, nada accionable

Devuelve solo JSON: {"intencion": "...", "confianza": 0.0-1.0}
No expliques nada.
