import { useQuery } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { ArrowRight, CheckCircle2, Clock, Cpu } from "lucide-react";
import { getDashboardMetrics } from "@/api/metrics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TextDemo } from "@/features/text/TextDemo";

const FLOW = [
  { title: "Submit a task", detail: "The visitor sends text to the API." },
  { title: "Task enters the queue", detail: "The job is stored with status pending." },
  { title: "A worker picks it up", detail: "A background worker leases the job." },
  { title: "The worker executes it", detail: "The handler processes the text." },
  { title: "The result is saved", detail: "The output is stored and shown here." }
];

export function OverviewPage() {
  const metrics = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
    refetchInterval: 5_000
  });

  const waiting = (metrics.data?.pending ?? 0) + (metrics.data?.scheduled ?? 0);
  const loading = metrics.isLoading;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-3 p-6">
          <h2 className="text-2xl font-semibold">Background tasks, processed by real workers</h2>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            TaskMesh is a background task processing platform. Instead of making a user wait while work is performed,
            it places the work in a queue so that background workers can execute it independently.
          </p>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            A worker is a background process that picks tasks from the queue and performs the actual work. The text
            task below is executed by a real worker in this deployment, and the result is stored in the database.
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Tasks waiting" hint="queued for a worker" value={loading ? null : waiting} icon={Clock} />
        <StatCard
          label="Tasks running"
          hint="being processed right now"
          value={loading ? null : metrics.data?.running ?? 0}
          icon={Cpu}
        />
        <StatCard
          label="Tasks completed"
          hint="finished successfully"
          value={loading ? null : metrics.data?.completed ?? 0}
          icon={CheckCircle2}
        />
      </div>
      {metrics.isError ? (
        <p className="text-sm text-destructive" role="alert">
          Live statistics are unavailable: {metrics.error.message}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>What happens when a task is submitted?</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-3 md:grid-cols-5">
            {FLOW.map((step, index) => (
              <li key={step.title} className="rounded-xl border border-border bg-muted/40 p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/15 text-[11px] font-semibold text-primary">
                    {index + 1}
                  </span>
                  {index < FLOW.length - 1 ? <ArrowRight className="ml-auto h-3.5 w-3.5" /> : null}
                </div>
                <div className="mt-2 text-sm font-medium">{step.title}</div>
                <p className="mt-1 text-xs text-muted-foreground">{step.detail}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <TextDemo />

      <p className="text-xs text-muted-foreground">
        Detailed monitoring is available in the sidebar: Jobs, Workers, Scheduler, Dead Letter Queue, Analytics, Events
        and Logs.
      </p>
    </div>
  );
}

function StatCard({
  label,
  hint,
  value,
  icon: Icon
}: {
  label: string;
  hint: string;
  value: number | null;
  icon: ComponentType<{ className?: string }>;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between">
        <div>
          <div className="text-xs text-muted-foreground">{label}</div>
          <div className="mt-2 text-2xl font-semibold">
            {value === null ? <Skeleton className="h-7 w-12" /> : value.toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
        </div>
        <Icon className="h-5 w-5 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}
