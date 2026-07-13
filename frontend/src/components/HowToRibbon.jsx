import { HOWTO_STEPS } from '../constants';

export default function HowToRibbon() {
  return (
    <div className="howto">
      {HOWTO_STEPS.map((s, i) => (
        <span key={i} style={{ display: 'contents' }}>
          <span className="hstep">
            <span className="hic" style={{ background: s.bg }}>{s.icon}</span>
            {s.label}
          </span>
          {i < HOWTO_STEPS.length - 1 && <span className="arr">→</span>}
        </span>
      ))}
    </div>
  );
}
