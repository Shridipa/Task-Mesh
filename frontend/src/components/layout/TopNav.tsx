import { LogOut, Menu, Search, ShieldCheck } from "lucide-react";
import { Link, useLocation } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth-store";
import { useUiStore } from "@/store/ui-store";

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
  const token = useAuthStore((state) => state.token);
  const signOut = useAuthStore((state) => state.signOut);
  const setCommandOpen = useUiStore((state) => state.setCommandOpen);

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
        {token && role ? (
          <div className="flex items-center gap-2">
            <Badge className="capitalize">{role}</Badge>
            <Button aria-label="Sign out" variant="ghost" onClick={signOut}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <Link
            className="inline-flex h-9 items-center gap-2 rounded-xl border border-border px-3 text-sm hover:bg-muted"
            to="/settings"
          >
            <ShieldCheck className="h-4 w-4" />
            <span className="hidden sm:inline">Sign in</span>
          </Link>
        )}
      </div>
    </header>
  );
}
