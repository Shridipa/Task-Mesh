import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SettingsPage } from "@/pages/SettingsPage";
import { useAuthStore } from "@/store/auth-store";

const requestToken = vi.fn();

vi.mock("@/api/auth", async () => {
  const actual = await vi.importActual<typeof import("@/api/auth")>("@/api/auth");
  return {
    ...actual,
    requestToken: (apiKey: string) => requestToken(apiKey)
  };
});

describe("SettingsPage", () => {
  beforeEach(() => {
    requestToken.mockReset();
    useAuthStore.setState({
      token: null,
      role: null,
      tenant: null,
      subject: null,
      expiresAt: null
    });
  });

  it("exchanges an API key for a session and shows the granted role", async () => {
    requestToken.mockResolvedValue({
      access_token: "signed-token",
      token_type: "bearer",
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      subject: "api-key:abc123",
      role: "developer",
      tenant: "team-a"
    });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "my-api-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Signed in as")).toBeInTheDocument();
    expect(screen.getByText("api-key:abc123")).toBeInTheDocument();
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("team-a")).toBeInTheDocument();
    expect(useAuthStore.getState().token).toBe("signed-token");
  });

  it("shows the backend error when the key is rejected", async () => {
    requestToken.mockRejectedValue({ status: 401, message: "Invalid API key" });

    render(<SettingsPage />);

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "wrong-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid API key"));
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("requires a key before calling the API", async () => {
    render(<SettingsPage />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Enter your API key"));
    expect(requestToken).not.toHaveBeenCalled();
  });
});
