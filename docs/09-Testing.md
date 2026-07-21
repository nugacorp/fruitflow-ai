# Estrategia de pruebas

## Piramide

    unit         dominio puro, sin I/O, milisegundos
    integration  testcontainers con Postgres real
    e2e          API completa y bot simulado
    golden       extraccion de IA con respuestas grabadas

## Estado actual

50 pruebas unitarias en verde:

    tests/unit/domain/test_tipos.py     5   Decimal, redondeo, monedas
    tests/unit/domain/test_cajas.py     14  signos, devoluciones, anulacion
    tests/unit/domain/test_costeo.py    15  FIFO, precio por kilo, utilidad
    tests/unit/ai/test_esquemas.py      10  frases reales del negocio
    tests/unit/ai/test_resolver.py      6   alias y ambiguedad

## Casos que nunca deben romperse

- 220 cajas a 385 vendidas a 455 dan utilidad de 15,400
- 220 entregadas menos 80 devueltas dejan 140 pendientes
- Una devolucion mayor al saldo se registra pero marca revision
- Un flete de 8,000 sobre 220 cajas sube el costo unitario a 421.36
- "Los Pinos" resuelve a "Rancho Los Pinos"; "Los" solo, no resuelve

## CI

En cada push: ruff format, ruff check, mypy y pytest con cobertura minima
de 80%. En tag `v*`: build de las tres imagenes, push a GHCR, despliegue por
SSH y verificacion de `/health`.
