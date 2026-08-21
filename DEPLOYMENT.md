# AegisOps — DEPLOYMENT.md

> A security-governed autonomous incident response platform where AI agents investigate incidents and perform operational actions only within cryptographically authorized scopes.

---

## 1. Local Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### Setup Environment
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. (Optional) Set `ARMORIQ_API_KEY` and `AEGISOPS_GEMINI_API_KEY` in `.env` for live mode. Without keys, the system runs hermetically in local test fallback mode.

### Running Locally

1. **Start Infrastructure (`auth-api`)**:
   ```bash
   docker compose up -d
   ```
2. **Start MCP Servers**:
   ```bash
   scripts/start_mcps.sh
   ```
3. **Start Agent Processes**:
   ```bash
   scripts/start_agents.sh
   ```
4. **Start Backend API**:
   ```bash
   .venv/Scripts/python -m uvicorn api.main:app --reload --port 8000
   ```
5. **Start Frontend (Vite)**:
   ```bash
   cd frontend
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## 2. Docker Production Deployment

### Prerequisites
- Docker Engine 24+ & Docker Compose 2.20+

### Configuration
1. Copy `.env.production.example` to `.env.production`:
   ```bash
   cp .env.production.example .env.production
   ```
2. Set secure production credentials (`AEGISOPS_API_PASSWORD`, `AEGISOPS_API_SECRET_KEY`, `ARMORIQ_API_KEY`, etc.).

### Build & Run
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

- **Frontend Console**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **Auth API**: `http://localhost:8080`

---

## 3. Health & Readiness Endpoints

- **Liveness**: `GET /api/health/live` — Returns `{"status": "alive"}`.
- **Readiness**: `GET /api/health/ready` — Checks SQLite database connectivity.

---

## 4. Backup & Data Safety

SQLite databases are stored under `database/`:
- `database/aegisops.db` — Persistent incidents and timeline events.
- `database/audit.db` — Audit mirror events.

**Backup**:
```bash
cp database/aegisops.db database/aegisops_backup_$(date +%Y%m%d).db
cp database/audit.db database/audit_backup_$(date +%Y%m%d).db
```

**Restore**:
```bash
cp database/aegisops_backup_YYYYMMDD.db database/aegisops.db
```

---

## 5. Security Architecture

- **Authentication**: HMAC-signed bearer tokens (separate from ArmorIQ).
- **Authorization**: Cryptographic intent tokens and subtree delegations enforced by ArmorIQ Proxy (PEP).
- **Secrets Management**: Environment variables only; never logged or exposed in API responses.
- **No Arbitrary Shell Execution**: Agents communicate over HTTP/MCP; no generic `docker` shell commands executed by agents.
