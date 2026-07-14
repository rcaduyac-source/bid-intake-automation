import { useEffect, useRef, useState } from 'react';
import { OPP_STATUS, EVT_STYLE } from '../constants';
import { daysTo, tShort } from '../utils';

function OppBody({ opp, onApprove, onAsk }) {
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState(null);
  const [asking, setAsking] = useState(false);

  const st = OPP_STATUS[opp.status] || { cls: 'gray', text: opp.status };
  const an = opp.analyses && opp.analyses[0] ? opp.analyses[0] : null;
  const d = daysTo(opp.due_date);

  const ask = async () => {
    const q = question.trim();
    if (!q || !onAsk) return;
    setAsking(true);
    try {
      const res = await onAsk(opp.id, q);
      setResult(res);
    } catch (err) {
      setResult({ answer: `Ask failed: ${err.message}`, sources: [] });
    } finally {
      setAsking(false);
    }
  };

  return (
    <>
      <div style={{ display: 'flex', gap: 9, flexWrap: 'wrap', alignItems: 'center', marginBottom: 14 }}>
        <span className={`pill ${st.cls}`}>{st.text}</span>
        {opp.due_date ? (
          <span className={`due ${d <= 7 ? 'urgent' : d <= 14 ? 'soon' : 'ok'}`}>
            ⏰ due {opp.due_date} {opp.due_tz || ''} ({d < 0 ? 'past due' : d + ' days'})
          </span>
        ) : (
          <span className="due tbd">⏰ deadline TBD</span>
        )}
        {an && (
          <span
            className={`pill ${
              an.payload.recommendation === 'GO'
                ? 'green'
                : an.payload.recommendation === 'NO-GO'
                  ? 'red'
                  : 'amber'
            }`}
          >
            AI: {an.payload.recommendation || '—'} ({(an.status || '').replace('_', ' ')})
          </span>
        )}
        <span className="pill gray">{opp.agency || 'agency not stated'}</span>
        <div style={{ flex: 1 }} />
        {['go_approved', 'conditional'].includes(opp.status) && (
          <button className="btn primary" onClick={() => onApprove(opp.id)}>
            🚀 Approve to Proceed
          </button>
        )}
      </div>

      <label>Ask the documents anything</label>
      <div style={{ display: 'flex', gap: 9 }}>
        <input
          type="text"
          placeholder="e.g. What bonding is required? When is the pre-bid conference?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()}
        />
        <button className="btn primary" onClick={ask} disabled={asking}>
          {asking ? '…' : 'Ask'}
        </button>
      </div>
      {result && (
        <>
          <div className="answer">{result.answer}</div>
          {result.sources?.length > 0 && (
            <div style={{ marginTop: 6 }}>
              {result.sources.map((s, i) => (
                <span key={i} className="cite">
                  [{s.seq}] {s.source} p.{s.page}
                </span>
              ))}
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 16 }}>
        <label>Timeline & calendar events</label>
        {(opp.events || []).length ? (
          opp.events.map((e) => {
            const s = EVT_STYLE[e.type] || ['gray', '•'];
            return (
              <div key={e.id} className="evt">
                <span className="etag" style={{ background: `var(--${s[0]}-bg)`, color: `var(--${s[0]})` }}>
                  {s[1]} {e.type}
                </span>
                <span style={{ flex: 1 }}>{e.detail}</span>
                <span className="ewhen">{tShort(e.created_at)}</span>
              </div>
            );
          })
        ) : (
          <span className="muted">none</span>
        )}
      </div>

      <div style={{ marginTop: 16 }}>
        <label>Indexed document excerpts ({(opp.chunks || []).length}) — these are the AI's citations</label>
        {(opp.chunks || []).length ? (
          opp.chunks.slice(0, 12).map((c) => (
            <div key={c.id} className="evt">
              <span className="etag" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
                [{c.seq}] p.{c.page}
              </span>
              <span style={{ flex: 1 }}>
                <b style={{ fontSize: '10.5px' }}>{c.source}</b>
                <br />
                <span className="muted">{c.preview}…</span>
              </span>
            </div>
          ))
        ) : (
          <span className="muted">none</span>
        )}
      </div>
    </>
  );
}

export default function OpportunityDialog({ opp, onClose, onApprove, onAsk }) {
  const ref = useRef(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (opp && !dlg.open) dlg.showModal();
    if (!opp && dlg.open) dlg.close();
  }, [opp]);

  return (
    <dialog ref={ref} onClose={onClose}>
      <div className="dlg-head">
        <h2>{opp ? `${opp.sol_number || ''} — ${opp.title || ''}` : 'Opportunity'}</h2>
        <button className="x" onClick={onClose}>✕</button>
      </div>
      <div className="dlg-body">
        {opp && <OppBody key={opp.id} opp={opp} onApprove={onApprove} onAsk={onAsk} />}
      </div>
    </dialog>
  );
}
