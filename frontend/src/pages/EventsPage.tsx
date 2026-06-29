import { useQuery } from "@tanstack/react-query";
import { listEvents } from "@/api/events";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { timeAgo } from "@/utils/format";

const EVENT_COLORS: Record<string, string> = {
  JobCreated: "bg-blue-500",
  JobStarted: "bg-yellow-500",
  JobCompleted: "bg-green-500",
  JobFailed: "bg-red-500",
  JobDeadLettered: "bg-red-700",
  JobRetryScheduled: "bg-orange-500",
  JobCancelled: "bg-gray-500",
  JobReplayed: "bg-purple-500",
  JobLeased: "bg-cyan-500",
};

export function EventsPage() {
  const events = useQuery({
    queryKey: ["events"],
    queryFn: () => listEvents({ limit: 200 }),
    refetchInterval: 5_000,
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Events</CardTitle></CardHeader>
        <CardContent>
          {events.isLoading ? <Skeleton className="h-96" /> : null}
          {events.isError ? <ErrorState message={events.error.message} onRetry={() => void events.refetch()} /> : null}
          {events.data?.length === 0 ? <EmptyState title="No events yet" body="Events will appear here as jobs are created and processed." /> : null}
          {events.data ? (
            <div className="space-y-2">
              {events.data.map((event) => (
                <div key={event.id} className="flex items-start gap-3 rounded-lg border p-3 text-sm">
                  <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${EVENT_COLORS[event.event_type] ?? "bg-gray-400"}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge className="font-mono text-xs">{event.event_type}</Badge>
                      {event.job_id ? <span className="font-mono text-xs text-muted-foreground truncate">{event.job_id}</span> : null}
                    </div>
                    <div className="mt-1 text-muted-foreground">{event.message}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{timeAgo(event.created_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}