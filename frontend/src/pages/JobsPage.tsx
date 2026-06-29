import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { listJobs } from "@/api/jobs";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { JobDetailDrawer } from "@/features/jobs/JobDetailDrawer";
import { CreateJobDrawer } from "@/features/jobs/CreateJobDrawer";
import { JobTable } from "@/features/jobs/JobTable";
import { useUiStore } from "@/store/ui-store";

const statuses = ["", "pending", "scheduled", "running", "completed", "failed", "dead_letter", "canceled"];

export function JobsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const selectedJobId = useUiStore((state) => state.selectedJobId);
  const setSelectedJobId = useUiStore((state) => state.setSelectedJobId);
  const jobs = useQuery({
    queryKey: ["jobs", status],
    queryFn: () => listJobs({ status: status || undefined, limit: 250 }),
    refetchInterval: 10_000
  });
  const filteredJobs = useMemo(
    () =>
      (jobs.data ?? []).filter((job) => {
        const haystack = `${job.id} ${job.job_type} ${job.tenant_id} ${job.worker_id ?? ""}`.toLowerCase();
        return haystack.includes(search.toLowerCase());
      }),
    [jobs.data, search]
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />Create job
        </Button>
        <div className="relative max-w-xl flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            aria-label="Search jobs"
            className="h-9 w-full rounded-xl border border-border bg-card pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            placeholder="Search by job, tenant, type, or worker"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <select
          aria-label="Filter by status"
          className="h-9 rounded-xl border border-border bg-card px-3 text-sm capitalize outline-none focus:ring-2 focus:ring-primary"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          {statuses.map((item) => (
            <option key={item || "all"} value={item}>{item ? item.replace("_", " ") : "All statuses"}</option>
          ))}
        </select>
      </div>
      {jobs.isLoading ? <Skeleton className="h-96" /> : null}
      {jobs.isError ? <ErrorState message={jobs.error?.message ?? "Unknown error"} onRetry={() => void jobs.refetch()} /> : null}
      {jobs.data && filteredJobs.length === 0 ? (
        <EmptyState title="No jobs found" body="The backend returned no jobs for the current filters." />
      ) : null}
      {filteredJobs.length > 0 ? <JobTable jobs={filteredJobs} onInspect={setSelectedJobId} /> : null}
      <JobDetailDrawer jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
      <CreateJobDrawer open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}