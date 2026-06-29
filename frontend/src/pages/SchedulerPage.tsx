import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, SquarePen, RotateCcw } from "lucide-react";
import { getSchedulerStatus, pauseScheduler, resumeScheduler, runSchedulerNow } from "@/api/scheduler";
import { listJobs } from "@/api/jobs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { StatusBadge } from "@/components/ui/badge";
import { formatDateTime } from "@/utils/format";

export function SchedulerPage() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["scheduler-status"],
    queryFn: getSchedulerStatus,
    refetchInterval: 10_000,
  });
  const jobs = useQuery({
    queryKey: ["jobs", "scheduled"],
    queryFn: () => listJobs({ status: "scheduled", limit: 200 }),
    refetchInterval: 15_000,
  });

  const pauseMutation = useMutation({
    mutationFn: pauseScheduler,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduler-status"] }),
  });
  const resumeMutation = useMutation({
    mutationFn: resumeScheduler,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduler-status"] }),
  });
  const runNowMutation = useMutation({
    mutationFn: runSchedulerNow,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs", "scheduled"] }),
  });

  const isPaused = status.data?.paused ?? false;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Scheduler Controls</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          {isPaused ? (
            <Button onClick={() => resumeMutation.mutate()} disabled={resumeMutation.isPending}>
              <Play className="h-4 w-4" />Resume
            </Button>
          ) : (
            <Button variant="secondary" onClick={() => pauseMutation.mutate()} disabled={pauseMutation.isPending}>
              <Pause className="h-4 w-4" />Pause
            </Button>
          )}
          <Button variant="secondary" onClick={() => runNowMutation.mutate()} disabled={runNowMutation.isPending}>
            <RotateCcw className="h-4 w-4" />Run now
          </Button>
          <span className="text-sm text-muted-foreground">
            Status: <span className="font-medium">{status.data?.status ?? "loading..."}</span>
          </span>
        </CardContent>
      </Card>
      {jobs.isError ? <ErrorState message={jobs.error.message} onRetry={() => void jobs.refetch()} /> : null}
      <Card>
        <CardHeader><CardTitle>Scheduled Jobs</CardTitle></CardHeader>
        <CardContent>
          {jobs.data?.length === 0 ? <EmptyState title="No scheduled jobs" body="Future tasks appear here when jobs have an execute_at timestamp in the future." /> : null}
          <div className="space-y-2">
            {jobs.data?.map((job) => (
              <div key={job.id} className="flex flex-col gap-2 rounded-xl border border-border p-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="text-sm font-medium">{job.job_type}</div>
                  <div className="font-mono text-xs text-muted-foreground">{job.id}</div>
                </div>
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <StatusBadge status={job.status} />
                  <span>{formatDateTime(job.execute_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}