# Despliegue en VPS

## Requisitos
VPS con 4 GB RAM, 2 vCPU, 80 GB SSD (Hetzner CX22 o similar), dominio
apuntando al servidor, Docker y Docker Compose instalados.

## Preparacion del servidor

    adduser fruitflow && usermod -aG sudo,docker fruitflow
    # /etc/ssh/sshd_config: PermitRootLogin no, PasswordAuthentication no
    ufw default deny incoming && ufw allow 22,80,443/tcp && ufw enable
    apt install fail2ban unattended-upgrades
    chmod 600 .env

## Puesta en marcha

    git clone <repo> /opt/fruitflow && cd /opt/fruitflow
    cp .env.example .env    # llenar todos los secretos
    docker compose -f docker/docker-compose.prod.yml up -d
    docker compose -f docker/docker-compose.prod.yml exec backend alembic upgrade head

Traefik obtiene el certificado de Let's Encrypt automaticamente. El webhook
de Telegram se registra al arrancar el bot con `secret_token`.

## Respaldos

`scripts/backup.sh` corre por cron a las 03:00: pg_dump cifrado con GPG,
sincronizacion a Backblaze B2 y retencion de 30 dias.

**Ensaya `scripts/restore.sh` en un servidor limpio antes de ir a
produccion.** Un respaldo que nunca se restauro no es un respaldo.

## Observabilidad

Sentry en los tres contenedores, `/health` vigilado por Uptime Kuma con
alerta a Telegram, logs estructurados en JSON.

## Costo mensual estimado

    VPS         $120-190 MXN
    OpenAI      $100-500 MXN
    Respaldos   $20 MXN
    Dominio     $200 MXN/ano
    Total       ~$300-800 MXN/mes
