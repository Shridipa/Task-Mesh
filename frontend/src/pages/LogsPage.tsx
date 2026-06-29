import { useQuery } from "@tanstack/react-query";
import { Download, Pause, Play, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getLogs, type LogEntry } from "@/api/logs";

export function LogsPage() {
  const [search, setSearch] = useState("");
  const [paused, setPaused] = useState(false);
  const logs = useQuery({
    queryKey: ["logs", search],
    queryFn: () => getLogs(200, 0, undefined, search || undefined),
    refetchInterval: paused ? false : 3000,
    enabled: !paused,
  });

  const handleDownload = () => {
    if (!logs.data) return;
    const text = logs.data
      .map((log: LogEntry) => `[${log.timestamp}] [${log.level}] ${log.message}`)
      .join("\n");
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `taskmesh-logs-${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Live Logs</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setPaused(!paused)}>
            {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            {paused ? "Resume" : "Pause"}
          </Button>
          <div className="relative flex-1 min-w-[200px]">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search logs..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Button variant="secondary" onClick={handleDownload} disabled={!logs.data?.length}>
            <Download className="h-4 w-4" />Download
          </Button>
        </div>
        <div className="h-[600px] overflow-auto rounded-xl border border-border bg-black p-4 font-mono text-xs">
          {logs.isLoading ? (
            <p className="text-muted-foreground">Loading logs...</p>
          ) : logs.isError ? (
            <p className="text-destructive">Failed to load logs: {(logs.error as Error).message}</p>
          ) : logs.data && logs.data.length > 0 ? (
            <div className="space-y-1">
              {logs.data.map((log: LogEntry, idx: number) => (
                <div key={idx} className="flex gap-3">
                  <span className="text-muted-foreground">[{log.timestamp}]</span>
                  <span
                    className={
                      log.level === "ERROR"
                        ? "text-destructive"
                        : log.level === "WARNING"
                        ? "text-yellow-500"
                        : log.level === "SUCCESS"
                        ? "text-green-500"
                        : "text-foreground"
                    }
                  >
                    [{log.level}]
                  </span>
                  <span className="text-foreground">{log.message}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground">No logs yet. Create a job to see activity.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
