import { Metadata } from "next";

export const metadata: Metadata = {
  title: "System Diagnostics | KnowWhere",
  description: "Monitor system health and service status.",
};

export default function DiagnosticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">System Diagnostics</h1>
        <p className="text-muted-foreground">
          Monitor the health and performance of KnowWhere Memory services.
        </p>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Placeholder for health cards */}
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between space-y-0 pb-2">
            <h3 className="text-sm font-medium">System Status</h3>
          </div>
          <div className="text-2xl font-bold text-muted-foreground italic">Initializing...</div>
        </div>
      </div>
    </div>
  );
}
