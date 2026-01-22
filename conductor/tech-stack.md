# Tech Stack: KnowWhere Memory

## Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI (Web API), FastMCP (Model Context Protocol server)
- **Database Interface:** `asyncpg` (Asynchronous PostgreSQL driver)
- **Validation:** `pydantic`, `pydantic-settings`

## Frontend
- **Framework:** Next.js (React)
- **Styling:** Tailwind CSS (Inferred from common Next.js setups)

## Storage & Database
- **Primary Database:** PostgreSQL with `pgvector` for vector similarity search.
- **Caching:** Redis for performance and session management.

## AI & Machine Learning
- **LLM Providers:** Anthropic (Primary), OpenAI (Embeddings and alternative LLM)
- **Search:** Semantic similarity search with 1536-dimensional (OpenAI) or compatible vectors.

## Infrastructure
- **Containerization:** Docker & Docker Compose
- **Deployment:** Supabase (Database/Auth), Railway (Inferred from `railway.toml`)
- **Logging:** `structlog`

## Development Tools
- **Linting/Formatting:** `ruff`
- **Type Checking:** `mypy`
- **Testing:** `pytest`, `pytest-asyncio`, `pytest-cov`
