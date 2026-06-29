import {
  Activity,
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  CalendarClock,
  FileText,
  Gauge,
  ListTree,
  Settings,
  User,
  Users
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
}

export const navigationItems: NavItem[] = [
  { label: "Overview", path: "/", icon: Gauge },
  { label: "Jobs", path: "/jobs", icon: BriefcaseBusiness },
  { label: "Workers", path: "/workers", icon: Users },
  { label: "Scheduler", path: "/scheduler", icon: CalendarClock },
  { label: "Dead Letter Queue", path: "/dead-letter", icon: AlertTriangle },
  { label: "Analytics", path: "/analytics", icon: BarChart3 },
  { label: "Events", path: "/events", icon: Activity },
  { label: "Logs", path: "/logs", icon: FileText },
  { label: "Settings", path: "/settings", icon: Settings },
  { label: "Profile", path: "/profile", icon: User }
];

export const commandItems = [
  ...navigationItems,
  { label: "Create job", path: "/jobs?create=1", icon: ListTree }
];
