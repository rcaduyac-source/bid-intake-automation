const TABS = [
  { key: 'pipeline', label: '📥 Incoming Emails' },
  { key: 'opps', label: '📁 Opportunities', count: 'oppCnt' },
  { key: 'review', label: '✅ Needs Your Review', count: 'revCnt' },
  { key: 'ops', label: '💓 System Health', count: 'excCnt' },
];

function Count({ n }) {
  if (!n) return null;
  return <span className="cnt">{n}</span>;
}

export default function Header({ ops, counts, tab, onTab, onOpenIntake }) {
  const live = ops.ai_mode === 'openai';
  const healthy = ops.errors_24h === 0;
  const counter = { oppCnt: counts.opps, revCnt: counts.reviews, excCnt: counts.exceptions };

  return (
    <header>
      <div className="hrow">
        <div className="brand">🎯</div>
        <div>
          <h1>BYRDSON SERVICES — BID INTAKE</h1>
          <div className="sub">Every bid email captured, analyzed, and put in front of a human.</div>
        </div>
        <div className="spacer" />
        <span className={'hchip' + (live ? '' : ' warn')}>
          <span className="dot" />
          {live ? `AI: OpenAI · ${ops.ai_model}` : 'AI: demo mode (no API key yet)'}
        </span>
        <span className={'hchip' + (healthy ? '' : ' warn')}>
          <span className="dot" />
          {healthy ? 'System healthy' : `${ops.errors_24h} errors (24h)`}
        </span>
        <button className="btn ghost" onClick={onOpenIntake}>＋ Submit an email</button>
      </div>
      <nav>
        {TABS.map((t) => (
          <button
            key={t.key}
            data-tab={t.key}
            className={tab === t.key ? 'active' : ''}
            onClick={() => onTab(t.key)}
          >
            {t.label}
            {t.count ? <Count n={counter[t.count]} /> : null}
          </button>
        ))}
      </nav>
    </header>
  );
}
