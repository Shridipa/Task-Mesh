import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TextDemo } from "@/features/text/TextDemo";
import type { TextJob } from "@/types/taskmesh";

const api = vi.hoisted(() => ({
  submitTextJob: vi.fn(),
  getTextJob: vi.fn()
}));

vi.mock("@/api/text", () => ({
  submitTextJob: api.submitTextJob,
  getTextJob: api.getTextJob
}));

const JOB_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301";

function makeJob(overrides: Partial<TextJob> = {}): TextJob {
  return {
    id: JOB_ID,
    job_type: "text.process",
    payload: { text: "Hello world. TaskMesh runs it!" },
    tenant_id: "demo",
    priority: 5,
    status: "pending",
    retry_count: 0,
    max_retries: 3,
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
      <TextDemo />
    </QueryClientProvider>
  );
}

async function submit(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Your text"), text);
  await user.click(screen.getByRole("button", { name: /submit task/i }));
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  api.submitTextJob.mockReset();
  api.getTextJob.mockReset();
});

describe("TextDemo", () => {
  it("rejects empty input without calling the backend", async () => {
    renderDemo();

    await userEvent.click(screen.getByRole("button", { name: /submit task/i }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter some text before submitting.");
    expect(api.submitTextJob).not.toHaveBeenCalled();
  });

  it("shows the real job id and status while the worker is processing", async () => {
    api.submitTextJob.mockResolvedValue(makeJob());
    api.getTextJob.mockResolvedValue(
      makeJob({ status: "running", worker_id: "worker-1", started_at: "2026-11-19T10:00:02Z" })
    );
    renderDemo();

    await submit("Hello world. TaskMesh runs it!");

    expect(api.submitTextJob).toHaveBeenCalledWith("Hello world. TaskMesh runs it!");
    expect(await screen.findByText(JOB_ID)).toBeInTheDocument();
    expect(await screen.findByText("running")).toBeInTheDocument();
    expect(await screen.findByText("worker-1")).toBeInTheDocument();
    expect(screen.queryByText("Words")).not.toBeInTheDocument();
  });

  it("renders the worker's stored result and stops polling after completion", async () => {
    api.submitTextJob.mockResolvedValue(makeJob());
    api.getTextJob.mockResolvedValue(
      makeJob({
        status: "completed",
        worker_id: "worker-1",
        started_at: "2026-11-19T10:00:02Z",
        completed_at: "2026-11-19T10:00:03Z",
        result: {
          words: 4,
          characters: 29,
          sentences: 2,
          lines: 1,
          cleaned_text: "Hello world. TaskMesh runs it!"
        }
      })
    );
    renderDemo();

    await submit("Hello world. TaskMesh runs it!");

    expect(await screen.findByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Hello world. TaskMesh runs it!", { selector: "pre" })).toBeInTheDocument();
    expect(screen.getByText("Words").parentElement).toHaveTextContent("4");
    expect(screen.getByText("Characters").parentElement).toHaveTextContent("29");
    expect(screen.getByText("Sentences").parentElement).toHaveTextContent("2");
    expect(screen.getByText("Lines").parentElement).toHaveTextContent("1");

    const callsAfterCompletion = api.getTextJob.mock.calls.length;
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    expect(api.getTextJob).toHaveBeenCalledTimes(callsAfterCompletion);
  });

  it("shows a submission error and no job when the backend rejects the task", async () => {
    api.submitTextJob.mockRejectedValue({ status: 429, message: "Too many tasks submitted." });
    renderDemo();

    await submit("Some text");

    expect(await screen.findByRole("alert")).toHaveTextContent("Too many tasks submitted.");
    expect(api.getTextJob).not.toHaveBeenCalled();
  });

  it("shows the worker's failure reason", async () => {
    api.submitTextJob.mockResolvedValue(makeJob());
    api.getTextJob.mockResolvedValue(
      makeJob({ status: "dead_letter", failure_reason: "text must not be empty" })
    );
    renderDemo();

    await submit("Hello");

    expect(await screen.findByText("dead letter")).toBeInTheDocument();
    expect(await screen.findByText(/Worker error: text must not be empty/)).toBeInTheDocument();
  });

  it("restores a completed task from the URL even when storage is unavailable", async () => {
    window.history.replaceState(null, "", `/?job=${JOB_ID}`);
    api.getTextJob.mockResolvedValue(
      makeJob({
        status: "completed",
        result: {
          words: 4,
          characters: 30,
          sentences: 2,
          lines: 1,
          cleaned_text: "Hello world. TaskMesh runs it!"
        }
      })
    );

    renderDemo();

    expect(await screen.findByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Hello world. TaskMesh runs it!", { selector: "pre" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your text")).toHaveValue("Hello world. TaskMesh runs it!");
    window.history.replaceState(null, "", "/");
  });

  it("restores a previously submitted task from storage after a refresh", async () => {
    window.localStorage.setItem(
      "taskmesh-text-demo",
      JSON.stringify({ jobId: JOB_ID, text: "Restored text." })
    );
    api.getTextJob.mockResolvedValue(
      makeJob({
        status: "completed",
        result: {
          words: 2,
          characters: 14,
          sentences: 1,
          lines: 1,
          cleaned_text: "Restored text."
        }
      })
    );

    renderDemo();

    await waitFor(() => expect(api.getTextJob).toHaveBeenCalledWith(JOB_ID));
    expect(await screen.findByText("Restored text.", { selector: "pre" })).toBeInTheDocument();
    expect(screen.getByLabelText("Your text")).toHaveValue("Restored text.");
  });
});
