# FruitFlow AI

ERP conversacional para comercializacion de fruta, operado desde Telegram.

Mandas un mensaje de voz diciendo "compramos 220 cajas de frambuesa a Los
Pinos a 385", el sistema lo entiende, te muestra una tarjeta para confirmar,
y al confirmar registra la compra, crea el lote de inventario y actualiza
las cajas que le debes al proveedor.

## Que resuelve

- Registro de compras y ventas sin capturar en Excel
- Costeo por lote (FIFO) y utilidad real por operacion
- **Control de cajas retornables con dueno**: cuando el proveedor te entrega
  fruta en sus cajas, tu quedas debiendo; cuando entregas al cliente, el
  cliente te debe. El saldo se lleva por contraparte y tipo de caja.
- Cuentas por cobrar y por pagar
- Resumen diario automatico y recordatorio de cajas pendientes

## Arranque rapido

    cp .env.example .env       # llena TELEGRAM_BOT_TOKEN y OPENAI_API_KEY
    make up
    make migrate
    make seed
    curl localhost:8000/health

## Estado

El dominio, el motor de extraccion y el esquema de datos estan implementados
y probados (50 pruebas unitarias). Ver `PLAN.md` para las fases pendientes.

## Documentacion

    CLAUDE.md   guia para trabajar con Claude Code
    PLAN.md     plan de ejecucion por fases
    docs/       especificacion completa
