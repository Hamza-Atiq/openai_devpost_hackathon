import { SampleChooser } from "@/components/sample-chooser";

export default function Home() {
  return (
    <main className="entry-page">
      <header className="entry-header">
        <a className="brand" href="#main-entry" aria-label="CrickOps AI home">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span>CrickOps <b>AI</b></span>
        </a>
        <span className="entry-tag">Global cricket operations copilot</span>
      </header>
      <section className="entry-hero" id="main-entry">
        <div>
          <p className="eyebrow">Plan cleanly. Recover calmly.</p>
          <h1>The tournament control room before the first ball.</h1>
          <p className="hero-copy">
            Generate three independently validated schedules, understand weather and
            fairness trade-offs, then repair disruption with the fewest possible changes.
          </p>
        </div>
        <div className="control-preview" aria-label="Version 1 competition structure">
          <div className="preview-header">
            <div><span className="status-dot" aria-hidden="true" /><b>Planning brief</b></div>
            <span>Demo ready</span>
          </div>
          <div className="preview-metrics">
            <div><strong>15</strong><span>fixtures</span></div>
            <div><strong>03</strong><span>profiles</span></div>
            <div><strong>01</strong><span>official baseline</span></div>
          </div>
          <div className="venue-lines">
            <div><span>Venue 01</span><i /><b>Group stage</b><i /><b>Semifinals</b></div>
            <div><span>Venue 02</span><i /><b>12 + 2 + 1</b><i /><b>Final</b></div>
          </div>
          <div className="preview-foot">
            <span>Weather guidance</span><b>Forecast based</b>
            <span>Validation</span><b>Independent</b>
          </div>
        </div>
      </section>
      <SampleChooser />
    </main>
  );
}
