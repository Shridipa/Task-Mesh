import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Loader2, RotateCcw, Send, XCircle } from "lucide-react";
import { getTextJob, submitTextJob } from "@/api/text";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { ApiError, TextJob } from "@/types/taskmesh";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

const MAX_CHARACTERS = 10_000;
const STORAGE_KEY = "taskmesh-text-demo";
const TERMINAL_STATUSES = new Set(["completed", "failed", "dead_letter", "canceled"]);

type StepState = "pending" | "active" | "done" | "failed";

function StepIcon({ state }: { state: StepState }) {
  if (state === "done") return <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400" />;
  if (state === "active") return <Loader2 className="h-5 w-5 shrink-0 animate-spin text-amber-300" />;
  if (state === "failed") return <XCircle className="h-5 w-5 shrink-0 text-rose-400" />;
  return <Circle className="h-5 w-5 shrink-0 text-muted-foreground/50" />;
}

export function TextDemo() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Restore the last submitted task so a page refresh keeps showing its result.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as { jobId?: string; text?: string };
      if (parsed.jobId) setJobId(parsed.jobId);
      if (typeof parsed.text === "string") setText(parsed.text);
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const jobQuery = useQuery<TextJob, ApiError>({
    queryKey: ["text-job", jobId],
    queryFn: () => getTextJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const current = query.state.data;
      if (!current) return 1_000;
      return TERMINAL_STATUSES.has(current.status) ? false : 1_000;
    }
  });

  const mutation = useMutation<TextJob, ApiError, string>({
    mutationFn: (value) => submitTextJob(value),
    onSuccess: (created, submitted) => {
      setFormError(null);
      setJobId(created.id);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ jobId: created.id, text: submitted }));
      queryClient.setQueryData(["text-job", created.id], created);
      void queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
    onError: (error) =>
      setFormError(error.message || "Could not submit the task. Is the backend running?")
  });

  const job = jobId ? jobQuery.data ?? null : null;
  const status = job?.status;
  const result = job?.result ?? null;

  useEffect(() => {
    if (job && TERMINAL_STATUSES.has(job.status)) {
      void queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    }
  }, [job, queryClient]);

  const submittedState: StepState = jobId ? "done" : "pending";
  const queuedState: StepState = !job
    ? "pending"
    : job.started_at || status === "running" || status === "completed"
      ? "done"
      : status === "failed" || status === "dead_letter" || status === "canceled"
        ? "failed"
        : "active";
  const runningState: StepState =
    status === "running"
      ? "active"
      : status === "completed"
        ? "done"
        : status === "failed" || status === "dead_letter"
          ? job?.started_at
            ? "failed"
            : "pending"
          : "pending";
  const completedState: StepState =
    status === "completed"
      ? "done"
      : status === "failed" || status === "dead_letter" || status === "canceled"
        ? "failed"
        : "pending";

  const steps: { title: string; description: string; state: StepState }[] = [
    {
      title: "Submitted",
      description: "The backend accepted the task and stored it as a job.",
      state: submittedState
    },
    {
      title: "Waiting in queue",
      description: "The job is persisted and waiting for an available worker.",
      state: queuedState
    },
    {
      title: "Worker processing",
      description: "A background worker leased the job and is executing it.",
      state: runningState
    },
    {
      title: "Completed",
      description: "The worker finished the task and saved the result.",
      state: completedState
    }
  ];

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim()) {
      setFormError("Enter some text before submitting.");
      return;
    }
    if (text.length > MAX_CHARACTERS) {
      setFormError(`Text must be at most ${MAX_CHARACTERS.toLocaleString()} characters.`);
      return;
    }
    setFormError(null);
    mutation.mutate(text);
  };

  const startAnother = () => {
    setJobId(null);
    setText("");
    setFormError(null);
    window.localStorage.removeItem(STORAGE_KEY);
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Try TaskMesh Yourself</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm leading-6 text-muted-foreground">
            Submit a task and watch TaskMesh process it in the background. Your task enters the queue, a worker picks
            it up, executes it, and returns the result. Nothing here is simulated: the counts below are computed from
            your text by the worker process.
          </p>
          <form className="space-y-3" onSubmit={handleSubmit} noValidate>
            <label className="block text-sm font-medium" htmlFor="task-text">
              Your text
            </label>
            <Textarea
              id="task-text"
              rows={8}
              value={text}
              maxLength={MAX_CHARACTERS}
              placeholder="Paste or type the text you want TaskMesh to process..."
              aria-describedby="task-text-help"
              aria-invalid={Boolean(formError)}
              onChange={(event) => {
                setText(event.target.value);
                if (formError) setFormError(null);
              }}
            />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span id="task-text-help">
                Counting rules: words split on whitespace, characters include spaces, sentences end with . ! or ?, lines
                are separated by newlines.
              </span>
              <span aria-live="polite">
                {text.length.toLocaleString()} / {MAX_CHARACTERS.toLocaleString()} characters
              </span>
            </div>
            {formError ? (
              <p className="text-sm text-destructive" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" variant="primary" disabled={mutation.isPending}>
                {mutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {mutation.isPending ? "Submitting..." : "Submit task"}
              </Button>
              {jobId ? (
                <Button type="button" variant="ghost" onClick={startAnother} disabled={mutation.isPending}>
                  <RotateCcw className="h-4 w-4" />
                  Process another task
                </Button>
              ) : null}
            </div>
          </form>
        </CardContent>
      </Card>

      {jobId ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle>Task lifecycle</CardTitle>
                {job ? <StatusBadge status={job.status} /> : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <ol className="space-y-3">
                {steps.map((step) => (
                  <li key={step.title} className="flex gap-3">
                    <StepIcon state={step.state} />
                    <div className="min-w-0">
                      <div
                        className={cn(
                          "text-sm font-medium",
                          step.state === "pending" && "text-muted-foreground"
                        )}
                      >
                        {step.title}
                      </div>
                      <p className="text-xs text-muted-foreground">{step.description}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <dl className="grid gap-2 border-t border-border pt-3 text-xs sm:grid-cols-2">
                <Meta label="Job ID" value={jobId} mono />
                <Meta label="Worker" value={job?.worker_id ?? "Not assigned yet"} />
                <Meta label="Submitted" value={job ? formatDateTime(job.created_at) : "Waiting for the API"} />
                <Meta label="Started" value={job?.started_at ? formatDateTime(job.started_at) : "Not started"} />
                <Meta label="Finished" value={job?.completed_at ? formatDateTime(job.completed_at) : "Not finished"} />
                <Meta
                  label="Attempts"
                  value={job ? `${job.retry_count + 1} of ${job.max_retries + 1}` : "—"}
                />
              </dl>
              {jobQuery.isError ? (
                <p className="text-sm text-destructive" role="alert">
                  Could not load this task: {jobQuery.error?.message ?? "unknown error"}
                </p>
              ) : null}
              {job?.failure_reason ? (
                <p className="text-sm text-destructive" role="alert">
                  Worker error: {job.failure_reason}
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Result</CardTitle>
            </CardHeader>
            <CardContent>
              {result ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <ResultStat label="Words" value={result.words} />
                    <ResultStat label="Characters" value={result.characters} />
                    <ResultStat label="Sentences" value={result.sentences} />
                    <ResultStat label="Lines" value={result.lines} />
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium text-muted-foreground">Cleaned text</div>
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-muted/40 p-3 text-sm">
                      {result.cleaned_text}
                    </pre>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {status === "completed"
                    ? "The worker completed this task without a stored result."
                    : "The result appears here as soon as the worker finishes."}
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}

function Meta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("truncate", mono && "font-mono text-[11px]")} title={value}>
        {value}
      </dd>
    </div>
  );
}

function ResultStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value.toLocaleString()}</div>
    </div>
  );
}
