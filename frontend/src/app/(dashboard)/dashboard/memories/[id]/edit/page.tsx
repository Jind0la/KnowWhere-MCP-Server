"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, Plus, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Memory } from "@/lib/api";
import { toast } from "sonner";

const memoryTypes = [
  {
    value: "episodic",
    label: "Episodic",
    description: "Spezifische Ereignisse und Gespräche",
  },
  {
    value: "semantic",
    label: "Semantic",
    description: "Fakten und Wissensbeziehungen",
  },
  {
    value: "preference",
    label: "Preference",
    description: "Persönliche Vorlieben und Entscheidungen",
  },
  {
    value: "procedural",
    label: "Procedural",
    description: "How-to Wissen und Workflows",
  },
  {
    value: "meta",
    label: "Meta",
    description: "Meta-kognitives Wissen über das Lernen",
  },
];

export default function EditMemoryPage() {
  const params = useParams();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [content, setContent] = useState("");
  const [memoryType, setMemoryType] = useState("semantic");
  const [importance, setImportance] = useState(5);
  const [entities, setEntities] = useState<string[]>([]);
  const [entityInput, setEntityInput] = useState("");

  useEffect(() => {
    const loadMemory = async () => {
      try {
        const memory = await api.getMemory(params.id as string);
        setContent(memory.content);
        setMemoryType(memory.memory_type);
        setImportance(memory.importance);
        setEntities(memory.entities);
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

  const handleAddEntity = () => {
    if (entityInput.trim() && !entities.includes(entityInput.trim())) {
      setEntities([...entities, entityInput.trim()]);
      setEntityInput("");
    }
  };

  const handleRemoveEntity = (entity: string) => {
    setEntities(entities.filter((e) => e !== entity));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!content.trim()) {
      toast.error("Bitte gib einen Inhalt ein");
      return;
    }

    setSaving(true);
    try {
      await api.updateMemory(params.id as string, {
        content: content.trim(),
        memory_type: memoryType,
        importance,
        entities,
      });

      toast.success("Memory aktualisiert!");
      router.push(`/dashboard/memories/${params.id}`);
    } catch (err) {
      toast.error("Fehler beim Speichern");
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 lg:p-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Skeleton className="h-96" />
          </div>
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/dashboard/memories/${params.id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Memory bearbeiten</h1>
          <p className="text-muted-foreground">
            Änderungen an deiner Memory vornehmen
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main Form */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Inhalt</CardTitle>
                <CardDescription>
                  Was möchtest du dir merken?
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea
                  placeholder="Beschreibe die Information, das Ereignis oder die Präferenz..."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={10}
                  className="resize-none"
                  disabled={saving}
                />
                <p className="text-xs text-muted-foreground mt-2">
                  {content.length}/8000 Zeichen
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Entities</CardTitle>
                <CardDescription>
                  Themen, Technologien oder Konzepte
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="Entity hinzufügen..."
                    value={entityInput}
                    onChange={(e) => setEntityInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddEntity();
                      }
                    }}
                    disabled={saving}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={handleAddEntity}
                    disabled={saving}
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>

                {entities.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {entities.map((entity) => (
                      <Badge
                        key={entity}
                        variant="secondary"
                        className="pl-3 pr-1 py-1 gap-1"
                      >
                        {entity}
                        <button
                          type="button"
                          onClick={() => handleRemoveEntity(entity)}
                          className="ml-1 rounded-full p-0.5 hover:bg-muted"
                          disabled={saving}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Memory-Typ</CardTitle>
                <CardDescription>
                  Wähle die passende Kategorie
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Select
                  value={memoryType}
                  onValueChange={setMemoryType}
                  disabled={saving}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {memoryTypes.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        <div>
                          <div className="font-medium">{type.label}</div>
                          <div className="text-xs text-muted-foreground">
                            {type.description}
                          </div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Wichtigkeit</CardTitle>
                <CardDescription>
                  Wie wichtig ist diese Information? (1-10)
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={importance}
                    onChange={(e) => setImportance(parseInt(e.target.value))}
                    className="flex-1"
                    disabled={saving}
                  />
                  <span className="w-8 text-center font-bold text-lg">
                    {importance}
                  </span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Niedrig</span>
                  <span>Mittel</span>
                  <span>Hoch</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6 space-y-2">
                <Button
                  type="submit"
                  className="w-full gap-2"
                  disabled={saving || !content.trim()}
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Wird gespeichert...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      Änderungen speichern
                    </>
                  )}
                </Button>
                <Link href={`/dashboard/memories/${params.id}`}>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    disabled={saving}
                  >
                    Abbrechen
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  );
}
