"use client";

import { useEffect, useState } from "react";

import { CrickOpsApiClient, type SystemModeResponse } from "@/lib/api-client";

export function SystemModePill() {
  const [mode, setMode] = useState<SystemModeResponse | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    let active = true;
    new CrickOpsApiClient().getSystemMode().then(
      (response) => { if (active) setMode(response); },
      () => { if (active) setUnavailable(true); },
    );
    return () => { active = false; };
  }, []);

  return (
    <span className="mode-pill" title={mode?.model ?? undefined} aria-live="polite">
      {mode?.label ?? (unavailable ? "Agent mode unavailable" : "Checking agent mode…")}
    </span>
  );
}
