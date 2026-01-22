import { Metadata } from "next";
import { HealthStatusCard } from "@/components/HealthStatusCard";

export const metadata: Metadata = {
  title: "System Diagnostics | KnowWhere",
  description: "Monitor system health and service status.",
};

export default function DiagnosticsPage() {
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">System Diagnostics</h1>
        <p className="text-muted-foreground">
          Monitor the health and performance of KnowWhere Memory services.
        </p>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <HealthStatusCard 
          service="postgresql"
          status="UP"
          latencyMs={1.2}
        />
        <HealthStatusCard 
          service="redis"
          status="UP"
          latencyMs={0.5}
        />
        <HealthStatusCard 
          service="vector_search"
          status="UP"
          latencyMs={12.4}
        />
        <HealthStatusCard 
          service="llm_provider"
          status="UP"
          latencyMs={245.8}
        />
      </div>
    </div>
  );
}