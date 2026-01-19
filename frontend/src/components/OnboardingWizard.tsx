"use client";

import { useState, useEffect } from "react";
import {
    Brain,
    Check,
    ChevronLeft,
    ChevronRight,
    Copy,
    Key,
    Loader2,
    Rocket,
    Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ConfigGenerator, type ApiKeyOption, type MCPClient } from "./ConfigGenerator";
import { cn } from "@/lib/utils";

// =============================================================================
// Types
// =============================================================================

interface OnboardingWizardProps {
    open: boolean;
    onComplete: () => void;
}

type OnboardingStep = 1 | 2 | 3 | 4 | 5;

interface ClientOption {
    id: MCPClient;
    name: string;
    description: string;
    recommended?: boolean;
}

// =============================================================================
// Step Components
// =============================================================================

function WelcomeStep({ onNext }: { onNext: () => void }) {
    return (
        <div className="text-center space-y-6 py-8">
            <div className="relative mx-auto w-20 h-20 bg-gradient-to-br from-primary to-primary/60 rounded-full flex items-center justify-center">
                <Brain className="w-10 h-10 text-primary-foreground" />
                <Sparkles className="absolute -top-2 -right-2 w-6 h-6 text-yellow-400" />
            </div>

            <div className="space-y-2">
                <h2 className="text-2xl font-bold">Willkommen bei KnowWhere!</h2>
                <p className="text-muted-foreground max-w-md mx-auto">
                    KnowWhere gibt deinem AI-Assistenten ein persistentes Gedächtnis.
                    Er merkt sich Dinge über dich und kann kontextbezogen antworten.
                </p>
            </div>

            <div className="grid grid-cols-3 gap-4 max-w-lg mx-auto text-sm">
                <div className="p-3 rounded-lg bg-muted/50">
                    <div className="font-medium">🧠 Memories</div>
                    <div className="text-xs text-muted-foreground">Speichert Vorlieben & Fakten</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                    <div className="font-medium">🔗 Kontext</div>
                    <div className="text-xs text-muted-foreground">Verknüpft Wissen</div>
                </div>
                <div className="p-3 rounded-lg bg-muted/50">
                    <div className="font-medium">🔒 Privat</div>
                    <div className="text-xs text-muted-foreground">Deine Daten gehören dir</div>
                </div>
            </div>

            <Button onClick={onNext} size="lg" className="gap-2">
                Los geht's
                <ChevronRight className="w-4 h-4" />
            </Button>
        </div>
    );
}

function ClientSelectStep({
    selectedClient,
    onSelectClient,
    onNext,
    onBack,
}: {
    selectedClient: MCPClient | null;
    onSelectClient: (client: MCPClient) => void;
    onNext: () => void;
    onBack: () => void;
}) {
    const clients: ClientOption[] = [
        { id: "cursor", name: "Cursor IDE", description: "Moderner Code-Editor", recommended: true },
        { id: "claude-desktop", name: "Claude Desktop", description: "Anthropics Desktop App" },
        { id: "claude-code", name: "Claude Code", description: "Claude CLI" },
        { id: "gemini-cli", name: "Gemini CLI", description: "Google Gemini" },
        { id: "custom", name: "Anderer Client", description: "Manuelle Konfiguration" },
    ];

    return (
        <div className="space-y-6 py-4">
            <div className="text-center space-y-2">
                <h2 className="text-xl font-bold">Welchen AI-Client nutzt du?</h2>
                <p className="text-sm text-muted-foreground">
                    Wir generieren die passende Konfiguration für dich.
                </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {clients.map((client) => (
                    <button
                        key={client.id}
                        onClick={() => onSelectClient(client.id)}
                        className={cn(
                            "relative p-4 rounded-lg border-2 transition-all text-left",
                            selectedClient === client.id
                                ? "border-primary bg-primary/5"
                                : "border-border hover:border-primary/50"
                        )}
                    >
                        {client.recommended && (
                            <Badge className="absolute -top-2 right-2 text-xs" variant="default">
                                Empfohlen
                            </Badge>
                        )}
                        <div className="font-medium">{client.name}</div>
                        <div className="text-xs text-muted-foreground">{client.description}</div>
                    </button>
                ))}
            </div>

            <div className="flex justify-between pt-4">
                <Button variant="ghost" onClick={onBack} className="gap-2">
                    <ChevronLeft className="w-4 h-4" />
                    Zurück
                </Button>
                <Button onClick={onNext} disabled={!selectedClient} className="gap-2">
                    Weiter
                    <ChevronRight className="w-4 h-4" />
                </Button>
            </div>
        </div>
    );
}

function CreateKeyStep({
    onKeyCreated,
    onBack,
}: {
    onKeyCreated: (key: string, id: string, name: string) => void;
    onBack: () => void;
}) {
    const [keyName, setKeyName] = useState("");
    const [creating, setCreating] = useState(false);

    const handleCreate = async () => {
        if (!keyName.trim()) {
            toast.error("Bitte gib einen Namen ein");
            return;
        }

        setCreating(true);
        try {
            const result = await api.createApiKey({
                name: keyName.trim(),
                scopes: ["memories:read", "memories:write"],
            });

            toast.success("API Key erstellt!");
            onKeyCreated(result.key, result.id, keyName.trim());
        } catch (err) {
            toast.error("Fehler beim Erstellen des API Keys");
            console.error(err);
        } finally {
            setCreating(false);
        }
    };

    return (
        <div className="space-y-6 py-4">
            <div className="text-center space-y-2">
                <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center">
                    <Key className="w-6 h-6 text-primary" />
                </div>
                <h2 className="text-xl font-bold">API Key erstellen</h2>
                <p className="text-sm text-muted-foreground">
                    Der API Key authentifiziert deinen AI-Client bei KnowWhere.
                </p>
            </div>

            <div className="max-w-sm mx-auto space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="key-name">Name für den Key</Label>
                    <Input
                        id="key-name"
                        placeholder="z.B. Mein Cursor Setup"
                        value={keyName}
                        onChange={(e) => setKeyName(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                    />
                    <p className="text-xs text-muted-foreground">
                        Hilft dir später, den Key zuzuordnen.
                    </p>
                </div>

                <Button
                    onClick={handleCreate}
                    disabled={creating || !keyName.trim()}
                    className="w-full gap-2"
                >
                    {creating ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Erstellen...
                        </>
                    ) : (
                        <>
                            <Key className="w-4 h-4" />
                            API Key erstellen
                        </>
                    )}
                </Button>
            </div>

            <div className="flex justify-start pt-4">
                <Button variant="ghost" onClick={onBack} className="gap-2">
                    <ChevronLeft className="w-4 h-4" />
                    Zurück
                </Button>
            </div>
        </div>
    );
}

function CopyConfigStep({
    apiKey,
    apiKeyId,
    apiKeyName,
    selectedClient,
    onNext,
    onBack,
}: {
    apiKey: string;
    apiKeyId: string;
    apiKeyName: string;
    selectedClient: MCPClient;
    onNext: () => void;
    onBack: () => void;
}) {
    const [copied, setCopied] = useState(false);

    const apiKeyOptions: ApiKeyOption[] = [{
        id: apiKeyId,
        name: apiKeyName,
        key_prefix: apiKey.substring(0, 10),
    }];

    return (
        <div className="space-y-4 py-4">
            <div className="text-center space-y-2">
                <h2 className="text-xl font-bold">Konfiguration kopieren</h2>
                <p className="text-sm text-muted-foreground">
                    Kopiere die Konfiguration und füge sie in deinen Client ein.
                </p>
            </div>

            <div className="max-h-[50vh] overflow-y-auto">
                <ConfigGenerator
                    apiKeys={apiKeyOptions}
                    selectedKeyId={apiKeyId}
                    newlyCreatedKey={apiKey}
                />
            </div>

            <div className="flex justify-between pt-4">
                <Button variant="ghost" onClick={onBack} className="gap-2">
                    <ChevronLeft className="w-4 h-4" />
                    Zurück
                </Button>
                <Button onClick={onNext} className="gap-2">
                    Weiter
                    <ChevronRight className="w-4 h-4" />
                </Button>
            </div>
        </div>
    );
}

function SuccessStep({ onComplete }: { onComplete: () => void }) {
    return (
        <div className="text-center space-y-6 py-8">
            <div className="relative mx-auto w-20 h-20 bg-gradient-to-br from-green-500 to-green-600 rounded-full flex items-center justify-center">
                <Check className="w-10 h-10 text-white" />
            </div>

            <div className="space-y-2">
                <h2 className="text-2xl font-bold">Alles bereit!</h2>
                <p className="text-muted-foreground max-w-md mx-auto">
                    Dein AI-Client ist jetzt mit KnowWhere verbunden.
                    Starte deinen Client neu und teste die Verbindung!
                </p>
            </div>

            <div className="p-4 bg-muted rounded-lg max-w-md mx-auto text-left">
                <div className="font-medium mb-2">Was du jetzt machen kannst:</div>
                <ul className="text-sm text-muted-foreground space-y-1">
                    <li>• Sag deinem AI: "Merke dir, dass ich..."</li>
                    <li>• Frag: "Was weißt du über mich?"</li>
                    <li>• Schau dir deine Memories im Dashboard an</li>
                </ul>
            </div>

            <Button onClick={onComplete} size="lg" className="gap-2">
                <Rocket className="w-4 h-4" />
                Zum Dashboard
            </Button>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export function OnboardingWizard({ open, onComplete }: OnboardingWizardProps) {
    const [step, setStep] = useState<OnboardingStep>(1);
    const [selectedClient, setSelectedClient] = useState<MCPClient | null>(null);
    const [createdKey, setCreatedKey] = useState<string | null>(null);
    const [createdKeyId, setCreatedKeyId] = useState<string | null>(null);
    const [createdKeyName, setCreatedKeyName] = useState<string | null>(null);
    const [completing, setCompleting] = useState(false);

    const handleComplete = async () => {
        setCompleting(true);
        try {
            await api.completeOnboarding();
            onComplete();
        } catch (err) {
            console.error("Failed to complete onboarding:", err);
            // Still complete on error - don't block user
            onComplete();
        } finally {
            setCompleting(false);
        }
    };

    const handleKeyCreated = (key: string, id: string, name: string) => {
        setCreatedKey(key);
        setCreatedKeyId(id);
        setCreatedKeyName(name);
        setStep(4);
    };

    const totalSteps = 5;
    const progress = (step / totalSteps) * 100;

    return (
        <Dialog open={open} onOpenChange={() => { }}>
            <DialogContent
                className="sm:max-w-2xl max-h-[90vh] overflow-hidden"
                onPointerDownOutside={(e) => e.preventDefault()}
                onEscapeKeyDown={(e) => e.preventDefault()}
            >
                <DialogHeader className="sr-only">
                    <DialogTitle>KnowWhere Setup</DialogTitle>
                    <DialogDescription>Richte dein KnowWhere Memory-System ein.</DialogDescription>
                </DialogHeader>

                {/* Progress bar */}
                <div className="absolute top-0 left-0 right-0 h-1 bg-muted">
                    <div
                        className="h-full bg-primary transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>

                {/* Step indicators */}
                <div className="flex justify-center gap-2 pt-4 pb-2">
                    {[1, 2, 3, 4, 5].map((s) => (
                        <div
                            key={s}
                            className={cn(
                                "w-2 h-2 rounded-full transition-all",
                                s === step
                                    ? "bg-primary w-4"
                                    : s < step
                                        ? "bg-primary/60"
                                        : "bg-muted-foreground/30"
                            )}
                        />
                    ))}
                </div>

                {/* Content */}
                <div className="overflow-y-auto max-h-[70vh]">
                    {step === 1 && <WelcomeStep onNext={() => setStep(2)} />}

                    {step === 2 && (
                        <ClientSelectStep
                            selectedClient={selectedClient}
                            onSelectClient={setSelectedClient}
                            onNext={() => setStep(3)}
                            onBack={() => setStep(1)}
                        />
                    )}

                    {step === 3 && (
                        <CreateKeyStep
                            onKeyCreated={handleKeyCreated}
                            onBack={() => setStep(2)}
                        />
                    )}

                    {step === 4 && createdKey && createdKeyId && createdKeyName && selectedClient && (
                        <CopyConfigStep
                            apiKey={createdKey}
                            apiKeyId={createdKeyId}
                            apiKeyName={createdKeyName}
                            selectedClient={selectedClient}
                            onNext={() => setStep(5)}
                            onBack={() => setStep(3)}
                        />
                    )}

                    {step === 5 && <SuccessStep onComplete={handleComplete} />}
                </div>
            </DialogContent>
        </Dialog>
    );
}

export default OnboardingWizard;
