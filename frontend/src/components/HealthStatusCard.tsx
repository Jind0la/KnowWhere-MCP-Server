"use client";

import { CheckCircle2, AlertCircle, XCircle, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type HealthStatus = "UP" | "DOWN" | "DEGRADED";

interface HealthStatusCardProps {
  service: string;
  status: HealthStatus;
  latencyMs: number;
  message?: string | null;
}

export function HealthStatusCard({
  service,
  status,
  latencyMs,
  message,
}: HealthStatusCardProps) {
  const getStatusConfig = (status: HealthStatus) => {
    switch (status) {
      case "UP":
        return {
          color: "text-green-500",
          bgColor: "bg-green-500/10",
          icon: CheckCircle2,
          label: "Operational",
          badgeVariant: "default" as const,
        };
      case "DEGRADED":
        return {
          color: "text-yellow-500",
          bgColor: "bg-yellow-500/10",
          icon: AlertCircle,
          label: "Degraded",
          badgeVariant: "outline" as const,
        };
      case "DOWN":
        return {
          color: "text-red-500",
          bgColor: "bg-red-500/10",
          icon: XCircle,
          label: "Outage",
          badgeVariant: "destructive" as const,
        };
    }
  };

  const config = getStatusConfig(status);
  const StatusIcon = config.icon;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium capitalize">
          {service.replace("_", " ")}
        </CardTitle>
        <StatusIcon className={cn("h-4 w-4", config.color)} />
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <Badge variant={config.badgeVariant} className="text-[10px]">
              {config.label}
            </Badge>
            {message && (
              <p className="text-[10px] text-destructive mt-1 max-w-[150px] truncate" title={message}>
                {message}
              </p>
            )}
          </div>
          <div className="flex flex-col items-end">
            <div className="text-2xl font-bold">{latencyMs.toFixed(1)}ms</div>
            <div className="flex items-center text-[10px] text-muted-foreground">
              <Clock className="mr-1 h-3 w-3" />
              Latency
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
