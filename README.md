# KnowWhere Memory MCP Server

**The persistent, intelligent memory layer that makes AI agents remember everything—deployable anywhere, integrated nowhere.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)

## 🎯 Was ist KnowWhere?

KnowWhere ist ein **persistentes Gedächtnissystem** für AI-Agenten. Es speichert Präferenzen, Fakten, Learnings und Erkenntnisse aus Konversationen und macht sie projektübergreifend abrufbar.

### Das Problem
- Claude/GPT vergessen alles nach jeder Session
- Kontext geht verloren zwischen Projekten
- Du musst dich ständig wiederholen

### Die Lösung
- **Semantische Suche** über alle gespeicherten Erinnerungen
- **Automatische Extraktion** wichtiger Claims aus Konversationen
- **Projektübergreifend** - Erinnerungen folgen dir überall hin

---

## ✨ Key Features

| Feature | Beschreibung |
|---------|--------------|
| 🧠 **Multimodale Memories** | Episodic, Semantic, Preference, Procedural, Meta |
| 🚀 **Batch Processing** | Parallele Verarbeitung für bis zu 5x schnellere Konsolidierung |
| 🔍 **Semantische Suche** | Vector Similarity mit pgvector (1408 Dimensionen) + Sampling |
| 🔄 **Session Consolidation** | Automatische Claim-Extraktion mit paralleler Entity-Verarbeitung |
| 📊 **Evolution Tracking** | Verfolge wie sich Präferenzen ändern |
| 🔒 **GDPR Compliant** | Export und Löschung aller Daten |
| 🌐 **Vendor Agnostic** | Funktioniert mit Claude, GPT, Grok, Gemini via MCP |
| 📡 **MCP Resources** | Vollständige MCP Integration mit Resources, Prompts & Roots |
| 🏗️ **Dependency Injection** | Saubere Architektur für Testbarkeit und Erweiterbarkeit |

---

## 🚀 Quick Start (Docker + Supabase)

### Voraussetzungen
- Docker & Docker Compose
- [Supabase](https://supabase.com) Account (kostenlos)
- OpenAI API Key (für Embeddings)
- Anthropic API Key (für LLM)

### 1. Repository klonen

```bash
git clone https://github.com/nimarfranklin/KW_Mem_MCP_Server.git
cd KW_Mem_MCP_Server
```

### 2. Supabase Projekt erstellen

1. Gehe zu [supabase.com](https://supabase.com) → New Project
2. Aktiviere die **pgvector Extension** unter Database → Extensions
3. Kopiere die Credentials:
   - Project URL
   - Anon Key
   - **Session Pooler** Database URL (unter Settings → Database → Connection string)

### 3. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
```

Editiere `.env`:

```env
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
DATABASE_URL=postgresql://postgres.xxxxx:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:5432/postgres

# API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-api03-...
LLM_PROVIDER=anthropic

# Optional
REDIS_URL=redis://localhost:6379
DEBUG=true
JWT_SECRET_KEY=dein-geheimer-key-min-32-zeichen
```

### 4. Datenbank-Migration ausführen

Führe die Migration in Supabase SQL Editor aus:
- `supabase/migrations/20260117190000_initial_schema.sql`

### 5. Docker starten

```bash
# Mit Supabase als externe DB (empfohlen)
docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d

# Logs prüfen
docker compose -f docker-compose.yml -f docker-compose.supabase.yml logs -f app
```

### 6. In Cursor integrieren

Öffne Cursor Settings → MCP → Add Server:

```json
{
  "knowwhere": {
    "url": "http://localhost:8000/sse"
  }
}
```

---

## 🎮 Verwendung in Cursor

### Mit @knowwhere Mention (empfohlen)

```
@knowwhere Was ist mein Lieblingsprojekt?
```

### Automatische Nutzung

Installiere die Cursor Rule für automatische Memory-Suche:

```bash
mkdir -p ~/.cursor/rules
cp .cursor/rules/knowwhere-memory.mdc ~/.cursor/rules/
```

Jetzt wird Claude automatisch in Memories suchen bei Fragen wie:
- "Was bevorzuge ich für..."
- "Was ist mein Lieblings..."
- "Erinnerst du dich an..."

---

## 🛠️ MCP Tools

### Memory Management Tools

#### `mcp_remember` - Memory speichern
```json
{
  "content": "User bevorzugt TypeScript über JavaScript",
  "memory_type": "preference",
  "importance": 8,
  "entities": ["TypeScript", "JavaScript"]
}
```

#### `mcp_recall` - Memory suchen (mit Sampling)
```json
{
  "query": "Welche Programmiersprache bevorzugt der User?",
  "filters": {"memory_type": "preference"},
  "limit": 5,
  "offset": 0,
  "include_sampling": false
}
```

#### `mcp_consolidate_session` - Konversation analysieren
```json
{
  "session_transcript": "User: Ich liebe Rust für Systems Programming...",
  "conversation_id": "session-123"
}
```

#### `mcp_analyze_evolution` - Veränderungen tracken
```json
{
  "entity_name": "TypeScript",
  "time_window": "last_30_days"
}
```

#### `mcp_export_memories` - Daten exportieren
```json
{
  "format": "json",
  "include_embeddings": false
}
```

#### `mcp_delete_memory` - Memory löschen
```json
{
  "memory_id": "uuid-hier",
  "hard_delete": false
}
```

### MCP Resources (Neu!)

#### `health://status` - Server Health Check
```json
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "version": "1.0.0"
}
```

#### `system://capabilities` - System Features
```json
{
  "memory_types": ["episodic", "semantic", "preference", "procedural", "meta"],
  "features": {
    "batch_processing": true,
    "parallel_processing": true,
    "knowledge_graph": true
  }
}
```

#### `user://{user_id}/stats` - User Statistics
```json
{
  "total_memories": 42,
  "by_type": {
    "preference": 15,
    "semantic": 20,
    "episodic": 7
  },
  "avg_importance": 6.8
}
```

#### `user://{user_id}/preferences` - User Preferences
```json
{
  "preferences": [
    {
      "content": "Bevorzugt TypeScript über JavaScript",
      "importance": 8,
      "entities": ["TypeScript", "JavaScript"]
    }
  ]
}
```

### MCP Prompts (Neu!)

#### `memory_guided_creation` - Geführte Memory-Erstellung
Interaktiver Prompt für strukturierte Memory-Erstellung mit Best Practices.

#### `preference_analysis` - Präferenz-Analyse
Umfassende Analyse aller User-Präferenzen und Muster-Erkennung.

#### `learning_session_analysis` - Lern-Session Analyse
Spezialisiert auf die Verarbeitung von Lern-Konversationen.

#### `troubleshooting_workflow` - Troubleshooting Workflow
Systematische Problemlösung mit Memory-Kontext.

---

## 🏗️ Architektur

```
┌──────────────────────────────────────────────────────────────┐
│                    AI Clients (Cursor, Claude Desktop)       │
└────────────────────────┬─────────────────────────────────────┘
                         │ MCP Protocol (SSE + Resources)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastMCP Server (Docker)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              6 MCP Tools + Resources                   │ │
│  │  Tools: remember | recall | consolidate | analyze |   │ │
│  │         export | delete                               │ │
│  │  Resources: health | stats | preferences | entities   │ │
│  │  Prompts: guided_creation | preference_analysis       │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Optimized Memory Engine                      │ │
│  │  Batch MemoryProcessor | Parallel ConsolidationEngine │ │
│  │  KnowledgeGraph | Dependency Injection Container      │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              External Services                         │ │
│  │    Supabase (pgvector)  |  Redis  |  OpenAI/Anthropic │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Projektstruktur

```
KW_Mem_MCP_Server/
├── src/
│   ├── main.py              # FastMCP Entry Point (SSE Transport)
│   ├── config.py            # Pydantic Settings
│   ├── tools/               # MCP Tool Implementierungen
│   │   ├── remember.py      # Memory speichern
│   │   ├── recall.py        # Semantische Suche
│   │   ├── consolidate.py   # Session-Analyse
│   │   ├── analyze.py       # Evolution Tracking
│   │   ├── export.py        # Daten-Export
│   │   └── delete.py        # Memory löschen
│   ├── engine/              # Business Logic
│   │   ├── memory_processor.py
│   │   ├── consolidation.py
│   │   ├── entity_extractor.py
│   │   └── knowledge_graph.py
│   ├── storage/             # Data Access Layer
│   │   ├── database.py      # asyncpg Pool
│   │   ├── cache.py         # Redis Client
│   │   └── repositories/    # CRUD Operations
│   ├── services/            # External APIs
│   │   ├── embedding.py     # OpenAI Embeddings
│   │   └── llm.py           # Anthropic/OpenAI LLM
│   └── models/              # Pydantic Models
├── migrations/              # SQL Migrations
├── supabase/migrations/     # Supabase-spezifische Migrations
├── tests/                   # Pytest Test Suite
├── scripts/
│   └── ingest_codebase.py   # Codebase in Memories laden
├── .cursor/rules/           # Cursor Rules für Auto-Recall
├── docker-compose.yml       # Lokale Entwicklung
├── docker-compose.supabase.yml  # Supabase Override
├── Dockerfile               # Production Container
└── railway.toml             # Railway Deployment
```

---

## 🔧 Entwicklung

### Lokale Entwicklung (ohne Docker)

```bash
# Virtual Environment
python3.11 -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Server starten (stdio für lokale Entwicklung)
python -m src.main
```

### Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage
pytest --cov=src

# Nur Unit Tests
pytest tests/test_tools/ tests/test_engine/

# Integration Tests (benötigt echte DB)
pytest tests/test_real_database.py -v
```

### Codebase in KnowWhere laden

```bash
# Indexiere die gesamte Codebase für semantische Suche
python scripts/ingest_codebase.py
```

---

## 🐛 Troubleshooting

### Container ist "unhealthy"
Das `/health` Endpoint existiert nicht bei FastMCP - kann ignoriert werden. Die MCP-Funktionalität ist nicht betroffen.

### "Tool not found" in Cursor
1. MCP Status prüfen (Cursor → Settings → MCP)
2. Disconnecten und neu connecten
3. Cursor neu starten

### Memories werden nicht gefunden
**User-ID Mismatch!** Stelle sicher, dass die gleiche User-ID für Speichern und Abrufen verwendet wird.

In `src/main.py`:
```python
DEFAULT_USER_ID = UUID("deine-user-id-hier")
```

### "Connection refused" zu Supabase
Verwende die **Session Pooler** URL (Port 5432), nicht die Direct Connection URL.

### Redis nicht erreichbar
Redis ist optional. Der Server funktioniert auch ohne Cache, aber langsamer.

---

## 🚢 Production Deployment

### Railway (empfohlen)

1. Fork zu deinem GitHub
2. Neues Railway Projekt erstellen
3. Add-ons: PostgreSQL, Redis
4. Environment Variables setzen
5. `railway.toml` wird automatisch erkannt

### Docker (Self-Hosted)

```bash
# Build
docker build -t knowwhere-mcp:latest .

# Run
docker run -d \
  --name knowwhere \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e OPENAI_API_KEY="sk-..." \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e MCP_TRANSPORT="sse" \
  knowwhere-mcp:latest
```

---

## 📚 Erkenntnisse aus der Entwicklung

### Wichtige Design-Entscheidungen

1. **SSE Transport für Docker**: stdio funktioniert nicht in containerisierten Umgebungen. Verwende `MCP_TRANSPORT=sse`.

2. **User-ID Management**: Im Debug-Modus wird eine Default-User-ID verwendet. Stelle sicher, dass alle Memories unter der gleichen ID gespeichert werden.

3. **Cursor Rules**: Claude entscheidet selbst, wann es Tools nutzt. Mit einer Cursor Rule kannst du automatische Memory-Suche erzwingen.

4. **Supabase Session Pooler**: Verwende die Session Pooler URL (5432) statt Direct Connection für bessere Performance.

5. **Claim Extraction**: Der LLM-Prompt für Claim-Extraktion ist kritisch. Aktuell optimiert für:
   - Persönliche Präferenzen (Wichtigkeit 8-10)
   - Projekt-Fakten (Wichtigkeit 6-8)
   - Learnings und Erkenntnisse (Wichtigkeit 5-7)
   - Entscheidungen (Wichtigkeit 7-9)

6. **JSONB Handling**: PostgreSQL JSONB Felder müssen explizit zu JSON-Strings konvertiert werden beim INSERT und beim SELECT zurück geparst werden.

---

## 🤝 Contributing

1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/amazing-feature`)
3. Änderungen committen (`git commit -m 'Add amazing feature'`)
4. Branch pushen (`git push origin feature/amazing-feature`)
5. Pull Request öffnen

---

## 📄 License

MIT License - siehe [LICENSE](LICENSE) für Details.

---

## 🔗 Links

- **Repository**: [github.com/nimarfranklin/KW_Mem_MCP_Server](https://github.com/nimarfranklin/KW_Mem_MCP_Server)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **Supabase**: [supabase.com](https://supabase.com)
- **FastMCP**: [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)

---

## 📋 Recent Updates (v1.1.0)

### 🚀 Performance Optimierungen
- **5x schnellere Consolidation**: Parallele Entity Extraction und Batch Embeddings
- **Batch Processing**: Gleichzeitige Verarbeitung mehrerer Memories
- **Optimized Connection Pooling**: Verbesserte Datenbank-Verbindungen
- **Async Improvements**: Mehr Parallelisierung in unabhängigen Operationen

### 📡 MCP Protocol Erweiterungen
- **Neue MCP Resources**: `health://status`, `system://capabilities`, `user://{id}/stats`, `user://{id}/preferences`, `user://{id}/memories`, `user://{id}/entities`
- **MCP Prompts**: `memory_guided_creation`, `preference_analysis`, `learning_session_analysis`, `troubleshooting_workflow`
- **Sampling Support**: Effiziente Pagination für große Resultate
- **Progress Notifications**: Fortschrittsanzeige für langlaufende Operationen

### 🏗️ Architektur Verbesserungen
- **Dependency Injection Container**: Saubere Service-Management
- **Service Abstraction**: Bessere Testbarkeit und Wartbarkeit
- **Batch Memory Processing**: Neue `process_memories_batch()` Methode

### 🔧 Developer Experience
- **Erweiterte System Capabilities**: Detaillierte Feature-Dokumentation
- **Verbesserte Error Handling**: Bessere Fehlermeldungen und Logging
- **Performance Monitoring**: Detaillierte Statistiken und Metriken

---

## 🎨 Semantic Intelligence (v1.2.0)

### 🌌 Semantic Galaxy View
Die Knowledge Graph Visualisierung wurde komplett überarbeitet:
- **Semantic Spine**: Hierarchische Cluster nach Domain -> Category -> Entities
- **Granular Code Classification**: Spezielles Verständnis für Source Code (API vs. UI vs. Core)
- **Interactive Exploration**: Expandierbare Cluster für bessere Übersicht

### 🧹 Data Quality Engine
- **Active Deduplication**: Erkennt und entfernt semantische Duplikate (>95% Ähnlichkeit)
- **Auto-Classification**: LLM-gestützte Kategorisierung aller Memories
- **Sprach-agnostisch**: Versteht Duplikate über Sprachgrenzen hinweg (DE/EN)

---

**Made with ❤️ for persistent AI memory**
