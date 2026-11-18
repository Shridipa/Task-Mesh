import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock3, Layers3, Play, RefreshCw, Server } from "lucide-react";
import { Link } from "react-router";
import { getDashboardMetrics } from "@/api/metrics";
import { listJobs } from "@/api/jobs";
import { listEvents } from "@/api/events";
import { generateDemoJobs, generateDemoWorkers } from "@/api/demo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/utils/format";
import type { Job, JobStatus } from "@/types/taskmesh";

function statusLabel(status: JobStatus): string {
  return status.replace("_", " ");
}

function statusClass(status: JobStatus): string {
  if (status === "completed") return "bg-emerald-500/15 text-emerald-400";
  if (status === "failed" || status === "dead_letter") return "bg-red-500/15 text-red-400";
  if (status === "running") return "bg-sky-500/15 text-sky-400";
  if (status === "pending" || status === "scheduled") return "bg-amber-500/15 text-amber-400";
  return "bg-muted text-muted-foreground";
}

function JobRow({ job }: { job: Job }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border py-3 last:border-0">
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{job.job_type}</div>
        <div className="mt-1 font-mono text-xs text-muted-foreground">{job.id.slice(0, 8)} · {timeAgo(job.created_at)}</div>
      </div>
      <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusClass(job.status)}`}>
        {statusLabel(job.status)}
      </span>
    </div>
  );
}

export function OverviewPage() {
  const queryClient = useQueryClient();
  const metrics = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
    refetchInterval: 10_000
  });
  const jobs = useQuery({
    queryKey: ["jobs", "overview"],
    queryFn: () => listJobs({ limit: 5 }),
    refetchInterval: 10_000
  });
  const events = useQuery({
    queryKey: ["recent-events"],
    queryFn: () => listEvents({ limit: 5 }),
    refetchInterval: 10_000
  });
  const sampleData = useMutation({
    mutationFn: async () => {
      await generateDemoWorkers(3);
      await generateDemoJobs(15);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["recent-events"] }),
        queryClient.invalidateQueries({ queryKey: ["workers"] })
      ]);
    }
  });

  if (metrics.isLoading) return <Skeleton className="h-[620px]" />;
  if (metrics.isError) return <ErrorState message={metrics.error.message} onRetry={() => void metrics.refetch()} />;

  const data = metrics.data;
  if (!data) return <Skeleton className="h-[620px]" />;

  const waiting = data.pending + data.scheduled;
  const attention = data.failed + data.dead_letter;
  const total = waiting + data.running + data.completed + attention;
  const cards = [
    { label: "Waiting to start", value: waiting, help: "Tasks in the queue", icon: Clock3, tone: "text-amber-400" },
    { label: "Being processed", value: data.running, help: "Tasks workers are handling", icon: Activity, tone: "text-sky-400" },
    { label: "Successfully finished", value: data.completed, help: "Tasks completed", icon: CheckCircle2, tone: "text-emerald-400" },
    { label: "Need attention", value: attention, help: "Failed or moved to recovery", icon: AlertTriangle, tone: attention ? "text-red-400" : "text-muted-foreground" }
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section className="flex flex-col justify-between gap-4 rounded-2xl border border-border bg-card p-5 sm:flex-row sm:items-center sm:p-7">
        <div className="max-w-2xl">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
            <Layers3 className="h-4 w-4" /> TaskMesh · Work queue
          </div>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">See all your background work in one place.</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            TaskMesh accepts tasks, places them in a queue, assigns them to available workers and tracks them until they finish—or need another attempt.
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2">
          <Button onClick={() => sampleData.mutate()} disabled={sampleData.isPending}>
            <Play className="h-4 w-4" />
            {sampleData.isPending ? "Preparing sample..." : "Show me a sample"}
          </Button>
          <Button variant="secondary" onClick={() => {
            void queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
            void queryClient.invalidateQueries({ queryKey: ["jobs"] });
            void queryClient.invalidateQueries({ queryKey: ["recent-events"] });
          }}>
            <RefreshCw className="h-4 w-4" /> Refresh information
          </Button>
        </div>
      </section>

      {sampleData.isError ? (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          Could not create sample activity: {sampleData.error.message}
        </div>
      ) : null}

      <section>
        <div className="mb-3">
          <h2 className="text-base font-semibold">What is happening right now?</h2>
          <p className="mt-1 text-sm text-muted-foreground">These numbers come from the TaskMesh job queue and update automatically.</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ label, value, help, icon: Icon, tone }) => (
            <Card key={label}>
              <CardContent className="flex items-start justify-between gap-3 p-5">
                <div>
                  <div className="text-sm text-muted-foreground">{label}</div>
                  <div className="mt-2 text-3xl font-semibold tabular-nums">{value.toLocaleString()}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{help}</div>
                </div>
                <Icon className={`h-5 w-5 ${tone}`} />
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <Card>
          <CardHeader>
            <CardTitle>How a task moves through TaskMesh</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">A simple view of the work lifecycle.</p>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-4">
              {[
                { step: "1", title: "Submitted", detail: "An app sends work to TaskMesh.", count: total, color: "text-primary" },
                { step: "2", title: "Waiting", detail: "The task waits for an available worker.", count: waiting, color: "text-amber-400" },
                { step: "3", title: "In progress", detail: "A worker picks it up and processes it.", count: data.running, color: "text-sky-400" },
                { step: "4", title: "Finished", detail: "The task completes or is flagged for attention.", count: data.completed + attention, color: "text-emerald-400" }
              ].map((item) => (
                <div key={item.step} className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className={`text-xs font-semibold uppercase tracking-wide ${item.color}`}>Step {item.step}</div>
                  <div className="mt-2 text-sm font-semibold">{item.title}</div>
                  <div className="mt-1 min-h-10 text-xs leading-5 text-muted-foreground">{item.detail}</div>
                  <div className="mt-3 text-2xl font-semibold tabular-nums">{item.count.toLocaleString()}</div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-5 text-muted-foreground">
              If a task fails, TaskMesh can retry it. Tasks that exceed their retry limit are moved to the dead-letter queue so they can be reviewed.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workers available</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">Workers are the processes that pick up and handle tasks.</p>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-primary/10 p-3"><Server className="h-6 w-6 text-primary" /></div>
              <div>
                <div className="text-3xl font-semibold tabular-nums">{data.active_workers}</div>
                <div className="text-xs text-muted-foreground">Active workers reported</div>
              </div>
            </div>
            <div className="mt-5 rounded-xl border border-border p-3">
              <div className="text-sm font-medium">{attention === 0 ? "No failed tasks are currently recorded." : `${attention} task(s) need attention.`}</div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">
                {attention === 0 ? "If a task fails later, it will appear here and in the task list." : "Open the task list to inspect failures and retry or review eligible tasks."}
              </p>
              <Link to="/dead-letter" className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                Review recovery queue <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div><CardTitle>Latest tasks</CardTitle><p className="mt-1 text-xs text-muted-foreground">The most recently submitted work.</p></div>
            <Link to="/jobs" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">All tasks <ArrowRight className="h-3.5 w-3.5" /></Link>
          </CardHeader>
          <CardContent>
            {jobs.isLoading ? <Skeleton className="h-40" /> : null}
            {jobs.isError ? <p className="text-sm text-muted-foreground">Task list could not be loaded.</p> : null}
            {jobs.data?.length === 0 ? <p className="py-5 text-sm text-muted-foreground">No tasks yet. Select “Show me a sample” to see how the system works.</p> : null}
            {jobs.data?.map((job) => <JobRow key={job.id} job={job} />)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">A short history of what the system has been doing.</p>
          </CardHeader>
          <CardContent>
            {events.isLoading ? <Skeleton className="h-40" /> : null}
            {events.isError ? <p className="text-sm text-muted-foreground">Recent activity could not be loaded.</p> : null}
            {events.data?.length === 0 ? <p className="py-5 text-sm text-muted-foreground">Activity will appear here as tasks move through the system.</p> : null}
            <div className="space-y-3">
              {events.data?.map((event) => (
                <div key={event.id} className="flex gap-3 text-sm">
                  <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
                  <div className="min-w-0">
                    <div className="font-medium">{event.event_type.replaceAll("_", " ")}</div>
                    <p className="mt-0.5 text-xs leading-5 text-muted-foreground">{event.message}</p>
                    <div className="mt-1 text-xs text-muted-foreground">{timeAgo(event.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
