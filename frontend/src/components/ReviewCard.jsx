import { useState } from 'react';
import { daysTo } from '../utils';

function List({ arr, color }) {
  const items = arr || [];
  if (!items.length) {
    return (
      <ul>
        <li style={{ '--dc': '#a8b4c6' }} className="muted">
          none detected
        </li>
      </ul>
    );
  }
  return (
    <ul>
      {items.map((x, i) => (
        <li key={i} style={{ '--dc': color }}>
          {x.text}
          <span className="cite">source [{x.cite}]</span>
        </li>
      ))}
    </ul>
  );
}

export default function ReviewCard({ review, open, onDecide }) {
  const r = review;
  const a = r.analysis || {};
  const d = daysTo(r.due_date);
  const [notes, setNotes] = useState('');

  return (
    <div className="revcard">
      <div className="revhead">
        <div className="rt">
          <h4>
            {r.sol_number} — {r.title || ''}
          </h4>
          <div className="meta">
            Due {r.due_date || 'TBD'} {r.due_tz || ''}
            {d !== null && (
              <>
                {' · '}
                <b style={{ color: d <= 7 ? 'var(--red)' : 'inherit' }}>
                  {d < 0 ? 'past due' : d + ' days left'}
                </b>
              </>
            )}
          </div>
        </div>
        <div className={`recbanner ${a.recommendation || 'CONDITIONAL'}`}>
          <span>AI recommends</span>
          <b>{a.recommendation || '—'}</b>
        </div>
      </div>

      <div className="revbody">
        <div>
          <div className="sect">
            <h5>
              <span className="sic" style={{ background: 'var(--blue-bg)' }}>📋</span>
              What they're asking for
            </h5>
            <div className="scopebox">{a.scope || '—'}</div>
          </div>
          <div className="sect">
            <h5>
              <span className="sic" style={{ background: 'var(--indigo-bg)' }}>✔️</span>
              Key requirements
            </h5>
            <List arr={a.requirements} color="#5548d9" />
          </div>
        </div>
        <div>
          <div className="sect">
            <h5>
              <span className="sic" style={{ background: 'var(--red-bg)' }}>⚠️</span>
              Risks to weigh
            </h5>
            <List arr={a.risks} color="#d3372c" />
          </div>
          <div className="sect">
            <h5>
              <span className="sic" style={{ background: 'var(--teal-bg)' }}>🔎</span>
              Cited findings
            </h5>
            <List arr={a.findings} color="#0e8f7e" />
          </div>
          <div className="sect">
            <h5>
              <span className="sic" style={{ background: 'var(--amber-bg)' }}>💭</span>
              Why the AI says {a.recommendation || 'this'}
            </h5>
            <div className="note">{a.rationale || ''}</div>
          </div>
        </div>
      </div>

      {open && (
        <div className="decide">
          <h5>Your call — this decision is logged and updates the opportunity</h5>
          <textarea
            rows="2"
            placeholder="Optional: notes, or corrections to anything the AI got wrong…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 10, marginTop: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <button className="btn go" onClick={() => onDecide(r.id, 'GO', notes)}>
              ✓ &nbsp;GO — pursue this bid
            </button>
            <button className="btn cond" onClick={() => onDecide(r.id, 'CONDITIONAL', notes)}>
              ◐ &nbsp;Conditional
            </button>
            <button className="btn nogo" onClick={() => onDecide(r.id, 'NO-GO', notes)}>
              ✕ &nbsp;No-Go
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
