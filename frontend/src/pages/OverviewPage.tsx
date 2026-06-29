import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Clock, Cpu, Database, Gauge, Server } from "lucide-react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDashboardMetrics } from "@/api/metrics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { compactNumber, percentage, timeAgo } from "@/utils/format";

function RecentEvents() {
  const { data: events, isLoading, isError } = useQuery({
    queryKey: ["recent-events"],
    queryFn: () => import("@/api/events").then((m) => m.listEvents({ limit: 10 })),
    refetchInterval: 10_000,
  });

  if (isLoading) return <Skeleton className="h-48" />;
  if (isError) return null;

  return (
    <Card>
      <CardHeader><CardTitle>Recent Events</CardTitle></CardHeader>
      <CardContent>
        {events && events.length > 0 ? (
          <div className="space-y-2">
            {events.map((event) => (
              <div key={event.id} className="flex items-start gap-3 text-sm">
                <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                <div className="min-w-0 flex-1">
                  <span className="font-medium">{event.event_type}</span>
                  <span className="ml-2 text-muted-foreground">{event.message}</span>
                  <div className="text-xs text-muted-foreground">{timeAgo(event.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No recent events.</div>
        )}
      </CardContent>
    </Card>
  );
}

export function OverviewPage() {
  const metrics = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
    refetchInterval: 10_000
  });

  if (metrics.isLoading) {
    return <Skeleton className="h-[620px]" />;
  }

  if (metrics.isError) {
    return <ErrorState message={metrics.error.message} onRetry={() => void metrics.refetch()} />;
  }

  const data = metrics.data;
  if (!data) {
    return <Skeleton className="h-[620px]" />;
  }
  const total = data.pending + data.scheduled + data.running + data.completed + data.failed + data.dead_letter;
  const successRate = total ? data.completed / total : 0;
  const queueData = [
    { name: "Pending", value: data.pending },
    { name: "Scheduled", value: data.scheduled },
    { name: "Running", value: data.running },
    { name: "Completed", value: data.completed },
    { name: "Failed", value: data.failed },
    { name: "DLQ", value: data.dead_letter }
  ];
  const statCards = [
    ["Cluster Health", data.dead_letter > 0 ? "Degraded" : "Healthy", Gauge],
    ["Pending Jobs", compactNumber(data.pending), Clock],
    ["Running Jobs", compactNumber(data.running), Activity],
    ["Completed Jobs", compactNumber(data.completed), CheckCircle2],
    ["Failed Jobs", compactNumber(data.failed + data.dead_letter), AlertTriangle],
    ["Throughput", `${data.throughput_per_minute}/min`, Database],
    ["Retries", percentage(data.retry_rate), Server],
    ["Worker Count", compactNumber(data.active_workers), Cpu]
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map(([label, value, Icon]) => (
          <Card key={label as string}>
            <CardContent className="flex items-center justify-between">
              <div>
                <div className="text-xs text-muted-foreground">{label as string}</div>
                <div className="mt-2 text-2xl font-semibold">{value as string}</div>
              </div>
              <Icon className="h-5 w-5 text-muted-foreground" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Queue Throughput</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer>
              <BarChart data={queueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Bar dataKey="value" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Task Success Rate</CardTitle></CardHeader>
          <CardContent className="h-80">
            <ResponsiveContainer>
              <AreaChart data={[{ name: "Current", success: Math.round(successRate * 100), retry: Math.round(data.retry_rate * 100) }]}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Area type="monotone" dataKey="success" stroke="hsl(var(--success))" fill="hsl(var(--success))" fillOpacity={0.2} />
                <Area type="monotone" dataKey="retry" stroke="hsl(var(--warning))" fill="hsl(var(--warning))" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
      <RecentEvents />
    </div>
  );
}
