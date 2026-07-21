/**
 * Public surface of the Voice Experience feature. Routes compose from here.
 */
export { VoiceExperience } from "./components/voice-experience";
export { useVoiceSession, type VoiceSession, type ExecutionStatus } from "./hooks/use-voice-session";
export {
  VOICE_STATES,
  VOICE_STATE_LABEL,
  type VoiceState,
} from "./lib/session-machine";
export {
  DEFAULT_INTERACTION_MODE,
  describeMode,
  type InteractionMode,
} from "./lib/interaction-mode";
export { detectAction, type PendingAction } from "./lib/action-intent";
