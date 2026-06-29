import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "@/app/App";

vi.mock("@/api/metrics", () => ({
  getDashboardMetrics: async () => ({
    pending: 1,
    scheduled: 0,
    running: 0,
    completed: 4,
    failed: 0,
    dead_letter: 0,
    active_workers: 2,
    throughput_per_minute: 4,
    retry_rate: 0
  })
}));

describe("App", () => {
  it("renders the console shell", async () => {
    render(<App />);
    expect(await screen.findByText("TaskMesh Console")).toBeInTheDocument();
  });
});
