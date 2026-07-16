export function DirectorPanel() {
  return (
    <aside className="director-panel" aria-label="Tournament Director">
      <div className="director-heading">
        <span className="status-dot" aria-hidden="true" />
        <div>
          <p className="eyebrow">Tournament Director</p>
          <p className="director-status">Deterministic mode ready</p>
        </div>
      </div>
      <div className="director-message">
        <p>
          I’ll help interpret goals, explain trade-offs, and guide recovery. Confirmed
          decisions always remain visible in the workspace.
        </p>
      </div>
      <button className="quiet-button" type="button" aria-expanded="false">
        Open Director chat
      </button>
    </aside>
  );
}

