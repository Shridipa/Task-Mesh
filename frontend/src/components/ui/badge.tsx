import { cn } from "@/utils/cn";
import type { JobStatus } from "@/types/taskmesh";
import type { ReactNode } from "react";

const statusClasses: Record<JobStatus, string> = {
  pending: "border-sky-500/40 bg-sky-500/10 text-sky-200",
  scheduled: "border-violet-500/40 bg-violet-500/10 text-violet-200",
  running: "border-amber-500/40 bg-amber-500/10 text-amber-100",
  completed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  failed: "border-rose-500/40 bg-rose-500/10 text-rose-100",
  dead_letter: "border-red-500/40 bg-red-500/10 text-red-100",
  canceled: "border-zinc-500/40 bg-zinc-500/10 text-zinc-200"
};

export function StatusBadge({ status }: { status: JobStatus | string }) {
  const knownStatus = status as JobStatus;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        statusClasses[knownStatus] ?? "border-border bg-muted text-muted-foreground"
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground",
        className
      )}
    >
      {children}
    </span>
  );
}
