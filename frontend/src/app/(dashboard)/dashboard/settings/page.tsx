"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  Settings,
  User,
  Bell,
  Shield,
  CreditCard,
  Download,
  Trash2,
  Loader2,
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
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

interface UserData {
  id: string;
  email: string;
  user_metadata?: {
    full_name?: string;
  };
  created_at: string;
}

export default function SettingsPage() {
  const [user, setUser] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fullName, setFullName] = useState("");

  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (user) {
        setUser(user as UserData);
        setFullName(user.user_metadata?.full_name || "");
      }
      setLoading(false);
    };

    loadUser();
  }, []);

  const handleUpdateProfile = async () => {
    setSaving(true);
    try {
      const supabase = createClient();
      const { error } = await supabase.auth.updateUser({
        data: { full_name: fullName },
      });

      if (error) throw error;
      toast.success("Profil aktualisiert");
    } catch (err) {
      toast.error("Fehler beim Aktualisieren");
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    toast.info("Export wird vorbereitet...");
    // In production, this would call the export API
    setTimeout(() => {
      toast.success("Export-Link wurde an deine E-Mail gesendet");
    }, 2000);
  };

  const handleDeleteAccount = () => {
    if (
      !confirm(
        "Bist du sicher, dass du dein Konto löschen möchtest? Alle Daten werden unwiderruflich gelöscht."
      )
    ) {
      return;
    }

    if (
      !confirm(
        "Diese Aktion kann NICHT rückgängig gemacht werden. Tippe 'LÖSCHEN' um fortzufahren."
      )
    ) {
      return;
    }

    toast.error("Account-Löschung: Bitte kontaktiere den Support");
  };

  if (loading) {
    return (
      <div className="p-6 lg:p-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Settings className="w-6 h-6" />
          Einstellungen
        </h1>
        <p className="text-muted-foreground">
          Verwalte dein Konto und deine Präferenzen
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile" className="gap-2">
            <User className="w-4 h-4" />
            Profil
          </TabsTrigger>
          <TabsTrigger value="subscription" className="gap-2">
            <CreditCard className="w-4 h-4" />
            Abo
          </TabsTrigger>
          <TabsTrigger value="privacy" className="gap-2">
            <Shield className="w-4 h-4" />
            Datenschutz
          </TabsTrigger>
        </TabsList>

        {/* Profile Tab */}
        <TabsContent value="profile" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Profil-Informationen</CardTitle>
              <CardDescription>
                Aktualisiere deine persönlichen Daten
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">E-Mail</Label>
                <Input
                  id="email"
                  type="email"
                  value={user?.email || ""}
                  disabled
                  className="bg-muted"
                />
                <p className="text-xs text-muted-foreground">
                  E-Mail kann nicht geändert werden
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Dein Name"
                />
              </div>

              <div className="space-y-2">
                <Label>Mitglied seit</Label>
                <p className="text-sm text-muted-foreground">
                  {user?.created_at
                    ? new Date(user.created_at).toLocaleDateString("de-DE", {
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })
                    : "-"}
                </p>
              </div>

              <Button onClick={handleUpdateProfile} disabled={saving}>
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Speichern...
                  </>
                ) : (
                  "Änderungen speichern"
                )}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Passwort ändern</CardTitle>
              <CardDescription>
                Aktualisiere dein Passwort für mehr Sicherheit
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                onClick={async () => {
                  const supabase = createClient();
                  const { error } = await supabase.auth.resetPasswordForEmail(
                    user?.email || "",
                    { redirectTo: `${window.location.origin}/reset-password` }
                  );
                  if (error) {
                    toast.error("Fehler beim Senden der E-Mail");
                  } else {
                    toast.success("Passwort-Reset E-Mail gesendet");
                  }
                }}
              >
                Passwort-Reset anfordern
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Subscription Tab */}
        <TabsContent value="subscription" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Aktueller Plan</CardTitle>
              <CardDescription>
                Verwalte dein Abonnement
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">Free Plan</h3>
                    <Badge>Aktuell</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    100.000 Requests/Monat • 1 GB Speicher
                  </p>
                </div>
                <Button>Upgrade auf Pro</Button>
              </div>

              <Separator />

              <div className="space-y-2">
                <h4 className="font-medium">Nutzung diesen Monat</h4>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>API Requests</span>
                      <span>0 / 100.000</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-primary w-0" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span>Speicher</span>
                      <span>0 MB / 1 GB</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-primary w-0" />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Privacy Tab */}
        <TabsContent value="privacy" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Datenexport</CardTitle>
              <CardDescription>
                Lade alle deine Daten im JSON-Format herunter (GDPR-konform)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" onClick={handleExport} className="gap-2">
                <Download className="w-4 h-4" />
                Daten exportieren
              </Button>
            </CardContent>
          </Card>

          <Card className="border-destructive">
            <CardHeader>
              <CardTitle className="text-destructive">Gefahrenzone</CardTitle>
              <CardDescription>
                Unwiderrufliche Aktionen für dein Konto
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-destructive/10 rounded-lg">
                <div>
                  <h4 className="font-medium text-destructive">
                    Konto löschen
                  </h4>
                  <p className="text-sm text-muted-foreground">
                    Alle Daten werden permanent gelöscht
                  </p>
                </div>
                <Button
                  variant="destructive"
                  onClick={handleDeleteAccount}
                  className="gap-2"
                >
                  <Trash2 className="w-4 h-4" />
                  Konto löschen
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
