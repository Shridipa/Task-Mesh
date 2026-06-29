import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Drawer } from "@/components/ui/drawer";
import { ErrorState } from "@/components/ui/error-state";
import { JsonViewer } from "@/components/ui/json-viewer";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getJob, cancelJob, duplicateJob, replayJob } from "@/api/jobs";
import { formatDateTime } from "@/utils/format";

export function JobDetailDrawer({
  jobId,
  onClose
}: {
  jobId: string | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: Boolean(jobId)
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelJob(jobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const duplicateMutation = useMutation({
    mutationFn: () => duplicateJob(jobId!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const replayMutation = useMutation({
    mutationFn: () => replayJob(jobId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const job = query.data;
  const canCancel = job && (job.status === "pending" || job.status === "scheduled");
  const canReplay = job && job.status === "dead_letter";

  return (
    <Drawer open={Boolean(jobId)} title="Job details" onClose={onClose}>
      {query.isLoading ? <Skeleton className="h-96" /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={query.data.status} />
            <span className="font-mono text-xs text-muted-foreground">{query.data.id}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["Type", query.data.job_type],
              ["Tenant", query.data.tenant_id],
              ["Worker", query.data.worker_id ?? "Unassigned"],
              ["Priority", String(query.data.priority)],
              ["Created", formatDateTime(query.data.created_at)],
              ["Started", formatDateTime(query.data.started_at)],
              ["Completed", formatDateTime(query.data.completed_at)],
              ["Retries", `${query.data.retry_count}/${query.data.max_retries}`]
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border bg-card p-3">
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="mt-1 truncate text-sm">{value}</div>
              </div>
            ))}
          </div>
          {query.data.failure_reason ? (
            <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
              {query.data.failure_reason}
            </div>
          ) : null}
          <section>
            <h3 className="mb-2 text-sm font-semibold">Payload</h3>
            <JsonViewer value={query.data.payload} />
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold">Execution timeline</h3>
            <ol className="space-y-2">
              {query.data.history.map((event) => (
                <li key={event} className="rounded-xl border border-border bg-card p-3 font-mono text-xs">
                  {event}
                </li>
              ))}
            </ol>
          </section>
          <section className="flex flex-wrap gap-2">
            {canCancel ? (
              <Button variant="danger" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
                Cancel job
              </Button>
            ) : null}
            {canReplay ? (
              <Button onClick={() => replayMutation.mutate()} disabled={replayMutation.isPending}>
                Replay
              </Button>
            ) : null}
            <Button variant="secondary" onClick={() => duplicateMutation.mutate()} disabled={duplicateMutation.isPending}>
              Duplicate
            </Button>
          </section>
        </div>
      ) : null}
    </Drawer>
  );
}
