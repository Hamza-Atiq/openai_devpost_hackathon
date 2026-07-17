import Link from "next/link";
import type { ReactNode } from "react";

type WorkspaceShellProps = {
  children: ReactNode;
  director: ReactNode;
};

export function WorkspaceShell({ children, director }: WorkspaceShellProps) {
  return (
    <div className="workspace-shell">
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <header className="topbar">
        <Link className="brand" href="/" aria-label="CrickOps AI home">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span>CrickOps <b>AI</b></span>
        </Link>
        <nav aria-label="Workspace navigation">
          <Link href="/workspace/setup">Setup</Link>
          <Link href="/workspace/options">Options</Link>
          <Link href="/workspace/schedule">Schedule</Link>
          <Link href="/workspace/activity">Activity</Link>
        </nav>
        <span className="mode-pill">Deterministic mode</span>
      </header>
      <div className="workspace-grid">
        <main id="main-content" tabIndex={-1}>{children}</main>
        {director}
      </div>
    </div>
  );
}
