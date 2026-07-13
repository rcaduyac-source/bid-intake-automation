import { OPP_STATUS } from '../constants';
import { daysTo } from '../utils';

export default function OpportunityCard({ opp, reviews, onOpen }) {
  const o = opp;
  const st = OPP_STATUS[o.status] || { cls: 'gray', text: o.status, border: 'var(--gray)' };
  const d = daysTo(o.due_date);

  const dueCls = d < 0 ? 'urgent' : d <= 7 ? 'urgent' : d <= 14 ? 'soon' : 'ok';
  const rev = reviews.find((r) => r.opp_id === o.id && r.analysis);
  const rec = rev && rev.analysis && rev.analysis.recommendation;

  return (
    <div className="oppcard" style={{ '--st': st.border }} onClick={() => onOpen(o.id)}>
      <div className="eyebrow">{o.sol_number}</div>
      <h4>{o.title || ''}</h4>
      <div className="agency">{o.agency || 'Agency not stated'}</div>
      <div className="opprow">
        {o.due_date ? (
          <span className={`due ${dueCls}`}>
            ⏰ {d < 0 ? 'PAST DUE' : 'due in ' + d + ' days'} · {o.due_date} {o.due_tz || ''}
          </span>
        ) : (
          <span className="due tbd">⏰ deadline TBD</span>
        )}
        <span className={`pill ${st.cls}`}>{st.text}</span>
        {rec && (
          <span className={`pill ${rec === 'GO' ? 'green' : rec === 'NO-GO' ? 'red' : 'amber'}`}>
            AI: {rec}
          </span>
        )}
        <span className="pill gray">📄 {o.chunk_count} excerpts</span>
      </div>
    </div>
  );
}
