"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  conversationKeys,
  conversationService,
  type ConversationMessage,
} from "@/services/conversations";
import { taskKeys, taskService } from "@/services/tasks";
import {
  useSpeechInput,
  useSpeechOutput,
} from "@/features/conversations/hooks/use-speech";
import {
  INITIAL_VOICE_STATE,
  VOICE_STATE_LABEL,
  isMicActive,
  voiceReducer,
  type VoiceEvent,
  type VoiceState,
} from "../lib/session-machine";
import { detectAction, type PendingAction } from "../lib/action-intent";
import {
  DEFAULT_INTERACTION_MODE,
  channelForMode,
  resolveMode,
  shouldAutoListen,
  shouldSpeakReplies,
  type InteractionMode,
} from "../lib/interaction-mode";

/**
 * The Conversation Orchestrator (Sprint 22).
 *
 * The single point that coordinates one intelligent assistant out of the parts
 * the platform already has — it *composes*, it does not duplicate:
 *
 *   speech in  →  the existing conversation turn (memory + AI employee)  →
 *   permission gate  →  executor seam (Task engine)  →  speech out
 *
 * sequenced by the pure session machine and shaped by the interaction mode.
 * There is no second conversation pipeline and no second voice pipeline: the
 * turn is `conversationService.send` (the real memory-grounded `/turn`
 * endpoint), speech is the existing `use-speech` hooks, and an approved action
 * creates a real task through the Task engine. The same React Query keys are
 * used as the conversation workspace, so the two share one cache and a voice
 * turn shows up in the thread — continuity is inherent, never re-implemented.
 */

export interface ExecutionStatus {
  label: string;
  active: boolean;
}

export interface VoiceSession {
  state: VoiceState;
  statusLabel: string;
  /** The employee this session is with. */
  employeeName: string;
  /** Live interim transcript while listening (or the last thing heard). */
  transcript: string;
  /** The full conversation, newest last — the same cache as the workspace. */
  messages: ConversationMessage[];
  /** The action awaiting the user's yes/no, or null. */
  pendingAction: PendingAction | null;
  /** Background work in progress (real task creation), or null. */
  execution: ExecutionStatus | null;
  mode: InteractionMode;
  error: string | null;
  micActive: boolean;
  speaking: boolean;
  speechInputSupported: boolean;
  speechOutputSupported: boolean;
  isLoading: boolean;
  isError: boolean;
  // --- controls -------------------------------------------------------
  startListening: () => void;
  stopListening: () => void;
  submitText: (text: string) => void;
  approve: () => void;
  deny: () => void;
  stopSpeaking: () => void;
  setMode: (mode: InteractionMode) => void;
  toggleOutput: () => void;
  end: () => void;
}

const MEDIUM = "MEDIUM" as const;
const MANUAL = "MANUAL" as const;

export function useVoiceSession(conversationId: string): VoiceSession {
  const queryClient = useQueryClient();
  const speechIn = useSpeechInput();
  const speechOut = useSpeechOutput();

  const [state, dispatch] = useReducer(voiceReducer, INITIAL_VOICE_STATE);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [execution, setExecution] = useState<ExecutionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [desiredMode, setDesiredMode] = useState<InteractionMode>(DEFAULT_INTERACTION_MODE);

  // What the browser can actually do decides the real mode (voice-disabled
  // fallback): a desired voice channel degrades to text when unsupported.
  const mode = useMemo(
    () =>
      resolveMode(desiredMode, {
        speechInput: speechIn.supported,
        speechOutput: speechOut.supported,
      }),
    [desiredMode, speechIn.supported, speechOut.supported]
  );

  // Refs so effects and async callbacks read live values without stale closures.
  const stateRef = useRef(state);
  const modeRef = useRef(mode);
  const detectedRef = useRef<PendingAction | null>(null);
  const startedRef = useRef(false);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  const detail = useQuery({
    queryKey: conversationKeys.detail(conversationId),
    queryFn: () => conversationService.detail(conversationId),
    staleTime: 30_000,
    retry: false,
  });
  const messagesQuery = useQuery({
    queryKey: conversationKeys.messages(conversationId),
    queryFn: () => conversationService.messages(conversationId),
    staleTime: 30_000,
    retry: false,
  });

  const emit = useCallback((type: VoiceEvent["type"]) => dispatch({ type } as VoiceEvent), []);

  // --- speech out: speak, then advance ---------------------------------

  const advanceAfterSpeaking = useCallback(() => {
    // completed → returning, then reopen the mic for a voice input mode.
    emit("SPEAK_END");
    emit("CONTINUE");
    if (shouldAutoListen(modeRef.current) && speechIn.supported) {
      emit("MIC_OPEN");
      speechIn.start();
    }
  }, [emit, speechIn]);

  const speakThenAdvance = useCallback(
    (text: string) => {
      if (shouldSpeakReplies(modeRef.current) && speechOut.supported && text.trim()) {
        speechOut.speak(text); // completion is picked up by the effect below
      } else {
        // Text output (or no synthesis): no audio to wait on — hand back now.
        advanceAfterSpeaking();
      }
    },
    [speechOut, advanceAfterSpeaking]
  );

  // Detect the end of a spoken reply (speaking true → false) and advance.
  const prevSpeaking = useRef(false);
  useEffect(() => {
    if (prevSpeaking.current && !speechOut.speaking && stateRef.current === "speaking") {
      advanceAfterSpeaking();
    }
    prevSpeaking.current = speechOut.speaking;
  }, [speechOut.speaking, advanceAfterSpeaking]);

  // --- the turn: conversation → memory → AI employee -------------------

  const handleReply = useCallback(
    (assistant: ConversationMessage) => {
      const action = detectedRef.current;
      if (action) {
        // An action was asked for: raise the confirmation gate and let the
        // assistant speak its reply (which explains it wants a yes) alongside it.
        emit("PLAN_ACTION"); // thinking → planning
        emit("PLAN_ACTION"); // planning → waiting_permission
        setPendingAction(action);
        if (shouldSpeakReplies(modeRef.current) && speechOut.supported) {
          speechOut.speak(assistant.content);
        }
      } else {
        emit("SPEAK"); // thinking → speaking
        speakThenAdvance(assistant.content);
      }
    },
    [emit, speechOut, speakThenAdvance]
  );

  const send = useMutation({
    mutationFn: (vars: { content: string; channel: "text" | "voice" }) =>
      conversationService.send(conversationId, {
        content: vars.content,
        attachments: [],
        channel: vars.channel,
      }),
    onSuccess: (receipt) => {
      // Land both messages into the shared thread cache — same key the
      // conversation workspace reads, so nothing is duplicated.
      queryClient.setQueryData<ConversationMessage[]>(
        conversationKeys.messages(conversationId),
        (thread) => {
          const rest = (thread ?? []).filter(
            (m) => m.id !== receipt.userMessage.id && m.id !== receipt.assistantMessage.id
          );
          return [...rest, receipt.userMessage, receipt.assistantMessage];
        }
      );
      void queryClient.invalidateQueries({ queryKey: conversationKeys.lists });
      handleReply(receipt.assistantMessage);
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "The assistant couldn't respond.");
      emit("ERROR");
    },
  });

  const submit = useCallback(
    (text: string, channel: "text" | "voice") => {
      const content = text.trim();
      if (!content || send.isPending) return;
      setError(null);
      detectedRef.current = detectAction(content);
      emit("TRANSCRIPT_FINAL"); // listening → understanding
      emit("THINK"); // understanding → thinking
      send.mutate({ content, channel });
    },
    [emit, send]
  );

  // --- speech in: listen, then submit the final transcript -------------

  const prevListening = useRef(false);
  useEffect(() => {
    if (prevListening.current && !speechIn.listening && stateRef.current === "listening") {
      const text = speechIn.transcript.trim();
      if (text) submit(text, "voice");
    }
    prevListening.current = speechIn.listening;
  }, [speechIn.listening, speechIn.transcript, submit]);

  // --- executor seam: an approved action creates a real task -----------

  const createTask = useMutation({
    mutationFn: (name: string) =>
      taskService.create({
        id: null,
        name,
        description: "Created from a voice session.",
        priority: MEDIUM,
        executionMode: MANUAL,
        workflowId: null,
        employeeId: null,
      }),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: taskKeys.lists });
      setExecution({ label: `Created ${task.businessId}`, active: false });
      emit("EXECUTE_DONE");
      speakThenAdvance(`Done — I've created a task to ${lower(pendingAction?.label)}.`);
      setPendingAction(null);
    },
    onError: () => {
      setExecution({ label: "That couldn't be completed just now.", active: false });
      emit("EXECUTE_DONE");
      speakThenAdvance("I couldn't complete that just now. Your message is saved.");
      setPendingAction(null);
    },
  });

  // --- controls --------------------------------------------------------

  const startListening = useCallback(() => {
    if (!speechIn.supported) return;
    setError(null);
    emit("MIC_OPEN");
    speechIn.start();
  }, [emit, speechIn]);

  const stopListening = useCallback(() => {
    speechIn.stop();
    // The listening→submit effect fires when recognition ends with a transcript.
  }, [speechIn]);

  const submitText = useCallback((text: string) => submit(text, "text"), [submit]);

  const approve = useCallback(() => {
    const action = pendingAction;
    if (!action) return;
    emit("APPROVE"); // waiting_permission → executing
    setExecution({ label: `${action.label}…`, active: true });
    createTask.mutate(`${action.label}: ${action.summary}`);
  }, [emit, pendingAction, createTask]);

  const deny = useCallback(() => {
    setPendingAction(null);
    emit("DENY"); // waiting_permission → speaking
    speakThenAdvance("Okay, I won't do that. Anything else?");
  }, [emit, speakThenAdvance]);

  const stopSpeaking = useCallback(() => {
    speechOut.cancel();
    if (stateRef.current === "speaking") advanceAfterSpeaking();
  }, [speechOut, advanceAfterSpeaking]);

  const setMode = useCallback((next: InteractionMode) => setDesiredMode(next), []);
  const toggleOutput = useCallback(
    () =>
      setDesiredMode((m) => ({ ...m, output: m.output === "voice" ? "text" : "voice" })),
    []
  );

  const end = useCallback(() => {
    speechIn.stop();
    speechOut.cancel();
    emit("STOP");
  }, [speechIn, speechOut, emit]);

  // --- start the session once the conversation is ready ----------------

  useEffect(() => {
    if (startedRef.current || !detail.data) return;
    startedRef.current = true;
    emit("CONNECT");
    emit("CONNECTED");
    if (shouldAutoListen(modeRef.current) && speechIn.supported) {
      emit("MIC_OPEN");
      speechIn.start();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once when ready
  }, [detail.data]);

  // Stop the microphone and any speech when the session unmounts.
  useEffect(() => {
    return () => {
      speechIn.stop();
      speechOut.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- teardown only
  }, []);

  return {
    state,
    statusLabel: pendingAction ? "Waiting for your confirmation" : VOICE_STATE_LABEL[state],
    employeeName: detail.data?.employee.employeeName ?? "Assistant",
    transcript: speechIn.transcript,
    messages: messagesQuery.data ?? [],
    pendingAction,
    execution,
    mode,
    error: error ?? (speechIn.error ?? null),
    micActive: isMicActive(state) && speechIn.listening,
    speaking: speechOut.speaking,
    speechInputSupported: speechIn.supported,
    speechOutputSupported: speechOut.supported,
    isLoading: detail.isPending || messagesQuery.isPending,
    isError: detail.isError,
    startListening,
    stopListening,
    submitText,
    approve,
    deny,
    stopSpeaking,
    setMode,
    toggleOutput,
    end,
  };
}

/** Lower-case a label for a natural spoken sentence, e.g. "Send email" → "send email". */
function lower(label: string | undefined): string {
  return (label ?? "do that").toLowerCase();
}
