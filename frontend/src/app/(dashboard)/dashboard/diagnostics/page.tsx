"use client";

import { useEffect, useState } from "react";
import { HealthStatusCard } from "@/components/HealthStatusCard";
import { api, HealthCheckResult } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { RefreshCcw, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

export default function DiagnosticsPage() {
  const [healthData, setHealthData] = useState<HealthCheckResult[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchHealth = async (silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const data = await api.getFullHealth();
      setHealthData(data);
      setLastUpdated(new Date());
    } catch (err) {
      console.error("Failed to fetch health data:", err);
      setError("Failed to connect to the health diagnostics service.");
      toast.error("Health check failed");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      fetchHealth(true);
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Diagnostics</h1>
          <p className="text-muted-foreground">
            Monitor the health and performance of KnowWhere Memory services.
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => fetchHealth()}
            disabled={isLoading}
          >
            <RefreshCcw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>
      
      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 flex items-center gap-3 text-destructive">
          <AlertTriangle className="h-5 w-5" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading && !healthData ? (
          // Skeleton loading
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 rounded-lg border bg-card animate-pulse" />
          ))
        ) : healthData ? (
          healthData.map((check) => (
            <HealthStatusCard 
              key={check.service}
              service={check.service}
              status={check.status}
              latencyMs={check.latency_ms}
              message={check.message}
            />
          ))
        ) : null}
      </div>
    </div>
  );
}
