# Backend

redis-server /opt/homebrew/etc/redis.conf
# celery -A config worker -l info
celery -A config worker -l info -Q celery --concurrency=5

celery -A config beat -l info
python manage.py runserver
python manage.py run_telegram_tasks_bot
python scripts/download_e5_model.py --output models/multilingual-e5-small
python manage.py rag_reindex_kb --workspace-id <client_id>

celery -A config worker -l info -Q media --concurrency=1 



# Frontend DevOps Guide

Path: `/Users/pavellebedev/Desktop/proj/zavod/frontend`
npm install 

## Stack Overview
- [Next.js 15.5.12] npm install next@15.5.12
- TypeScript + Tailwind CSS + Radix UI components
- Node package manager: npm (lockfile: `package-lock.json`)

## Prerequisites
- Node.js **>= 18.18** (20 LTS recommended because React 19 RC benefits from the latest V8 features).
- npm **>= 10** (bundled with Node 20).
- System packages needed for building native dependencies are not required; everything is pure JS/TS.
- Ensure outbound network access from the build host to install npm packages (registry.npmjs.org).

Use `nvm use 20` (or similar) locally so dev/prod match. In CI, pin the Node runtime explicitly, e.g. `actions/setup-node@v4` with `node-version: 20`.

## Environment Configuration
Next.js reads environment variables at build time. Create `frontend/.env.local` (gitignored) with:

```env
NEXT_PUBLIC_API_URL=https://api.example.com           # Base URL of backend REST API (no trailing slash)
NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=MyAwesomeBot        # Telegram bot username shown in the login modal
NEXT_PUBLIC_VK_AUTH_REDIRECT_URI=https://app.example.com/auth/vk/callback  # VK callback page on frontend
NEXT_PUBLIC_DEV_MODE=false                            # 'true' enables dev-only UI (video generation, dev login)
```

Notes:
- `NEXT_PUBLIC_API_URL` is used by all fetches (`/api/auth/…`, `/api/...`). Because fetch calls use `credentials: 'include'`, the backend must send `Access-Control-Allow-Credentials: true` and `Access-Control-Allow-Origin` must match the frontend origin.
- `NEXT_PUBLIC_DEV_MODE` gates `useCanGenerateVideo` and enables the PUT `/api/auth/telegram` dev login shortcut. Leave `false` in production.
- `NEXT_PUBLIC_VK_AUTH_REDIRECT_URI` must match the VK app trusted redirect and Django `VK_AUTH_REDIRECT_URI`.
- Any change requires rebuilding because the values are baked into the client bundle.

## Installing Dependencies
```bash
cd /Users/pavellebedev/Desktop/proj/zavod/frontend
npm ci   # preferred for CI/prod
# or npm install for local hacking
```
`npm ci` deletes `node_modules` and installs exactly what `package-lock.json` specifies.

## Useful npm Scripts
| Command        | Purpose |
| -------------- | ------- |
| `npm run dev`  | Start Next.js dev server on port 3000 (use `-p` to change). |
| `npm run build`| Production build, outputs `.next` artifacts. |
| `npm run start`| Run the compiled Next.js server (expects previous build). Honors `PORT`/`HOST`. |
| `npm run lint` | ESLint + Next lint rules. Run in CI to fail on lint errors. |

## Local Development Workflow
1. Copy `.env.local` as described above.
2. `npm install` (first time) or `npm ci`.
3. `npm run dev -- --hostname 0.0.0.0 --port 3000` if you need LAN access.
4. Point the backend (`NEXT_PUBLIC_API_URL`) to your staging/Django server (default fallback is `http://localhost:4000`).
5. Visit `http://localhost:3000/login` and ensure Telegram modal loads without the "NEXT_PUBLIC_API_URL не задан" error.

## Production Build & Runtime
Typical pipeline:
1. `npm ci`
2. `npm run lint`
3. `npm run build`
4. Persist `.next`, `package.json`, `package-lock.json`, and `node_modules` (if you install on the build host) to the deployment target.
5. Launch with `npm run start -- --port 3000` (or set `PORT`).

Deploy behind a reverse proxy (nginx, Caddy, etc.) that terminates TLS and forwards to the Node process. Example systemd unit:

```ini
[Unit]
Description=Zavod Frontend
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/zavod/frontend
Environment=NODE_ENV=production
EnvironmentFile=/opt/zavod/frontend/.env.local
ExecStart=/usr/bin/npm run start -- --port 3000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Expose via proxy:
```
443 -> nginx -> http://127.0.0.1:3000
```

## Backend/API Integration
- All API calls go through `NEXT_PUBLIC_API_URL` (default fallback `http://localhost:4000`). Endpoints used today:
  - `POST /api/auth/logout/` (AppShell logout)
  - `GET/POST/PUT/DELETE /api/auth/telegram` (TelegramAuth component)
  - `GET /api/auth/vk/url`, `GET/POST/DELETE /api/auth/vk` (VKAuth component)
  - `GET /api/...` routes consumed in other `app/*` pages
- Cookies: the frontend always sends cookies; configure backend CORS accordingly (allow credentials + allowed origin = frontend URL).
- When serving from a different domain than the backend, remember to set `SameSite=None; Secure` on auth cookies.

Backend env for VK login:
```env
VK_AUTH_APP_ID=12345678
VK_AUTH_APP_SECRET=your-vk-app-secret
VK_AUTH_REDIRECT_URI=https://app.example.com/auth/vk/callback
```

VK app settings must include the same trusted redirect URI.

## Telegram Auth Integration
- `components/auth/TelegramAuth.tsx` displays instructions that mention the bot username. Keep `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` in sync with the real bot.
- The optional dev login (`PUT /api/auth/telegram`) only renders when `NEXT_PUBLIC_DEV_MODE === 'true'`. Keep it disabled in prod to hide the control.

## VK Auth Integration
- `components/auth/VKAuth.tsx` starts popup login via `GET /api/auth/vk/url`.
- Callback page is `app/auth/vk/callback/page.tsx`; it uses `postMessage` for popup flow and direct `POST /api/auth/vk` fallback when popup is blocked.
- `VK_AUTH_REDIRECT_URI` (backend) and `NEXT_PUBLIC_VK_AUTH_REDIRECT_URI` (frontend) must be identical and registered in VK app settings.

## Verification Checklist
- `curl -I https://frontend-domain/` returns `200`.
- Browser console has no `NEXT_PUBLIC_API_URL` warning.
- Login modal reaches `/api/auth/telegram` without CORS errors (check Network tab).
- VK login works in both modes: popup + fallback redirect when popup is blocked.
- `npm run lint` passes in CI before deploy.

## Troubleshooting
- **Build fails with Node version error** → ensure Node >= 18.18; ideally use Node 20.
- **CORS/credential errors** → confirm backend sends `Access-Control-Allow-Credentials: true` and `Access-Control-Allow-Origin` with the exact scheme+host of this frontend.
- **Env changes not applied** → rerun `npm run build`; Next.js reads env vars at build time.
- **High memory usage during build** → allocate ~2 GB RAM; Next.js 15 with React 19 can spike during SWC compilation.

## Housekeeping
- Keep `package-lock.json` committed; it defines reproducible installs.
- Renovate/Dependabot should watch for Next.js canary updates; React 19 RC can change APIs quickly.
- When rotating backend URLs, Telegram bots, or VK redirect URIs, update env vars + redeploy; no code changes required unless routes change.


### REDIS ubuntu###

На **Ubuntu** Redis обычно запускают **через systemd**, а не вручную. Это проще, стабильнее и автоматически поднимается при перезагрузке.

## ✅ Как запустить Redis на Ubuntu

### 1. Убедись, что Redis установлен

```bash
redis-server --version
```

Если нет — установи:

```bash
sudo apt update
sudo apt install redis-server
```

### 2. Включи systemd-режим (если нужен классический standalone)

На новых Ubuntu Redis ставится в режиме supervised = systemd, обычно менять ничего не нужно.

Проверить конфиг:

```bash
sudo nano /etc/redis/redis.conf
```

Проверь строку:

```
supervised systemd
```

(если стоит `no`, поменяй на `systemd`)

### 3. Запусти службу Redis

```bash
sudo systemctl start redis-server
```

### 4. Включи автозапуск при загрузке

```bash
sudo systemctl enable redis-server
```

### 5. Проверить статус

```bash
systemctl status redis-server
```

### 6. Проверить, что Redis работает

```bash
redis-cli ping
```


sudo nano /etc/systemd/system/celery-beat.service

[Unit]
Description=Celery Beat
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=next
Group=next
WorkingDirectory=/var/py/zavod/backend

Environment=PATH=/var/py/zavod/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
Environment=PYTHONPATH=/var/py/zavod/backend
Environment=DJANGO_SETTINGS_MODULE=config.settings.dev
EnvironmentFile=/var/py/zavod/backend/.env

ExecStart=/var/py/zavod/.venv/bin/celery -A config beat -l info

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl enable celery-beat.service
sudo systemctl start celery-beat.service
