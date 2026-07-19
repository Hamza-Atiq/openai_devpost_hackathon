import type { OfficialScheduleVersion } from "@/lib/api-client";

export function ScheduleVersionBrowser({ versions, selectedId, currentId, pending = false, onSelect }: {
  versions: OfficialScheduleVersion[];
  selectedId: string;
  currentId: string;
  pending?: boolean;
  onSelect: (versionId: string) => void;
}) {
  if (versions.length < 2) return null;
  return (
    <nav className="version-history" aria-label="Browse official history">
      <div><p className="eyebrow">Immutable versions</p><h2>Browse official history</h2><p>Viewing an earlier version never restores or changes it.</p></div>
      <ul>{versions.map((version) => {
        const current = version.version_id === currentId;
        return <li key={version.version_id}><span><strong>Version {version.version_number} · {current ? "current official" : "superseded"}</strong><small>{new Date(version.approved_at).toLocaleString()}</small></span><button className="secondary-action" type="button" aria-pressed={selectedId === version.version_id} disabled={pending || selectedId === version.version_id} onClick={() => onSelect(version.version_id)}>{selectedId === version.version_id ? "Viewing" : "View version"}</button></li>;
      })}</ul>
    </nav>
  );
}
