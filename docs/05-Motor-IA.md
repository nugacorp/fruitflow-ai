# Motor de IA

## Pipeline

    texto normalizado
      -> clasificar intencion   (compra|venta|devolucion_cajas|pago|gasto|
                                 consulta|correccion|otro)
      -> extraer JSON estricto  (Structured Outputs con prompts/schemas/operacion.json)
      -> resolver entidades     (pg_trgm contra la BD, NO con la IA)
      -> validar                (Pydantic + reglas de dominio)
      -> borrador + preguntas por campos faltantes

## Principio central

La IA extrae texto; la base de datos resuelve identidades. Al modelo jamas
se le pide un `contraparte_id`. Devuelve `"Rancho Los Pinos"` tal cual y el
resolutor busca por similitud. Esto evita alucinaciones de identificadores,
que son el fallo mas caro en este tipo de sistema.

## Prompts

    prompts/clasificar_intencion.md
    prompts/extraer_operacion.md
    prompts/extraer_documento.md
    prompts/schemas/operacion.json

Estan versionados en el repositorio. Cualquier cambio a un prompt debe venir
acompanado de golden tests que lo respalden.

## Golden tests

`tests/unit/ai/test_esquemas.py` cubre las frases reales del negocio sin
llamar a la API: compra completa, venta con referencia anterior, devolucion
de cajas, dos operaciones en una frase, precio por kilo sin peso, gasto de
flete, montos con simbolo y comas, mensaje sin operacion, cajas negativas.

Cuando una frase real falle en el piloto, se agrega aqui antes de tocar el
prompt.

## Control de costo

Cada llamada se registra en `ia_llamadas` con modelo, tokens, costo, latencia
y exito. `AI_DAILY_BUDGET_MXN` limita el gasto diario; al superarlo el bot
avisa y pide confirmacion para continuar.
