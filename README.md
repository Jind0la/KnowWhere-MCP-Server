# Knowwhere Memory MCP Server

**The persistent, intelligent memory layer that makes AI agents remember everything—deployable anywhere, integrated nowhere.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Knowwhere Memory MCP Server is a vendor-agnostic, distributed memory infrastructure for AI agents that integrates with any AI service via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

### Key Features

- **🧠 Multimodal Memory Storage** - Episodic, semantic, preference, procedural, and meta-cognitive memories
- **🔍 Intelligent Semantic Search** - Vector similarity search with pgvector
- **🔄 Session Consolidation** - Automatically extract memories from conversations
- **📊 Evolution Tracking** - Track how preferences change over time
- **🔒 GDPR Compliant** - Data export and deletion support
- **🌐 Vendor Agnostic** - Works with Claude, GPT, Grok, Gemini via MCP

## Quick Start

Für eine schnelle Testinstallation mit Docker:

```bash
git clone https://github.com/your-org/knowwhere-memory-mcp.git
cd knowwhere-memory-mcp
cp .env.example .env
# Editiere .env mit deinen API-Keys
docker-compose up -d
```

---

## Detaillierte Installationsanleitung

### Inhaltsverzeichnis

1. [Systemvoraussetzungen](#1-systemvoraussetzungen)
2. [Lokale Entwicklungsumgebung](#2-lokale-entwicklungsumgebung)
3. [Datenbank-Setup](#3-datenbank-setup)
4. [Redis Cache Setup](#4-redis-cache-setup)
5. [Umgebungsvariablen konfigurieren](#5-umgebungsvariablen-konfigurieren)
6. [Server starten](#6-server-starten)
7. [Docker Installation](#7-docker-installation)
8. [Produktions-Deployment](#8-produktions-deployment)
9. [Fehlerbehebung](#9-fehlerbehebung)

---

### 1. Systemvoraussetzungen

#### Mindestanforderungen

| Komponente | Version | Hinweis |
|-----------|---------|---------|
| **Python** | 3.11+ | [Download](https://www.python.org/downloads/) |
| **PostgreSQL** | 14+ | Mit pgvector Extension |
| **Redis** | 7.0+ | Optional, aber empfohlen |
| **Tesseract** | 5.0+ | Nur für Dokument-OCR |

#### Benötigte API-Keys

| Service | Zweck | Link |
|---------|-------|------|
| **OpenAI** | Embeddings (text-embedding-3-large) | [API Keys](https://platform.openai.com/api-keys) |
| **Anthropic** ODER **OpenAI** | LLM für Consolidation | [Console](https://console.anthropic.com/) |
| **AWS S3 / Cloudflare R2** | Dokumenten-Upload (optional) | - |

---

### 2. Lokale Entwicklungsumgebung

#### 2.1 Repository klonen

```bash
git clone https://github.com/your-org/knowwhere-memory-mcp.git
cd knowwhere-memory-mcp
```

#### 2.2 Python Virtual Environment erstellen

**macOS / Linux:**
```bash
python3.11 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### 2.3 Dependencies installieren

```bash
# Produktions-Dependencies
pip install -r requirements.txt

# Entwickler-Dependencies (Tests, Linting)
pip install -e ".[dev]"
```

#### 2.4 Überprüfung der Installation

```bash
python -c "import fastmcp; print('✅ FastMCP:', fastmcp.__version__)"
python -c "import asyncpg; print('✅ asyncpg installiert')"
python -c "import anthropic; print('✅ Anthropic SDK installiert')"
```

---

### 3. Datenbank-Setup

#### Option A: PostgreSQL lokal installieren

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16

# pgvector Extension installieren
brew install pgvector
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-16 postgresql-16-pgvector

sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
1. Download PostgreSQL von [postgresql.org](https://www.postgresql.org/download/windows/)
2. pgvector manuell installieren: [pgvector Windows Guide](https://github.com/pgvector/pgvector#windows)

#### Option B: Supabase verwenden (empfohlen für Produktion)

1. Erstelle ein Projekt auf [supabase.com](https://supabase.com)
2. pgvector ist bereits aktiviert
3. Kopiere die Connection URL aus Settings → Database

#### 3.1 Datenbank und Benutzer erstellen

```bash
# Als postgres User anmelden
sudo -u postgres psql

# In psql:
CREATE USER knowwhere WITH PASSWORD 'sicheres_passwort_hier';
CREATE DATABASE knowwhere OWNER knowwhere;
GRANT ALL PRIVILEGES ON DATABASE knowwhere TO knowwhere;

# pgvector Extension aktivieren (als Superuser)
\c knowwhere
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

\q
```

#### 3.2 Schema-Migration ausführen

```bash
# Initiales Schema
psql -h localhost -U knowwhere -d knowwhere -f migrations/001_initial_schema.sql

# Row-Level Security (optional, für Multi-Tenant)
psql -h localhost -U knowwhere -d knowwhere -f migrations/002_enable_rls.sql
```

#### 3.3 Migration verifizieren

```bash
psql -h localhost -U knowwhere -d knowwhere -c "\dt"
```

Erwartete Tabellen:
```
 Schema |         Name          | Type  |  Owner   
--------+-----------------------+-------+----------
 public | access_logs           | table | knowwhere
 public | api_keys              | table | knowwhere
 public | consolidation_history | table | knowwhere
 public | document_chunks       | table | knowwhere
 public | files                 | table | knowwhere
 public | knowledge_edges       | table | knowwhere
 public | memories              | table | knowwhere
 public | schema_migrations     | table | knowwhere
 public | users                 | table | knowwhere
```

---

### 4. Redis Cache Setup

Redis ist optional, aber **dringend empfohlen** für:
- Rate Limiting
- Embedding-Caching (spart API-Kosten)
- Session State

#### Option A: Redis lokal installieren

**macOS:**
```bash
brew install redis
brew services start redis

# Testen
redis-cli ping  # Sollte "PONG" zurückgeben
```

**Ubuntu/Debian:**
```bash
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

redis-cli ping
```

**Windows:**
```bash
# Mit WSL2 oder Docker empfohlen
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

#### Option B: Redis Cloud verwenden

- [Upstash](https://upstash.com) (Serverless Redis, Free Tier)
- [Redis Cloud](https://redis.com/cloud/)

---

### 5. Umgebungsvariablen konfigurieren

#### 5.1 Template kopieren

```bash
cp .env.example .env
```

#### 5.2 .env Datei editieren

```bash
# Mit deinem bevorzugten Editor
nano .env
# oder
code .env
```

#### 5.3 Minimale Konfiguration

```env
# ============================================
# PFLICHT-KONFIGURATION
# ============================================

# Datenbank
DATABASE_URL=postgresql://knowwhere:dein_passwort@localhost:5432/knowwhere

# Supabase (für Auth, kann lokal leer sein)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# OpenAI für Embeddings
OPENAI_API_KEY=sk-proj-...

# LLM für Consolidation (wähle eines)
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...

# ============================================
# OPTIONALE KONFIGURATION
# ============================================

# Redis (dringend empfohlen)
REDIS_URL=redis://localhost:6379

# Debug-Modus (für Entwicklung)
DEBUG=true

# JWT Secret (WICHTIG: in Produktion ändern!)
JWT_SECRET_KEY=dein-super-geheimes-jwt-secret-min-32-zeichen
```

#### 5.4 Vollständige Konfigurationsreferenz

| Variable | Pflicht | Standard | Beschreibung |
|----------|---------|----------|--------------|
| `DATABASE_URL` | ✅ | - | PostgreSQL Connection String |
| `OPENAI_API_KEY` | ✅ | - | Für Embeddings |
| `LLM_PROVIDER` | ✅ | `anthropic` | `anthropic` oder `openai` |
| `ANTHROPIC_API_KEY` | Wenn LLM=anthropic | - | Claude API Key |
| `REDIS_URL` | ❌ | `redis://localhost:6379` | Cache URL |
| `JWT_SECRET_KEY` | ⚠️ Produktion | Fallback | Min. 32 Zeichen |
| `RATE_LIMIT_ENABLED` | ❌ | `true` | Rate Limiting aktiv |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | ❌ | `100` | Requests pro Minute |
| `STORAGE_PROVIDER` | ❌ | `s3` | `s3`, `r2`, `gcs` |
| `STORAGE_BUCKET` | ❌ | `knowwhere-documents` | Bucket Name |

---

### 6. Server starten

#### 6.1 Entwicklungsmodus

```bash
# Aktiviere venv falls nötig
source venv/bin/activate

# Server starten
python -m src.main
```

Erwartete Ausgabe:
```
2024-01-17T10:30:00.000Z [info] Knowwhere Memory MCP Server starting host=0.0.0.0 port=8000 debug=true
2024-01-17T10:30:00.100Z [info] Database connected
2024-01-17T10:30:00.150Z [info] Redis cache connected
2024-01-17T10:30:00.200Z [info] Audit logger started
2024-01-17T10:30:00.210Z [info] Rate limiter initialized
```

#### 6.2 Health Check

```bash
# In einem neuen Terminal
curl http://localhost:8000/health || echo "Server läuft als MCP, nicht als HTTP"
```

#### 6.3 Mit Claude Desktop verbinden

Editiere `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) oder `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "knowwhere": {
      "command": "/pfad/zu/venv/bin/python",
      "args": ["-m", "src.main"],
      "cwd": "/pfad/zu/knowwhere-memory-mcp",
      "env": {
        "DATABASE_URL": "postgresql://knowwhere:passwort@localhost:5432/knowwhere",
        "OPENAI_API_KEY": "sk-...",
        "LLM_PROVIDER": "anthropic",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Starte Claude Desktop neu, um die Änderungen zu übernehmen.

---

### 7. Docker Installation

#### 7.1 Docker Compose (empfohlen für lokale Entwicklung)

```bash
# .env konfigurieren
cp .env.example .env
nano .env

# Alle Services starten
docker-compose up -d

# Logs anzeigen
docker-compose logs -f app
```

Das startet:
- **app**: Knowwhere MCP Server
- **db**: PostgreSQL 16 mit pgvector
- **redis**: Redis 7

#### 7.2 Nur Datenbank & Redis mit Docker

Falls du den Server lokal entwickeln willst:

```bash
# Nur PostgreSQL und Redis
docker-compose up -d db redis

# Server lokal starten
source venv/bin/activate
python -m src.main
```

#### 7.3 Docker Image bauen

```bash
# Image bauen
docker build -t knowwhere-mcp:latest .

# Container starten
docker run -d \
  --name knowwhere \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e OPENAI_API_KEY="sk-..." \
  knowwhere-mcp:latest
```

---

### 8. Produktions-Deployment

#### 8.1 Railway (empfohlen)

1. Forke das Repository zu deinem GitHub
2. Erstelle ein neues Projekt auf [railway.app](https://railway.app)
3. Füge Services hinzu:
   - **PostgreSQL** (Add-on)
   - **Redis** (Add-on)
4. Verbinde dein GitHub Repository
5. Setze Umgebungsvariablen im Dashboard:
   ```
   OPENAI_API_KEY=sk-...
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   JWT_SECRET_KEY=...
   ```
6. Railway erkennt `railway.toml` und deployed automatisch

#### 8.2 Render

1. Erstelle einen neuen **Web Service**
2. Verbinde GitHub Repository
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn src.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
5. Füge PostgreSQL und Redis als Add-ons hinzu

#### 8.3 AWS / GCP / Azure

Für Self-Hosting mit Kubernetes:

```bash
# Docker Image zu Registry pushen
docker tag knowwhere-mcp:latest your-registry.io/knowwhere-mcp:latest
docker push your-registry.io/knowwhere-mcp:latest

# Kubernetes Deployment (Beispiel)
kubectl apply -f k8s/deployment.yaml
```

---

### 9. Fehlerbehebung

#### ❌ "FATAL: password authentication failed"

```bash
# PostgreSQL Benutzer neu erstellen
sudo -u postgres psql
ALTER USER knowwhere WITH PASSWORD 'neues_passwort';
```

#### ❌ "extension vector does not exist"

```bash
# pgvector nachinstallieren
# macOS:
brew install pgvector

# Dann in psql:
CREATE EXTENSION vector;
```

#### ❌ "Redis connection refused"

```bash
# Redis Status prüfen
redis-cli ping

# Falls nicht läuft:
# macOS:
brew services start redis

# Linux:
sudo systemctl start redis-server
```

#### ❌ "OpenAI API error: rate limit"

Die Standard-Embedding-Rate ist begrenzt. Lösungen:
1. Redis-Cache aktivieren (reduziert API-Calls drastisch)
2. OpenAI Tier upgraden
3. `RATE_LIMIT_REQUESTS_PER_MINUTE` reduzieren

#### ❌ "JWT secret key not set"

```bash
# Sicheren Key generieren
python -c "import secrets; print(secrets.token_urlsafe(32))"

# In .env eintragen:
JWT_SECRET_KEY=dein_generierter_key
```

#### ❌ Module nicht gefunden

```bash
# Sicherstellen, dass venv aktiviert ist
which python  # Sollte venv/bin/python zeigen

# Dependencies neu installieren
pip install -r requirements.txt --force-reinstall
```

---

### Nächste Schritte

Nach erfolgreicher Installation:

1. **Ersten Memory erstellen**: Teste mit Claude Desktop den `remember` Befehl
2. **API-Key erstellen**: Für Server-zu-Server Integration
3. **Monitoring einrichten**: Logs in Grafana/Datadog integrieren
4. **Backups konfigurieren**: PostgreSQL pg_dump automatisieren

## Usage

### Connecting from Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "knowwhere": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/knowwhere-memory-mcp"
    }
  }
}
```

### Available Tools

#### 1. `remember` - Store a Memory

```json
{
  "content": "User prefers async/await over callbacks",
  "memory_type": "preference",
  "importance": 8
}
```

#### 2. `recall` - Search Memories

```json
{
  "query": "What programming patterns does the user prefer?",
  "limit": 5
}
```

#### 3. `consolidate_session` - Process Conversation

```json
{
  "session_transcript": "User: I love TypeScript...",
  "conversation_id": "session-123"
}
```

#### 4. `analyze_evolution` - Track Changes

```json
{
  "entity_name": "TypeScript",
  "time_window": "last_30_days"
}
```

#### 5. `export_memories` - Export Data

```json
{
  "format": "json",
  "include_embeddings": false
}
```

#### 6. `delete_memory` - Remove Memory

```json
{
  "memory_id": "uuid-here",
  "hard_delete": false
}
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    LLM Clients                               │
│            (Claude, Grok, Gemini, Custom)                    │
└────────────────────────┬─────────────────────────────────────┘
                         │ MCP Protocol
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastMCP Server                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   6 MCP Tools                          │ │
│  │  remember | recall | consolidate | analyze | export |  │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │               Memory Engine                            │ │
│  │  MemoryProcessor | ConsolidationEngine | KnowledgeGraph│ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Storage Layer                             │ │
│  │      PostgreSQL + pgvector    |    Redis Cache         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Project Structure

```
knowwhere-memory-mcp/
├── src/
│   ├── main.py              # FastMCP entry point
│   ├── config.py            # Configuration
│   ├── tools/               # MCP tool implementations
│   ├── engine/              # Business logic
│   ├── storage/             # Data access layer
│   ├── services/            # External service clients
│   └── models/              # Pydantic models
├── migrations/              # Database migrations
├── tests/                   # Test suite
├── docker-compose.yml       # Local development
├── Dockerfile              # Production container
└── railway.toml            # Railway deployment
```

## Deployment

### Docker

```bash
docker-compose up -d
```

### Railway

1. Connect your GitHub repository to Railway
2. Add PostgreSQL and Redis add-ons
3. Set environment variables in Railway dashboard
4. Deploy!

### Vercel (Serverless)

Note: Vercel has execution time limits. Recommended for light workloads only.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/

# Type checking
mypy src/
```

## API Documentation

Full OpenAPI specification available at `/docs` when running in debug mode.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- 📚 [Documentation](https://docs.knowwhere.ai)
- 💬 [Discord Community](https://discord.gg/knowwhere)
- 🐛 [Issue Tracker](https://github.com/your-org/knowwhere-memory-mcp/issues)

---

**Made with ❤️ by the Knowwhere Team**
