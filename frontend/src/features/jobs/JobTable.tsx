import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye, RefreshCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { deleteJob, replayJob } from "@/api/jobs";
import { useAuthStore } from "@/store/auth-store";
import type { Job } from "@/types/taskmesh";
import { formatDateTime } from "@/utils/format";

export function JobTable({ jobs, onInspect }: { jobs: Job[]; onInspect: (jobId: string) => void }) {
  const queryClient = useQueryClient();
  const role = useAuthStore((state) => state.role);
  const isAdmin = role === "admin";
  const replay = useMutation({
    mutationFn: replayJob,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });
  const remove = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-sm">
          <thead className="border-b border-border bg-muted/60 text-xs uppercase text-muted-foreground">
            <tr>
              {["Job ID", "Type", "Status", "Priority", "Tenant", "Created", "Started", "Completed", "Retries", "Worker", "Actions"].map((header) => (
                <th key={header} className="px-3 py-3 font-medium">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.map((job) => (
              <tr
                key={job.id}
                className="cursor-pointer bg-card/40 hover:bg-muted/40"
                onClick={() => onInspect(job.id)}
              >
                <td className="max-w-48 truncate px-3 py-3 font-mono text-xs">{job.id}</td>
                <td className="px-3 py-3">{job.job_type}</td>
                <td className="px-3 py-3"><StatusBadge status={job.status} /></td>
                <td className="px-3 py-3">{job.priority}</td>
                <td className="px-3 py-3">{job.tenant_id}</td>
                <td className="px-3 py-3">{formatDateTime(job.created_at)}</td>
                <td className="px-3 py-3">{formatDateTime(job.started_at)}</td>
                <td className="px-3 py-3">{formatDateTime(job.completed_at)}</td>
                <td className="px-3 py-3">{job.retry_count}/{job.max_retries}</td>
                <td className="px-3 py-3">{job.worker_id ?? "Unassigned"}</td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-1" onClick={(event) => event.stopPropagation()}>
                    <Button aria-label="Inspect job" variant="ghost" onClick={() => onInspect(job.id)}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    {isAdmin ? (
                      <Button
                        aria-label="Replay job"
                        variant="ghost"
                        disabled={job.status !== "dead_letter" || replay.isPending}
                        onClick={() => replay.mutate(job.id)}
                      >
                        <RefreshCcw className="h-4 w-4" />
                      </Button>
                    ) : null}
                    {isAdmin ? (
                      <Button
                        aria-label="Delete job"
                        variant="ghost"
                        disabled={remove.isPending}
                        onClick={() => remove.mutate(job.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
