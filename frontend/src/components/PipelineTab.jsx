import HowToRibbon from './HowToRibbon';
import MailCard from './MailCard';

export default function PipelineTab({ emails, scenarios, onSimulate }) {
  return (
    <section>
      <HowToRibbon />
      <div className="toolbar">
        <b>TRY IT — SEND A SAMPLE:</b>
        <span>
          {Object.entries(scenarios).map(([k, v]) => (
            <button key={k} className="btn" onClick={() => onSimulate(k)} style={{ marginRight: 6 }}>
              {v}
            </button>
          ))}
        </span>
      </div>
      <div>
        {emails.length ? (
          emails.map((e) => <MailCard key={e.id} email={e} />)
        ) : (
          <div className="empty">
            <b>No emails yet</b>
            Click one of the sample buttons above to watch the pipeline work, or submit your own email.
          </div>
        )}
      </div>
    </section>
  );
}
