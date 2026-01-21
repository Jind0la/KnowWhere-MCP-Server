"""
MCP Prompts & Resources: System Prompt Templates and Context Resources for KnowWhere Memory

These prompts follow the best practices from the official MCP Memory server,
instructing LLMs to proactively use memory tools during conversations.

Resources provide static context that can be loaded at session start.
"""

from fastmcp.prompts import Message


def register_prompts(mcp):
    """Register all prompts with the FastMCP server."""
    
    @mcp.prompt(
        name="memory_aware_system",
        description="System prompt that instructs the LLM to use KnowWhere memory tools. Use at the start of a conversation."
    )
    def memory_aware_system() -> str:
        """
        Generates a system prompt for memory-aware conversations.
        This prompt should be injected at the start of sessions.
        
        Based on official Anthropic MCP Memory best practices.
        """
        return """
KNOWWHERE MEMORY INTEGRATION

Follow these steps for EVERY interaction:

1. SESSION START - Memory Retrieval:
   - ALWAYS begin by saying: "Einen Moment, ich erinnere mich..."
   - Then call mcp_recall("user identity preferences projects") 
   - This retrieves what you already know about the user
   - Refer to your knowledge as your "memory" (never "database" or "records")
   - Use remembered context to personalize your greeting

2. CONVERSATION - Memory Awareness:
   While conversing, be attentive to NEW information in these categories:
   
   a) Identity: Name, age, location, job, education
   b) Preferences: Language, style, favorites, dislikes  
   c) Goals: Targets, aspirations, current projects
   d) Relationships: People, organizations, connections
   e) Skills: What they know, what they're learning
   f) Procedures: Recipes, workflows, how-to knowledge they share

3. DURING CONVERSATION - Memory Updates:
   When you learn NEW important information:
   - First check via mcp_recall if you already know this (avoid duplicates!)
   - Call mcp_remember with the COMPLETE fact
   - For recipes/procedures: Include ALL ingredients and steps!
   - Choose appropriate memory_type:
     * semantic: Facts and knowledge  
     * preference: Likes, dislikes, preferences
     * procedural: How-to knowledge, recipes, processes
     * episodic: Events and experiences
   - Set importance (1-10):
     * 10: Name, critical preferences
     * 7-8: Job, location, key relationships, recipes
     * 5-6: General preferences, interests
     * 1-4: Casual mentions

4. MEMORY HYGIENE:
   ✅ DO store: Personal facts, preferences, recurring topics, valuable procedures
   ❌ DON'T store: Temporary states ("I'm tired"), obvious facts (Wikipedia), one-time requests
   
5. SESSION END:
   - If user says goodbye or conversation ends naturally
   - Consider calling mcp_consolidate_session with the transcript
   - This extracts any facts you might have missed
"""

    @mcp.prompt(
        name="session_consolidation",
        description="Prompt for analyzing a conversation transcript and extracting memories."
    )
    def session_consolidation(transcript: str) -> list[Message]:
        """
        Generates a conversation for analyzing and consolidating session memories.
        Use at the end of a conversation or periodically.
        """
        return [
            Message(
                f"""Please analyze this conversation transcript and:

1. Identify facts about the user worth remembering
2. For each new fact, call mcp_remember with appropriate type and importance
3. Summarize what you learned

The transcript:
---
{transcript}
---

Please extract and save any valuable information."""
            ),
            Message(
                "I'll analyze the conversation and save any important information I find about you.",
                role="assistant"
            )
        ]

    @mcp.prompt(
        name="recall_context",
        description="Quick prompt to recall relevant memories before responding to a topic."
    )
    def recall_context(topic: str) -> str:
        """
        Generates a prompt to recall context about a specific topic.
        """
        return f"""Before responding about "{topic}", first call mcp_recall to check what you already know about this topic or related subjects. Use this context to provide a more personalized response."""


def register_resources(mcp):
    """Register all resources with the FastMCP server."""
    
    @mcp.resource(
        uri="memory://profile",
        name="User Profile",
        description="Compact user profile summary. Load at session start for immediate context.",
        mime_type="text/plain"
    )
    async def get_user_profile() -> str:
        """
        Returns a compact summary of the user for session start.
        
        This resource can be automatically included by MCP clients
        to provide immediate context without requiring a tool call.
        
        Contains:
        - Core identity (name, job, location)
        - Top preferences
        - Current projects
        """
        from src.auth.middleware import AuthContext
        from src.tools.recall import recall
        
        user_id = AuthContext.get_user_id()
        if not user_id:
            return "⚠️ Not authenticated. Use mcp_recall to retrieve memories after authentication."
        
        # Fetch core context
        try:
            identity_result = await recall(
                user_id=user_id,
                query="name identity job location",
                limit=3
            )
            prefs_result = await recall(
                user_id=user_id,
                query="preference favorite",
                limit=3
            )
            projects_result = await recall(
                user_id=user_id,
                query="current project working on",
                limit=2
            )
            
            # Format compact profile
            lines = ["=== USER PROFILE ===\n"]
            
            # Identity
            if identity_result.memories:
                lines.append("📋 Identity:")
                for mem in identity_result.memories[:3]:
                    content = mem.content[:100] + "..." if len(mem.content) > 100 else mem.content
                    lines.append(f"  • {content}")
                lines.append("")
            
            # Preferences
            if prefs_result.memories:
                lines.append("⭐ Top Preferences:")
                for mem in prefs_result.memories[:3]:
                    content = mem.content[:80] + "..." if len(mem.content) > 80 else mem.content
                    lines.append(f"  • {content}")
                lines.append("")
            
            # Projects
            if projects_result.memories:
                lines.append("🚧 Current Projects:")
                for mem in projects_result.memories[:2]:
                    content = mem.content[:80] + "..." if len(mem.content) > 80 else mem.content
                    lines.append(f"  • {content}")
            
            if not any([identity_result.memories, prefs_result.memories, projects_result.memories]):
                lines.append("No memories found yet. Start a conversation to build your profile!")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"⚠️ Error loading profile: {str(e)}"

    @mcp.resource(
        uri="memory://stats",
        name="Memory Statistics",
        description="Overview of stored memories and usage statistics.",
        mime_type="application/json"
    )
    async def get_memory_stats() -> str:
        """Returns memory statistics as JSON."""
        import json
        from src.auth.middleware import AuthContext
        from src.storage.database import get_database
        from src.storage.repositories.memory_repo import MemoryRepository
        
        user_id = AuthContext.get_user_id()
        if not user_id:
            return json.dumps({"error": "Not authenticated"})
        
        try:
            db = await get_database()
            repo = MemoryRepository(db)
            stats = await repo.get_memory_stats(user_id)
            
            return json.dumps({
                "total_memories": stats.get("total_memories", 0),
                "by_type": stats.get("by_type", {}),
                "avg_importance": round(stats.get("avg_importance", 0), 2),
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
