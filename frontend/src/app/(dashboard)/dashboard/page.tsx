"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Brain,
  Database,
  TrendingUp,
  Clock,
  ArrowRight,
  Plus,
  Search,
  Download,
  Inbox,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type MemoryStats, type Memory } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";

const memoryTypeColors: Record<string, string> = {
  episodic: "bg-blue-500/10 text-blue-500",
  semantic: "bg-emerald-500/10 text-emerald-500",
  preference: "bg-pink-500/10 text-pink-500",
  procedural: "bg-orange-500/10 text-orange-500",
  meta: "bg-purple-500/10 text-purple-500",
};

const memoryTypeLabels: Record<string, string> = {
  episodic: "Episodic",
  semantic: "Semantic",
  preference: "Preference",
  procedural: "Procedural",
  meta: "Meta",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Memory[]>([]);
  const [loadingDrafts, setLoadingDrafts] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await api.getStats();
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Fehler beim Laden");
      } finally {
        setLoading(false);
      }
    };

    loadStats();
  }, []);

  useEffect(() => {
    const loadDrafts = async () => {
      try {
        const data = await api.getDraftMemories();
        setDrafts(data.memories);
      } catch (err) {
        console.error("Failed to load drafts:", err);
      } finally {
        setLoadingDrafts(false);
      }
    };

    loadDrafts();
  }, []);

  const handleFeedback = async (id: string, action: "approve" | "reject") => {
    try {
      await api.submitFeedback(id, action);
      setDrafts(drafts.filter((d) => d.id !== id));
      // Refresh stats if approved (adds to active count)
      if (action === "approve") {
        const data = await api.getStats();
        setStats(data);
      }
    } catch (err) {
      console.error("Feedback failed:", err);
    }
  };

  if (loading) {
    return (
      <div className="p-6 lg:p-8 space-y-8">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Fehler</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => window.location.reload()}>
              Erneut versuchen
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Übersicht über deine Memories und Aktivitäten
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/memories">
            <Button variant="outline" size="sm" className="gap-2">
              <Search className="w-4 h-4" />
              Suchen
            </Button>
          </Link>
          <Link href="/dashboard/memories/new">
            <Button size="sm" className="gap-2">
              <Plus className="w-4 h-4" />
              Neue Memory
            </Button>
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Gesamt Memories
            </CardTitle>
            <Database className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {stats?.total_memories || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              In deiner Wissensdatenbank
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Top Entities
            </CardTitle>
            <Brain className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {stats?.top_entities?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Verschiedene Themen erkannt
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Durchschn. Wichtigkeit
            </CardTitle>
            <TrendingUp className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {stats?.avg_importance?.toFixed(1) || "0"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">von 10 Punkten</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Letzte Aktivität
            </CardTitle>
            <Clock className="w-4 h-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {stats?.recent_activity?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Kürzlich hinzugefügt
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Memory Types Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Memory-Typen</CardTitle>
            <CardDescription>Verteilung deiner Memories</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats?.by_type &&
                Object.entries(stats.by_type).map(([type, count]) => {
                  const percentage =
                    stats.total_memories > 0
                      ? (count / stats.total_memories) * 100
                      : 0;
                  return (
                    <div key={type} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant="secondary"
                            className={memoryTypeColors[type]}
                          >
                            {memoryTypeLabels[type] || type}
                          </Badge>
                        </div>
                        <span className="text-sm font-medium">{count}</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${memoryTypeColors[type]?.includes("blue")
                            ? "bg-blue-500"
                            : memoryTypeColors[type]?.includes("emerald")
                              ? "bg-emerald-500"
                              : memoryTypeColors[type]?.includes("pink")
                                ? "bg-pink-500"
                                : memoryTypeColors[type]?.includes("orange")
                                  ? "bg-orange-500"
                                  : "bg-purple-500"
                            }`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}

              {(!stats?.by_type ||
                Object.keys(stats.by_type).length === 0) && (
                  <div className="text-center py-8 text-muted-foreground">
                    <Database className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Noch keine Memories vorhanden</p>
                    <Link href="/dashboard/memories/new">
                      <Button variant="link" className="mt-2">
                        Erste Memory erstellen
                      </Button>
                    </Link>
                  </div>
                )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Letzte Aktivität</CardTitle>
              <CardDescription>Kürzlich hinzugefügte Memories</CardDescription>
            </div>
            <Link href="/dashboard/memories">
              <Button variant="ghost" size="sm" className="gap-1">
                Alle anzeigen
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats?.recent_activity?.slice(0, 5).map((activity) => (
                <Link
                  key={activity.id}
                  href={`/dashboard/memories/${activity.id}`}
                  className="block"
                >
                  <div className="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
                    <Badge
                      variant="secondary"
                      className={memoryTypeColors[activity.type]}
                    >
                      {memoryTypeLabels[activity.type] || activity.type}
                    </Badge>
                    {(activity as any).category && (
                      <Badge variant="outline" className="ml-1 text-xs border-blue-500/30 text-blue-600 bg-blue-500/5">
                        {(activity as any).category}
                      </Badge>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm line-clamp-2">
                        {activity.content_preview}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {new Date(activity.date).toLocaleDateString("de-DE", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </p>
                    </div>
                  </div>
                </Link>
              ))}

              {(!stats?.recent_activity ||
                stats.recent_activity.length === 0) && (
                  <div className="text-center py-8 text-muted-foreground">
                    <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>Keine kürzlichen Aktivitäten</p>
                  </div>
                )}
            </div>
          </CardContent>
        </Card>

        {/* Review Desk (Draft Memories) */}
        <Card className="border-amber-500/30 bg-gradient-to-br from-amber-500/5 to-transparent">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Inbox className="w-5 h-5 text-amber-500" />
                Review Desk
              </CardTitle>
              <CardDescription>
                Proaktiv erfasste Memories zur Überprüfung
              </CardDescription>
            </div>
            {drafts.length > 0 && (
              <Badge variant="secondary" className="bg-amber-500/10 text-amber-600">
                {drafts.length} ausstehend
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            {loadingDrafts ? (
              <div className="space-y-3">
                <Skeleton className="h-16" />
                <Skeleton className="h-16" />
              </div>
            ) : drafts.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Inbox className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Keine Drafts zur Überprüfung</p>
              </div>
            ) : (
              <div className="space-y-3">
                {drafts.slice(0, 5).map((draft) => (
                  <div
                    key={draft.id}
                    className="p-3 border rounded-lg bg-background/50 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm line-clamp-2">{draft.content}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <Badge
                            variant="secondary"
                            className={memoryTypeColors[draft.memory_type]}
                          >
                            {memoryTypeLabels[draft.memory_type] || draft.memory_type}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            Konfidenz: {Math.round(draft.confidence * 100)}%
                          </span>
                        </div>
                      </div>
                      <div className="flex gap-1 shrink-0">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-emerald-600 hover:bg-emerald-500/10"
                          onClick={() => handleFeedback(draft.id, "approve")}
                        >
                          <CheckCircle2 className="w-4 h-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-red-600 hover:bg-red-500/10"
                          onClick={() => handleFeedback(draft.id, "reject")}
                        >
                          <XCircle className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Entities */}
        <Card>
          <CardHeader>
            <CardTitle>Top Entities</CardTitle>
            <CardDescription>
              Häufigste Themen in deinen Memories
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {stats?.top_entities?.map((entity) => (
                <Badge
                  key={entity.entity}
                  variant="outline"
                  className="py-1.5 px-3"
                >
                  {entity.entity}
                  <span className="ml-2 text-muted-foreground">
                    {entity.count}
                  </span>
                </Badge>
              ))}

              {(!stats?.top_entities || stats.top_entities.length === 0) && (
                <div className="w-full text-center py-8 text-muted-foreground">
                  <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p>Noch keine Entities erkannt</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Schnellaktionen</CardTitle>
            <CardDescription>Häufig genutzte Funktionen</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link href="/dashboard/memories/new" className="block">
              <Button variant="outline" className="w-full justify-start gap-3">
                <Plus className="w-4 h-4" />
                Neue Memory erstellen
              </Button>
            </Link>
            <Link href="/dashboard/memories" className="block">
              <Button variant="outline" className="w-full justify-start gap-3">
                <Search className="w-4 h-4" />
                Memories durchsuchen
              </Button>
            </Link>
            <Link href="/dashboard/graph" className="block">
              <Button variant="outline" className="w-full justify-start gap-3">
                <Brain className="w-4 h-4" />
                Knowledge Graph ansehen
              </Button>
            </Link>
            <Button variant="outline" className="w-full justify-start gap-3">
              <Download className="w-4 h-4" />
              Memories exportieren
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
