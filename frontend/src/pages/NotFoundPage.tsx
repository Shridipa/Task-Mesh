import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      body="The requested console route does not exist."
      action={
        <Link to="/">
          <Button>Go to overview</Button>
        </Link>
      }
    />
  );
}
