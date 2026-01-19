"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Edit,
  Trash2,
  Calendar,
  Eye,
  Clock,
  Network,
  Tag,
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
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Memory } from "@/lib/api";
import { toast } from "sonner";

const memoryTypeColors: Record<string, string> = {
  episodic: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  semantic: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  preference: "bg-pink-500/10 text-pink-500 border-pink-500/20",
  procedural: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  meta: "bg-purple-500/10 text-purple-500 border-purple-500/20",
};

const memoryTypeDescriptions: Record<string, string> = {
  episodic: "Ein spezifisches Ereignis oder Gespräch",
  semantic: "Ein Fakt oder eine Information",
  preference: "Eine persönliche Vorliebe oder Entscheidung",
  procedural: "Eine Anleitung oder ein Workflow",
  meta: "Meta-kognitives Wissen über das Lernen",
};

// Entity Hub type colors (D+B)
const entityTypeColors: Record<string, string> = {
  person: "border-red-500 text-red-600 bg-red-500/10",
  place: "border-green-500 text-green-600 bg-green-500/10",
  event: "border-yellow-500 text-yellow-600 bg-yellow-500/10",
  recipe: "border-orange-500 text-orange-600 bg-orange-500/10",
  concept: "border-purple-500 text-purple-600 bg-purple-500/10",
  tech: "border-cyan-500 text-cyan-600 bg-cyan-500/10",
  project: "border-blue-500 text-blue-600 bg-blue-500/10",
  organization: "border-pink-500 text-pink-600 bg-pink-500/10",
};

export default function MemoryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [memory, setMemory] = useState<Memory | null>(null);
  const [loading, setLoading] = useState(true);

  // Entity Hub state (D+B navigation)
  const [entityHubs, setEntityHubs] = useState<Array<{
    id: string;
    name: string;
    type: string;
    related_memory_count: number;
  }>>([]);
  const [loadingEntities, setLoadingEntities] = useState(false);

  useEffect(() => {
    const loadMemory = async () => {
      try {
        const data = await api.getMemory(params.id as string);
        setMemory(data);

        // Load Entity Hubs for this memory
        setLoadingEntities(true);
        try {
          const entityData = await api.getMemoryEntities(params.id as string);
          setEntityHubs(entityData.entities);
        } catch {
          // Entity hubs not available - that's ok
          setEntityHubs([]);
        } finally {
          setLoadingEntities(false);
        }
      } catch (err) {
        toast.error("Memory nicht gefunden");
        router.push("/dashboard/memories");
      } finally {
        setLoading(false);
      }
    };

    if (params.id) {
      loadMemory();
    }
  }, [params.id, router]);

  const handleDelete = async () => {
    if (!memory) return;
    if (!confirm("Memory wirklich löschen?")) return;

    try {
      await api.deleteMemory(memory.id);
      toast.success("Memory gelöscht");
      router.push("/dashboard/memories");
    } catch (err) {
      toast.error("Fehler beim Löschen");
    }
  };

  if (loading) {
    return (
      <div className="p-6 lg:p-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!memory) {
    return null;
  }

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/memories">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-5 h-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Memory Details</h1>
            <p className="text-muted-foreground text-sm">
              ID: {memory.id.slice(0, 8)}...
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Link href={`/dashboard/memories/${memory.id}/edit`}>
            <Button variant="outline" className="gap-2">
              <Edit className="w-4 h-4" />
              Bearbeiten
            </Button>
          </Link>
          <Button
            variant="destructive"
            className="gap-2"
            onClick={handleDelete}
          >
            <Trash2 className="w-4 h-4" />
            Löschen
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <Badge
                  variant="outline"
                  className={`${memoryTypeColors[memory.memory_type]} text-sm`}
                >
                  {memory.memory_type.charAt(0).toUpperCase() +
                    memory.memory_type.slice(1)}
                </Badge>
                <Badge
                  variant={memory.status === "active" ? "default" : "secondary"}
                >
                  {memory.status}
                </Badge>
              </div>
              <CardDescription>
                {memoryTypeDescriptions[memory.memory_type]}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <p className="whitespace-pre-wrap">{memory.content}</p>
              </div>
            </CardContent>
          </Card>

          {/* Entity Hubs (D+B) */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Tag className="w-5 h-5" />
                Entity Hubs
              </CardTitle>
              <CardDescription>
                Zettelkasten-Verbindungen zu verwandten Memories
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {loadingEntities ? (
                <div className="text-sm text-muted-foreground">Lade Entities...</div>
              ) : entityHubs.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {entityHubs.map((entity) => (
                    <Link
                      key={entity.id}
                      href={`/dashboard/graph?entity=${entity.id}`}
                    >
                      <Badge
                        variant="outline"
                        className={`cursor-pointer hover:opacity-80 transition-opacity ${entityTypeColors[entity.type] || "border-gray-500 text-gray-600"}`}
                      >
                        {entity.name}
                        <span className="ml-1.5 opacity-70 text-xs">
                          ({entity.related_memory_count})
                        </span>
                      </Badge>
                    </Link>
                  ))}
                </div>
              ) : memory.entities.length > 0 ? (
                // Fallback to old entities if no entity hubs
                <div className="flex flex-wrap gap-2">
                  {memory.entities.map((entity) => (
                    <Badge key={entity} variant="secondary" className="text-sm">
                      {entity}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Keine Entities erkannt
                </p>
              )}
            </CardContent>
          </Card>

          {/* Related Memories (Placeholder) */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Network className="w-5 h-5" />
                Verwandte Memories
              </CardTitle>
              <CardDescription>
                Über den Knowledge Graph verbunden
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link href="/dashboard/graph">
                <Button variant="outline" className="w-full">
                  Im Knowledge Graph anzeigen
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Metadata */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Metadaten</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Wichtigkeit
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${(memory.importance / 10) * 100}%` }}
                    />
                  </div>
                  <span className="font-medium">{memory.importance}/10</span>
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  Confidence
                </span>
                <span className="font-medium">
                  {(memory.confidence * 100).toFixed(0)}%
                </span>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Quelle</span>
                <Badge variant="outline">{memory.source}</Badge>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Aufrufe</span>
                <div className="flex items-center gap-1 text-muted-foreground">
                  <Eye className="w-4 h-4" />
                  <span>{memory.access_count}</span>
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Domain</span>
                <Badge variant="outline" className="border-amber-500/50 text-amber-600 bg-amber-500/5">
                  {memory.domain || "-"}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Category</span>
                <Badge variant="outline" className="border-blue-500/50 text-blue-600 bg-blue-500/5">
                  {memory.category || "-"}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Timestamps */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Zeitstempel</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-start gap-3">
                <Calendar className="w-4 h-4 mt-0.5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Erstellt</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(memory.created_at).toLocaleDateString("de-DE", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Edit className="w-4 h-4 mt-0.5 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Aktualisiert</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(memory.updated_at).toLocaleDateString("de-DE", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>

              {memory.last_accessed && (
                <div className="flex items-start gap-3">
                  <Clock className="w-4 h-4 mt-0.5 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Letzter Zugriff</p>
                    <p className="text-sm text-muted-foreground">
                      {new Date(memory.last_accessed).toLocaleDateString(
                        "de-DE",
                        {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        }
                      )}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div >
  );
}
