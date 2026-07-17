"use client";

import { useEffect, useMemo, useState } from "react";

import { ActivityTimeline, type AuditEventView, type FeedbackReason } from "./activity-timeline";
import { CrickOpsApiClient } from "../lib/api-client";

export function ActivityTimelineLive() {
  const [events, setEvents] = useState<AuditEventView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const client = useMemo(() => new CrickOpsApiClient(), []);

  async function refresh() {
    try {
      const page = await client.getAuditEvents();
      setEvents(page.items);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Activity could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  const feedbackEvent = events.find((event) => typeof event.structured_payload?.draft_id === "string");
  const draftId = feedbackEvent?.structured_payload?.draft_id;
  const feedbackTarget = typeof draftId === "string"
    ? { draftId, label: "the selected schedule draft" }
    : undefined;

  if (loading) return <div className="activity-loading" role="status">Loading organizer history…</div>;
  if (error) return <div className="error-banner" role="alert">{error}</div>;

  async function saveFeedback(reason: FeedbackReason, note?: string) {
    if (!feedbackTarget) return;
    await client.recordScheduleFeedback(feedbackTarget.draftId, reason, note);
    await refresh();
  }

  return <ActivityTimeline events={events} feedbackTarget={feedbackTarget} onFeedback={saveFeedback} />;
}
