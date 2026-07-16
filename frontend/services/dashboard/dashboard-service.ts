import { MockDashboardAdapter } from "./mock-adapter";
import type { DashboardAdapter } from "./types";

/**
 * The app's single entry point to dashboard data. Swapping providers = swapping
 * this one adapter; callers (the feature hooks) never change. No fetch/axios/SDKs.
 */
const adapter: DashboardAdapter = new MockDashboardAdapter();

export const dashboardService = {
  overview: () => adapter.overview(),
  recentTasks: () => adapter.recentTasks(),
  recentWorkflows: () => adapter.recentWorkflows(),
  activeEmployees: () => adapter.activeEmployees(),
  pendingApprovals: () => adapter.pendingApprovals(),
  memorySummary: () => adapter.memorySummary(),
  recentNotifications: () => adapter.recentNotifications(),
  health: () => adapter.health(),
  workspaceSignals: () => adapter.workspaceSignals(),
};

export type DashboardService = typeof dashboardService;
