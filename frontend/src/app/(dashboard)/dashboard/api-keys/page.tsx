"use client";

import { useEffect, useState } from "react";
import {
  Key,
  Plus,
  Copy,
  Trash2,
  AlertTriangle,
  Check,
  Eye,
  EyeOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type ApiKey } from "@/lib/api";
import { toast } from "sonner";

const availableScopes = [
  { value: "memories:read", label: "Memories lesen" },
  { value: "memories:write", label: "Memories schreiben" },
  { value: "memories:delete", label: "Memories löschen" },
  { value: "consolidate:execute", label: "Konsolidierung ausführen" },
  { value: "export:execute", label: "Export ausführen" },
];

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newKeyDialogOpen, setNewKeyDialogOpen] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);

  // Form state
  const [keyName, setKeyName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    "memories:read",
    "memories:write",
  ]);
  const [expiresIn, setExpiresIn] = useState<string>("never");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    setLoading(true);
    try {
      const data = await api.getApiKeys();
      setKeys(data.keys);
    } catch (err) {
      toast.error("Fehler beim Laden der API Keys");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!keyName.trim()) {
      toast.error("Bitte gib einen Namen ein");
      return;
    }

    setCreating(true);
    try {
      const result = await api.createApiKey({
        name: keyName.trim(),
        scopes: selectedScopes,
        expires_in_days: expiresIn === "never" ? undefined : parseInt(expiresIn),
      });

      setCreatedKey(result.key);
      setCreateDialogOpen(false);
      setNewKeyDialogOpen(true);
      
      // Reset form
      setKeyName("");
      setSelectedScopes(["memories:read", "memories:write"]);
      setExpiresIn("never");
      
      // Reload keys
      loadKeys();
    } catch (err) {
      toast.error("Fehler beim Erstellen des API Keys");
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    if (!confirm("API Key wirklich widerrufen? Diese Aktion kann nicht rückgängig gemacht werden.")) {
      return;
    }

    try {
      await api.revokeApiKey(id);
      toast.success("API Key widerrufen");
      loadKeys();
    } catch (err) {
      toast.error("Fehler beim Widerrufen");
      console.error(err);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("In Zwischenablage kopiert");
  };

  const toggleScope = (scope: string) => {
    if (selectedScopes.includes(scope)) {
      setSelectedScopes(selectedScopes.filter((s) => s !== scope));
    } else {
      setSelectedScopes([...selectedScopes, scope]);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Key className="w-6 h-6" />
            API Keys
          </h1>
          <p className="text-muted-foreground">
            Verwalte deine API Keys für die Integration mit externen Diensten
          </p>
        </div>
        <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              Neuen Key erstellen
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Neuen API Key erstellen</DialogTitle>
              <DialogDescription>
                Erstelle einen neuen API Key für die MCP Integration oder andere
                Dienste.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  placeholder="z.B. Claude Desktop, Cursor IDE..."
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Berechtigungen</Label>
                <div className="space-y-2">
                  {availableScopes.map((scope) => (
                    <label
                      key={scope.value}
                      className="flex items-center gap-2 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedScopes.includes(scope.value)}
                        onChange={() => toggleScope(scope.value)}
                        className="rounded border-input"
                      />
                      <span className="text-sm">{scope.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Gültigkeit</Label>
                <Select value={expiresIn} onValueChange={setExpiresIn}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="never">Nie ablaufen</SelectItem>
                    <SelectItem value="30">30 Tage</SelectItem>
                    <SelectItem value="90">90 Tage</SelectItem>
                    <SelectItem value="365">1 Jahr</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setCreateDialogOpen(false)}
              >
                Abbrechen
              </Button>
              <Button onClick={handleCreate} disabled={creating}>
                {creating ? "Erstellen..." : "Erstellen"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* New Key Dialog */}
      <Dialog open={newKeyDialogOpen} onOpenChange={setNewKeyDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Check className="w-5 h-5 text-green-500" />
              API Key erstellt
            </DialogTitle>
            <DialogDescription>
              Kopiere deinen API Key jetzt. Er wird nur einmal angezeigt!
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="p-4 bg-muted rounded-lg space-y-2">
              <div className="flex items-center justify-between">
                <Label>Dein API Key</Label>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowKey(!showKey)}
                  >
                    {showKey ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => copyToClipboard(createdKey || "")}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <code className="block text-sm break-all">
                {showKey ? createdKey : "••••••••••••••••••••••••••••••••"}
              </code>
            </div>

            <div className="flex items-start gap-2 p-3 bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 rounded-lg">
              <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
              <p className="text-sm">
                Speichere diesen Key sicher ab. Du wirst ihn nicht mehr sehen
                können!
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={() => {
                setNewKeyDialogOpen(false);
                setCreatedKey(null);
                setShowKey(false);
              }}
            >
              Verstanden
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Keys Table */}
      <Card>
        <CardHeader>
          <CardTitle>Deine API Keys</CardTitle>
          <CardDescription>
            Verwalte und widerrufe deine aktiven API Keys
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : keys.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Key className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Keine API Keys</p>
              <p className="text-sm">
                Erstelle deinen ersten API Key für die Integration
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Berechtigungen</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Zuletzt verwendet</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-medium">{key.name}</TableCell>
                    <TableCell>
                      <code className="text-sm text-muted-foreground">
                        {key.key_prefix}...
                      </code>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {key.scopes.slice(0, 2).map((scope) => (
                          <Badge
                            key={scope}
                            variant="secondary"
                            className="text-xs"
                          >
                            {scope.split(":")[0]}
                          </Badge>
                        ))}
                        {key.scopes.length > 2 && (
                          <Badge variant="secondary" className="text-xs">
                            +{key.scopes.length - 2}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          key.status === "active" ? "default" : "secondary"
                        }
                      >
                        {key.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {key.last_used_at
                        ? new Date(key.last_used_at).toLocaleDateString(
                            "de-DE",
                            {
                              day: "numeric",
                              month: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )
                        : "Nie"}
                    </TableCell>
                    <TableCell>
                      {key.status === "active" && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRevoke(key.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Usage Info */}
      <Card>
        <CardHeader>
          <CardTitle>Verwendung</CardTitle>
          <CardDescription>So verwendest du deinen API Key</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm font-medium">HTTP Header</Label>
            <pre className="mt-2 p-3 bg-muted rounded-lg text-sm overflow-x-auto">
              <code>Authorization: Bearer YOUR_API_KEY</code>
            </pre>
          </div>
          <div>
            <Label className="text-sm font-medium">MCP Config (claude_desktop_config.json)</Label>
            <pre className="mt-2 p-3 bg-muted rounded-lg text-sm overflow-x-auto">
              <code>{`{
  "mcpServers": {
    "knowwhere": {
      "command": "npx",
      "args": ["-y", "knowwhere-mcp"],
      "env": {
        "KNOWWHERE_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}`}</code>
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
