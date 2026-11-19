import { useState } from "react";
import { getRoleCapabilities, requestToken } from "@/api/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/store/auth-store";
import type { ApiError } from "@/types/taskmesh";

export function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const tenant = useAuthStore((state) => state.tenant);
  const subject = useAuthStore((state) => state.subject);
  const setSession = useAuthStore((state) => state.setSession);
  const signOut = useAuthStore((state) => state.signOut);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const key = apiKey.trim();
    if (!key) {
      setError("Enter your API key.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const session = await requestToken(key);
      setSession(session);
      setApiKey("");
    } catch (err) {
      setError((err as ApiError).message || "Sign-in failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            Management pages call the API with a short-lived signed token. Exchange an API key for
            one below; the role is decided by the backend, never by the browser. The public demo
            panels on the Overview page work without signing in.
          </p>
          {token && role ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span>Signed in as</span>
                <span className="font-mono text-xs text-foreground">{subject}</span>
                <Badge className="capitalize">{role}</Badge>
                <span>tenant</span>
                <span className="font-mono text-xs text-foreground">{tenant}</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {getRoleCapabilities(role).map((capability) => (
                  <Badge key={capability}>{capability}</Badge>
                ))}
              </div>
              <Button variant="secondary" onClick={signOut}>
                Sign out
              </Button>
            </div>
          ) : (
            <form className="space-y-3" onSubmit={handleSubmit}>
              <div className="space-y-1">
                <Label htmlFor="api-key">API key</Label>
                <Input
                  id="api-key"
                  type="password"
                  autoComplete="off"
                  placeholder="Paste the API key from your deployment"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                />
              </div>
              <Button type="submit" disabled={pending}>
                {pending ? "Signing in…" : "Sign in"}
              </Button>
            </form>
          )}
          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            The API base URL is configured with <code>VITE_API_BASE_URL</code> and defaults to the
            proxy at <code>/api</code>.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
