import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Cpu, MemoryStick, Server } from "lucide-react";
import { listWorkers } from "@/api/workers";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/utils/format";

export function WorkersPage() {
  const [activeOnly, setActiveOnly] = useState(false);
  const workers = useQuery({
    queryKey: ["workers", activeOnly],
    queryFn: () => listWorkers(activeOnly),
    refetchInterval: 10_000
  });
  const averageCpu = useMemo(
    () => (workers.data?.length ? workers.data.reduce((sum, worker) => sum + worker.cpu_usage, 0) / workers.data.length : 0),
    [workers.data]
  );

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={activeOnly} onChange={(event) => setActiveOnly(event.target.checked)} />
        Active workers only
      </label>
      <div className="grid gap-4 md:grid-cols-3">
        <Card><CardContent><div className="text-xs text-muted-foreground">Workers</div><div className="mt-2 text-2xl font-semibold">{workers.data?.length ?? 0}</div></CardContent></Card>
        <Card><CardContent><div className="text-xs text-muted-foreground">Average CPU</div><div className="mt-2 text-2xl font-semibold">{Math.round(averageCpu)}%</div></CardContent></Card>
        <Card><CardContent><div className="text-xs text-muted-foreground">Utilization</div><div className="mt-2 text-2xl font-semibold">Live</div></CardContent></Card>
      </div>
      {workers.isLoading ? <Skeleton className="h-96" /> : null}
      {workers.isError ? <ErrorState message={workers.error.message} onRetry={() => void workers.refetch()} /> : null}
      {workers.data?.length === 0 ? <EmptyState title="No workers registered" body="Worker cards will appear after heartbeat events reach the backend." /> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {workers.data?.map((worker) => (
          <Card key={worker.id}>
            <CardContent className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Server className="h-4 w-4" />
                    {worker.hostname}
                  </div>
                  <div className="mt-1 font-mono text-xs text-muted-foreground">{worker.id}</div>
                </div>
                <Badge>{worker.status}</Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Metric icon={Cpu} label="CPU" value={`${worker.cpu_usage}%`} />
                <Metric icon={MemoryStick} label="Memory" value={`${worker.memory_usage}%`} />
                <Metric icon={Activity} label="Active jobs" value={String(worker.active_jobs)} />
              </div>
              <div className="text-xs text-muted-foreground">Last heartbeat {timeAgo(worker.last_heartbeat)}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Cpu; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="h-3.5 w-3.5" />{label}</div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
    </div>
  );
}
