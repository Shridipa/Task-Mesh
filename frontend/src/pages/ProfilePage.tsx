import { getRoleCapabilities } from "@/api/auth";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth-store";

export function ProfilePage() {
  const role = useAuthStore((state) => state.role);
  return (
    <Card>
      <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="text-xs text-muted-foreground">Current role</div>
          <div className="mt-1 text-lg font-semibold capitalize">{role}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {getRoleCapabilities(role).map((capability) => <Badge key={capability}>{capability}</Badge>)}
        </div>
      </CardContent>
    </Card>
  );
}
