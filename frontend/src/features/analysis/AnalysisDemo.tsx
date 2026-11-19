import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Send } from "lucide-react";
import { getAnalysisJob, submitAnalysisJob } from "@/api/analysis";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type {
  AnalysisJob,
  AnalysisTask,
  ApiError,
  CsvAnalysisResult,
  JsonValidationResult
} from "@/types/taskmesh";
import { cn } from "@/utils/cn";
import { formatDateTime } from "@/utils/format";

const STORAGE_KEY = "taskmesh-analysis-demo";
const JOB_PARAM = "analysis";
const TERMINAL_STATUSES = new Set(["completed", "failed", "dead_letter", "canceled"]);

const TASKS: {
  id: AnalysisTask;
  label: string;
  description: string;
  maxLength: number;
  placeholder: string;
  action: string;
}[] = [
  {
    id: "json.validate",
    label: "JSON validation",
    description:
      "Parses the document, formats it, and counts objects, arrays, keys and values. Invalid JSON fails with its line and column.",
    maxLength: 100_000,
    placeholder: '{\n  "name": "TaskMesh",\n  "tags": ["queue", "worker"]\n}',
    action: "Validate JSON"
  },
  {
    id: "csv.analyze",
    label: "CSV analysis",
    description:
      "Counts rows and columns, finds missing values and duplicate rows, and computes statistics for numeric columns.",
    maxLength: 200_000,
    placeholder: "name,score\nAda,90\nGrace,80",
    action: "Analyze CSV"
  }
];

function readStoredJob(): { jobId?: string; task?: AnalysisTask; content?: string } | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as { jobId?: string; task?: AnalysisTask; content?: string }) : null;
  } catch {
    // Storage can be unavailable (sandboxed iframe); the URL still carries the job id.
    return null;
  }
}

function storeJob(jobId: string, task: AnalysisTask, content: string) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ jobId, task, content }));
  } catch {
    // Ignore storage failures: the URL keeps the task recoverable.
  }
}

function clearStoredJob() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to clean up when storage is unavailable.
  }
}

function jobIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get(JOB_PARAM);
}

function setJobInUrl(jobId: string | null) {
  const url = new URL(window.location.href);
  if (jobId) url.searchParams.set(JOB_PARAM, jobId);
  else url.searchParams.delete(JOB_PARAM);
  window.history.replaceState(null, "", url.toString());
}

function taskById(task: string | undefined): AnalysisTask {
  return task === "csv.analyze" ? "csv.analyze" : "json.validate";
}

export function AnalysisDemo() {
  const queryClient = useQueryClient();
  const [task, setTask] = useState<AnalysisTask>("json.validate");
  const [content, setContent] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const selected = TASKS.find((option) => option.id === task) ?? TASKS[0];

  // Restore the last submitted task so a refresh keeps showing its result.
  useEffect(() => {
    const fromUrl = jobIdFromUrl();
    const parsed = readStoredJob();
    const restoredId = fromUrl ?? parsed?.jobId;
    if (restoredId) setJobId(restoredId);
    if (!fromUrl) {
      if (parsed?.task) setTask(taskById(parsed.task));
      if (typeof parsed?.content === "string") setContent(parsed.content);
    }
  }, []);

  const jobQuery = useQuery<AnalysisJob, ApiError>({
    queryKey: ["analysis-job", jobId],
    queryFn: () => getAnalysisJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const current = query.state.data;
      if (!current) return 1_000;
      return TERMINAL_STATUSES.has(current.status) ? false : 1_000;
    }
  });

  const mutation = useMutation<AnalysisJob, ApiError, { task: AnalysisTask; content: string }>({
    mutationFn: ({ task: submittedTask, content: submitted }) =>
      submitAnalysisJob(submittedTask, submitted),
    onSuccess: (created, submitted) => {
      setFormError(null);
      setJobId(created.id);
      setJobInUrl(created.id);
      storeJob(created.id, submitted.task, submitted.content);
      queryClient.setQueryData(["analysis-job", created.id], created);
      void queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    },
    onError: (error) =>
      setFormError(error.message || "Could not submit the task. Is the backend running?")
  });

  const job = jobId ? jobQuery.data ?? null : null;
  const result = job?.result ?? null;
  const jsonResult: JsonValidationResult | null = result && "formatted" in result ? result : null;
  const csvResult: CsvAnalysisResult | null = result && "rows" in result ? result : null;

  // When the page was restored from the URL, show the submitted document again.
  useEffect(() => {
    const original = job?.payload?.content;
    if (typeof original === "string" && original) {
      setTask(taskById(job?.job_type));
      setContent((current) => (current ? current : original));
    }
  }, [job]);

  useEffect(() => {
    if (job && TERMINAL_STATUSES.has(job.status)) {
      void queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
    }
  }, [job, queryClient]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!content.trim()) {
      setFormError("Paste a document before submitting.");
      return;
    }
    if (content.length > selected.maxLength) {
      setFormError(`${selected.label} accepts at most ${selected.maxLength.toLocaleString()} characters.`);
      return;
    }
    setFormError(null);
    mutation.mutate({ task, content });
  };

  const startAnother = () => {
    setJobId(null);
    setContent("");
    setFormError(null);
    setJobInUrl(null);
    clearStoredJob();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Validate JSON or analyze CSV</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-6 text-muted-foreground">
          Both tasks run through the same queue and worker as the text task: the API stores a real job, a background
          worker executes it, and the result below is read back from the database.
        </p>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Task type">
          {TASKS.map((option) => (
            <Button
              key={option.id}
              type="button"
              variant={option.id === task ? "primary" : "secondary"}
              aria-pressed={option.id === task}
              disabled={mutation.isPending}
              onClick={() => {
                setTask(option.id);
                setFormError(null);
              }}
            >
              {option.label}
            </Button>
          ))}
        </div>

        <p className="text-xs text-muted-foreground">{selected.description}</p>

        <form className="space-y-3" onSubmit={handleSubmit} noValidate>
          <label className="block text-sm font-medium" htmlFor="analysis-input">
            Document
          </label>
          <Textarea
            id="analysis-input"
            rows={8}
            value={content}
            maxLength={selected.maxLength}
            placeholder={selected.placeholder}
            aria-describedby="analysis-input-help"
            aria-invalid={Boolean(formError)}
            className="font-mono text-xs"
            onChange={(event) => {
              setContent(event.target.value);
              if (formError) setFormError(null);
            }}
          />
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span id="analysis-input-help">{selected.label} runs in a worker; nothing is evaluated as code.</span>
            <span aria-live="polite">
              {content.length.toLocaleString()} / {selected.maxLength.toLocaleString()} characters
            </span>
          </div>
          {formError ? (
            <p className="text-sm text-destructive" role="alert">
              {formError}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" variant="primary" disabled={mutation.isPending}>
              {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              {mutation.isPending ? "Submitting..." : selected.action}
            </Button>
            {jobId ? (
              <Button type="button" variant="ghost" onClick={startAnother} disabled={mutation.isPending}>
                <RotateCcw className="h-4 w-4" />
                Process another task
              </Button>
            ) : null}
          </div>
        </form>

        {jobId ? (
          <div className="space-y-4 border-t border-border pt-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm font-medium">Task status</div>
              {job ? <StatusBadge status={job.status} /> : null}
            </div>
            <dl className="grid gap-2 text-xs sm:grid-cols-2">
              <Meta label="Job ID" value={jobId} mono />
              <Meta label="Task type" value={job?.job_type ?? "—"} />
              <Meta label="Worker" value={job?.worker_id ?? "Not assigned yet"} />
              <Meta label="Submitted" value={job ? formatDateTime(job.created_at) : "Waiting for the API"} />
              <Meta label="Finished" value={job?.completed_at ? formatDateTime(job.completed_at) : "Not finished"} />
            </dl>

            {jobQuery.isError ? (
              <p className="text-sm text-destructive" role="alert">
                Could not load this task: {jobQuery.error?.message ?? "unknown error"}
              </p>
            ) : null}
            {job?.failure_reason ? (
              <p className="text-sm text-destructive" role="alert">
                Task failed: {job.failure_reason}
              </p>
            ) : null}

            {jsonResult ? <JsonReport result={jsonResult} /> : null}
            {csvResult ? <CsvReport result={csvResult} /> : null}
            {!result && !job?.failure_reason ? (
              <p className="text-sm text-muted-foreground">
                {job?.status === "completed"
                  ? "The worker completed this task without a stored result."
                  : "The result appears here as soon as the worker finishes."}
              </p>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function JsonReport({ result }: { result: JsonValidationResult }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-100">Valid JSON</Badge>
        <span className="text-xs text-muted-foreground">root type: {result.root_type}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Objects" value={result.counts.objects.toLocaleString()} />
        <Stat label="Arrays" value={result.counts.arrays.toLocaleString()} />
        <Stat label="Keys" value={result.counts.keys.toLocaleString()} />
        <Stat label="Max depth" value={result.max_depth.toLocaleString()} />
        <Stat label="Strings" value={result.counts.strings.toLocaleString()} />
        <Stat label="Numbers" value={result.counts.numbers.toLocaleString()} />
        <Stat label="Booleans" value={result.counts.booleans.toLocaleString()} />
        <Stat label="Nulls" value={result.counts.nulls.toLocaleString()} />
      </div>
      <div>
        <div className="mb-1 text-xs font-medium text-muted-foreground">Formatted JSON</div>
        <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-border bg-muted/40 p-3 text-xs">
          {result.formatted}
        </pre>
      </div>
    </div>
  );
}

function CsvReport({ result }: { result: CsvAnalysisResult }) {
  const numeric = Object.entries(result.statistics);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Rows" value={result.rows.toLocaleString()} />
        <Stat label="Columns" value={result.columns.toLocaleString()} />
        <Stat label="Missing values" value={result.missing_values.total.toLocaleString()} />
        <Stat label="Duplicate rows" value={result.duplicate_rows.toLocaleString()} />
      </div>

      <div>
        <div className="mb-1 text-xs font-medium text-muted-foreground">Column names</div>
        <div className="flex flex-wrap gap-2">
          {result.column_names.map((name) => (
            <Badge key={name}>
              {name} · {result.missing_values.by_column[name] ?? 0} missing
            </Badge>
          ))}
        </div>
      </div>

      {result.ragged_rows > 0 ? (
        <p className="text-xs text-amber-200">
          {result.ragged_rows.toLocaleString()} row(s) had a different number of fields than the header.
        </p>
      ) : null}

      {numeric.length > 0 ? (
        <div className="overflow-x-auto">
          <div className="mb-1 text-xs font-medium text-muted-foreground">Numeric statistics</div>
          <table className="w-full text-left text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 pr-3 font-medium">Column</th>
                <th className="py-1 pr-3 font-medium">Count</th>
                <th className="py-1 pr-3 font-medium">Mean</th>
                <th className="py-1 pr-3 font-medium">Median</th>
                <th className="py-1 pr-3 font-medium">Min</th>
                <th className="py-1 font-medium">Max</th>
              </tr>
            </thead>
            <tbody>
              {numeric.map(([name, stats]) => (
                <tr key={name} className="border-t border-border">
                  <td className="py-1 pr-3">{name}</td>
                  <td className="py-1 pr-3">{stats.count.toLocaleString()}</td>
                  <td className="py-1 pr-3">{stats.mean.toLocaleString()}</td>
                  <td className="py-1 pr-3">{stats.median.toLocaleString()}</td>
                  <td className="py-1 pr-3">{stats.min.toLocaleString()}</td>
                  <td className="py-1">{stats.max.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No numeric columns were found.</p>
      )}

      {result.preview.length > 0 ? (
        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">First rows</div>
          <div className="max-h-56 overflow-auto rounded-xl border border-border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  {result.column_names.map((name) => (
                    <th key={name} className="px-2 py-1 font-medium">
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.map((row, index) => (
                  <tr key={index} className="border-t border-border">
                    {result.column_names.map((name) => (
                      <td key={name} className="px-2 py-1">
                        {row[name]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
