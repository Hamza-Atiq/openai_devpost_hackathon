"use client";

import React, { useState } from "react";
import { AppDialog } from "./app-dialog";

type ScheduleApprovalDialogProps = {
  profileLabel: string;
  pending?: boolean;
  onCancel: () => void;
  onApprove: () => Promise<void> | void;
};

export function ScheduleApprovalDialog({ profileLabel, pending = false, onCancel, onApprove }: ScheduleApprovalDialogProps) {
  const [confirmed, setConfirmed] = useState(false);
  return (
    <AppDialog labelledBy="approval-title" onClose={onCancel} closeDisabled={pending}>
      <div className="approval-dialog-mark" aria-hidden="true">✓</div>
      <div>
        <p className="eyebrow">Official workspace baseline</p>
        <h2 id="approval-title">Approve the {profileLabel} schedule?</h2>
        <p>This creates a timestamped official version inside this guest workspace. It does not publish or distribute fixtures externally.</p>
        <label className="approval-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I reviewed the validated metrics and want this schedule to become official.</label>
        <div className="approval-dialog-actions">
          <button className="secondary-action" type="button" onClick={onCancel}>Keep as draft</button>
          <button className="primary-action" type="button" disabled={!confirmed || pending} onClick={() => void onApprove()}>{pending ? "Approving…" : "Set as official workspace schedule"}</button>
        </div>
      </div>
    </AppDialog>
  );
}
