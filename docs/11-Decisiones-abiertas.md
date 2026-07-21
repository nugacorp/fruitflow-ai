# Decisiones abiertas

Cuando algo no este especificado, usa el default y deja `TODO(decision-N)`.

| # | Decision | Default aplicado | Alternativa | Impacto si cambia |
|---|---|---|---|---|
| 1 | Saldo negativo de cajas | Permitir y advertir | Bloquear | Solo config, sin migracion |
| 2 | Metodo de costeo | FIFO por lote | Promedio ponderado / asignacion manual | Alto: cambia `costeo.py` y reportes historicos |
| 3 | Multi-moneda | Columna presente, siempre MXN | Tipo de cambio por operacion | Medio: requiere tabla de tipos de cambio |
| 4 | Multi-usuario | Un admin; `empresa_id` en todas las tablas | Roles y permisos | Bajo: el esquema ya lo soporta |
| 5 | Facturacion CFDI | Fuera de alcance del MVP | Integrar PAC | Alto |
| 6 | Anticipos y credito | Pagos simples sin plazos | Aging y vencimientos | Medio |
| 7 | Inventario por ubicacion | Un solo inventario global | Por bodega | Medio |
| 8 | Reversion de gastos prorrateados | Se recalcula al anular | Congelar historico | Bajo |

## Pendientes de confirmar contigo

1. **Costeo (decision 2)**: quedo FIFO. Si en la practica sueles decir
   "esas cajas eran de la compra de tal", el sistema ya lo soporta como
   excepcion, pero conviene confirmarlo antes del piloto.
2. **Merma**: hoy reduce lo que te deben. Si prefieres cobrarla al cliente,
   cambia el signo en `politica.py`.
3. **Cajas de terceros**: si un cliente devuelve cajas de OTRO tipo al que
   se le entrego, hoy se registran por separado. Si quieres equivalencias
   entre tipos, hay que agregar una tabla de conversion.
