"use client";

import { useState } from "react";

export type FeedbackReason =
  | "weather_preference"
  | "unfair_rest_distribution"
  | "venue_preference"
  | "unsuitable_time_slot"
  | "rivalry_requirement"
  | "travel_concern"
  | "other";

export type AuditEventView = {
  id: string;
  actor_type: string;
  event_type: string;
  summary: string;
  occurred_at: string;
  structured_payload?: Record<string, unknown>;
};

type Props = {
  events: AuditEventView[];
  feedbackTarget?: { draftId: string; label: string };
  onFeedback?: (reason: FeedbackReason, note?: string) => Promise<void>;
};

const eventLabels: Record<string, string> = {
  constraints_confirmed: "Constraints confirmed",
  schedule_options_generated: "Schedule options validated",
  schedule_feedback_recorded: "Decision feedback recorded",
  schedule_approved: "Official schedule approved",
  schedule_rejected: "Draft rejected",
  schedule_restored: "Earlier schedule restored",
  disruption_declared: "Disruption declared",
  repair_generated: "Repair option generated",
};

const reasonOptions: Array<{ value: FeedbackReason; label: string }> = [
  { value: "weather_preference", label: "Weather preference" },
  { value: "unfair_rest_distribution", label: "Unfair rest distribution" },
  { value: "venue_preference", label: "Venue preference" },
  { value: "unsuitable_time_slot", label: "Unsuitable time slot" },
  { value: "rivalry_requirement", label: "Rivalry requirement" },
  { value: "travel_concern", label: "Travel concern" },
  { value: "other", label: "Other" },
];

const hiddenPayloadKeys = new Set([
  "raw_prompt",
  "hidden_reasoning",
  "stack_trace",
  "trace_id",
  "tool_call",
  "token",
]);

function payloadDetails(payload: Record<string, unknown> | undefined) {
  return Object.entries(payload ?? {}).filter(
    ([key, value]) => !hiddenPayloadKeys.has(key) && value !== null && value !== undefined,
  );
}

function readableKey(key: string) {
  return key.replaceAll("_", " ");
}

export function ActivityTimeline({ events, feedbackTarget, onFeedback }: Props) {
  const [reason, setReason] = useState<FeedbackReason>("weather_preference");
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submitFeedback() {
    if (!onFeedback) return;
    setPending(true);
    setStatus(null);
    try {
      await onFeedback(reason, note.trim() || undefined);
      setStatus("Feedback saved to this tournament workspace.");
      setNote("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Feedback could not be saved.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="activity-studio" aria-labelledby="activity-title">
      <header className="activity-head">
        <div>
          <p className="eyebrow">Organizer audit timeline</p>
          <h1 id="activity-title">Operational history</h1>
          <p>Material decisions, deterministic evidence, and official schedule changes—without internal prompts or diagnostics.</p>
        </div>
        <div className="activity-seal"><strong>{events.length}</strong><span>recorded events</span></div>
      </header>

      {events.length === 0 ? (
        <div className="activity-empty"><strong>No material decisions recorded yet</strong><span>Confirmed setup, generated options, approvals, and repairs will appear here.</span></div>
      ) : (
        <ol className="activity-ledger">
          {events.map((event, index) => {
            const details = payloadDetails(event.structured_payload);
            return (
              <li key={event.id} className={`activity-event event-${event.actor_type}`}>
                <div className="activity-marker" aria-hidden="true"><span>{String(events.length - index).padStart(2, "0")}</span></div>
                <article>
                  <header>
                    <div><span>{eventLabels[event.event_type] ?? readableKey(event.event_type)}</span><small>{event.actor_type === "system" ? "Deterministic service" : "Organizer action"}</small></div>
                    <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time>
                  </header>
                  <p>{event.summary}</p>
                  {details.length > 0 && <dl>{details.map(([key, value]) => <div key={key}><dt>{readableKey(key)}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl>}
                </article>
              </li>
            );
          })}
        </ol>
      )}

      {feedbackTarget && (
        <form className="feedback-desk" onSubmit={(event) => { event.preventDefault(); void submitFeedback(); }}>
          <div><p className="eyebrow">Workspace memory</p><h2>Optional decision feedback</h2><p>Tell CrickOps why you changed or rejected {feedbackTarget.label}. This stays with the current tournament and helps avoid repeating unsuitable recommendations.</p></div>
          <label>Reason<select value={reason} onChange={(event) => setReason(event.target.value as FeedbackReason)}>{reasonOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label>Context <span>(optional)</span><textarea maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add concise operational context" /></label>
          <button className="primary-action" type="submit" disabled={pending || !onFeedback}>{pending ? "Saving…" : "Save workspace feedback"}</button>
          {status && <p className="feedback-status" role="status">{status}</p>}
        </form>
      )}
    </section>
  );
}
