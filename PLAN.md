# PLAN.md — FruitFlow AI

Regla: no se avanza de fase con pruebas en rojo.
Marca cada tarea con [x] y haz commit al cerrar la fase.

---

## FASE 0 — Bootstrap  [x] COMPLETADA
- [x] Estructura de carpetas, pyproject, Makefile, .env.example, .gitignore
- [x] pre-commit con ruff y mypy
Verificacion: `make lint`

## FASE 1 — Infraestructura local  [~] PARCIAL
- [x] Dockerfile multi-stage con tres objetivos (backend, bot, worker)
- [x] docker-compose.yml con Postgres 17, Redis, MinIO y healthchecks
- [x] `/health` que verifica Postgres y Redis
- [x] Config con pydantic-settings
- [ ] Logs estructurados JSON con structlog y request_id
Verificacion: `make up && curl localhost:8000/health`

## FASE 2 — Base de datos  [~] PARCIAL
- [x] Esquema SQL completo (sql/001_schema.sql, 22 tablas)
- [x] Vistas de lectura (sql/002_vistas.sql)
- [x] Modelos SQLAlchemy 2.0 con bloqueo optimista
- [x] scripts/seed_dev.py
- [ ] alembic/env.py y migracion inicial
- [ ] Prueba de integracion con testcontainers
Verificacion: `make migrate && make seed`

## FASE 3 — Dominio puro  [x] COMPLETADA
- [x] Dinero (Decimal), Peso, UUIDv7, errores tipados, eventos
- [x] Politica de cajas con tabla de signos (RN-03, RN-04, RN-08)
- [x] Costeo FIFO por lote con lotes preferidos (RN-05)
- [x] Importes por caja y por kilo (RN-07)
- [x] Utilidad, prorrateo de gastos y margen (RN-06)
- [x] 34 pruebas unitarias incluyendo casos borde
Verificacion: `pytest tests/unit/domain` -> 34 pasan

## FASE 4 — Persistencia  [~] CASI COMPLETA
- [x] UnitOfWork que persiste eventos de dominio en auditoria
- [x] Puertos de repositorio (Protocol) en application/ports
- [x] Puerto UnidadDeTrabajo y adaptadores en memoria (tests/fakes.py)
- [x] Repositorios SQLAlchemy: contrapartes, compras, ventas, lotes,
      movimientos, pagos, gastos, borradores y catalogos
- [x] UnitOfWorkSQLAlchemy conectado a obtener_uow
- [x] Esquema al arranque (pg_trgm + create_all + empresa por defecto);
      TODO(fase-2): reemplazar por alembic
- [x] Busqueda difusa real con pg_trgm (buscar_por_nombre)
- [ ] Repositorio de documentos (fase 9 lo necesita)
Verificacion: `TEST_DATABASE_URL=... pytest tests/integration/db`

## FASE 5 — Casos de uso  [x] COMPLETADA
- [x] Agregados de dominio: armar_compra, armar_venta, finanzas (RN-10)
- [x] registrar_compra, registrar_venta, registrar_devolucion_cajas
- [x] registrar_pago, registrar_gasto (con prorrateo a lote), anular_operacion
- [x] crear_borrador, confirmar_borrador, editar_borrador, cancelar, expirar
      (RN-01: confirmacion y operacion en una sola transaccion)
- [x] Consultas: saldo_cajas, cxc, cxp, resumen_dia, utilidad, margen
Verificacion: `pytest tests/integration/use_cases` -> 29 pasan (en memoria)

## FASE 6 — API HTTP  [~] PARCIAL
- [x] App FastAPI con manejo de ErrorDominio (422, nunca 500)
- [x] Routers /v1: compras, ventas, devoluciones, pagos, gastos, anulaciones,
      saldos, resumen y ciclo de borradores
- [x] Autenticacion por X-Internal-Key (interfaces/http/dependencias.py)
- [x] obtener_uow conectado a SQLAlchemy (e2e sigue usando memoria)
- [ ] Rate limit con Redis
Verificacion: `pytest tests/e2e/api` -> 8 pasan; /docs accesible

## FASE 7 — Bot de texto  [~] PARCIAL
- [x] Dispatcher, middleware de whitelist, teclados, formateadores
- [x] Comandos /start y /ayuda
- [x] Handler de texto conectado a la API (extraccion -> resolucion -> borrador -> tarjeta)
- [x] Callbacks GUARDAR / EDITAR / CANCELAR conectados
- [x] Flujo de edicion campo por campo (FSM aiogram)
- [x] Comandos /cajas, /saldo, /debo, /medeben y /pendientes conectados
- [x] Panel web /panel (solo lectura, HTTP Basic con la llave interna)
- [ ] Guion manual de 10 casos en docs/06 ejecutado contra Telegram real
Verificacion: guion manual de 10 casos en docs/06

## FASE 8 — Motor IA  [~] PARCIAL
- [x] Prompts versionados y JSON Schema estricto
- [x] Esquemas Pydantic con limpieza de montos y campos faltantes
- [x] Resolutor de alias con umbral 0.75 y deteccion de ambiguedad
- [x] 16 golden tests
- [~] Cliente OpenAI con tenacity y timeout (falta limite de gasto diario)
- [ ] Registro de llamadas en ia_llamadas
Verificacion: `pytest tests/unit/ai` -> 16 pasan

## FASE 9 — Multimedia  [ ] PENDIENTE
- [ ] Descarga de Telegram a MinIO con deduplicacion por sha256
- [ ] Transcripcion con Whisper (worker/tasks/transcribir.py)
- [ ] PDF con PyMuPDF, respaldo Tesseract (worker/tasks/ocr.py)
- [ ] Fotos con Vision usando prompts/extraer_documento.md
Verificacion: un audio, una foto y un PDF reales producen borrador correcto

## FASE 10 — Reportes  [ ] PENDIENTE
- [x] Celery beat configurado (resumen 20:00, cajas 08:00, expirar borradores)
- [ ] worker/tasks/reportes.py y mantenimiento.py implementados
- [ ] /reporte con CSV adjunto
Verificacion: forzar la tarea y recibir el mensaje

## FASE 11 — Produccion  [~] PARCIAL
- [x] docker-compose.prod.yml con Traefik y Let's Encrypt
- [x] scripts/backup.sh y restore.sh
- [x] GitHub Actions: calidad, publicacion GHCR, despliegue SSH
- [ ] Endurecimiento del servidor ejecutado
- [ ] Sentry conectado en los tres contenedores
- [ ] Restauracion de respaldo ENSAYADA en servidor limpio
- [ ] Runbook escrito
Verificacion: checklist go-live completo

## FASE 12 — Piloto real  [ ] PENDIENTE
- [ ] Dos semanas en paralelo con la libreta
- [ ] Saldos de cajas reconciliados
- [ ] Frases fallidas agregadas a golden tests
- [ ] Retirar la libreta

---

## Checklist go-live

- [ ] Restauracion de respaldo ensayada con exito
- [ ] Webhook con HTTPS valido y secret_token verificado
- [ ] Whitelist probada con una cuenta ajena
- [ ] Presupuesto diario de IA configurado
- [ ] Sentry recibiendo errores de los tres contenedores
- [ ] Uptime Kuma vigilando /health con alerta a Telegram
- [ ] Resumen diario llegando a las 20:00
- [ ] 20 operaciones reales sin correccion manual
- [ ] Saldos de cajas cuadran contra la libreta dos semanas
- [ ] Runbook escrito
