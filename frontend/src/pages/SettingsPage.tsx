import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SettingsPage() {
  return (
    <Card>
      <CardHeader><CardTitle>Settings</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <p>API base URL is configured with VITE_API_BASE_URL and defaults to the Vite proxy at /api.</p>
        <p>Authentication currently uses the backend X-Role contract. TODO: Backend endpoint required for JWT login, refresh tokens, and persisted user profile settings.</p>
      </CardContent>
    </Card>
  );
}
