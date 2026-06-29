export function JsonViewer({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-xl border border-border bg-black/30 p-3 font-mono text-xs leading-5 text-slate-200">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
