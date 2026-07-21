/**
 * Public surface of the resource-collaboration service. Feature hooks compose
 * from here and never reach into the service's internals.
 */
export { resourceCollaborationService } from "./service";
export type { ResourceCollaborationService } from "./service";
export { resourceCollaborationKeys } from "./keys";
export {
  COLLABORATION_RESOURCE_TYPES,
  COLLABORATION_ROLES,
  COLLABORATION_ROLE_LABEL,
  ResourceCollaborationError,
} from "./types";
export type {
  AddParticipantInput,
  CollaborationResourceType,
  CollaborationRole,
  CreateShareInput,
  CreatedShareLink,
  ParticipantType,
  ResourceAccess,
  ResourceActivity,
  ResourceCollaborationCode,
  ResourceParticipant,
  ShareLink,
} from "./types";
