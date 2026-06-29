import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Drawer } from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { createJob } from "@/api/jobs";
import type { JobCreateInput } from "@/types/taskmesh";

interface CreateJobDrawerProps {
  open: boolean;
  onClose: () => void;
}

export function CreateJobDrawer({ open, onClose }: CreateJobDrawerProps) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: createJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["metrics-summary"] });
      onClose();
    },
  });

  const [form, setForm] = useState<JobCreateInput>({
    job_type: "email",
    payload: { to: "", subject: "", body: "" },
    priority: 5,
    tenant_id: "default",
    max_retries: 5,
  });

  const update = (patch: Partial<JobCreateInput>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  };

  const updatePayload = (patch: Record<string, unknown>) => {
    setForm((prev) => ({ ...prev, payload: { ...prev.payload, ...patch } }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Drawer open={open} title="Create job" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <Label htmlFor="job_type">Job type</Label>
          <Input
            id="job_type"
            value={form.job_type}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) => update({ job_type: event.target.value })}
            placeholder="email, report, cleanup..."
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="tenant_id">Tenant</Label>
          <Input
            id="tenant_id"
            value={form.tenant_id}
            onChange={(event: React.ChangeEvent<HTMLInputElement>) => update({ tenant_id: event.target.value })}
            placeholder="default"
            required
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2">
            <Label htmlFor="priority">Priority (0-9)</Label>
            <Input
              id="priority"
              type="number"
              min={0}
              max={9}
              value={form.priority}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => update({ priority: Number(event.target.value) })}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max_retries">Max retries</Label>
            <Input
              id="max_retries"
              type="number"
              min={0}
              max={20}
              value={form.max_retries}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => update({ max_retries: Number(event.target.value) })}
              required
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label>Payload (JSON)</Label>
          <Textarea
            className="font-mono text-xs"
            rows={6}
            value={JSON.stringify(form.payload, null, 2)}
            onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => {
              try {
                const parsed = JSON.parse(event.target.value);
                update({ payload: parsed });
              } catch {
                // allow incomplete JSON while typing
              }
            }}
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating..." : "Create job"}
          </Button>
        </div>

        {mutation.isError ? (
          <p className="text-sm text-destructive">{(mutation.error as Error).message}</p>
        ) : null}
      </form>
    </Drawer>
  );
}