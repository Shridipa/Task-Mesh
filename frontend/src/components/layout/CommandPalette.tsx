import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { commandItems } from "@/constants/navigation";
import { useUiStore } from "@/store/ui-store";
import { cn } from "@/utils/cn";

export function CommandPalette() {
  const open = useUiStore((state) => state.commandOpen);
  const setOpen = useUiStore((state) => state.setCommandOpen);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setOpen]);

  const items = useMemo(
    () =>
      commandItems.filter((item) =>
        item.label.toLowerCase().includes(query.trim().toLowerCase())
      ),
    [query]
  );

  return (
    <div className={cn("fixed inset-0 z-50", open ? "block" : "hidden")}>
      <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
      <div
        className="absolute left-1/2 top-20 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 rounded-xl border border-border bg-card shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="h-12 w-full rounded-t-xl border-b border-border bg-transparent px-4 text-sm outline-none"
          placeholder="Search commands and pages"
        />
        <div className="max-h-80 overflow-y-auto p-2">
          {items.map((item) => (
            <button
              key={item.label}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={() => {
                navigate(item.path);
                setOpen(false);
                setQuery("");
              }}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
