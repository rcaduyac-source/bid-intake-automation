import ReviewCard from './ReviewCard';
import { tShort } from '../utils';

function decisionColor(dec) {
  return dec === 'GO' ? 'green' : dec === 'NO-GO' ? 'red' : 'amber';
}

export default function ReviewTab({ reviews, onDecide }) {
  const open = reviews.filter((r) => r.status === 'open');
  const done = reviews.filter((r) => r.status !== 'open');

  return (
    <section>
      <div className="card" style={{ background: 'none', border: 'none', boxShadow: 'none', padding: '0 2px 6px' }}>
        <h3>Waiting on you</h3>
        <p className="lead">
          The AI has read the documents and prepared its analysis. Confirm or correct it, then make
          the call.
        </p>
      </div>

      {open.length ? (
        open.map((r) => <ReviewCard key={r.id} review={r} open onDecide={onDecide} />)
      ) : (
        <div className="empty">
          <b>Nothing waiting on you</b>
          New review tasks appear here as soon as the AI finishes analyzing a bid.
        </div>
      )}

      {done.length > 0 && (
        <div className="card">
          <h3>Completed reviews</h3>
          {done.map((r) => {
            const c = decisionColor(r.decision);
            return (
              <div key={r.id} className="evt">
                <span className="etag" style={{ background: `var(--${c}-bg)`, color: `var(--${c})` }}>
                  {r.decision || '—'}
                </span>
                <b>{r.sol_number}</b> <span className="muted">{r.notes || ''}</span>
                <span className="ewhen">{tShort(r.completed_at)}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
