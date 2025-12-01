# Frontend DevOps Guide

Path: `/Users/pavellebedev/Desktop/proj/zavod/frontend`

## Stack Overview
- [Next.js 15.0.0-canary.64](https://nextjs.org/) (App Router) with React 19 RC
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
NEXT_PUBLIC_DEV_MODE=false                            # 'true' enables dev-only UI (video generation, dev login)
```

Notes:
- `NEXT_PUBLIC_API_URL` is used by all fetches (`/api/auth/…`, `/api/...`). Because fetch calls use `credentials: 'include'`, the backend must send `Access-Control-Allow-Credentials: true` and `Access-Control-Allow-Origin` must match the frontend origin.
- `NEXT_PUBLIC_DEV_MODE` gates `useCanGenerateVideo` and enables the PUT `/api/auth/telegram` dev login shortcut. Leave `false` in production.
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
  - `GET /api/...` routes consumed in other `app/*` pages
- Cookies: the frontend always sends cookies; configure backend CORS accordingly (allow credentials + allowed origin = frontend URL).
- When serving from a different domain than the backend, remember to set `SameSite=None; Secure` on auth cookies.

## Telegram Auth Integration
- `components/auth/TelegramAuth.tsx` displays instructions that mention the bot username. Keep `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` in sync with the real bot.
- The optional dev login (`PUT /api/auth/telegram`) only renders when `NEXT_PUBLIC_DEV_MODE === 'true'`. Keep it disabled in prod to hide the control.

## Verification Checklist
- `curl -I https://frontend-domain/` returns `200`.
- Browser console has no `NEXT_PUBLIC_API_URL` warning.
- Login modal reaches `/api/auth/telegram` without CORS errors (check Network tab).
- `npm run lint` passes in CI before deploy.

## Troubleshooting
- **Build fails with Node version error** → ensure Node >= 18.18; ideally use Node 20.
- **CORS/credential errors** → confirm backend sends `Access-Control-Allow-Credentials: true` and `Access-Control-Allow-Origin` with the exact scheme+host of this frontend.
- **Env changes not applied** → rerun `npm run build`; Next.js reads env vars at build time.
- **High memory usage during build** → allocate ~2 GB RAM; Next.js 15 with React 19 can spike during SWC compilation.

## Housekeeping
- Keep `package-lock.json` committed; it defines reproducible installs.
- Renovate/Dependabot should watch for Next.js canary updates; React 19 RC can change APIs quickly.
- When rotating backend URLs or Telegram bots, update `.env.local` + redeploy; no code changes required unless routes change.
