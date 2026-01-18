import Link from "next/link";
import {
  Brain,
  Sparkles,
  Database,
  Network,
  Shield,
  Zap,
  ArrowRight,
  Check,
  MessageSquare,
  BookOpen,
  Heart,
  Lightbulb,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const memoryTypes = [
  {
    icon: MessageSquare,
    name: "Episodic",
    description: "Spezifische Ereignisse und Gespräche",
    example: '"In Session #42 sagte der User..."',
    color: "text-blue-500",
    bg: "bg-blue-500/10",
  },
  {
    icon: BookOpen,
    name: "Semantic",
    description: "Fakten und Wissensbeziehungen",
    example: '"TypeScript ist ein Superset von JavaScript"',
    color: "text-emerald-500",
    bg: "bg-emerald-500/10",
  },
  {
    icon: Heart,
    name: "Preference",
    description: "Persönliche Vorlieben und Entscheidungen",
    example: '"User bevorzugt async/await gegenüber Promises"',
    color: "text-pink-500",
    bg: "bg-pink-500/10",
  },
  {
    icon: GitBranch,
    name: "Procedural",
    description: "How-to Wissen und Workflows",
    example: '"Um React zu installieren: npm create vite..."',
    color: "text-orange-500",
    bg: "bg-orange-500/10",
  },
  {
    icon: Lightbulb,
    name: "Meta",
    description: "Meta-kognitives Wissen über das Lernen",
    example: '"User kämpft mit async Konzepten"',
    color: "text-purple-500",
    bg: "bg-purple-500/10",
  },
];

const features = [
  {
    icon: Database,
    title: "Vektorspeicher",
    description:
      "Semantic Search mit pgvector für blitzschnelle Ähnlichkeitssuche über alle deine Memories.",
  },
  {
    icon: Network,
    title: "Knowledge Graph",
    description:
      "Visualisiere Zusammenhänge zwischen deinen Erkenntnissen mit interaktiven Graphen.",
  },
  {
    icon: Sparkles,
    title: "AI-gestützte Konsolidierung",
    description:
      "Automatische Extraktion von Wissen aus Gesprächen mit LLM-Unterstützung.",
  },
  {
    icon: Shield,
    title: "GDPR-konform",
    description:
      "Volle Kontrolle über deine Daten mit Soft-Delete und Export-Funktionen.",
  },
  {
    icon: Zap,
    title: "MCP Integration",
    description:
      "Nahtlose Integration mit AI-Assistenten über das Model Context Protocol.",
  },
  {
    icon: Brain,
    title: "Evolution Tracking",
    description:
      "Verfolge wie sich deine Präferenzen und dein Wissen über Zeit entwickeln.",
  },
];

const pricingPlans = [
  {
    name: "Free",
    price: "0€",
    description: "Für den Einstieg",
    features: [
      "100.000 Requests/Monat",
      "1 GB Speicher",
      "Remember & Recall",
      "Memory löschen",
      "Community Support",
    ],
    cta: "Kostenlos starten",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "19€",
    period: "/Monat",
    description: "Für Power-User",
    features: [
      "1 Million Requests/Monat",
      "10 GB Speicher",
      "Alle Free Features",
      "Session Konsolidierung",
      "Memory Export",
      "Priority Support",
    ],
    cta: "Pro werden",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Kontakt",
    description: "Für Teams",
    features: [
      "Unbegrenzte Requests",
      "100 GB Speicher",
      "Alle Pro Features",
      "Evolution Tracking",
      "Team Management",
      "Dedicated Support",
      "Custom Integrationen",
    ],
    cta: "Kontaktieren",
    highlighted: false,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-lg">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="font-bold text-xl">Knowwhere</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-muted-foreground hover:text-foreground transition-colors">
                Features
              </a>
              <a href="#pricing" className="text-muted-foreground hover:text-foreground transition-colors">
                Pricing
              </a>
              <a href="#faq" className="text-muted-foreground hover:text-foreground transition-colors">
                FAQ
              </a>
            </div>
            <div className="flex items-center gap-4">
              <Link href="/login">
                <Button variant="ghost">Anmelden</Button>
              </Link>
              <Link href="/register">
                <Button>Registrieren</Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-20 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f08_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f08_1px,transparent_1px)] bg-[size:32px_32px]" />
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-primary/5 rounded-full blur-3xl" />
        
        <div className="container mx-auto px-4 relative">
          <div className="max-w-4xl mx-auto text-center">
            <Badge variant="secondary" className="mb-6">
              <Sparkles className="w-3 h-3 mr-1" />
              MCP-powered Memory System
            </Badge>
            
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
              Dein persönliches{" "}
              <span className="bg-gradient-to-r from-primary via-primary/80 to-primary bg-clip-text text-transparent">
                AI-Gedächtnis
              </span>
          </h1>
            
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Speichere Wissen, Präferenzen und Erkenntnisse. Lass deine AI-Assistenten sich an alles erinnern, was wichtig ist.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link href="/register">
                <Button size="lg" className="gap-2 w-full sm:w-auto">
                  Kostenlos starten
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link href="#features">
                <Button size="lg" variant="outline" className="w-full sm:w-auto">
                  Mehr erfahren
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Memory Types Section */}
      <section className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">5 Memory-Typen</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Inspiriert von kognitiver Wissenschaft - strukturiere dein Wissen nach bewährten Prinzipien.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            {memoryTypes.map((type) => (
              <Card key={type.name} className="relative overflow-hidden group hover:shadow-lg transition-all">
                <CardHeader className="pb-2">
                  <div className={`w-10 h-10 rounded-lg ${type.bg} flex items-center justify-center mb-2`}>
                    <type.icon className={`w-5 h-5 ${type.color}`} />
                  </div>
                  <CardTitle className="text-lg">{type.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground mb-2">{type.description}</p>
                  <p className="text-xs italic text-muted-foreground/70">{type.example}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Alles was du brauchst</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Leistungsstarke Features für effektives Wissensmanagement.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature) => (
              <Card key={feature.title} className="border-border/50 hover:border-primary/50 transition-colors">
                <CardHeader>
                  <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <feature.icon className="w-6 h-6 text-primary" />
                  </div>
                  <CardTitle>{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it Works Section */}
      <section className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">So funktioniert&apos;s</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              In drei einfachen Schritten zu deinem persönlichen Wissens-System.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            {[
              {
                step: "01",
                title: "Verbinden",
                description: "Integriere Knowwhere mit deinem AI-Assistenten über das MCP Protocol oder nutze die API.",
              },
              {
                step: "02",
                title: "Speichern",
                description: "Memories werden automatisch aus Gesprächen extrahiert oder manuell hinzugefügt.",
              },
              {
                step: "03",
                title: "Erinnern",
                description: "Dein AI-Assistent hat Zugriff auf alle relevanten Informationen - immer im Kontext.",
              },
            ].map((item, index) => (
              <div key={item.step} className="relative">
                <div className="text-6xl font-bold text-primary/10 mb-4">{item.step}</div>
                <h3 className="text-xl font-semibold mb-2">{item.title}</h3>
                <p className="text-muted-foreground">{item.description}</p>
                {index < 2 && (
                  <ArrowRight className="hidden md:block absolute top-8 -right-4 w-8 h-8 text-muted-foreground/30" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Einfache Preise</h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Wähle den Plan, der zu dir passt. Jederzeit upgraden oder downgraden.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {pricingPlans.map((plan) => (
              <Card
                key={plan.name}
                className={`relative ${
                  plan.highlighted
                    ? "border-primary shadow-lg scale-105"
                    : "border-border/50"
                }`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <Badge className="bg-primary">Beliebt</Badge>
                  </div>
                )}
                <CardHeader>
                  <CardTitle>{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                  <div className="mt-4">
                    <span className="text-4xl font-bold">{plan.price}</span>
                    {plan.period && (
                      <span className="text-muted-foreground">{plan.period}</span>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {plan.features.map((feature) => (
                      <li key={feature} className="flex items-center gap-2">
                        <Check className="w-4 h-4 text-primary" />
                        <span className="text-sm">{feature}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  <Link href="/register" className="w-full">
                    <Button
                      className="w-full"
                      variant={plan.highlighted ? "default" : "outline"}
                    >
                      {plan.cta}
                    </Button>
                  </Link>
                </CardFooter>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="py-20 bg-muted/30">
        <div className="container mx-auto px-4">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">Häufige Fragen</h2>
          </div>
          
          <div className="max-w-3xl mx-auto space-y-4">
            {[
              {
                q: "Was ist das Model Context Protocol (MCP)?",
                a: "MCP ist ein offener Standard von Anthropic, der AI-Assistenten erlaubt, mit externen Datenquellen und Tools zu interagieren. Knowwhere nutzt MCP, um Memories direkt in deinen AI-Workflow zu integrieren.",
              },
              {
                q: "Wie sicher sind meine Daten?",
                a: "Alle Daten werden verschlüsselt gespeichert. Du hast volle Kontrolle über deine Memories mit GDPR-konformen Export- und Löschfunktionen. Wir verkaufen oder teilen deine Daten niemals mit Dritten.",
              },
              {
                q: "Kann ich Knowwhere mit jedem AI-Assistenten nutzen?",
                a: "Ja! Neben der MCP-Integration bieten wir eine REST API und API Keys für die Integration mit jedem System. Claude, ChatGPT, lokale LLMs - alles funktioniert.",
              },
              {
                q: "Was passiert, wenn ich mein Abo kündige?",
                a: "Deine Daten bleiben 30 Tage erhalten. Du kannst jederzeit alles exportieren. Downgrade auf Free ist immer möglich, wobei ältere Memories archiviert werden.",
              },
            ].map((faq) => (
              <Card key={faq.q} className="border-border/50">
                <CardHeader>
                  <CardTitle className="text-lg">{faq.q}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{faq.a}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto text-center">
            <h2 className="text-3xl font-bold mb-4">
              Bereit, alles zu erinnern?
            </h2>
            <p className="text-muted-foreground mb-8">
              Starte kostenlos und entdecke, wie Knowwhere deine AI-Interaktionen revolutioniert.
            </p>
            <Link href="/register">
              <Button size="lg" className="gap-2">
                Jetzt kostenlos starten
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/40 py-12">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                  <Brain className="w-5 h-5 text-primary-foreground" />
                </div>
                <span className="font-bold text-xl">Knowwhere</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Dein persönliches AI-Gedächtnis für dauerhaftes Wissen.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Produkt</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#features" className="hover:text-foreground">Features</a></li>
                <li><a href="#pricing" className="hover:text-foreground">Pricing</a></li>
                <li><a href="#" className="hover:text-foreground">API Docs</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Unternehmen</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground">Über uns</a></li>
                <li><a href="#" className="hover:text-foreground">Blog</a></li>
                <li><a href="#" className="hover:text-foreground">Kontakt</a></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="#" className="hover:text-foreground">Datenschutz</a></li>
                <li><a href="#" className="hover:text-foreground">AGB</a></li>
                <li><a href="#" className="hover:text-foreground">Impressum</a></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-border/40 mt-12 pt-8 text-center text-sm text-muted-foreground">
            <p>© 2026 Knowwhere. Alle Rechte vorbehalten.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
