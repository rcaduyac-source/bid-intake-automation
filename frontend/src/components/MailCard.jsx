import { OUTCOMES, STAGES } from '../constants';
import { tShort } from '../utils';

export default function MailCard({ email }) {
  const e = email;
  const running = ['received', 'routed'].includes(e.status);
  const oc =
    e.status === 'error'
      ? { cls: 'red', icon: '✕', text: 'Pipeline error' }
      : running
        ? { cls: 'blue', icon: '…', text: 'Processing' }
        : OUTCOMES[e.classification] || { cls: 'gray', icon: '…', text: e.status };

  const byStage = {};
  e.stages.forEach((s) => {
    byStage[s.stage] = s;
  });

  const last = e.stages[e.stages.length - 1];

  return (
    <div className="mailcard">
      <div className="mailtop">
        <div className="who">
          <div className="subj">{e.subject}</div>
          <div className="meta">
            from {e.from_addr} · {tShort(e.received_at)}
          </div>
          {e.attachments.map((a) => (
            <span
              key={a.id}
              className={`filetag ${a.status === 'rejected' ? 'bad' : ''}`}
              title={a.note || ''}
            >
              📎 {a.filename}
              {a.status === 'rejected' ? ' · rejected' : ''}
            </span>
          ))}
        </div>
        <span className={`outcome ${oc.cls} ${running ? 'pulse' : ''}`}>
          {oc.icon} {oc.text}{' '}
          {e.confidence != null && <small>{(e.confidence * 100).toFixed(0)}% confident</small>}
        </span>
      </div>

      <div className="tracker">
        {STAGES.map((st, i) => {
          const hit = st.match.map((m) => byStage[m]).find(Boolean);
          const cls = hit ? (hit.status === 'error' ? 'error' : 'done') : '';
          const mark = hit ? (hit.status === 'error' ? '✕' : '✓') : i + 1;
          return (
            <div
              key={i}
              className={`tstep ${cls}`}
              style={{ '--sc': st.c }}
              title={hit ? hit.detail : 'not reached'}
            >
              <div className="tdot">{mark}</div>
              <div className="tlbl">{st.lbl}</div>
            </div>
          );
        })}
      </div>

      {last && (
        <div className="lastdetail">
          <b>{last.stage}</b>
          <span>{last.detail}</span>
        </div>
      )}
      {e.error && (
        <div className="lastdetail" style={{ color: 'var(--red)' }}>
          <b>Error</b>
          <span>{e.error}</span>
        </div>
      )}
    </div>
  );
}
