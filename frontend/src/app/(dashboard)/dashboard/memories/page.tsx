"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Plus,
  Filter,
  MoreVertical,
  Trash2,
  Eye,
  Edit,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Memory, type MemoryWithSimilarity } from "@/lib/api";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const memoryTypeColors: Record<string, string> = {
  episodic: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  semantic: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  preference: "bg-pink-500/10 text-pink-500 border-pink-500/20",
  procedural: "bg-orange-500/10 text-orange-500 border-orange-500/20",
  meta: "bg-purple-500/10 text-purple-500 border-purple-500/20",
};

const statusColors: Record<string, string> = {
  active: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  archived: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  superseded: "bg-gray-500/10 text-gray-500 border-gray-500/20",
  deleted: "bg-red-500/10 text-red-500 border-red-500/20",
};

const ITEMS_PER_PAGE = 10;

export default function MemoriesPage() {
  const [memories, setMemories] = useState<(Memory | MemoryWithSimilarity)[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [importanceFilter, setImportanceFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const loadMemories = useCallback(async () => {
    // ... existing loadMemories implementation ...
    setLoading(true);
    try {
      const params: {
        limit: number;
        offset: number;
        memory_type?: string;
        importance_min?: number;
      } = {
        limit: ITEMS_PER_PAGE,
        offset: page * ITEMS_PER_PAGE,
      };

      if (typeFilter !== "all") {
        params.memory_type = typeFilter;
      }
      if (importanceFilter !== "all") {
        params.importance_min = parseInt(importanceFilter);
      }

      const data = await api.getMemories(params);
      setMemories(data.memories);
      setTotal(data.total);
      setHasMore(data.has_more);
    } catch (err) {
      toast.error("Fehler beim Laden der Memories");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, typeFilter, importanceFilter]);

  const searchMemories = useCallback(async () => {
    // ... existing searchMemories implementation ...
    if (!searchQuery.trim()) {
      setSearchMode(false);
      loadMemories();
      return;
    }

    setLoading(true);
    setSearchMode(true);
    try {
      const filters: Record<string, unknown> = {};
      if (typeFilter !== "all") {
        filters.memory_type = typeFilter;
      }
      if (importanceFilter !== "all") {
        filters.importance_min = parseInt(importanceFilter);
      }

      const data = await api.searchMemories(searchQuery, filters);
      setMemories(data.memories);
      setTotal(data.total);
      setHasMore(false);
    } catch (err) {
      toast.error("Fehler bei der Suche");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, typeFilter, importanceFilter, loadMemories]);

  // ... useEffect ...
  useEffect(() => {
    if (!searchMode) {
      loadMemories();
    }
  }, [loadMemories, searchMode]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    searchMemories();
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteMemory(id);
      toast.success("Memory gelöscht");
      if (searchMode) {
        searchMemories();
      } else {
        loadMemories();
      }
    } catch (err) {
      toast.error("Fehler beim Löschen");
      console.error(err);
    }
  };

  const handleFilterChange = () => {
    setPage(0);
    if (searchMode && searchQuery.trim()) {
      searchMemories();
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Memories</h1>
          <p className="text-muted-foreground">
            {total} Memories in deiner Datenbank
          </p>
        </div>
        <Link href="/dashboard/memories/new">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            Neue Memory
          </Button>
        </Link>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col lg:flex-row gap-4">
            <form onSubmit={handleSearch} className="flex-1 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Semantische Suche..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button type="submit" variant="secondary">
                Suchen
              </Button>
              {searchMode && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setSearchQuery("");
                    setSearchMode(false);
                    setPage(0);
                  }}
                >
                  Zurücksetzen
                </Button>
              )}
            </form>

            <div className="flex gap-2">
              <Select
                value={typeFilter}
                onValueChange={(value) => {
                  setTypeFilter(value);
                  handleFilterChange();
                }}
              >
                <SelectTrigger className="w-[150px]">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Typ" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle Typen</SelectItem>
                  <SelectItem value="episodic">Episodic</SelectItem>
                  <SelectItem value="semantic">Semantic</SelectItem>
                  <SelectItem value="preference">Preference</SelectItem>
                  <SelectItem value="procedural">Procedural</SelectItem>
                  <SelectItem value="meta">Meta</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={importanceFilter}
                onValueChange={(value) => {
                  setImportanceFilter(value);
                  handleFilterChange();
                }}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Wichtigkeit" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Alle</SelectItem>
                  <SelectItem value="8">Hoch (8+)</SelectItem>
                  <SelectItem value="5">Mittel (5+)</SelectItem>
                  <SelectItem value="1">Niedrig (1+)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : memories.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground">
              <p className="mb-4">Keine Memories gefunden</p>
              <Link href="/dashboard/memories/new">
                <Button variant="outline">Erste Memory erstellen</Button>
              </Link>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Typ</TableHead>
                  <TableHead>Inhalt</TableHead>
                  <TableHead>Domain / Category</TableHead>
                  <TableHead className="w-[80px]">Quelle</TableHead>
                  <TableHead className="w-[90px]">Wichtigkeit</TableHead>
                  <TableHead className="w-[80px]">Konfidenz</TableHead>
                  {searchMode && (
                    <TableHead className="w-[80px]">Relevanz</TableHead>
                  )}
                  <TableHead className="w-[80px]">Status</TableHead>
                  <TableHead className="w-[70px]">Zugriffe</TableHead>
                  <TableHead className="w-[100px]">Datum</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {memories.map((memory) => (
                  <TableRow
                    key={memory.id}
                    className={memory.status === 'superseded' ? 'opacity-60 bg-muted/30' : ''}
                  >
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={memoryTypeColors[memory.memory_type]}
                      >
                        {memory.memory_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Link
                        href={`/dashboard/memories/${memory.id}`}
                        className="hover:underline"
                      >
                        <p className="line-clamp-2 text-sm">{memory.content}</p>
                        {memory.entities && memory.entities.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {Array.from(new Set(memory.entities)).slice(0, 3).map((entity) => (
                              <Badge
                                key={entity}
                                variant="secondary"
                                className="text-xs"
                              >
                                {entity}
                              </Badge>
                            ))}
                            {new Set(memory.entities).size > 3 && (
                              <Badge variant="secondary" className="text-xs">
                                +{new Set(memory.entities).size - 3}
                              </Badge>
                            )}
                          </div>
                        )}

                      </Link>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        {memory.domain && (
                          <Badge variant="outline" className="text-xs w-fit border-amber-500/50 text-amber-600 bg-amber-500/5">
                            {memory.domain}
                          </Badge>
                        )}
                        {memory.category && (
                          <Badge variant="outline" className="text-xs w-fit border-blue-500/50 text-blue-600 bg-blue-500/5">
                            {memory.category}
                          </Badge>
                        )}
                        {!memory.domain && !memory.category && (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs capitalize">
                        {memory.source || "user"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <div className="w-12 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{
                              width: `${(memory.importance / 10) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {memory.importance}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <div className="w-10 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full"
                            style={{
                              width: `${(memory.confidence || 0.8) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {((memory.confidence || 0.8) * 100).toFixed(0)}%
                        </span>
                      </div>
                    </TableCell>
                    {searchMode && "similarity" in memory && (
                      <TableCell>
                        <span className="text-sm font-medium text-amber-500">
                          {((memory.similarity as number) * 100).toFixed(0)}%
                        </span>
                      </TableCell>
                    )}
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={statusColors[memory.status]}
                      >
                        {memory.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="text-sm text-muted-foreground">
                        {memory.access_count || 0}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(memory.created_at).toLocaleDateString("de-DE", {
                        day: "numeric",
                        month: "short",
                        year: "2-digit",
                      })}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link href={`/dashboard/memories/${memory.id}`}>
                              <Eye className="w-4 h-4 mr-2" />
                              Anzeigen
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuItem asChild>
                            <Link
                              href={`/dashboard/memories/${memory.id}/edit`}
                            >
                              <Edit className="w-4 h-4 mr-2" />
                              Bearbeiten
                            </Link>
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onSelect={() => setDeleteId(memory.id)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Löschen
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {!searchMode && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Zeige {page * ITEMS_PER_PAGE + 1}-
            {Math.min((page + 1) * ITEMS_PER_PAGE, total)} von {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft className="w-4 h-4" />
              Zurück
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore}
            >
              Weiter
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )
      }

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Memory wirklich löschen?</AlertDialogTitle>
            <AlertDialogDescription>
              Diese Aktion kann nicht rückgängig gemacht werden.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Abbrechen</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteId) handleDelete(deleteId);
                setDeleteId(null);
              }}
              className="bg-destructive hover:bg-destructive/90"
            >
              Löschen
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
