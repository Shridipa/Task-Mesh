import { formatDistanceToNowStrict, isValid, parseISO } from "date-fns";

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Not set";
  }
  const date = parseISO(value);
  return isValid(date) ? date.toLocaleString() : value;
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) {
    return "Never";
  }
  const date = parseISO(value);
  return isValid(date) ? `${formatDistanceToNowStrict(date)} ago` : value;
}

export function compactNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact" }).format(value);
}

export function percentage(value: number): string {
  return `${Math.round(value * 100)}%`;
}
