"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { GuidedSetup } from "@/components/guided-setup";
import {
  ScheduleGenerationProgress,
  type GenerationStage,
} from "@/components/schedule-generation-progress";
import { ApiProblemError, CrickOpsApiClient } from "@/lib/api-client";
import {
  type SetupSaveState,
  type TournamentSetupSaveInput,
  type TournamentSetupView,
} from "@/lib/setup-contract";

const PENDING_SETUP_KEY = "crickops:pending-setup";
const AUTOSAVE_DELAY_MS = 650;

type PendingSetup = {
  workspaceSetupId: string;
  draft: TournamentSetupSaveInput;
};

function readPendingSetup(): PendingSetup | null {
  try {
    const value = sessionStorage.getItem(PENDING_SETUP_KEY);
    return value ? (JSON.parse(value) as PendingSetup) : null;
  } catch {
    sessionStorage.removeItem(PENDING_SETUP_KEY);
    return null;
  }
}

export function GuidedSetupLive() {
  const router = useRouter();
  const clientRef = useRef<CrickOpsApiClient | null>(null);
  const [setup, setSetup] = useState<TournamentSetupView | null>(null);
  const [saveState, setSaveState] = useState<SetupSaveState>("saved");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<"stale" | null>(null);
  const [generationStage, setGenerationStage] = useState<GenerationStage>("idle");
  const [generationError, setGenerationError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestDraftRef = useRef<TournamentSetupSaveInput | null>(null);
  const saveInFlightRef = useRef(false);

  if (clientRef.current === null) clientRef.current = new CrickOpsApiClient();

  const loadSetup = useCallback(async () => {
    setLoadError(null);
    try {
      const loaded = await clientRef.current!.getTournamentSetup();
      setSetup(loaded);
      setConflict(null);

      const pending = readPendingSetup();
      if (
        pending?.workspaceSetupId === loaded.id &&
        pending.draft.expected_revision === loaded.revision
      ) {
        latestDraftRef.current = pending.draft;
        setSaveState("dirty");
      } else {
        sessionStorage.removeItem(PENDING_SETUP_KEY);
        latestDraftRef.current = null;
        setSaveState("saved");
      }
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "The tournament setup could not be loaded.");
    }
  }, []);

  const flushLatestDraft = useCallback(async () => {
    if (saveInFlightRef.current || !setup || !latestDraftRef.current) return;
    const draftBeingSaved = latestDraftRef.current;
    saveInFlightRef.current = true;
    setSaveState("saving");
    try {
      const saved = await clientRef.current!.saveTournamentSetup(draftBeingSaved);
      const newerDraft = latestDraftRef.current;
      setSetup(saved);
      setConflict(null);

      if (newerDraft === draftBeingSaved) {
        latestDraftRef.current = null;
        sessionStorage.removeItem(PENDING_SETUP_KEY);
        setSaveState("saved");
      } else if (newerDraft) {
        const rebased = { ...newerDraft, expected_revision: saved.revision };
        latestDraftRef.current = rebased;
        sessionStorage.setItem(
          PENDING_SETUP_KEY,
          JSON.stringify({ workspaceSetupId: saved.id, draft: rebased } satisfies PendingSetup),
        );
        setSaveState("dirty");
      }
    } catch (error) {
      if (error instanceof ApiProblemError && error.code === "stale_tournament_revision") {
        setConflict("stale");
      }
      setSaveState("error");
      setLoadError(error instanceof Error ? error.message : "Setup changes could not be saved.");
    } finally {
      saveInFlightRef.current = false;
      if (latestDraftRef.current && latestDraftRef.current !== draftBeingSaved) {
        timerRef.current = setTimeout(() => void flushLatestDraft(), 0);
      }
    }
  }, [setup]);

  useEffect(() => {
    void loadSetup();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [loadSetup]);

  useEffect(() => {
    if (saveState !== "dirty" || !latestDraftRef.current) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => void flushLatestDraft(), AUTOSAVE_DELAY_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [flushLatestDraft, saveState]);

  function handleDraftChange(draft: TournamentSetupSaveInput) {
    if (!setup) return;
    const revisionedDraft = { ...draft, expected_revision: setup.revision };
    latestDraftRef.current = revisionedDraft;
    sessionStorage.setItem(
      PENDING_SETUP_KEY,
      JSON.stringify({ workspaceSetupId: setup.id, draft: revisionedDraft } satisfies PendingSetup),
    );
    setLoadError(null);
    setSaveState("dirty");
    setGenerationStage("idle");
    setGenerationError(null);
  }

  async function confirmAndGenerate(input: Parameters<CrickOpsApiClient["confirmSetup"]>[0]) {
    if (generationStage !== "idle" && generationStage !== "failed") return;
    setGenerationError(null);
    setGenerationStage("confirming");
    try {
      const readiness = await clientRef.current!.confirmSetup(input);
      if (!readiness.ready) {
        throw new Error(readiness.violations.join(" ") || "The saved setup is not feasible yet.");
      }
      setGenerationStage("solving");
      const run = await clientRef.current!.createScheduleRun();
      setGenerationStage("validating");
      const comparison = await clientRef.current!.getScheduleComparison(run.run_id);
      if (comparison.options.length !== 3 || comparison.options.some((option) => !option.validation_valid)) {
        throw new Error("Independent validation did not return three valid scheduling options.");
      }
      setGenerationStage("ready");
      router.push(`/workspace/options?run_id=${encodeURIComponent(run.run_id)}`);
    } catch (error) {
      setGenerationStage("failed");
      setGenerationError(error instanceof Error ? error.message : "Schedule generation failed safely.");
      throw error;
    }
  }

  if (!setup && !loadError) {
    return <div className="operation-status" role="status">Loading your saved tournament setup…</div>;
  }

  if (!setup) {
    return (
      <div className="operation-status operation-status-error" role="alert">
        <strong>We could not load this tournament.</strong>
        <p>{loadError}</p>
        <button type="button" onClick={() => void loadSetup()}>Try again</button>
      </div>
    );
  }

  const pending = latestDraftRef.current;
  const renderedSetup = pending
    ? { ...setup, ...pending, allocation_minutes: pending.match_format_preset === "T10" ? 120 : 240 }
    : setup;

  return (
    <>
      {loadError && saveState === "error" && (
        <div className="operation-status operation-status-error" role="alert">
          <strong>Your edits are safe in this browser, but not yet saved.</strong>
          <p>{loadError}</p>
          <button type="button" onClick={() => void flushLatestDraft()}>Retry save</button>
        </div>
      )}
      <GuidedSetup
        key={`${setup.id}:${setup.revision}`}
        initialSetup={renderedSetup}
        revision={setup.revision}
        saveState={saveState}
        conflict={conflict}
        onDraftChange={handleDraftChange}
        onConfirmAndGenerate={confirmAndGenerate}
      />
      <ScheduleGenerationProgress stage={generationStage} error={generationError} />
    </>
  );
}
