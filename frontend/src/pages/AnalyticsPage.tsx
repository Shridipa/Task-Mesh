import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAnalyticsTimeSeries } from "@/api/analytics";
import { getMetricsSummary } from "@/api/metrics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";

export function AnalyticsPage() {
  const metrics = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: getMetricsSummary,
    refetchInterval: 15_000,
  });

  const timeSeries = useQuery({
    queryKey: ["analytics-time-series"],
    queryFn: () => getAnalyticsTimeSeries(24),
    refetchInterval: 30_000,
  });

  if (metrics.isLoading || timeSeries.isLoading) {
    return <Skeleton className="h-[600px]" />;
  }

  if (metrics.isError || timeSeries.isError) {
    return <ErrorState message={(metrics.error || timeSeries.error).message} onRetry={() => { metrics.refetch(); timeSeries.refetch(); }} />;
  }

  const m = metrics.data;
  const series = timeSeries.data ?? [];

  const distribution = m && m.pending !== undefined
    ? [
        { name: "Pending", jobs: m.pending },
        { name: "Running", jobs: m.running },
        { name: "Completed", jobs: m.completed },
        { name: "Failed", jobs: m.failed + m.dead_letter },
      ]
    : [];

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Job Distribution</CardTitle></CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer>
            <BarChart data={distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Bar dataKey="jobs" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Job Throughput (last 24h)</CardTitle></CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer>
            <AreaChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="hour" stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Legend />
              <Area type="monotone" dataKey="completed" stroke="hsl(var(--success))" fill="hsl(var(--success))" fillOpacity={0.2} />
              <Area type="monotone" dataKey="failed" stroke="hsl(var(--destructive))" fill="hsl(var(--destructive))" fillOpacity={0.2} />
              <Area type="monotone" dataKey="running" stroke="hsl(var(--warning))" fill="hsl(var(--warning))" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="xl:col-span-2">
        <CardHeader><CardTitle>Queue Depth Over Time</CardTitle></CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer>
            <AreaChart data={series}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="hour" stroke="hsl(var(--muted-foreground))" />
              <YAxis stroke="hsl(var(--muted-foreground))" />
              <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Legend />
              <Area type="monotone" dataKey="pending" stroke="hsl(var(--primary))" fill="hsl(var(--primary))" fillOpacity={0.2} />
              <Area type="monotone" dataKey="running" stroke="hsl(var(--warning))" fill="hsl(var(--warning))" fillOpacity={0.2} />
              <Area type="monotone" dataKey="dead_letter" stroke="hsl(var(--destructive))" fill="hsl(var(--destructive))" fillOpacity={0.2} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}