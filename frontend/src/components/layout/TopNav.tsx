import { useState } from "react";
import { Menu, Search, Zap } from "lucide-react";
import { useLocation } from "react-router";
import { Button } from "@/components/ui/button";
import { supportedRoles } from "@/api/auth";
import { useAuthStore } from "@/store/auth-store";
import { useUiStore } from "@/store/ui-store";
import { generateDemoWorkers, generateDemoJobs } from "@/api/demo";
import type { UserRole } from "@/types/taskmesh";

function titleFromPath(pathname: string): string {
  if (pathname === "/") {
    return "Overview";
  }
  return pathname
    .slice(1)
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function TopNav() {
  const location = useLocation();
  const role = useAuthStore((state) => state.role);
  const setRole = useAuthStore((state) => state.setRole);
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);
  const [demoLoading, setDemoLoading] = useState(false);

  const runDemo = async () => {
    setDemoLoading(true);
    try {
      await generateDemoWorkers(3);
      await generateDemoJobs(15);
    } catch (error) {
      console.error("Demo generation failed:", error);
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur">
      <div className="flex min-w-0 items-center gap-3">
        <Button className="md:hidden" aria-label="Open navigation" variant="ghost">
          <Menu className="h-4 w-4" />
        </Button>
        <div>
          <div className="text-sm text-muted-foreground">TaskMesh Console</div>
          <h1 className="truncate text-base font-semibold">{titleFromPath(location.pathname)}</h1>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="secondary" onClick={() => setCommandOpen(true)}>
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">Ctrl+K</span>
        </Button>
        <Button variant="primary" onClick={runDemo} disabled={demoLoading}>
          <Zap className="h-4 w-4" />
          <span className="hidden sm:inline">{demoLoading ? "Generating..." : "Demo"}</span>
        </Button>
        <label className="sr-only" htmlFor="role-select">
          Role
        </label>
        <select
          id="role-select"
          className="h-9 rounded-xl border border-border bg-muted px-3 text-sm capitalize outline-none focus:ring-2 focus:ring-primary"
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
        >
          {supportedRoles.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
