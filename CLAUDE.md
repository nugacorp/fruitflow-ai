# Guia para Claude Code

## Que es esto
FruitFlow AI: ERP conversacional para compra-venta de berries en Mexico,
operado 100% desde Telegram (voz, texto, foto, PDF). Un solo usuario admin
en el MVP. El valor no esta en el chat sino en el modelo de datos y las
reglas de negocio: costeo por lote, control de cajas retornables y auditoria.

## Reglas innegociables
1. **El dominio es Python puro.** `backend/domain/` no importa SQLAlchemy,
   FastAPI, aiogram ni nada de infraestructura. Si necesitas algo de afuera,
   define un puerto (Protocol) en `backend/application/ports/`.
2. **Dinero es siempre `Decimal`.** Nunca float. El tipo `Dinero` lo impone.
3. **Nada se guarda sin confirmacion explicita del usuario** (RN-01).
4. **Nunca se borra nada.** Anular genera contra-asientos (RN-08).
5. **La IA extrae, la base de datos resuelve.** El modelo nunca inventa
   identificadores; los alias se resuelven con pg_trgm (RN-09).
6. **Todo texto de cara al usuario vive en `backend/interfaces/i18n/es.py`.**
7. **No se avanza de fase con pruebas en rojo.**

## Flujo de un mensaje
Telegram -> webhook (idempotente por update_id) -> si es audio/imagen/PDF,
tarea Celery para normalizar a texto -> clasificar intencion -> extraer JSON
-> resolver entidades contra la BD -> validar -> crear borrador (TTL 24h) ->
tarjeta de confirmacion -> callback GUARDAR -> caso de uso -> una transaccion
-> eventos -> respuesta.

## Comandos
    make install     instalar dependencias
    make up          levantar stack local
    make test        pruebas
    make lint        formato y estilo
    make typecheck   mypy
    make migrate     migraciones
    make seed        datos de desarrollo

## Donde esta cada cosa
    backend/domain/          reglas de negocio puras (empieza aqui)
    backend/application/     casos de uso, puertos, unit of work
    backend/infrastructure/  SQLAlchemy, MinIO, OpenAI, Celery
    backend/interfaces/      FastAPI e i18n
    telegram_bot/            aiogram: handlers, teclados, formateadores
    worker/                  tareas asincronas y programadas
    prompts/                 prompts de IA versionados
    sql/                     esquema de referencia
    docs/                    especificacion completa
    PLAN.md                  plan de ejecucion por fases

## Si algo no esta especificado
No lo inventes. Consulta `docs/11-Decisiones-abiertas.md`, usa el default
que ahi se indica y deja un `TODO(decision-N)`. Si no hay default, pregunta.
