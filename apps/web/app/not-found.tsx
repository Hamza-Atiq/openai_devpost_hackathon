import Link from "next/link";

export default function NotFound() {
  return (
    <main className="site-shell">
      <section className="operation-status operation-status-error" aria-labelledby="not-found-title">
        <p className="eyebrow">Boundary not found</p>
        <h1 id="not-found-title">This tournament view is no longer on the board.</h1>
        <p>The link may be outdated, or the guest workspace may have expired.</p>
        <div className="comparison-actions">
          <Link className="primary-action" href="/">Return to CrickOps home</Link>
          <Link className="secondary-action" href="/workspace/setup">Open current workspace</Link>
        </div>
      </section>
    </main>
  );
}
