# Arquitectura

Hexagonal. Las dependencias apuntan siempre hacia adentro.

    interfaces/        Telegram (aiogram), HTTP (FastAPI), CLI
        |
        v
    application/       casos de uso, puertos (Protocol), unit of work
        |
        v
    domain/            Python puro: reglas, tipos, eventos
        ^
        |
    infrastructure/    SQLAlchemy, MinIO, OpenAI, Whisper, OCR, Redis, Celery

`domain/` no importa nada de `infrastructure/`. Los casos de uso dependen de
puertos abstractos; la infraestructura los implementa y se inyecta al
arranque.

## Contenedores

Tres procesos comparten una sola imagen base y el mismo paquete `backend/`;
solo cambia el entrypoint.

- **backend**: FastAPI, recibe el webhook y expone la API interna
- **bot**: aiogram, conversa con el usuario y llama a la API
- **worker**: Celery, transcripcion, OCR, reportes programados

Mas Postgres 17, Redis, MinIO y Traefik en produccion.

## Por que asi

El dominio puro permite probar toda la logica de cajas y costeo en
milisegundos, sin base de datos ni red. Eso es lo que hace viable iterar
rapido sobre reglas de negocio que van a cambiar durante el piloto.
