"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Network, RefreshCw, ZoomIn, ZoomOut, Maximize2, ChevronDownSquare, ChevronUpSquare, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { api, type GraphEdge, type Memory } from "@/lib/api";
import { toast } from "sonner";

const edgeTypeColors: Record<string, string> = {
  leads_to: "#3b82f6",
  related_to: "#8b5cf6",
  contradicts: "#ef4444",
  supports: "#22c55e",
  likes: "#ec4899",
  dislikes: "#f97316",
  depends_on: "#06b6d4",
  evolves_into: "#eab308",
  preference_of: "#ec4899",
};

const nodeTypeColors: Record<string, string> = {
  episodic: "#3b82f6",
  semantic: "#10b981",
  preference: "#ec4899",
  procedural: "#f97316",
  meta: "#8b5cf6",
  user_profile: "#ffffff",
  // Entity Hub Types (used for sidebars)
  entity_person: "#ef4444",      // Red
  entity_place: "#22c55e",       // Green
  entity_event: "#eab308",       // Yellow
  entity_recipe: "#f97316",      // Orange
  entity_concept: "#8b5cf6",     // Purple
  entity_tech: "#06b6d4",        // Cyan
  entity_project: "#3b82f6",     // Blue
  entity_organization: "#ec4899", // Pink
};

interface GraphNode {
  id: string;
  content: string;
  memory_type: string;
  importance: number;
  entities?: string[];
  domain?: string;
  category?: string;
  status: string;
}

interface GraphData {
  edges: GraphEdge[];
  nodes: GraphNode[];
}

export default function KnowledgeGraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<unknown>(null);
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [edgeFilter, setEdgeFilter] = useState<string>("all");
  const [showIrrelevant, setShowIrrelevant] = useState<boolean>(false);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());

  // Entity Navigation State (D+B)
  const [memoryEntities, setMemoryEntities] = useState<Array<{
    id: string;
    name: string;
    type: string;
    related_memory_count: number;
  }>>([]);
  const [highlightedMemories, setHighlightedMemories] = useState<Set<string>>(new Set());
  const [loadingEntities, setLoadingEntities] = useState(false);

  // Helper to toggle cluster
  const toggleCluster = (clusterId: string) => {
    const newSet = new Set(expandedClusters);
    if (newSet.has(clusterId)) {
      newSet.delete(clusterId);
      // If collapsing a domain, also collapse its categories
      if (clusterId.startsWith("domain_")) {
        const domainName = clusterId.replace("domain_", "");
        Array.from(newSet).forEach(id => {
          if (id.startsWith(`category_${domainName}_`)) {
            newSet.delete(id);
          }
        });
      }
    } else {
      newSet.add(clusterId);
    }
    setExpandedClusters(newSet);
  };

  const loadGraphData = async () => {
    setLoading(true);
    try {
      const data = await api.getGraphEdges();
      setGraphData(data);
    } catch (err) {
      toast.error("Fehler beim Laden des Graphen");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Load entities when a memory is selected (D+B)
  const loadMemoryEntities = async (memoryId: string) => {
    setLoadingEntities(true);
    try {
      const data = await api.getMemoryEntities(memoryId);
      setMemoryEntities(data.entities);
    } catch (err) {
      console.error("Failed to load entities:", err);
      setMemoryEntities([]);
    } finally {
      setLoadingEntities(false);
    }
  };

  // Highlight related memories when entity clicked (D+B)
  const handleEntityClick = async (entityId: string) => {
    try {
      const data = await api.getEntityMemories(entityId);
      const memoryIds = new Set(data.memory_ids);
      setHighlightedMemories(memoryIds);

      // Auto-expand domains and categories to show the highlighted memories
      if (graphData) {
        const newExpanded = new Set(expandedClusters);

        // Find domains and categories that contain the highlighted memories
        graphData.nodes.forEach((node) => {
          if (memoryIds.has(node.id)) {
            const domain = node.domain || "Unclassified";
            newExpanded.add(`domain_${domain}`);

            if (node.category) {
              newExpanded.add(`category_${domain}_${node.category}`);
            }
          }
        });

        setExpandedClusters(newExpanded);
      }

      // Update node colors in vis-network to highlight them
      if (networkRef.current && graphData) {
        const network = networkRef.current as {
          body: {
            data: {
              nodes: {
                update: (nodes: Array<{ id: string; color?: { background: string; border: string } }>) => void;
                get: (id: string) => { id: string; color: unknown } | null;
              }
            }
          }
        };

        // Reset all node colors first, then highlight the matching ones
        // This will be handled by the useEffect that rebuilds the graph
      }

      toast.success(`${data.total_memories} Memories zu "${data.entity.name}" gefunden`);
    } catch (err) {
      console.error("Failed to load entity memories:", err);
      toast.error("Fehler beim Laden der verwandten Memories");
    }
  };

  // Clear highlights
  const clearHighlights = () => {
    setHighlightedMemories(prev => {
      if (prev.size === 0) return prev;
      return new Set();
    });
  };

  const handleExpandAll = () => {
    if (!graphData) return;
    const allClusters = new Set<string>();
    graphData.nodes.forEach(node => {
      const domain = node.domain || "Unclassified";
      allClusters.add(`domain_${domain}`);
      if (node.category) {
        allClusters.add(`category_${domain}_${node.category}`);
      }
    });
    setExpandedClusters(allClusters);
    toast.success("Alle Domains und Kategorien aufgeklappt");
  };

  const handleCollapseAll = () => {
    setExpandedClusters(new Set());
    toast.success("Alle Domains und Kategorien eingeklappt");
  };

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    loadGraphData();
  }, []);

  useEffect(() => {
    if (!graphData || !containerRef.current || loading) return;

    // Dynamically import vis-network
    import("vis-network/standalone").then(({ Network, DataSet }) => {
      // ---------------------------------------------------------
      // 1. ANALYZE HIERARCHY (Domain -> Category)
      // ---------------------------------------------------------
      const domains = new Set<string>();
      const domainCounts = new Map<string, number>();

      const categories = new Set<string>(); // Format: "Domain:Category"
      const categoryCounts = new Map<string, number>();

      graphData.nodes.forEach((node) => {
        if (node.memory_type === "user_profile") return;

        const domain = node.domain || "Unclassified";
        domains.add(domain);
        domainCounts.set(domain, (domainCounts.get(domain) || 0) + 1);

        if (node.category) {
          const catKey = `${domain}:${node.category}`;
          categories.add(catKey);
          categoryCounts.set(catKey, (categoryCounts.get(catKey) || 0) + 1);
        }
      });

      // ---------------------------------------------------------
      // 2. GENERATE NODES
      // ---------------------------------------------------------
      const nodes: any[] = [];

      // A. Domain Nodes (Planets)
      domains.forEach(domain => {
        nodes.push({
          id: `domain_${domain}`,
          label: `${domain} (${domainCounts.get(domain)})`,
          title: `Domain: ${domain}`,
          value: 40 + (domainCounts.get(domain) || 0),
          color: { background: "#fbbf24", border: "#d97706" }, // Amber
          shape: "dot",
          font: { size: 20, strokeWidth: 2, strokeColor: "#ffffff" },
          group: "domain",
          fixed: false,
        });
      });

      // B. Category Nodes (Moons) - Only if domain is expanded
      categories.forEach(catKey => {
        const [domain, catName] = catKey.split(":");
        if (expandedClusters.has(`domain_${domain}`)) {
          nodes.push({
            id: `category_${domain}_${catName}`,
            label: `${catName}`,
            title: `Category: ${catName}`,
            value: 20 + (categoryCounts.get(catKey) || 0),
            color: { background: "#60a5fa", border: "#2563eb" }, // Blue
            shape: "triangle",
            font: { size: 14, strokeWidth: 2, strokeColor: "#ffffff" },
            group: "category",
          });
        }
      });

      // C. Memory Nodes 
      graphData.nodes.forEach((node) => {
        if (node.memory_type === "user_profile") {
          nodes.push({
            id: node.id,
            label: "User",
            title: node.content,
            color: { background: "#ffffff", border: "#000000" },
            shape: "star",
            size: 40,
            font: { size: 18 },
          });
          return;
        }

        // Skip any entity_ nodes from backend (shouldn't exist anymore)
        if (node.memory_type.startsWith("entity_")) {
          return;
        }

        const domain = node.domain || "Unclassified";
        const category = node.category;

        let isVisible = false;

        // Visibility Rule:
        // 1. If has category: Visible if Category is expanded
        // 2. If no category: Visible if Domain is expanded

        if (category) {
          if (expandedClusters.has(`category_${domain}_${category}`)) {
            isVisible = true;
          }
        } else {
          if (expandedClusters.has(`domain_${domain}`)) {
            isVisible = true;
          }
        }

        if (isVisible) {
          // Visibility by status
          if (node.status === "irrelevant" && !showIrrelevant) {
            return;
          }

          // Check if this node should be highlighted (D+B Entity Navigation)
          const isHighlighted = highlightedMemories.has(node.id);
          const isIrrelevant = node.status === "irrelevant";
          const isStale = node.status === "stale";

          nodes.push({
            id: node.id,
            label: node.content.length > 20 ? node.content.substring(0, 20) + "..." : node.content,
            title: `[${node.status.toUpperCase()}] ${node.content}`,
            color: isHighlighted
              ? { background: "#22c55e", border: "#15803d" } // Green highlight
              : isIrrelevant
                ? { background: "#94a3b840", border: "#94a3b880" } // Dimmed gray
                : isStale
                  ? { background: "#f9731640", border: "#f97316" } // Orange tint
                  : nodeTypeColors[node.memory_type] || "#94a3b8",
            value: isHighlighted ? node.importance + 5 : node.importance, // Make highlighted nodes bigger
            shape: "dot",
            borderWidth: isHighlighted ? 4 : (isStale ? 3 : 2),
            opacity: isIrrelevant ? 0.4 : 1.0,
            font: { color: isIrrelevant ? "#94a3b8" : "#334155" },
          });
        }
      });

      const finalNodes = new DataSet(nodes);

      // ---------------------------------------------------------
      // 3. GENERATE EDGES
      // ---------------------------------------------------------
      const edges: any[] = [];
      const nodeIds = new Set(nodes.map(n => n.id));

      // Domain -> Category Links
      categories.forEach(catKey => {
        const [domain, catName] = catKey.split(":");
        const domId = `domain_${domain}`;
        const catId = `category_${domain}_${catName}`;

        if (nodeIds.has(domId) && nodeIds.has(catId)) {
          edges.push({
            from: domId,
            to: catId,
            length: 100,
            color: { color: "#fbbf24", opacity: 0.5 },
            dashes: true,
          });
        }
      });

      // Category/Domain -> Memory Links
      graphData.nodes.forEach((node) => {
        if (node.memory_type === "user_profile") return;
        if (!nodeIds.has(node.id)) return;

        const domain = node.domain || "Unclassified";
        const category = node.category;

        let sourceId = "";
        if (category && nodeIds.has(`category_${domain}_${category}`)) {
          sourceId = `category_${domain}_${category}`;
        } else if (nodeIds.has(`domain_${domain}`)) {
          sourceId = `domain_${domain}`;
        }

        if (sourceId) {
          edges.push({
            from: sourceId,
            to: node.id,
            length: 50,
            color: { color: "#cbd5e1", opacity: 0.3 },
          });
        }
      });

      // Real edges (filtered)
      graphData.edges.forEach(e => {
        if (nodeIds.has(e.from_node_id) && nodeIds.has(e.to_node_id)) {
          if (edgeFilter === "all" || e.edge_type === edgeFilter) {
            edges.push({
              id: e.id,
              from: e.from_node_id,
              to: e.to_node_id,
              color: edgeTypeColors[e.edge_type] || "#cbd5e1",
            });
          }
        }
      });

      const finalEdges = new DataSet(edges);

      // ... (Network Options)
      const options = {
        nodes: { borderWidth: 2, shadow: true },
        edges: { width: 1, smooth: { enabled: true, type: "continuous", roundness: 0.5 } },
        physics: {
          enabled: true,
          stabilization: { iterations: 200 },
          barnesHut: {
            gravitationalConstant: -4000,
            springLength: 150,
            springConstant: 0.04,
          }
        },
        interaction: { hover: true },
        // Add manual layout stabilization to prevent jumps
        layout: { improvedLayout: true }
      };

      const network = new Network(containerRef.current!, { nodes: finalNodes, edges: finalEdges }, options);

      network.on("click", (params: { nodes: string[] }) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const idStr = String(nodeId);
          if (idStr.startsWith("domain_") || idStr.startsWith("category_")) {
            toggleCluster(idStr);
          } else if (!idStr.startsWith("user_")) {
            // It's a memory node - select it and load entities
            setSelectedNode(idStr);
            loadMemoryEntities(idStr);
            clearHighlights();
          }
        } else {
          // Optimization: Only update state if something was actually selected/highlighted
          // This prevents the graph from reloading when clicking on empty space
          let changed = false;
          if (selectedNode !== null) {
            setSelectedNode(null);
            changed = true;
          }
          if (memoryEntities.length > 0) {
            setMemoryEntities([]);
            changed = true;
          }

          // clearHighlights has its own internal check to avoid re-renders
          clearHighlights();
        }
      });

      network.on("doubleClick", (params: { nodes: string[] }) => {
        if (params.nodes.length > 0) {
          const nodeId = String(params.nodes[0]);
          // Only navigate to actual memory nodes (no domain/category/user prefix)
          if (!nodeId.startsWith("domain_") && !nodeId.startsWith("category_") && !nodeId.startsWith("user_")) {
            router.push(`/dashboard/memories/${nodeId}`);
          }
        }
      });

      networkRef.current = network;
    });

    return () => {
      if (networkRef.current) {
        (networkRef.current as { destroy: () => void }).destroy();
      }
    };
  }, [graphData, loading, edgeFilter, expandedClusters, highlightedMemories, showIrrelevant]);

  const handleZoomIn = () => {
    if (networkRef.current) {
      const scale = (networkRef.current as { getScale: () => number }).getScale();
      (networkRef.current as { moveTo: (options: { scale: number }) => void }).moveTo({ scale: scale * 1.2 });
    }
  };

  const handleZoomOut = () => {
    if (networkRef.current) {
      const scale = (networkRef.current as { getScale: () => number }).getScale();
      (networkRef.current as { moveTo: (options: { scale: number }) => void }).moveTo({ scale: scale / 1.2 });
    }
  };

  const handleFit = () => {
    if (networkRef.current) {
      (networkRef.current as { fit: () => void }).fit();
    }
  };

  const selectedMemory = graphData?.nodes.find((n) => n.id === selectedNode);

  if (!mounted) {
    return null;
  }

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Network className="w-6 h-6" />
            Knowledge Graph
          </h1>
          <p className="text-muted-foreground">
            Visualisiere Zusammenhänge zwischen deinen Memories
          </p>
        </div>
        <Button variant="outline" onClick={loadGraphData} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Aktualisieren
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        {/* Graph */}
        <div className="lg:col-span-3">
          <Card className="h-[600px]">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Graph View</CardTitle>
                  <CardDescription>
                    {graphData?.nodes.length || 0} Nodes •{" "}
                    {graphData?.edges.length || 0} Edges
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Select value={edgeFilter} onValueChange={setEdgeFilter}>
                    <SelectTrigger className="w-[150px]">
                      <SelectValue placeholder="Filter" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Alle Edges</SelectItem>
                      <SelectItem value="leads_to">Leads to</SelectItem>
                      <SelectItem value="related_to">Related to</SelectItem>
                      <SelectItem value="contradicts">Contradicts</SelectItem>
                      <SelectItem value="supports">Supports</SelectItem>
                      <SelectItem value="depends_on">Depends on</SelectItem>
                      <SelectItem value="evolves_into">Evolves into</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="flex border rounded-md">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleZoomIn}
                      className="h-8 w-8"
                    >
                      <ZoomIn className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleZoomOut}
                      className="h-8 w-8"
                    >
                      <ZoomOut className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleFit}
                      className="h-8 w-8"
                    >
                      <Maximize2 className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="flex border rounded-md">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleExpandAll}
                      className="h-8 w-8 text-blue-600 hover:text-blue-700"
                      title="Alle aufklappen"
                    >
                      <ChevronDownSquare className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={handleCollapseAll}
                      className="h-8 w-8 text-amber-600 hover:text-amber-700"
                      title="Alle einklappen"
                    >
                      <ChevronUpSquare className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setShowIrrelevant(!showIrrelevant)}
                      className={`h-8 w-8 ${showIrrelevant ? "text-red-500" : "text-muted-foreground"}`}
                      title={showIrrelevant ? "Irrelevante ausblenden" : "Irrelevante einblenden"}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="h-[calc(100%-80px)]">
              {loading ? (
                <div className="h-full flex items-center justify-center">
                  <Skeleton className="h-full w-full" />
                </div>
              ) : graphData?.nodes.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                  <Network className="w-16 h-16 mb-4 opacity-50" />
                  <p className="text-lg font-medium">
                    Keine Graph-Daten vorhanden
                  </p>
                  <p className="text-sm">
                    Erstelle Memories mit Beziehungen, um den Graph zu füllen
                  </p>
                </div>
              ) : (
                <div
                  ref={containerRef}
                  className="h-full w-full bg-muted/20 rounded-lg"
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Legend */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Legende</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-2">Node-Typen</p>
                <div className="space-y-1">
                  {Object.entries(nodeTypeColors)
                    .filter(([type]) => !type.startsWith("entity_"))
                    .map(([type, color]) => (
                      <div key={type} className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: color }}
                        />
                        <span className="text-sm capitalize">
                          {type.replace("_", " ")}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
              <div>
                <p className="text-sm font-medium mb-2">Edge-Typen</p>
                <div className="space-y-1">
                  {Object.entries(edgeTypeColors).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="w-6 h-0.5"
                        style={{ backgroundColor: color }}
                      />
                      <span className="text-sm capitalize">
                        {type.replace("_", " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Selected Node */}
          {selectedMemory && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Ausgewählte Memory</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Badge
                  style={{
                    backgroundColor:
                      nodeTypeColors[selectedMemory.memory_type] + "20",
                    color: nodeTypeColors[selectedMemory.memory_type],
                  }}
                >
                  {selectedMemory.memory_type}
                </Badge>
                <p className="text-sm line-clamp-4">{selectedMemory.content}</p>
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>Wichtigkeit</span>
                  <span className="font-medium">
                    {selectedMemory.importance}/10
                  </span>
                </div>

                {/* Entity Hubs Section (D+B) */}
                {loadingEntities ? (
                  <div className="text-sm text-muted-foreground">Lade Entities...</div>
                ) : memoryEntities.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Entity Hubs:</p>
                    <div className="flex flex-wrap gap-1">
                      {memoryEntities.map((entity) => (
                        <Badge
                          key={entity.id}
                          variant="outline"
                          className="cursor-pointer hover:bg-primary/10 text-xs"
                          style={{
                            borderColor: nodeTypeColors[`entity_${entity.type}`] || "#8b5cf6",
                            color: nodeTypeColors[`entity_${entity.type}`] || "#8b5cf6",
                          }}
                          onClick={() => handleEntityClick(entity.id)}
                        >
                          {entity.name}
                          <span className="ml-1 opacity-60">({entity.related_memory_count})</span>
                        </Badge>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Klicke auf ein Entity um verwandte Memories zu finden
                    </p>
                  </div>
                )}

                {/* Highlighted memories indicator */}
                {highlightedMemories.size > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-green-600">{highlightedMemories.size} verwandte Memories</span>
                    <Button variant="ghost" size="sm" onClick={clearHighlights}>
                      ✕ Clear
                    </Button>
                  </div>
                )}

                <Link href={`/dashboard/memories/${selectedMemory.id}`}>
                  <Button variant="outline" size="sm" className="w-full">
                    Details anzeigen
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* Tips */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Tipps</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-2">
              <p>• Klicke auf einen Node um Details zu sehen</p>
              <p>• Doppelklicke um zur Memory zu navigieren</p>
              <p>• Ziehe Nodes um den Graph anzupassen</p>
              <p>• Scrolle zum Zoomen</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
