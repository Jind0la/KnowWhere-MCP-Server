"""
MCP Prompts: System Prompt Templates for KnowWhere Memory

These prompts follow the best practices from the official MCP Memory server,
instructing LLMs to proactively use memory tools during conversations.
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
        """
        return """
Follow these steps for each interaction:

1. Memory Retrieval:
   - At the start of conversation, call mcp_recall with relevant context
   - Refer to your knowledge as your "memory"
   - Always check if you already know something before asking

2. Memory Awareness:
   While conversing, be attentive to new information in these categories:
   a) Basic Identity (name, age, location, job, education)
   b) Preferences (language, style, favorites, dislikes)
   c) Goals (targets, aspirations, projects)
   d) Relationships (people, organizations, connections)
   e) Skills & Knowledge (what they know, what they're learning)

3. Memory Updates:
   When you learn NEW important information:
   - Call mcp_remember with the fact
   - Choose appropriate memory_type:
     * semantic: Facts and knowledge
     * preference: Likes, dislikes, preferences
     * procedural: How-to knowledge, recipes, processes
     * episodic: Events and experiences
   - Set importance appropriately (1-10):
     * 10: Name, critical preferences
     * 7-8: Job, location, key relationships
     * 5-6: General preferences, interests
     * 1-4: Casual mentions

4. Best Practices:
   - Don't store temporary information ("I'm tired right now")
   - Don't store obvious facts (Wikipedia knowledge)
   - DO store personal, recurring, or valuable information
   - When in doubt, ask if they want you to remember something
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
