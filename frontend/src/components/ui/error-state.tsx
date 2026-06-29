import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4">
      <p className="text-sm font-medium text-red-100">{message}</p>
      {onRetry ? (
        <Button className="mt-3" variant="secondary" onClick={onRetry}>
          <RotateCcw className="h-4 w-4" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}
