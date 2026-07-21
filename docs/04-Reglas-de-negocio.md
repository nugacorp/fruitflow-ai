# Reglas de negocio

## RN-01 Confirmacion obligatoria
Ninguna operacion se persiste como confirmada sin accion explicita del
usuario. Toda extraccion crea un borrador con TTL de 24 horas. Los borradores
vencidos pasan a estado `expirado`, nunca se ejecutan solos.

## RN-02 Idempotencia
`telegram_update_id` es unico. Un documento con el mismo sha256 dentro de la
empresa se rechaza como duplicado. Un folio externo repetido del mismo
proveedor levanta advertencia.

## RN-03 Cajas retornables
La caja tiene dueno. El saldo se lee desde la perspectiva del usuario:

    saldo > 0  ->  la contraparte me debe cajas
    saldo < 0  ->  yo le debo cajas

| Evento | Movimiento | Signo |
|---|---|---|
| Venta confirmada | entrega_llena | +1 |
| Compra confirmada | recepcion_llena | -1 |
| Me regresan vacias | devolucion_recibida | -1 |
| Regreso vacias | devolucion_entregada | +1 |
| Perdida o rotura | merma | -1 |
| Conciliacion | ajuste | explicito |

Solo aplica si la contraparte tiene `cajas_retornables = true` y el tipo de
caja es retornable.

## RN-04 Devolucion mayor al saldo
Se registra igual, se marca `requiere_revision` y el bot advierte. En la
practica los clientes devuelven cajas de embarques no registrados; bloquear
mataria la adopcion. Configurable con `PERMITIR_SALDO_CAJAS_NEGATIVO`.

## RN-05 Asignacion de lotes
Cada linea de compra crea un lote. Las ventas consumen lotes por FIFO sobre
fecha. Si el usuario indica "esas mismas cajas", esos lotes se consumen
primero (lotes preferidos). Si no alcanza el inventario, se reporta el
faltante y se marca para revision.

## RN-06 Costo y utilidad
    costo_total = suma(asignacion.cajas * (costo_unitario + costo_indirecto))
    utilidad    = ingreso - costo_total - gastos_directos

Un gasto imputado a un lote se prorratea entre sus cajas iniciales.

## RN-07 Precios
El precio puede ser por caja o por kilo. Por kilo requiere `kg_por_caja`;
si falta, el bot lo pregunta antes de permitir confirmar.

## RN-08 Anulacion
Nunca se hace DELETE. Anular genera movimientos inversos de cajas, libera
las cajas de los lotes consumidos, marca la operacion como `anulado` y
registra el evento en auditoria.

## RN-09 Alias
Un alias se aplica automaticamente solo si la similitud es >= 0.75 Y hay un
unico candidato (o el segundo queda 0.15 por debajo). Si hay ambiguedad, el
bot pregunta con botones. Los alias creados por IA nacen sin confirmar.

## RN-10 Efectivo
El saldo de caja chica no puede quedar negativo. A diferencia de las cajas
retornables, esta regla si bloquea.
