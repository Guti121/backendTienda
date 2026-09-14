# Desplegar en un VPS Ubuntu (Docker)

Todo corre en contenedores: `db` (MySQL), `redis`, `web` (gunicorn), `worker`
(Celery, código de barras bajo demanda) y `nginx` (reverse proxy). Estático y
media van a S3 (ya configurado en `settings/production.py`), así que el VPS no
necesita disco para eso ni backups de imágenes.

## 1. Preparar el VPS

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # cerrar sesión y volver a entrar para que aplique
```

Firewall mínimo (ajustá si usás otra cosa):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
```

`db` y `redis` **no publican puertos al host** (solo se ven dentro de la red
del compose) — no hace falta ni conviene abrirlos en el firewall.

## 2. Clonar y configurar

```bash
git clone <tu-repo> tienda-backend
cd tienda-backend
cp .env.production.example .env
nano .env   # rellenar SECRET_KEY, ALLOWED_HOSTS (la IP del VPS), DB_*, AWS_*
```

Puntos clave del `.env` (ver comentarios en `.env.production.example`):
- `DJANGO_ALLOWED_HOSTS`: la IP del VPS (sumá el dominio cuando lo tengas).
- `DJANGO_SECURE_SSL_REDIRECT=False` y `DJANGO_SECURE_HSTS_SECONDS=0`: **dejalos
  así mientras no haya dominio + HTTPS** — nginx todavía sirve solo HTTP, y si
  Django exige redirect a HTTPS el sitio queda inalcanzable.
- `DB_PASSWORD`/`DB_ROOT_PASSWORD`: claves fuertes y distintas entre sí.

## 3. Levantar

```bash
docker compose up -d --build
docker compose ps                 # los 5 servicios "healthy"/"running"
```

Primera vez (BD nueva, sin datos):

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py collectstatic --noinput
```

Verificar:

```bash
curl -i http://<ip-del-vps>/healthz/     # {"status": "ok"}
docker compose logs web worker --tail=50
```

## 4. Actualizar una versión nueva

```bash
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate
```

## 5. Cuando tengas dominio (HTTPS)

1. Apuntá el DNS del dominio a la IP del VPS.
2. Instalá certbot y sacá el certificado (método webroot, sin bajar nginx):
   ```bash
   sudo apt install -y certbot
   sudo certbot certonly --webroot -w /var/www/certbot -d tu-dominio.com
   ```
   (Requiere sumar un `location /.well-known/acme-challenge/` en
   `deploy/nginx/default.conf` apuntando a ese `webroot`, montado como volumen
   en el servicio `nginx` — o usar `certbot --standalone` parando `nginx` un
   momento.)
3. Sumá un `server { listen 443 ssl; ... }` en `deploy/nginx/default.conf` con
   `ssl_certificate`/`ssl_certificate_key` apuntando a los archivos de certbot
   (montalos como volumen en el servicio `nginx`), y hacé que el bloque de 80
   redirija a 443.
4. En `.env`: quitá `DJANGO_SECURE_SSL_REDIRECT`/`DJANGO_SECURE_HSTS_SECONDS`
   (o ponelos en `True`/`31536000`) y `docker compose up -d` para que tomen el
   nuevo valor.
5. Renovación automática: `sudo crontab -e` →
   `0 3 * * * certbot renew --quiet && docker compose restart nginx`.

## Notas

- No hay `beat` de Celery — los reportes de inventario se calculan al leer
  (ver `apps/inventario/api/cache.py`). El `worker` solo procesa el código de
  barras bajo demanda.
- `GUNICORN_WORKERS` en `.env` (default 3): regla general, `2 × núcleos + 1`.
- Sin backup automatizado todavía: `docker compose exec db mysqldump -u root
  -p"$DB_ROOT_PASSWORD" tienda > backup.sql` a mano, o programar un cron con
  ese comando.
- No hay monitoreo de errores (Sentry ni similar) — un 500 en producción hoy
  solo se ve con `docker compose logs web`.
