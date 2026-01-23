"""
Knowwhere Memory MCP Server

Main entry point for the FastMCP server with authentication,
rate limiting, and audit logging.
"""

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import structlog
import uvicorn
from datetime import datetime, UTC
from fastmcp import FastMCP

from src.config import Settings, get_settings, init_container, close_container
from src.auth.middleware import AuthContext, get_current_user
from src.auth.jwt import verify_token
from src.auth.api_keys import verify_api_key
from src.middleware.rate_limit import check_rate_limit, get_rate_limiter
from src.middleware.audit import AuditContext, close_audit_logger, get_audit_logger
from src.tools.remember import remember, REMEMBER_SPEC
from src.tools.recall import recall, RECALL_SPEC
from src.tools.consolidate import consolidate_session, CONSOLIDATE_SESSION_SPEC
from src.tools.analyze import analyze_evolution, ANALYZE_EVOLUTION_SPEC
from src.tools.export import export_memories, EXPORT_MEMORIES_SPEC
from src.tools.delete import delete_memory, DELETE_MEMORY_SPEC
from src.tools.refine import refine_knowledge, REFINE_SPEC
from src.tools.update import update_memory, UPDATE_MEMORY_SPEC

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Get settings
settings = get_settings()

# Module-level state removed - Shadow Listener deprecated per Lean MCP Memory strategy

# =============================================================================
# Lifecycle Management
# =============================================================================

@asynccontextmanager
async def lifespan_context(app):
    """Manage server lifecycle - connect/disconnect resources."""
    logger.info("Starting Knowwhere Memory MCP Server...")

    # Initialize dependency container
    try:
        container = await init_container()
        logger.info("Dependency container initialized")

        # Start audit logger
        audit_logger = await get_audit_logger()
        logger.info("Audit logger started")

        # Initialize rate limiter
        rate_limiter = await get_rate_limiter()
        logger.info("Rate limiter initialized")

        # Authenticate via environment API key if provided
        if KNOWWHERE_API_KEY:
            user_id = await authenticate_from_env_api_key()
            if user_id:
                logger.info("✅ Authenticated via KNOWWHERE_API_KEY", user_id=str(user_id))
            else:
                logger.warning("⚠️ KNOWWHERE_API_KEY provided but authentication failed")
        else:
            logger.warning("⚠️ No KNOWWHERE_API_KEY provided - running in dev mode")

        # Shadow Listener removed - Lean MCP Memory strategy
        # Memory capture now relies on explicit tool calls (remember, consolidate)

        logger.info("✅ All services initialized successfully!")

    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise

    yield

    # Cleanup
    logger.info("Shutting down Knowwhere Memory MCP Server...")
    
    # Shadow Listener cleanup removed
        
    await close_container()
    await close_audit_logger()
    logger.info("Shutdown complete")


# Create FastMCP app with lifespan
mcp = FastMCP("Knowwhere Memory Server", lifespan=lifespan_context)

# Register MCP prompts for memory-aware conversations
from src.prompts import register_prompts, register_resources
register_prompts(mcp)
register_resources(mcp)



# =============================================================================
# Authentication & Rate Limiting
# =============================================================================

async def authenticate_request(
    bearer_token: str | None = None,
    api_key: str | None = None,
) -> UUID | None:
    """
    Authenticate a request and return user_id.
    
    Supports:
    - JWT in Authorization: Bearer <token>
    - API Key in Authorization: Bearer <kw_...>
    - API Key in X-API-Key: <kw_...>
    """
    # 1. Normalize tokens from headers
    token_to_verify = None
    if bearer_token:
        if bearer_token.startswith("Bearer "):
            token_to_verify = bearer_token[7:]
        else:
            token_to_verify = bearer_token
            
    api_key_to_verify = api_key
    
    # 2. If Authorization header contains an API key (kw_...), treat it as such
    if token_to_verify and token_to_verify.startswith("kw_"):
        api_key_to_verify = token_to_verify
        token_to_verify = None

    # 3. Try JWT authentication if we have a potential token
    if token_to_verify:
        token_data = verify_token(token_to_verify, token_type="access")
        if token_data:
            user_id = UUID(token_data.sub)
            AuthContext.set_user_from_token(token_data)
            return user_id
    
    # 4. Try API key authentication
    if api_key_to_verify:
        user_info = await verify_api_key(api_key_to_verify)
        if user_info:
            user_id = user_info["user_id"]
            AuthContext.set_user_from_api_key(user_info)
            return user_id
    
    return None


async def check_rate_limit_for_user(user_id: UUID) -> tuple[bool, dict]:
    """Check if user is within rate limits."""
    return await check_rate_limit(str(user_id))


# =============================================================================
# MCP Context Extraction
# =============================================================================

# For development/testing - allows unauthenticated access
# In production, set REQUIRE_AUTH=true in environment
REQUIRE_AUTH = settings.debug is False
# This is the test user created during development - matches memories in DB
DEFAULT_USER_ID = UUID("21f38efd-0e43-4314-96f7-c4195fc8290c")

# Read API key from environment (for MCP clients like Claude Desktop)
import os
KNOWWHERE_API_KEY = os.getenv("KNOWWHERE_API_KEY")
_env_authenticated_user_id: UUID | None = None


async def authenticate_from_env_api_key() -> UUID | None:
    """Authenticate using API key from environment variable."""
    global _env_authenticated_user_id
    
    if _env_authenticated_user_id:
        return _env_authenticated_user_id
    
    if KNOWWHERE_API_KEY:
        logger.info("Authenticating with KNOWWHERE_API_KEY from environment")
        user_info = await verify_api_key(KNOWWHERE_API_KEY)
        if user_info:
            _env_authenticated_user_id = user_info["user_id"]
            AuthContext.set_user_from_api_key(user_info)
            logger.info("Authenticated via API key", user_id=str(_env_authenticated_user_id))
            return _env_authenticated_user_id
        else:
            logger.error("Invalid KNOWWHERE_API_KEY")
    
    return None


def get_user_id_from_context() -> UUID:
    """
    Extract user_id from the globally managed AuthContext.
    
    Priority:
    1. Environment API key (KNOWWHERE_API_KEY)
    2. AuthContext (set by authenticated request middleware)
    3. Default (development only fallback)
    """
    global _env_authenticated_user_id
    
    # 1. Check if we authenticated via env API key (highest priority for CLI)
    if _env_authenticated_user_id:
        return _env_authenticated_user_id
    
    # 2. Check AuthContext (set by the shared HTTP middleware)
    # This is the standard path for both REST and integrated MCP requests
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id:
        return auth_user_id
    
    # 3. Fall back to default (development only)
    if not REQUIRE_AUTH:
        logger.warning("No authenticated user found - using default user_id (DEV ONLY)")
        return DEFAULT_USER_ID
        
    # If we get here in production without auth, something is wrong
    raise ValueError("Authentication required: No user session found in context.")
    
    raise ValueError("Authentication required: no user_id found in context")


async def with_auth_and_audit(
    tool_name: str,
    user_id: UUID,
    operation_func,
    **kwargs,
) -> dict[str, Any]:
    """
    Wrapper that handles rate limiting and audit logging for tool calls.
    """
    # Check rate limit
    is_allowed, rate_info = await check_rate_limit_for_user(user_id)
    
    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            user_id=str(user_id),
            tool=tool_name,
        )
        return {
            "error": "Rate limit exceeded",
            "retry_after_seconds": rate_info.get("reset_at", 60) - int(time.time()),
            "limit": rate_info.get("limit"),
        }
    
    # Shadow Listener hook removed - Lean MCP Memory strategy
    # Memory capture relies on explicit tool calls (mcp_remember, mcp_consolidate)
    
    # Execute with audit logging
    async with AuditContext(user_id, f"tool:{tool_name}") as ctx:
        try:
            result = await operation_func(user_id=user_id, **kwargs)
            
            # Track accessed memory IDs if present in result
            try:
                if hasattr(result, "memory_id") and result.memory_id:
                    ctx.add_memory_id(result.memory_id)
                elif hasattr(result, "memories") and result.memories:
                    for mem in result.memories[:10]:  # Limit to first 10
                        if hasattr(mem, "id"):
                            ctx.add_memory_id(mem.id)
            except Exception as audit_e:
                logger.warning("Audit tracking failed", error=str(audit_e))

            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json")
            return result
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(
                f"TOOL FAILURE: {tool_name}", 
                user_id=str(user_id), 
                error=str(e),
                trace=error_trace
            )
            ctx.set_error(str(e))
            # Return error in the result so it shows up in client
            return {
                "status": "failed",
                "error": str(e),
                "traceback": error_trace
            }


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def mcp_remember(
    content: str,
    memory_type: str,
    entities: list[str] | None = None,
    importance: int = 5,
) -> dict[str, Any]:
    """
    💾 SPEICHERE wichtige Informationen über den User für zukünftige Gespräche.

    ⚠️ KRITISCH - WAS GENAU SPEICHERN:

    📋 Bei LANGEN INHALTEN (Rezepte, Anleitungen, Code):
       → VOLLSTÄNDIG speichern mit ALLEN Details, Zutaten, Schritten!
       → NIEMALS nur eine Zusammenfassung speichern!

    📌 Bei KURZEN FAKTEN (Name, Ort, Vorlieben):
       → Kurze, prägnante Aussage OK

    ✅ RICHTIGE BEISPIELE:
    - Rezept: content="Lasagne Rezept für Sarah:\n\nZutaten:\n- 500g Hackfleisch\n- 2 Dosen Tomaten\n- Bechamel: 50g Butter, 50g Mehl, 500ml Milch\n\nZubereitung:\n1. Hackfleisch anbraten\n2. Tomaten dazu, 20 Min köcheln..."
    - Fakt: content="User's name is Max, lives in Berlin"
    - Vorliebe: content="User prefers Python over JavaScript for backend"

    ❌ FALSCH (NIE SO MACHEN!):
    - content="User wants to remember a lasagne recipe" ← Das ist KEINE Memory!
    - content="User shared a recipe" ← Wo sind die Zutaten und Schritte?!

    🎯 MEMORY TYPES:
    - procedural: Rezepte, Anleitungen, Workflows → IMMER VOLLSTÄNDIG!
    - semantic: Fakten (Name, Job, Ort) → Kurz OK
    - preference: Vorlieben → Kurz OK  
    - episodic: Ereignisse → Mit relevanten Details
    - meta: Über das Lernen selbst

    💡 GOLDENE REGEL: Wenn der User später fragt "Was war das Rezept?", 
       muss die Memory ALLE Infos enthalten um die Frage zu beantworten!

    ❌ NICHT SPEICHERN:
    - Temporäre Infos ("Ich bin gerade müde")
    - Allgemeinwissen (Wikipedia-Fakten)
    - Einmalige Anfragen ohne Wiederholungswert

    Args:
        content: Der VOLLSTÄNDIGE Inhalt. Bei Rezepten/Anleitungen: ALLE Zutaten und Schritte!
        memory_type: procedural | semantic | preference | episodic | meta
        entities: Relevante Begriffe ["Lasagne", "Sarah"] - auto-extrahiert wenn leer
        importance: 1-10 (10=Name, 8=Rezept/Anleitung, 5=normal)
    """
    user_id = get_user_id_from_context()
    
    return await with_auth_and_audit(
        tool_name="remember",
        user_id=user_id,
        operation_func=remember,
        content=content,
        memory_type=memory_type,
        entities=entities,
        importance=importance,
    )


@mcp.tool()
async def mcp_recall(
    query: str,
    filters: dict | None = None,
    limit: int = 5,
    offset: int = 0,
    relevance_threshold: float = 0.0,
    include_sampling: bool = False,
) -> dict[str, Any]:
    """
    🔍 **IMMER ZUERST NUTZEN** bei persönlichen Fragen über den User!
    
    Verwendet semantische Suche um relevante Memories zu finden.

    🔄 WICHTIGER WORKFLOW:
    1. ZUERST recall() um zu prüfen ob Info bereits existiert
    2. Nur DANN remember() wenn wirklich NEUE Info (nicht doppelt speichern!)

    ⚡ TRIGGER - Rufe recall() auf bei:
    ┌─────────────────────────────────────────────────────────────┐
    │ User fragt nach...          │ Query                         │
    ├─────────────────────────────┼───────────────────────────────┤
    │ Namen                       │ recall("name")                │
    │ "Was weißt du über mich?"   │ recall("user info")           │
    │ Vorlieben/Favorites         │ recall("preference favorite") │
    │ Arbeit/Job                  │ recall("work job company")    │
    │ Projekte                    │ recall("project working on")  │
    │ Standort                    │ recall("location city")       │
    │ Techstack/Tools             │ recall("programming tech")    │
    │ Bei Begrüßung "Hallo!"      │ recall("name") → personalisieren! │
    └─────────────────────────────┴───────────────────────────────┘

    🎯 TIPPS für gute Queries:
    - Nutze Keywords statt Sätze: "python preference" statt "Was mag der User bei Python?"
    - Kombiniere Begriffe: "work project current" für aktuelle Arbeitsprojekte
    - Bei Unsicherheit: breite Query wie "user info preferences"

    ❌ NICHT für allgemeines Wissen (Wikipedia-Fragen) - nur für User-spezifisches!

    Args:
        query: Suchbegriffe (Keywords funktionieren besser als Sätze!)
        filters: Optional {"memory_type": "preference", "importance_min": 7}
        limit: Max Ergebnisse 1-10 (default 5, mehr = mehr Kontext)
    """
    user_id = get_user_id_from_context()
    
    # Limit results to prevent context overflow
    limit = min(limit, 10)

    result = await with_auth_and_audit(
        tool_name="recall",
        user_id=user_id,
        operation_func=recall,
        query=query,
        filters=filters,
        limit=limit,
        offset=offset,
        include_sampling=include_sampling,
    )
    
    # Truncate content AND remove embeddings (Compact Response Mode)
    MAX_CONTENT_LENGTH = 500
    if "memories" in result:
        filtered_memories = []
        for memory in result["memories"]:
            # 1. Relevance Threshold Filter
            score = memory.get("similarity", 0.0)
            if score < relevance_threshold:
                continue
                
            # 2. Manual Embedding Removal (Guaranteeing Compact Response)
            if "embedding" in memory:
                del memory["embedding"]
                
            # 3. Content Truncation
            if "content" in memory and len(memory["content"]) > MAX_CONTENT_LENGTH:
                memory["content"] = memory["content"][:MAX_CONTENT_LENGTH] + "... [truncated]"
            
            filtered_memories.append(memory)
        
        result["memories"] = filtered_memories
        result["count"] = len(filtered_memories)
        # Final safety check: remove any leftover embedding keys
        for m in result.get("memories", []):
            if "embedding" in m:
                del m["embedding"]
                
        result["_debug_compact_mode"] = True
        result["_server_version"] = "1.3.0-EVOLUTION"
    
    return result


@mcp.tool()
async def mcp_consolidate_session(
    session_transcript: str,
    session_date: str | None = None,
    conversation_id: str | None = None,
) -> dict[str, Any]:
    """
    📋 Analysiere ein ganzes Gespräch und extrahiere automatisch alle wichtigen Memories.

    ✅ WANN NUTZEN:
    - Am Ende einer langen Session mit vielen Informationen
    - User sagt "Speichere alles Wichtige aus diesem Gespräch"
    - Batch-Verarbeitung von Chat-Logs

    ❌ NICHT NUTZEN:
    - Für einzelne Fakten → nutze stattdessen remember()
    - Bei kurzen Gesprächen ohne neue Infos

    🔄 WAS PASSIERT:
    1. LLM analysiert Transcript
    2. Extrahiert Fakten, Vorlieben, Lernpunkte
    3. Speichert als strukturierte Memories
    4. Dedupliziert gegen bestehende Memories

    ⚠️ HINWEIS: Kann 10-30 Sekunden dauern bei langen Transkripten!

    Args:
        session_transcript: Vollständiges Gespräch als Text
        session_date: Datum (ISO 8601, z.B. "2024-01-15")
        conversation_id: Optionale Referenz-ID
    """
    import asyncio

    user_id = get_user_id_from_context()

    # Parse session_date if provided
    parsed_date = None
    if session_date:
        try:
            parsed_date = datetime.fromisoformat(session_date)
        except ValueError:
            pass

    # Progress-aware wrapper
    async def consolidate_with_progress(
        user_id: UUID,
        session_transcript: str,
        session_date: datetime | None,
        conversation_id: str | None,
    ) -> dict[str, Any]:
        """Consolidate session with progress reporting."""
        total_steps = 4  # claim extraction, conflict resolution, memory creation, cleanup

        # Progress notification function
        async def report_progress(step: int, message: str):
            logger.info(f"Consolidation progress: {message}", step=step, total=total_steps)
            # Note: MCP progress notifications would be sent here if supported by client

        await report_progress(1, "Extracting claims from transcript...")
        result = await consolidate_session(
            user_id=user_id,
            session_transcript=session_transcript,
            session_date=session_date,
            conversation_id=conversation_id,
        )
        
        # Log failure if engine reported it
        if result.status == "failed":
            logger.error("Engine reported failure in tool", error=result.error_message)

        await report_progress(total_steps, "Consolidation complete")
        return result

    return await with_auth_and_audit(
        tool_name="consolidate_session",
        user_id=user_id,
        operation_func=consolidate_with_progress,
        session_transcript=session_transcript,
        session_date=parsed_date,
        conversation_id=conversation_id,
    )


@mcp.tool()
async def mcp_analyze_evolution(
    entity_id: str | None = None,
    entity_name: str | None = None,
    time_window: str = "all_time",
) -> dict[str, Any]:
    """
    📈 Verfolge wie sich ein Thema/Preference über Zeit entwickelt hat.

    ✅ WANN NUTZEN:
    - "Wie hat sich meine Meinung zu X geändert?"
    - "Was habe ich über Y über die Zeit gelernt?"
    - "Zeige mir die Entwicklung meiner TypeScript-Kenntnisse"

    📊 BEISPIELE:
    - analyze_evolution(entity_name="TypeScript") → Zeigt alle TypeScript-bezogenen Memories chronologisch
    - analyze_evolution(entity_name="Python", time_window="last_30_days") → Letzte 30 Tage Python-Aktivität

    ❌ NICHT NUTZEN:
    - Für einfache Suchen → nutze recall()
    - Ohne konkretes Thema/Entity

    Args:
        entity_id: UUID einer spezifischen Memory (optional)
        entity_name: Thema/Begriff zu tracken z.B. "TypeScript", "React", "Machine Learning"
        time_window: last_7_days | last_30_days | last_year | all_time (default)
    """
    user_id = get_user_id_from_context()
    
    parsed_entity_id = None
    if entity_id:
        try:
            parsed_entity_id = UUID(entity_id)
        except ValueError:
            pass
    
    return await with_auth_and_audit(
        tool_name="analyze_evolution",
        user_id=user_id,
        operation_func=analyze_evolution,
        entity_id=parsed_entity_id,
        entity_name=entity_name,
        time_window=time_window,
    )


@mcp.tool()
async def mcp_export_memories(
    format: str = "json",
    filters: dict | None = None,
    include_embeddings: bool = False,
) -> dict[str, Any]:
    """
    📤 Exportiere alle Memories als Backup oder zur Analyse.

    ✅ WANN NUTZEN:
    - "Exportiere alle meine Memories"
    - "Mach ein Backup meiner Daten"
    - "Gib mir alle Preferences als JSON"

    📁 FORMATE:
    - json: Strukturiert, ideal für Backups und Import
    - csv: Tabellen-Format, gut für Excel/Analyse

    ⚠️ HINWEIS:
    - include_embeddings=True macht die Datei SEHR groß (1536 floats pro Memory)
    - Nur für technische Analyse nötig

    Args:
        format: "json" (default) oder "csv"
        filters: Optional {"memory_type": "preference"} für nur Preferences
        include_embeddings: Embedding-Vektoren inkludieren (default: False)
    """
    user_id = get_user_id_from_context()
    
    return await with_auth_and_audit(
        tool_name="export_memories",
        user_id=user_id,
        operation_func=export_memories,
        format=format,
        filters=filters,
        include_embeddings=include_embeddings,
    )


@mcp.tool()
async def mcp_delete_memory(
    memory_id: str,
    hard_delete: bool = False,
) -> dict[str, Any]:
    """
    🗑️ Lösche eine spezifische Memory.

    ✅ WANN NUTZEN:
    - "Lösche diese Memory"
    - "Vergiss dass ich X gesagt habe" (nach recall() → ID holen)
    - "Diese Info ist falsch, entferne sie"

    🔒 SICHERHEIT:
    - Default: Soft-Delete (30 Tage Wiederherstellbar, GDPR-konform)
    - hard_delete=True: Sofort permanent gelöscht

    ⚠️ WORKFLOW:
    1. Erst recall() um die Memory zu finden
    2. Memory-ID aus dem Ergebnis verwenden
    3. delete_memory(memory_id="...")

    Args:
        memory_id: UUID der Memory (aus recall()-Ergebnis)
        hard_delete: True = permanent, False = soft-delete (default)
    """
    user_id = get_user_id_from_context()
    return await with_auth_and_audit(
        tool_name="delete_memory",
        user_id=user_id,
        operation_func=delete_memory,
        memory_id=UUID(memory_id),
        hard_delete=hard_delete,
    )


@mcp.tool(name=UPDATE_MEMORY_SPEC["name"], description=UPDATE_MEMORY_SPEC["description"])
async def mcp_update_memory(
    memory_id: str,
    status: str | None = None,
    importance: int | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Updates specific fields of an existing memory."""
    user_id = get_user_id_from_context()
    return await with_auth_and_audit(
        tool_name="update_memory",
        user_id=user_id,
        operation_func=update_memory,
        memory_id=memory_id,
        status=status,
        importance=importance,
        memory_type=memory_type
    )


@mcp.tool(name=REFINE_SPEC["name"], description=REFINE_SPEC["description"])
async def mcp_refine_knowledge(
    memory_id: str,
    new_content: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    - Die alte Memory wird als "superseded" archiviert
    - Die neue Memory wird automatisch verknüpft
    
    Args:
        memory_id: UUID der Memory (aus mcp_recall)
        new_content: Der korrigierte oder erweiterte Inhalt
        reason: Optionaler Grund für die Korrektur (z.B. 'User Korrektur')
    """
    user_id = get_user_id_from_context()
    
    return await with_auth_and_audit(
        tool_name="refine_knowledge",
        user_id=user_id,
        operation_func=refine_knowledge,
        memory_id=memory_id,
        new_content=new_content,
        reason=reason,
    )


# =============================================================================
# MCP Prompts
# =============================================================================

@mcp.prompt()
async def memory_guided_creation(
    context: str | None = None,
    memory_type: str | None = None,
) -> str:
    """
    Guided memory creation prompt.

    Helps users create structured memories by asking the right questions
    based on context and desired memory type.
    """
    base_prompt = """Du bist ein Memory Creation Assistant für KnowWhere.
Deine Aufgabe ist es, Benutzern zu helfen, strukturierte und nützliche Erinnerungen zu erstellen.

RICHTLINIEN FÜR GUTE MEMORIES:
1. **Spezifisch**: Nicht "Ich mag Technologie" sondern "Ich bevorzuge TypeScript gegenüber JavaScript weil..."
2. **Kontextreich**: Erkläre WARUM etwas wichtig ist
3. **Handlungsorientiert**: Was folgt daraus? Was ändert sich?
4. **Zeitgebunden**: Wann wurde das entschieden/gelernt?

MEMORY TYPEN:
- **episodic**: Spezifische Ereignisse ("In Session #42 erwähnte der User...")
- **semantic**: Fakten ("Python verwendet Einrückung für Code-Blöcke")
- **preference**: Vorlieben ("Ich bevorzuge async/await gegenüber Promises")
- **procedural**: Anleitungen ("Um React zu installieren: npm create vite --template react-ts")
- **meta**: Über das Lernen selbst ("Ich kämpfe mit async/await Konzepten")

SCHRITT-FÜR-SCHRITT ANLEITUNG:
1. Frage nach dem WAS (was genau soll erinnert werden?)
2. Frage nach dem WARUM (warum ist das wichtig?)
3. Frage nach ENTITIES (welche Technologien/Konzepte sind beteiligt?)
4. Empfehle den richtigen MEMORY_TYPE
5. Erstelle das Memory mit mcp_remember()"""

    if context:
        base_prompt += f"\n\nKONTEXT: {context}"

    if memory_type:
        type_descriptions = {
            "episodic": "Ein spezifisches Ereignis oder Gespräch",
            "semantic": "Ein Fakt oder eine Information",
            "preference": "Eine persönliche Vorliebe oder Entscheidung",
            "procedural": "Eine Anleitung oder ein Workflow",
            "meta": "Etwas über das eigene Lernen oder Verstehen",
        }
        base_prompt += f"\n\nGEWÜNSCHTER TYP: {memory_type} - {type_descriptions.get(memory_type, 'Unbekannter Typ')}"

    return base_prompt


@mcp.prompt()
async def preference_analysis() -> str:
    """
    Comprehensive preference analysis prompt.

    Helps analyze all user preferences and create insights.
    """
    return """Du bist ein Preference Analyst für KnowWhere.

Deine Aufgabe: Analysiere alle Benutzer-Präferenzen systematisch.

SCHRITTE:
1. **Sammle alle Präferenzen**: Verwende mcp_recall("preference") um alle Vorlieben zu bekommen
2. **Kategorisiere**: Gruppiere nach Themen (Technologie, Workflow, Tools, etc.)
3. **Finde Muster**: Was sagt das über den Benutzer aus?
4. **Erkenne Konflikte**: Gibt es widersprüchliche Präferenzen?
5. **Erstelle Insights**: Was bedeuten diese Muster?

ANALYSE-FRAGEN:
- Welche Technologien werden bevorzugt und warum?
- Welche Arbeitsweisen werden favorisiert?
- Gibt es Entwicklung über Zeit? (mcp_analyze_evolution)
- Welche Entscheidungsmuster sind erkennbar?

Erstelle eine strukturierte Zusammenfassung der Benutzer-Präferenzen."""


@mcp.prompt()
async def learning_session_analysis() -> str:
    """
    Learning session consolidation prompt.

    Helps process and consolidate learning from a session.
    """
    return """Du bist ein Learning Session Analyst für KnowWhere.

Deine Aufgabe: Verarbeite eine Lern-Session und extrahiere wertvolles Wissen.

PROZESS:
1. **Sammle Session-Daten**: Hole relevante Memories aus der letzten Session
2. **Identifiziere Learnings**: Was wurde neu gelernt oder verstanden?
3. **Erkenne Herausforderungen**: Wo gab es Schwierigkeiten?
4. **Dokumentiere Lösungen**: Welche Probleme wurden gelöst?
5. **Erstelle Memories**: Speichere wichtige Erkenntnisse mit mcp_remember()

WICHTIGE FRAGEN:
- Welche neuen Konzepte wurden verstanden?
- Welche Fehlverständnisse wurden korrigiert?
- Welche Techniken/Tools wurden erfolgreich angewendet?
- Was würde der Benutzer beim nächsten Mal anders machen?

Verwende mcp_consolidate_session() für die komplette Session-Verarbeitung."""


@mcp.prompt()
async def troubleshooting_workflow() -> str:
    """
    Troubleshooting workflow prompt.

    Guides through systematic problem-solving using memory context.
    """
    return """Du bist ein Troubleshooting Assistant für KnowWhere.

Deine Aufgabe: Hilf bei der systematischen Problemlösung mit Memory-Kontext.

TROUBLESHOOTING-PROZESS:
1. **Problem definieren**: Was genau ist das Problem?
2. **Kontext sammeln**: Suche nach ähnlichen Problemen (mcp_recall)
3. **Lösungsansätze prüfen**: Welche Lösungen wurden früher verwendet?
4. **Schritt-für-Schritt vorgehen**: Systematische Problemlösung
5. **Lösung dokumentieren**: Speichere die Lösung für die Zukunft

FRAGEN STELLEN:
- Wann trat das Problem zum ersten Mal auf?
- Welche Schritte wurden bereits versucht?
- Welche Fehlermeldungen gibt es?
- In welcher Umgebung tritt es auf?

Verwende vorhandene Memories, um ähnliche Probleme und deren Lösungen zu finden."""


# =============================================================================
# MCP Setup - Roots via Resource Templates
# =============================================================================

# Note: FastMCP doesn't support @mcp.root decorator
# Roots are implemented via resource templates and resource hierarchies


# =============================================================================
# MCP Resources
# =============================================================================

@mcp.resource("health://status")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    try:
        db = await get_database()
        db_healthy = await db.health_check()
    except Exception:
        db_healthy = False

    try:
        cache = await get_cache()
        cache_healthy = await cache.health_check()
    except Exception:
        cache_healthy = False

    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "cache": "connected" if cache_healthy else "disconnected",
        "version": "1.0.0",
        "auth_required": REQUIRE_AUTH,
        "rate_limit_enabled": settings.rate_limit_enabled,
    }


@mcp.resource("user://{user_id}/stats")
async def user_memory_stats(user_id: str) -> dict[str, Any]:
    """Get memory statistics for a specific user."""
    from uuid import UUID
    from src.storage.repositories.memory_repo import MemoryRepository

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return {"error": "Invalid user_id format"}

    # Check auth context (in production, this would be enforced)
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id and auth_user_id != parsed_user_id:
        return {"error": "Access denied: can only view own stats"}

    try:
        db = await get_database()
        repo = MemoryRepository(db)

        stats = await repo.get_memory_stats(parsed_user_id)
        return stats.model_dump(mode="json")

    except Exception as e:
        logger.error("Failed to get user stats", user_id=user_id, error=str(e))
        return {"error": "Failed to retrieve statistics"}


@mcp.resource("user://{user_id}/preferences")
async def user_preferences(user_id: str) -> dict[str, Any]:
    """Get user preferences summary."""
    from uuid import UUID
    from src.storage.repositories.memory_repo import MemoryRepository
    from src.models.memory import MemoryType

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return {"error": "Invalid user_id format"}

    # Check auth context
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id and auth_user_id != parsed_user_id:
        return {"error": "Access denied: can only view own preferences"}

    try:
        db = await get_database()
        repo = MemoryRepository(db)

        preferences = await repo.get_memories_by_type(
            parsed_user_id, MemoryType.PREFERENCE, limit=20
        )

        return {
            "preferences": [
                {
                    "content": mem.content,
                    "importance": mem.importance,
                    "entities": mem.entities,
                    "created_at": mem.created_at.isoformat(),
                }
                for mem in preferences
            ]
        }

    except Exception as e:
        logger.error("Failed to get user preferences", user_id=user_id, error=str(e))
        return {"error": "Failed to retrieve preferences"}


@mcp.resource("system://capabilities")
async def system_capabilities() -> dict[str, Any]:
    """Get system capabilities and configuration."""
    return {
        "memory_types": ["episodic", "semantic", "preference", "procedural", "meta"],
        "max_content_length": 8000,
        "supported_providers": {
            "llm": ["anthropic", "openai"],
            "embedding": ["openai"],
            "storage": ["s3", "r2", "gcs"],
        },
        "features": {
            "knowledge_graph": settings.feature_knowledge_graph,
            "document_processing": settings.feature_document_processing,
            "evolution_tracking": settings.feature_evolution_tracking,
            "consolidation": True,
            "audit_logging": True,
            "rate_limiting": settings.rate_limit_enabled,
            "batch_processing": True,
            "parallel_processing": True,
        },
        "limits": {
            "rate_limit_per_minute": settings.rate_limit_requests_per_minute,
            "max_entities_per_memory": 10,
            "max_importance": 10,
            "embedding_dimensions": settings.embedding_dimensions,
        },
    }


@mcp.resource("user://{user_id}/memories")
async def user_memories_list(user_id: str, limit: int = 20) -> dict[str, Any]:
    """Get a list of user's memories with basic info."""
    from uuid import UUID
    from src.storage.repositories.memory_repo import MemoryRepository

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return {"error": "Invalid user_id format"}

    # Check auth context
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id and auth_user_id != parsed_user_id:
        return {"error": "Access denied: can only view own memories"}

    try:
        db = await get_database()
        repo = MemoryRepository(db)

        memories = await repo.list_by_user(parsed_user_id, limit=limit)

        return {
            "memories": [
                {
                    "id": str(mem.id),
                    "content": mem.content[:200] + "..." if len(mem.content) > 200 else mem.content,
                    "memory_type": mem.memory_type.value,
                    "importance": mem.importance,
                    "entities": mem.entities,
                    "created_at": mem.created_at.isoformat(),
                }
                for mem in memories
            ],
            "total_count": len(memories),
            "limit": limit,
        }

    except Exception as e:
        logger.error("Failed to get user memories", user_id=user_id, error=str(e))
        return {"error": "Failed to retrieve memories"}


@mcp.resource("user://{user_id}/entities")
async def user_entities(user_id: str) -> dict[str, Any]:
    """Get all entities known for a user."""
    from uuid import UUID
    from src.storage.repositories.memory_repo import MemoryRepository

    try:
        parsed_user_id = UUID(user_id)
    except ValueError:
        return {"error": "Invalid user_id format"}

    # Check auth context
    auth_user_id = AuthContext.get_user_id()
    if auth_user_id and auth_user_id != parsed_user_id:
        return {"error": "Access denied: can only view own entities"}

    try:
        db = await get_database()
        repo = MemoryRepository(db)

        entities = await repo.get_entities_for_user(parsed_user_id)

        return {
            "entities": entities,
            "count": len(entities),
        }

    except Exception as e:
        logger.error("Failed to get user entities", user_id=user_id, error=str(e))
        return {"error": "Failed to retrieve entities"}


# =============================================================================
# Entry Points
# =============================================================================

def main():
    """Main entry point for CLI."""
    import os
    from fastapi.middleware.cors import CORSMiddleware
    
    # Determine transport mode: use SSE for Docker/HTTP, stdio for CLI
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    
    logger.info(
        "Knowwhere Memory MCP Server starting",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        auth_required=REQUIRE_AUTH,
        transport=transport,
    )
    
    # Run the MCP server with appropriate transport
    if transport == "sse":
        # SSE transport for HTTP-based communication (Docker, web clients)
        # Use 0.0.0.0 to allow external connections in Docker
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from starlette.middleware.base import BaseHTTPMiddleware
        from src.api.web import router as api_router
        
        # 1. Initialize FastMCP with standard SSE transport
        # This app contains /sse and /messages natively at the root
        server_app = mcp.http_app(transport="sse")
        
        # 2. Create the FastAPI REST app
        api_app = FastAPI(
            title="Knowwhere REST API",
            description="Integrated Personal Knowledge Engine",
            version="1.4.5-STABLE",
        )

        # Add CORS to the REST app
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if settings.frontend_url:
            origins.extend([o.strip() for o in settings.frontend_url.split(",") if o.strip()])
        
        api_app.add_middleware(
            CORSMiddleware,
            allow_origins=[o for o in origins if o],
            allow_origin_regex=r"https://know-where-mcp-server-.*\.vercel\.app",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add REST-specific routes
        api_app.include_router(api_router)
        
        # Add health check to api_app for internal consistency
        @api_app.get("/health")
        async def api_health():
            return {"status": "healthy"}

        # 3. Add root-level routes (BEFORE mounting the catch-all "/")
        # This prevents the mount from shadowing these specific paths
        
        # Root health check for Railway
        @server_app.route("/health")
        async def root_health(request: Request):
            return JSONResponse({
                "status": "healthy",
                "service": "knowwhere",
                "version": "1.4.5-STABLE",
                "mcp": "/sse",
                "rest": "/api"
            })

        # Special handler for POST /sse to prevent discovery noise
        @server_app.route("/sse", methods=["POST"])
        async def sse_post_handler(request: Request):
            return Response("SSE endpoint requires GET. Use /messages for POST.", status_code=405)

        # 4. Mount REST API at root (as a fallback)
        # We mount this AFTER the specific routes above
        server_app.mount("/", api_app)

        # 4. Integrate SHARED Authentication Middleware
        # This runs on the root Starlette app and covers both MCP and REST
        @server_app.middleware("http")
        async def shared_auth_middleware(request: Request, call_next):
            auth_header = request.headers.get("Authorization")
            api_key = request.headers.get("X-API-Key")
            
            try:
                # Inject user identity into context
                await authenticate_request(bearer_token=auth_header, api_key=api_key)
            except Exception as e:
                # Optional auth: don't block
                logger.debug("Optional server auth check complete", error=str(e))
                
            return await call_next(request)

        # Global Exception Handler for the entire server
        @server_app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            import traceback
            logger.error("SYSTEM ERROR", path=request.url.path, error=str(exc), trace=traceback.format_exc())
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "error": str(exc)})

        logger.info(
            "Starting Stabilized Knowwhere Integrated Server",
            host=host,
            port=port,
            version="1.4.5-STABLE",
            mcp_endpoint="/sse",
            rest_prefix="/api"
        )
        
        # Run the root Starlette server
        uvicorn.run(server_app, host=host, port=port)
    else:
        # Default stdio transport for CLI/direct integration
        mcp.run()


async def run_server():
    """Run the server programmatically."""
    # Lifespan is now handled by FastMCP
    await mcp.run_async()


@mcp.resource("system://version")
def get_version() -> str:
    """Get the current server version."""
    return "KnowWhere MCP Server v1.3.0-EVOLUTION. Features: CompactMode, RelevanceThreshold, EvolutionFix, KnowledgeRefinement"


if __name__ == "__main__":
    main()
