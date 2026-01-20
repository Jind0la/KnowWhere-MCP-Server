"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Wand2, ArrowLeft, Save, Plus, X, Loader2 } from "lucide-react";
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
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function NewMemoryPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const [content, setContent] = useState("");
  const [entities, setEntities] = useState<string[]>([]);
  const [entityInput, setEntityInput] = useState("");

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

    setLoading(true);
    try {
      const response = await api.createMemory({
        content: content.trim(),
        entities: entities.length > 0 ? entities : undefined,
      });

      const { memory, status } = response;

      if (status === "updated") {
        toast.info("Duplikat gefunden! Bestehende Memory wurde aktualisiert.", {
          duration: 5000,
        });
      } else if (status === "refined") {
        toast.success("Wissen weiterentwickelt! Ein Widerspruch wurde automatisch korrigiert.", {
          duration: 5000,
        });
      } else {
        toast.success("Memory erfolgreich gespeichert! Die KI hat die Einordnung übernommen.", {
          duration: 5000,
        });
      }

      router.push(`/dashboard/memories/${memory.id}`);
    } catch (err) {
      toast.error("Fehler beim Erstellen der Memory");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/dashboard/memories">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Neues Wissen erfassen</h1>
          <p className="text-muted-foreground">
            Gib einfach ein, was du dir merken willst. Der Bibliothekar kümmert sich um den Rest.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card className="border-primary/20 shadow-lg overflow-hidden">
          <div className="h-1 bg-gradient-to-r from-primary/40 via-primary to-primary/40" />
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wand2 className="w-5 h-5 text-primary" />
              Gedanken erfassen
            </CardTitle>
            <CardDescription>
              Die KI analysiert deinen Text, extrahiert Entitäten und ordnet das Wissen automatisch in deinen Graphen ein.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder="Was gibt es Neues? (z.B. 'Ich habe heute gelernt, dass TypeScript Interfaces besser sind als Types für öffentliche APIs' oder 'Merk dir mein Lieblingsrezept für Pasta Carbonara...')"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={12}
              className="resize-none text-lg p-4 focus-visible:ring-primary"
              disabled={loading}
            />
            <div className="flex justify-between items-center text-xs text-muted-foreground px-1">
              <span>{content.length}/8000 Zeichen</span>
              <span className="flex items-center gap-1">
                <Wand2 className="w-3 h-3" /> Automatisierte Klassifizierung aktiv
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Optional Entities Section */}
        <Card className="bg-muted/30 border-none">
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-medium">Manuelle Stichpunkte (Optional)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pb-4">
            <div className="flex gap-2">
              <Input
                placeholder="Stichpunkt hinzufügen..."
                value={entityInput}
                onChange={(e) => setEntityInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddEntity();
                  }
                }}
                className="bg-background h-9"
                disabled={loading}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddEntity}
                disabled={loading}
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
                    className="pl-2 pr-1 h-7 gap-1"
                  >
                    {entity}
                    <button
                      type="button"
                      onClick={() => handleRemoveEntity(entity)}
                      className="rounded-full hover:bg-muted p-0.5"
                      disabled={loading}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button
            type="submit"
            size="lg"
            className="w-full sm:w-auto px-8 gap-2 shadow-primary/20 shadow-lg"
            disabled={loading || !content.trim()}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Der Bibliothekar arbeitet...
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                In den Graphen aufnehmen
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
