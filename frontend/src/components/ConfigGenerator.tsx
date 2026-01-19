"use client";

import { useState, useEffect } from "react";
import { Copy, Check, Monitor, Terminal, Cloud, Eye, EyeOff, Key, Loader2, Wifi, WifiOff, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// =============================================================================
// Types
// =============================================================================

export type MCPClient =
    | "cursor"
    | "claude-desktop"
    | "claude-code"
    | "gemini-cli"
    | "custom";

export type TransportMode = "sse" | "stdio";

interface ClientConfig {
    id: MCPClient;
    name: string;
    icon: React.ReactNode;
    recommended?: boolean;
    description: string;
    configPath: {
        macos: string;
        windows: string;
        linux: string;
    };
    supportsSSE: boolean;
    supportsStdio: boolean;
    instructions: {
        sse: string[];
        stdio: string[];
    };
}

export interface ApiKeyOption {
    id: string;
    name: string;
    key_prefix: string;
    fullKey?: string; // Only available for newly created keys
}

interface ConfigGeneratorProps {
    /** List of available API keys to choose from */
    apiKeys: ApiKeyOption[];
    /** Optional: Pre-select a specific key (e.g., newly created) */
    selectedKeyId?: string;
    /** Optional: The full key value (only shown once after creation) */
    newlyCreatedKey?: string;
}

// =============================================================================
// Client Configurations
// =============================================================================

const CLIENT_CONFIGS: Record<MCPClient, ClientConfig> = {
    cursor: {
        id: "cursor",
        name: "Cursor IDE",
        icon: <Monitor className="w-5 h-5" />,
        recommended: true,
        description: "Moderner Code-Editor mit AI-Integration",
        configPath: {
            macos: "~/.cursor/mcp.json",
            windows: "%APPDATA%\\Cursor\\mcp.json",
            linux: "~/.config/Cursor/mcp.json",
        },
        supportsSSE: true,
        supportsStdio: false,
        instructions: {
            sse: [
                "Öffne Cursor → Settings → MCP",
                'Klicke auf "Add Server"',
                "Füge die Konfiguration unten ein",
                "Starte Cursor neu",
            ],
            stdio: [],
        },
    },
    "claude-desktop": {
        id: "claude-desktop",
        name: "Claude Desktop",
        icon: <Terminal className="w-5 h-5" />,
        description: "Anthropics offizielle Desktop App",
        configPath: {
            macos: "~/Library/Application Support/Claude/claude_desktop_config.json",
            windows: "%APPDATA%\\Claude\\claude_desktop_config.json",
            linux: "~/.config/Claude/claude_desktop_config.json",
        },
        supportsSSE: true,
        supportsStdio: true,
        instructions: {
            sse: [
                "Öffne die Claude Desktop Config-Datei (Pfad siehe unten)",
                'Füge die Konfiguration unter "mcpServers" ein',
                "Speichern und Claude Desktop neustarten",
            ],
            stdio: [
                "Öffne die Claude Desktop Config-Datei (Pfad siehe unten)",
                'Füge die Konfiguration unter "mcpServers" ein',
                "Passe den Pfad zu deinem KnowWhere-Ordner an",
                "Speichern und Claude Desktop neustarten",
            ],
        },
    },
    "claude-code": {
        id: "claude-code",
        name: "Claude Code",
        icon: <Terminal className="w-5 h-5" />,
        description: "Claude CLI für Terminal-Nutzung",
        configPath: {
            macos: "~/.claude/settings.json",
            windows: "%USERPROFILE%\\.claude\\settings.json",
            linux: "~/.claude/settings.json",
        },
        supportsSSE: true,
        supportsStdio: true,
        instructions: {
            sse: [
                "Öffne ~/.claude/settings.json",
                'Füge die Konfiguration unter "mcpServers" ein',
                "Speichern und neue Terminal-Session starten",
            ],
            stdio: [
                "Öffne ~/.claude/settings.json",
                'Füge die Konfiguration unter "mcpServers" ein',
                "Passe den Pfad zu deinem KnowWhere-Ordner an",
                "Speichern und neue Terminal-Session starten",
            ],
        },
    },
    "gemini-cli": {
        id: "gemini-cli",
        name: "Gemini CLI",
        icon: <Terminal className="w-5 h-5" />,
        description: "Google Gemini CLI Tool",
        configPath: {
            macos: "~/.config/gemini/settings.json",
            windows: "%APPDATA%\\gemini\\settings.json",
            linux: "~/.config/gemini/settings.json",
        },
        supportsSSE: true,
        supportsStdio: true,
        instructions: {
            sse: [
                "Öffne die Gemini CLI Einstellungen",
                "Füge die MCP-Konfiguration hinzu",
                "Starte eine neue Session",
            ],
            stdio: [
                "Öffne die Gemini CLI Einstellungen",
                "Füge die MCP-Konfiguration hinzu",
                "Passe den Pfad zu deinem KnowWhere-Ordner an",
                "Starte eine neue Session",
            ],
        },
    },
    custom: {
        id: "custom",
        name: "Anderer Client",
        icon: <Terminal className="w-5 h-5" />,
        description: "Manuelle Konfiguration für andere MCP-Clients",
        configPath: {
            macos: "",
            windows: "",
            linux: "",
        },
        supportsSSE: true,
        supportsStdio: true,
        instructions: {
            sse: [
                "Öffne die Konfigurationsdatei deines MCP-Clients",
                "Füge die unten stehende Konfiguration ein",
                "Starte den Client neu",
            ],
            stdio: [
                "Öffne die Konfigurationsdatei deines MCP-Clients",
                "Füge die unten stehende Konfiguration ein",
                "Passe den Pfad zu deinem KnowWhere-Ordner an",
                "Starte den Client neu",
            ],
        },
    },
};

// =============================================================================
// Helper Functions
// =============================================================================

function detectOS(): "macos" | "windows" | "linux" {
    if (typeof window === "undefined") return "macos";
    const platform = navigator.platform.toLowerCase();
    if (platform.includes("mac")) return "macos";
    if (platform.includes("win")) return "windows";
    return "linux";
}

function generateSSEConfig(apiKey: string, showKey: boolean): string {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "https://app.knowwhere.dev";
    const displayKey = showKey ? apiKey : "••••••••••••••••••••";
    return JSON.stringify(
        {
            knowwhere: {
                url: `${baseUrl}/sse`,
                headers: {
                    Authorization: `Bearer ${displayKey}`,
                },
            },
        },
        null,
        2
    );
}

function generateStdioConfig(apiKey: string, showKey: boolean): string {
    const displayKey = showKey ? apiKey : "••••••••••••••••••••";
    return JSON.stringify(
        {
            knowwhere: {
                command: "python",
                args: ["-m", "src.main"],
                cwd: "/path/to/KW_Mem_MCP_Server",
                env: {
                    KNOWWHERE_API_KEY: displayKey,
                    PYTHONPATH: "/path/to/KW_Mem_MCP_Server",
                },
            },
        },
        null,
        2
    );
}

// Get the actual key for copying (with real value)
function generateSSEConfigForCopy(apiKey: string): string {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "https://app.knowwhere.dev";
    return JSON.stringify(
        {
            knowwhere: {
                url: `${baseUrl}/sse`,
                headers: {
                    Authorization: `Bearer ${apiKey}`,
                },
            },
        },
        null,
        2
    );
}

function generateStdioConfigForCopy(apiKey: string): string {
    return JSON.stringify(
        {
            knowwhere: {
                command: "python",
                args: ["-m", "src.main"],
                cwd: "/path/to/KW_Mem_MCP_Server",
                env: {
                    KNOWWHERE_API_KEY: apiKey,
                    PYTHONPATH: "/path/to/KW_Mem_MCP_Server",
                },
            },
        },
        null,
        2
    );
}

// =============================================================================
// Components
// =============================================================================

interface CopyButtonProps {
    text: string;
    className?: string;
}

function CopyButton({ text, className }: CopyButtonProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        toast.success("In Zwischenablage kopiert");
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            className={cn("gap-2", className)}
        >
            {copied ? (
                <>
                    <Check className="w-4 h-4 text-green-500" />
                    Kopiert
                </>
            ) : (
                <>
                    <Copy className="w-4 h-4" />
                    Kopieren
                </>
            )}
        </Button>
    );
}

interface ClientCardProps {
    client: ClientConfig;
    selected: boolean;
    onSelect: () => void;
}

function ClientCard({ client, selected, onSelect }: ClientCardProps) {
    return (
        <button
            onClick={onSelect}
            className={cn(
                "relative flex flex-col items-center p-4 rounded-lg border-2 transition-all text-left w-full",
                selected
                    ? "border-primary bg-primary/5"
                    : "border-border hover:border-primary/50 hover:bg-muted/50"
            )}
        >
            {client.recommended && (
                <Badge className="absolute -top-2 -right-2 text-xs" variant="default">
                    Empfohlen
                </Badge>
            )}
            <div
                className={cn(
                    "p-3 rounded-full mb-2",
                    selected ? "bg-primary text-primary-foreground" : "bg-muted"
                )}
            >
                {client.icon}
            </div>
            <span className="font-medium text-sm">{client.name}</span>
            <span className="text-xs text-muted-foreground text-center mt-1">
                {client.description}
            </span>
        </button>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export function ConfigGenerator({
    apiKeys,
    selectedKeyId,
    newlyCreatedKey,
}: ConfigGeneratorProps) {
    const [selectedClient, setSelectedClient] = useState<MCPClient>("cursor");
    const [transportMode, setTransportMode] = useState<TransportMode>("sse");
    const [showKeyInConfig, setShowKeyInConfig] = useState(false);
    const [selectedKey, setSelectedKey] = useState<string>(selectedKeyId || "");

    // Set default selected key
    useEffect(() => {
        if (selectedKeyId) {
            setSelectedKey(selectedKeyId);
        } else if (apiKeys.length > 0 && !selectedKey) {
            setSelectedKey(apiKeys[0].id);
        }
    }, [apiKeys, selectedKeyId, selectedKey]);

    const clientConfig = CLIENT_CONFIGS[selectedClient];
    const os = detectOS();
    const configPath = clientConfig.configPath[os];

    // Get the currently selected key info
    const currentKey = apiKeys.find((k) => k.id === selectedKey);

    // Determine which key value to use
    // If we have a newly created key and it matches the selection, use the full key
    // Otherwise, we can only show the prefix
    const selectedKeyInfo = currentKey;
    const hasFullKey = newlyCreatedKey && selectedKeyId === selectedKey;
    const keyValueForConfig = hasFullKey ? newlyCreatedKey : currentKey?.key_prefix + "...";
    const actualKeyValue = hasFullKey ? newlyCreatedKey : "";

    // Generate display config (may have masked key)
    const displayConfig =
        transportMode === "sse"
            ? generateSSEConfig(keyValueForConfig, showKeyInConfig || !hasFullKey)
            : generateStdioConfig(keyValueForConfig, showKeyInConfig || !hasFullKey);

    // Generate config for copying (always with real key if available)
    const copyConfig =
        transportMode === "sse"
            ? hasFullKey
                ? generateSSEConfigForCopy(newlyCreatedKey)
                : generateSSEConfig(keyValueForConfig, true)
            : hasFullKey
                ? generateStdioConfigForCopy(newlyCreatedKey)
                : generateStdioConfig(keyValueForConfig, true);

    const instructions =
        transportMode === "sse"
            ? clientConfig.instructions.sse
            : clientConfig.instructions.stdio;

    // Check if client supports selected transport
    const canUseSSE = clientConfig.supportsSSE;
    const canUseStdio = clientConfig.supportsStdio;

    // Auto-switch transport if not supported
    useEffect(() => {
        if (transportMode === "sse" && !canUseSSE && canUseStdio) {
            setTransportMode("stdio");
        } else if (transportMode === "stdio" && !canUseStdio && canUseSSE) {
            setTransportMode("sse");
        }
    }, [transportMode, canUseSSE, canUseStdio]);

    if (apiKeys.length === 0) {
        return (
            <div className="text-center py-8 text-muted-foreground">
                <Key className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium">Keine API Keys vorhanden</p>
                <p className="text-sm">
                    Erstelle zuerst einen API Key, um die Konfiguration zu generieren.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* API Key Selection */}
            <div className="space-y-3">
                <Label className="text-base font-semibold flex items-center gap-2">
                    <Key className="w-4 h-4" />
                    API Key auswählen
                </Label>
                <div className="flex items-center gap-3">
                    <Select value={selectedKey} onValueChange={setSelectedKey}>
                        <SelectTrigger className="flex-1">
                            <SelectValue placeholder="Wähle einen API Key" />
                        </SelectTrigger>
                        <SelectContent>
                            {apiKeys.map((key) => (
                                <SelectItem key={key.id} value={key.id}>
                                    <span className="flex items-center gap-2">
                                        {key.name}
                                        <span className="text-muted-foreground text-xs">
                                            ({key.key_prefix}...)
                                        </span>
                                        {newlyCreatedKey && selectedKeyId === key.id && (
                                            <Badge variant="secondary" className="text-xs">
                                                Neu
                                            </Badge>
                                        )}
                                    </span>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    {/* Eye toggle for showing/hiding key in config */}
                    {hasFullKey && (
                        <Button
                            variant="outline"
                            size="icon"
                            onClick={() => setShowKeyInConfig(!showKeyInConfig)}
                            title={showKeyInConfig ? "Key verstecken" : "Key anzeigen"}
                        >
                            {showKeyInConfig ? (
                                <EyeOff className="w-4 h-4" />
                            ) : (
                                <Eye className="w-4 h-4" />
                            )}
                        </Button>
                    )}
                </div>

                {!hasFullKey && selectedKey && (
                    <p className="text-xs text-muted-foreground">
                        💡 Der vollständige Key wird nur einmalig nach der Erstellung angezeigt.
                        Wähle einen neu erstellten Key, um die Konfiguration mit dem echten Key zu kopieren.
                    </p>
                )}
            </div>

            {/* Client Selection */}
            <div className="space-y-3">
                <Label className="text-base font-semibold">Wähle deinen AI-Client</Label>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                    {Object.values(CLIENT_CONFIGS).map((client) => (
                        <ClientCard
                            key={client.id}
                            client={client}
                            selected={selectedClient === client.id}
                            onSelect={() => setSelectedClient(client.id)}
                        />
                    ))}
                </div>
            </div>

            {/* Transport Mode Selection */}
            {canUseSSE && canUseStdio && (
                <div className="space-y-3">
                    <Label className="text-base font-semibold">Verbindungsmodus</Label>
                    <Tabs
                        value={transportMode}
                        onValueChange={(v) => setTransportMode(v as TransportMode)}
                    >
                        <TabsList className="grid w-full grid-cols-2">
                            <TabsTrigger value="sse" className="gap-2">
                                <Cloud className="w-4 h-4" />
                                Cloud (SSE)
                                <Badge variant="secondary" className="ml-1 text-xs">
                                    Empfohlen
                                </Badge>
                            </TabsTrigger>
                            <TabsTrigger value="stdio" className="gap-2">
                                <Terminal className="w-4 h-4" />
                                Self-Hosted (Stdio)
                            </TabsTrigger>
                        </TabsList>
                        <TabsContent value="sse" className="mt-3">
                            <div className="p-3 bg-green-500/10 text-green-700 dark:text-green-400 rounded-lg text-sm">
                                ✓ Keine Installation nötig • Automatische Updates • Funktioniert
                                sofort
                            </div>
                        </TabsContent>
                        <TabsContent value="stdio" className="mt-3">
                            <div className="p-3 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 rounded-lg text-sm">
                                ⚠️ Erfordert lokales Python-Setup und geklontes Repository.
                                <br />
                                Nur für Power-User empfohlen.
                            </div>
                        </TabsContent>
                    </Tabs>
                </div>
            )}

            {/* Instructions */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        📋 Konfiguration für {clientConfig.name}
                    </CardTitle>
                    <CardDescription>
                        Folge diesen Schritten, um KnowWhere zu verbinden
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Step-by-step instructions */}
                    <div className="space-y-2">
                        {instructions.map((step, index) => (
                            <div key={index} className="flex items-start gap-3">
                                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium">
                                    {index + 1}
                                </div>
                                <span className="text-sm pt-0.5">{step}</span>
                            </div>
                        ))}
                    </div>

                    {/* Config path */}
                    {configPath && (
                        <div className="p-3 bg-muted rounded-lg">
                            <Label className="text-xs text-muted-foreground">
                                Config-Datei Pfad ({os})
                            </Label>
                            <code className="block text-sm mt-1 break-all">{configPath}</code>
                        </div>
                    )}

                    {/* Config code block */}
                    <div className="relative">
                        <div className="absolute top-2 right-2 z-10 flex gap-2">
                            {hasFullKey && (
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => setShowKeyInConfig(!showKeyInConfig)}
                                    title={showKeyInConfig ? "Key verstecken" : "Key anzeigen"}
                                    className="h-8 w-8 bg-zinc-800 hover:bg-zinc-700"
                                >
                                    {showKeyInConfig ? (
                                        <EyeOff className="w-4 h-4 text-zinc-300" />
                                    ) : (
                                        <Eye className="w-4 h-4 text-zinc-300" />
                                    )}
                                </Button>
                            )}
                            <CopyButton text={copyConfig} />
                        </div>
                        <pre className="p-4 bg-zinc-950 text-zinc-100 rounded-lg overflow-x-auto text-sm">
                            <code>{displayConfig}</code>
                        </pre>
                    </div>

                    {/* Stdio path warning */}
                    {transportMode === "stdio" && (
                        <div className="p-3 bg-orange-500/10 text-orange-700 dark:text-orange-400 rounded-lg text-sm">
                            ⚠️ <strong>Wichtig:</strong> Ersetze{" "}
                            <code className="bg-orange-500/20 px-1 rounded">
                                /path/to/KW_Mem_MCP_Server
                            </code>{" "}
                            mit dem tatsächlichen Pfad zu deinem geklonten Repository.
                        </div>
                    )}

                    {/* Connection Test */}
                    <ConnectionTestButton />
                </CardContent>
            </Card>
        </div>
    );
}

// =============================================================================
// Connection Test Button Component
// =============================================================================

function ConnectionTestButton() {
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<{
        success: boolean;
        message: string;
        memory_count?: number;
    } | null>(null);

    const handleTest = async () => {
        setTesting(true);
        setTestResult(null);

        try {
            const result = await api.testConnection();
            setTestResult({
                success: true,
                message: result.message,
                memory_count: result.memory_count,
            });
            toast.success("Verbindung erfolgreich!");
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Verbindungsfehler";
            setTestResult({
                success: false,
                message: errorMessage,
            });
            toast.error("Verbindungstest fehlgeschlagen", {
                description: errorMessage,
            });
        } finally {
            setTesting(false);
        }
    };

    return (
        <div className="pt-2 border-t">
            <div className="flex items-center justify-between gap-4">
                <div className="text-sm">
                    <div className="font-medium">Verbindung testen</div>
                    <div className="text-muted-foreground text-xs">
                        Prüfe ob dein Client verbunden ist
                    </div>
                </div>
                <Button
                    variant={testResult?.success ? "outline" : "default"}
                    size="sm"
                    onClick={handleTest}
                    disabled={testing}
                    className={cn(
                        "gap-2 min-w-[140px]",
                        testResult?.success && "border-green-500 text-green-600"
                    )}
                >
                    {testing ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Teste...
                        </>
                    ) : testResult?.success ? (
                        <>
                            <CheckCircle2 className="w-4 h-4" />
                            Verbunden!
                        </>
                    ) : testResult && !testResult.success ? (
                        <>
                            <WifiOff className="w-4 h-4" />
                            Erneut testen
                        </>
                    ) : (
                        <>
                            <Wifi className="w-4 h-4" />
                            Test starten
                        </>
                    )}
                </Button>
            </div>

            {/* Result display */}
            {testResult && (
                <div
                    className={cn(
                        "mt-3 p-3 rounded-lg text-sm",
                        testResult.success
                            ? "bg-green-500/10 text-green-700 dark:text-green-400"
                            : "bg-red-500/10 text-red-700 dark:text-red-400"
                    )}
                >
                    {testResult.success ? (
                        <div className="space-y-1">
                            <div className="font-medium">{testResult.message}</div>
                            {testResult.memory_count !== undefined && (
                                <div className="text-xs opacity-80">
                                    Du hast {testResult.memory_count} Memories gespeichert.
                                </div>
                            )}
                        </div>
                    ) : (
                        <div>
                            <div className="font-medium">Verbindung fehlgeschlagen</div>
                            <div className="text-xs opacity-80 mt-1">{testResult.message}</div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default ConfigGenerator;
