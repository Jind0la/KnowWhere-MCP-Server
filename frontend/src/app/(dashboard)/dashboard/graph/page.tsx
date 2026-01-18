"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Network, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
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
};

const nodeTypeColors: Record<string, string> = {
  episodic: "#3b82f6",
  semantic: "#10b981",
  preference: "#ec4899",
  procedural: "#f97316",
  meta: "#8b5cf6",
};

interface GraphData {
  edges: GraphEdge[];
  nodes: Array<{
    id: string;
    content: string;
    memory_type: string;
    importance: number;
  }>;
}

export default function KnowledgeGraphPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [edgeFilter, setEdgeFilter] = useState<string>("all");

  useEffect(() => {
    loadGraphData();
  }, []);

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

  useEffect(() => {
    if (!graphData || !containerRef.current || loading) return;

    // Dynamically import vis-network
    import("vis-network/standalone").then(({ Network, DataSet }) => {
      const filteredEdges =
        edgeFilter === "all"
          ? graphData.edges
          : graphData.edges.filter((e) => e.edge_type === edgeFilter);

      // Create nodes
      const nodes = new DataSet(
        graphData.nodes.map((node) => ({
          id: node.id,
          label:
            node.content.length > 30
              ? node.content.slice(0, 30) + "..."
              : node.content,
          title: node.content,
          color: {
            background: nodeTypeColors[node.memory_type] || "#6b7280",
            border: nodeTypeColors[node.memory_type] || "#6b7280",
            highlight: {
              background: nodeTypeColors[node.memory_type] || "#6b7280",
              border: "#fff",
            },
          },
          size: 20 + node.importance * 2,
          font: {
            color: "#fff",
            size: 12,
          },
        }))
      );

      // Create edges
      const edges = new DataSet(
        filteredEdges.map((edge) => ({
          id: edge.id,
          from: edge.from_node_id,
          to: edge.to_node_id,
          label: edge.edge_type.replace("_", " "),
          color: {
            color: edgeTypeColors[edge.edge_type] || "#6b7280",
            highlight: "#fff",
          },
          width: edge.strength * 3,
          arrows: "to",
          smooth: {
            enabled: true,
            type: "curvedCW",
            roundness: 0.2,
          },
          font: {
            size: 10,
            color: "#9ca3af",
            strokeWidth: 0,
          },
        }))
      );

      // Network options - use any to avoid vis-network type issues
      const options: Record<string, unknown> = {
        physics: {
          enabled: true,
          stabilization: {
            enabled: true,
            iterations: 100,
          },
          barnesHut: {
            gravitationalConstant: -2000,
            centralGravity: 0.1,
            springLength: 150,
            springConstant: 0.04,
          },
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          zoomView: true,
          dragView: true,
        },
        nodes: {
          shape: "dot",
          borderWidth: 2,
          shadow: true,
        },
        edges: {
          smooth: {
            enabled: true,
            type: "dynamic",
            roundness: 0.5,
          },
        },
      };

      // Create network
      const network = new Network(containerRef.current!, { nodes, edges }, options);

      // Handle node click
      network.on("click", (params: { nodes: string[] }) => {
        if (params.nodes.length > 0) {
          setSelectedNode(params.nodes[0]);
        } else {
          setSelectedNode(null);
        }
      });

      // Handle double click to open memory
      network.on("doubleClick", (params: { nodes: string[] }) => {
        if (params.nodes.length > 0) {
          window.location.href = `/dashboard/memories/${params.nodes[0]}`;
        }
      });

      networkRef.current = network;
    });

    return () => {
      if (networkRef.current) {
        (networkRef.current as { destroy: () => void }).destroy();
      }
    };
  }, [graphData, loading, edgeFilter]);

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
                  {Object.entries(nodeTypeColors).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                      <span className="text-sm capitalize">{type}</span>
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
