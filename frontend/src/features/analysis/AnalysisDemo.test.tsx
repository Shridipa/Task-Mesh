import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisDemo } from "@/features/analysis/AnalysisDemo";
import type { AnalysisJob } from "@/types/taskmesh";

const api = vi.hoisted(() => ({
  submitAnalysisJob: vi.fn(),
  getAnalysisJob: vi.fn()
}));

vi.mock("@/api/analysis", () => ({
  submitAnalysisJob: api.submitAnalysisJob,
  getAnalysisJob: api.getAnalysisJob
}));

const JOB_ID = "9c858901-8a57-4791-81fe-4c455b099bc9";

function makeJob(overrides: Partial<AnalysisJob> = {}): AnalysisJob {
  return {
    id: JOB_ID,
    job_type: "json.validate",
    payload: { content: '{"a": 1}' },
    tenant_id: "demo",
    priority: 5,
    status: "pending",
    retry_count: 0,
    max_retries: 2,
    failure_reason: null,
    result: null,
    idempotency_key: null,
    created_at: "2026-11-19T10:00:00Z",
    execute_at: null,
    started_at: null,
    completed_at: null,
    worker_id: null,
    history: [],
    ...overrides
  };
}

function renderDemo() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AnalysisDemo />
    </QueryClientProvider>
  );
}

async function fillDocument(document: string) {
  const user = userEvent.setup();
  await user.click(screen.getByLabelText("Document"));
  // paste() avoids userEvent's key-descriptor parsing of "{" in JSON input.
  await user.paste(document);
  return user;
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  api.submitAnalysisJob.mockReset();
  api.getAnalysisJob.mockReset();
});

describe("AnalysisDemo", () => {
  it("rejects empty input without calling the backend", async () => {
    renderDemo();

    await userEvent.click(screen.getByRole("button", { name: /validate json/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Paste a document before submitting.");
    expect(api.submitAnalysisJob).not.toHaveBeenCalled();
  });

  it("renders the worker's JSON report", async () => {
    api.submitAnalysisJob.mockResolvedValue(makeJob());
    api.getAnalysisJob.mockResolvedValue(
      makeJob({
        status: "completed",
        worker_id: "worker-1",
        started_at: "2026-11-19T10:00:02Z",
        completed_at: "2026-11-19T10:00:03Z",
        result: {
          valid: true,
          formatted: '{\n  "a": 1,\n  "b": [2, 3]\n}',
          root_type: "object",
          counts: { objects: 1, arrays: 1, keys: 2, strings: 0, numbers: 3, booleans: 0, nulls: 0 },
          max_depth: 3,
          size: 23
        }
      })
    );
    renderDemo();

    const user = await fillDocument('{"a": 1, "b": [2, 3]}');
    await user.click(screen.getByRole("button", { name: /validate json/i }));

    expect(api.submitAnalysisJob).toHaveBeenCalledWith("json.validate", '{"a": 1, "b": [2, 3]}');
    expect(await screen.findByText(JOB_ID)).toBeInTheDocument();
    expect(await screen.findByText("Valid JSON")).toBeInTheDocument();
    expect(await screen.findByText("root type: object")).toBeInTheDocument();
    expect(screen.getByText("Objects").parentElement).toHaveTextContent("1");
    expect(screen.getByText("Arrays").parentElement).toHaveTextContent("1");
    expect(screen.getByText("Keys").parentElement).toHaveTextContent("2");
    expect(screen.getByText("Max depth").parentElement).toHaveTextContent("3");
  });

  it("renders the worker's CSV report", async () => {
    api.submitAnalysisJob.mockResolvedValue(makeJob({ job_type: "csv.analyze" }));
    api.getAnalysisJob.mockResolvedValue(
      makeJob({
        job_type: "csv.analyze",
        status: "completed",
        completed_at: "2026-11-19T10:00:03Z",
        result: {
          rows: 3,
          columns: 2,
          column_names: ["name", "score"],
          missing_values: { total: 1, by_column: { name: 0, score: 1 } },
          numeric_columns: ["score"],
          statistics: { score: { count: 2, mean: 85, median: 85, min: 80, max: 90 } },
          duplicate_rows: 1,
          ragged_rows: 0,
          preview: [{ name: "Ada", score: "90" }]
        }
      })
    );
    renderDemo();

    const user = await fillDocument("name,score\nAda,90\nGrace,80");
    await user.click(screen.getByRole("button", { name: /csv analysis/i }));
    await user.click(screen.getByRole("button", { name: /analyze csv/i }));

    expect(api.submitAnalysisJob).toHaveBeenCalledWith("csv.analyze", "name,score\nAda,90\nGrace,80");
    expect(await screen.findByText("Rows").then((node) => node.parentElement)).toHaveTextContent("3");
    expect(screen.getByText("Columns").parentElement).toHaveTextContent("2");
    expect(screen.getByText("Missing values").parentElement).toHaveTextContent("1");
    expect(screen.getByText("Duplicate rows").parentElement).toHaveTextContent("1");
    expect(screen.getByText("Numeric statistics")).toBeInTheDocument();
    expect(screen.getByText("score", { selector: "td" })).toBeInTheDocument();
  });

  it("shows the worker's failure reason for invalid JSON", async () => {
    api.submitAnalysisJob.mockResolvedValue(makeJob());
    api.getAnalysisJob.mockResolvedValue(
      makeJob({
        status: "failed",
        retry_count: 1,
        failure_reason: "Invalid JSON at line 2, column 3: Expecting value"
      })
    );
    renderDemo();

    const user = await fillDocument('{"a": }');
    await user.click(screen.getByRole("button", { name: /validate json/i }));

    expect(await screen.findByText("failed")).toBeInTheDocument();
    expect(
      await screen.findByText(/Task failed: Invalid JSON at line 2, column 3: Expecting value/)
    ).toBeInTheDocument();
    expect(screen.queryByText("Valid JSON")).not.toBeInTheDocument();
  });

  it("restores a completed analysis job from the URL after a refresh", async () => {
    window.history.replaceState(null, "", `/?analysis=${JOB_ID}`);
    api.getAnalysisJob.mockResolvedValue(
      makeJob({
        status: "completed",
        result: {
          valid: true,
          formatted: '{\n  "a": 1\n}',
          root_type: "object",
          counts: { objects: 1, arrays: 0, keys: 1, strings: 0, numbers: 1, booleans: 0, nulls: 0 },
          max_depth: 2,
          size: 9
        }
      })
    );

    renderDemo();

    expect(await screen.findByText("Valid JSON")).toBeInTheDocument();
    expect(screen.getByLabelText("Document")).toHaveValue('{"a": 1}');
    window.history.replaceState(null, "", "/");
  });
});
