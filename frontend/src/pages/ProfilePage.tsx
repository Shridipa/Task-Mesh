import { getRoleCapabilities } from "@/api/auth";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/store/auth-store";

export function ProfilePage() {
  const role = useAuthStore((state) => state.role);
  const tenant = useAuthStore((state) => state.tenant);
  const subject = useAuthStore((state) => state.subject);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {role ? (
          <>
            <div>
              <div className="text-xs text-muted-foreground">Signed in as</div>
              <div className="mt-1 font-mono text-sm">{subject}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Current role</div>
              <div className="mt-1 text-lg font-semibold capitalize">{role}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Tenant</div>
              <div className="mt-1 font-mono text-sm">{tenant}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {getRoleCapabilities(role).map((capability) => (
                <Badge key={capability}>{capability}</Badge>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Not signed in. Use Settings to exchange an API key for a session.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
