import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Types
export interface Memory {
  id: string;
  content: string;
  memory_type: "episodic" | "semantic" | "preference" | "procedural" | "meta";
  entities: string[];
  importance: number;
  confidence: number;
  status: "active" | "archived" | "deleted" | "superseded" | "draft";
  source: string;
  access_count: number;
  created_at: string;
  updated_at: string;
  last_accessed: string | null;
  domain?: string;
  category?: string;
}

export interface MemoryWithSimilarity extends Memory {
  similarity: number;
}

export interface MemoryCreateResponse {
  memory: Memory;
  status: "created" | "updated" | "refined";
}

export interface MemoryStats {
  total_memories: number;
  by_type: Record<string, number>;
  by_importance: Record<string, number>;
  recent_activity: {
    id: string;
    date: string;
    content_preview: string;
    type: string;
  }[];
  top_entities: {
    entity: string;
    count: number;
  }[];
  avg_importance: number;
}

export interface ApiKey {
  id: string;
  key_prefix: string;
  name: string;
  scopes: string[];
  status: "active" | "revoked" | "expired";
  last_used_at: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface GraphEdge {
  id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  strength: number;
  confidence: number;
}

// API Client
class ApiClient {
  private async getAuthHeader(): Promise<Record<string, string>> {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (session?.access_token) {
      return {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      };
    }

    return { "Content-Type": "application/json" };
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers = await this.getAuthHeader();

    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async getMe() {
    return this.fetch<{ id: string; email: string; tier: string }>("/api/auth/me");
  }

  // Memories
  async getMemories(params?: {
    limit?: number;
    offset?: number;
    memory_type?: string;
    importance_min?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set("limit", String(params.limit));
    if (params?.offset) searchParams.set("offset", String(params.offset));
    if (params?.memory_type) searchParams.set("memory_type", params.memory_type);
    if (params?.importance_min)
      searchParams.set("importance_min", String(params.importance_min));

    const query = searchParams.toString();
    return this.fetch<{ memories: Memory[]; total: number; has_more: boolean }>(
      `/api/memories${query ? `?${query}` : ""}`
    );
  }

  async getMemory(id: string) {
    return this.fetch<Memory>(`/api/memories/${id}`);
  }

  async createMemory(data: {
    content: string;
    memory_type?: string;
    entities?: string[];
    importance?: number;
    domain?: string;
    category?: string;
  }) {
    return this.fetch<MemoryCreateResponse>("/api/memories", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateMemory(
    id: string,
    data: Partial<{
      content: string;
      memory_type: string;
      entities: string[];
      importance: number;
      status: string;
      domain: string;
      category: string;
    }>
  ) {
    return this.fetch<Memory>(`/api/memories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteMemory(id: string, hard?: boolean) {
    return this.fetch<{ success: boolean }>(
      `/api/memories/${id}${hard ? "?hard=true" : ""}`,
      {
        method: "DELETE",
      }
    );
  }

  async searchMemories(query: string, filters?: Record<string, unknown>) {
    return this.fetch<{ memories: MemoryWithSimilarity[]; total: number }>(
      "/api/memories/search",
      {
        method: "POST",
        body: JSON.stringify({ query, filters }),
      }
    );
  }

  // Stats
  async getStats() {
    return this.fetch<MemoryStats>("/api/stats");
  }

  // Knowledge Graph
  async getGraphEdges(memoryId?: string) {
    const timestamp = new Date().getTime();
    const query = memoryId ? `?memory_id=${memoryId}&_t=${timestamp}` : `?_t=${timestamp}`;
    return this.fetch<{
      edges: GraphEdge[];
      nodes: Array<{
        id: string;
        content: string;
        memory_type: string;
        importance: number;
        entities?: string[];
        domain?: string;
        category?: string;
      }>;
    }>(`/api/graph/edges${query}`);
  }

  // Entity Navigation (On-Demand D+B)
  async getMemoryEntities(memoryId: string) {
    return this.fetch<{
      memory_id: string;
      entities: Array<{
        id: string;
        name: string;
        type: string;
        category: string | null;
        strength: number;
        is_primary: boolean;
        related_memory_count: number;
      }>;
    }>(`/api/memories/${memoryId}/entities`);
  }

  async getEntityMemories(entityId: string, limit?: number) {
    const query = limit ? `?limit=${limit}` : "";
    return this.fetch<{
      entity: {
        id: string;
        name: string;
        type: string;
        category: string | null;
      };
      total_memories: number;
      by_domain: Record<string, Array<{
        id: string;
        content_preview: string;
        memory_type: string;
        category: string | null;
        strength: number;
        is_primary: boolean;
      }>>;
      memory_ids: string[];
    }>(`/api/entities/${entityId}/memories${query}`);
  }

  // Draft Memories & Feedback
  async getDraftMemories() {
    return this.fetch<{ memories: Memory[]; total: number; has_more: boolean }>(
      "/api/memories?status=draft"
    );
  }

  async submitFeedback(id: string, action: "approve" | "reject") {
    return this.fetch<Memory>(`/api/memories/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
  }

  // API Keys
  async getApiKeys() {
    return this.fetch<{ keys: ApiKey[] }>("/api/keys");
  }

  async createApiKey(data: {
    name: string;
    scopes: string[];
    expires_in_days?: number;
  }) {
    return this.fetch<{ key: string; id: string; key_prefix: string }>(
      "/api/keys",
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  async revokeApiKey(id: string) {
    return this.fetch<{ success: boolean }>(`/api/keys/${id}`, {
      method: "DELETE",
    });
  }

  // Onboarding
  async getOnboardingStatus() {
    return this.fetch<{ completed: boolean; completed_at: string | null }>(
      "/api/onboarding/status"
    );
  }

  async completeOnboarding() {
    return this.fetch<{ success: boolean; completed_at: string | null }>(
      "/api/onboarding/complete",
      {
        method: "POST",
      }
    );
  }

  // Connection Test
  async testConnection() {
    return this.fetch<{
      success: boolean;
      user_id: string;
      email: string;
      tier: string;
      memory_count: number;
      message: string;
    }>("/api/connection/test");
  }
}

export const api = new ApiClient();
