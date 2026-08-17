/**
 * Public surface of the employees feature. Routes compose from here and never
 * reach into the feature's internals.
 */
export { EmployeeDirectory } from "./components/employee-directory";
export { EmployeeProfile } from "./profile/employee-profile";
export { NewEmployeeBuilder } from "./builder/new-employee-builder";
export { ExistingEmployeeBuilder } from "./builder/existing-employee-builder";
export { EmployeeBuilder } from "./builder/employee-builder";
export { TemplateGrid } from "./templates/template-grid";
export { ActivityTimeline } from "./activity/activity-timeline";
export { AssignmentPanel } from "./assignments/assignment-panel";
export { CapabilityGrid } from "./capabilities/capability-grid";
export {
  EmployeeCardGridLoading,
  EmployeeListLoading,
  EmployeeProfileLoading,
} from "./components/employee-loading-state";
