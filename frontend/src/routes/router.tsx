import { lazy, Suspense } from "react";
import type { ReactNode } from "react";
import { createBrowserRouter } from "react-router";
import { AppLayout } from "@/layouts/AppLayout";
import { Skeleton } from "@/components/ui/skeleton";

const OverviewPage = lazy(() => import("@/pages/OverviewPage").then((module) => ({ default: module.OverviewPage })));
const JobsPage = lazy(() => import("@/pages/JobsPage").then((module) => ({ default: module.JobsPage })));
const WorkersPage = lazy(() => import("@/pages/WorkersPage").then((module) => ({ default: module.WorkersPage })));
const SchedulerPage = lazy(() => import("@/pages/SchedulerPage").then((module) => ({ default: module.SchedulerPage })));
const DeadLetterPage = lazy(() => import("@/pages/DeadLetterPage").then((module) => ({ default: module.DeadLetterPage })));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage").then((module) => ({ default: module.AnalyticsPage })));
const EventsPage = lazy(() => import("@/pages/EventsPage").then((module) => ({ default: module.EventsPage })));
const LogsPage = lazy(() => import("@/pages/LogsPage").then((module) => ({ default: module.LogsPage })));
const ProfilePage = lazy(() => import("@/pages/ProfilePage").then((module) => ({ default: module.ProfilePage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((module) => ({ default: module.NotFoundPage })));

function RouteFallback() {
  return <Skeleton className="h-[520px]" />;
}

function withSuspense(node: ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{node}</Suspense>;
}

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: withSuspense(<OverviewPage />) },
      { path: "/jobs", element: withSuspense(<JobsPage />) },
      { path: "/workers", element: withSuspense(<WorkersPage />) },
      { path: "/scheduler", element: withSuspense(<SchedulerPage />) },
      { path: "/dead-letter", element: withSuspense(<DeadLetterPage />) },
      { path: "/analytics", element: withSuspense(<AnalyticsPage />) },
      { path: "/events", element: withSuspense(<EventsPage />) },
      { path: "/logs", element: withSuspense(<LogsPage />) },
      { path: "/profile", element: withSuspense(<ProfilePage />) },
      { path: "*", element: withSuspense(<NotFoundPage />) }
    ]
  }
]);
