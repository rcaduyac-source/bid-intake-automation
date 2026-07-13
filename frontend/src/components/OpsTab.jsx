import { NTYPE } from '../constants';
import { tShort } from '../utils';

export default function OpsTab({ state, onResolveExc }) {
  const { ops } = state;
  const tiles = [
    ['📧', 'Emails seen (24h)', ops.emails_24h, false],
    ['⚙️', 'Pipeline steps run (24h)', ops.executions_24h, false],
    ['🛑', 'Errors (24h)', ops.errors_24h, ops.errors_24h > 0],
    ['⚠️', 'Open exceptions', ops.open_exceptions, ops.open_exceptions > 0],
    ['✅', 'Awaiting review', ops.open_reviews, false],
    ['📁', 'Opportunities', state.opportunities.length, false],
  ];

  const openExc = state.exceptions.filter((x) => x.status === 'open');

  return (
    <section>
      <div className="tiles">
        {tiles.map(([i, l, v, a], idx) => (
          <div key={idx} className={`tile ${a ? 'alert' : ''}`}>
            <div className="tic">{i}</div>
            <div>
              <b>{v}</b>
              <span>{l}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="two">
        <div className="card">
          <h3>⚠️ Open exceptions</h3>
          <p className="lead">Things the system wasn't sure about — each needs a quick human look.</p>
          {openExc.length ? (
            openExc.map((x) => (
              <div key={x.id} className="evt">
                <span className="etag" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
                  open
                </span>
                <span style={{ flex: 1 }}>{x.reason}</span>
                <button
                  className="btn"
                  style={{ padding: '3px 11px', fontSize: '10.5px' }}
                  onClick={() => onResolveExc(x.id)}
                >
                  Resolve
                </button>
              </div>
            ))
          ) : (
            <div className="muted" style={{ fontSize: '12.5px' }}>
              None — all clear 🎉
            </div>
          )}
        </div>

        <div className="card">
          <h3>🔔 Notifications</h3>
          <p className="lead">What the system would send to the team (email/Slack in production).</p>
          {state.notifications.length ? (
            state.notifications.slice(0, 12).map((n) => {
              const t = NTYPE[n.type] || { cls: 'gray', icon: '•' };
              return (
                <div key={n.id} className="evt">
                  <span className="etag" style={{ background: `var(--${t.cls}-bg)`, color: `var(--${t.cls})` }}>
                    {t.icon} {n.type}
                  </span>
                  <span style={{ flex: 1 }}>{n.message}</span>
                  <span className="ewhen">{tShort(n.created_at)}</span>
                </div>
              );
            })
          ) : (
            <div className="muted" style={{ fontSize: '12.5px' }}>
              None yet.
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h3>🧾 Audit log</h3>
        <p className="lead">Every action, logged. Nothing happens silently.</p>
        <table>
          <thead>
            <tr>
              <th style={{ width: 150 }}>When (UTC)</th>
              <th style={{ width: 90 }}>Actor</th>
              <th style={{ width: 160 }}>Action</th>
              <th style={{ width: 110 }}>Entity</th>
              <th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {state.audit.map((a) => (
              <tr key={a.id}>
                <td className="muted" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {a.created_at.replace('T', ' ').replace('Z', '')}
                </td>
                <td>
                  <b>{a.actor}</b>
                </td>
                <td>{a.action.replace(/_/g, ' ')}</td>
                <td className="muted">{a.entity}</td>
                <td className="muted">{a.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
