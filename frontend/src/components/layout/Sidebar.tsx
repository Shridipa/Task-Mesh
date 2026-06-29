import { NavLink } from "react-router";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { navigationItems } from "@/constants/navigation";
import { useUiStore } from "@/store/ui-store";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

export function Sidebar() {
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const setCollapsed = useUiStore((state) => state.setSidebarCollapsed);

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r border-border bg-card/80 md:block",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-border px-3">
        {!collapsed ? <span className="text-sm font-semibold">TaskMesh</span> : null}
        <Button aria-label="Toggle sidebar" variant="ghost" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
        </Button>
      </div>
      <nav className="space-y-1 p-2" aria-label="Primary navigation">
        {navigationItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              cn(
                "flex h-10 items-center gap-3 rounded-xl px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground",
                isActive && "bg-muted text-foreground"
              )
            }
            title={item.label}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            {!collapsed ? <span className="truncate">{item.label}</span> : null}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
