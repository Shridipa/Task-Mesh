import { useQuery } from "@tanstack/react-query";
import { listJobs } from "@/api/jobs";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { JobTable } from "@/features/jobs/JobTable";
import { JobDetailDrawer } from "@/features/jobs/JobDetailDrawer";
import { useUiStore } from "@/store/ui-store";

export function DeadLetterPage() {
  const selectedJobId = useUiStore((state) => state.selectedJobId);
  const setSelectedJobId = useUiStore((state) => state.setSelectedJobId);
  const jobs = useQuery({
    queryKey: ["jobs", "dead_letter"],
    queryFn: () => listJobs({ status: "dead_letter", limit: 250 }),
    refetchInterval: 10_000
  });

  return (
    <div className="space-y-4">
      {jobs.isError ? <ErrorState message={jobs.error.message} onRetry={() => void jobs.refetch()} /> : null}
      {jobs.data?.length === 0 ? <EmptyState title="Dead letter queue is empty" body="Jobs that exceed retry limits will appear here for replay, deletion, or inspection." /> : null}
      {jobs.data && jobs.data.length > 0 ? <JobTable jobs={jobs.data} onInspect={setSelectedJobId} /> : null}
      <JobDetailDrawer jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
    </div>
  );
}
