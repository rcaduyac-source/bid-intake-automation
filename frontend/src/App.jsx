import { useMemo, useState } from 'react';
import demoData from './data/demoData.json';
import { daysTo } from './utils';
import Header from './components/Header';
import AttentionBar from './components/AttentionBar';
import PipelineTab from './components/PipelineTab';
import OpportunitiesTab from './components/OpportunitiesTab';
import ReviewTab from './components/ReviewTab';
import OpsTab from './components/OpsTab';
import OpportunityDialog from './components/OpportunityDialog';
import IntakeDialog from './components/IntakeDialog';
import Flash from './components/Flash';

const clone = (o) => JSON.parse(JSON.stringify(o));
const nowIso = () => new Date().toISOString().slice(0, 19) + 'Z';

export default function App() {
  const [state, setState] = useState(() => clone(demoData.state));
  const [tab, setTab] = useState('pipeline');
  const [flash, setFlash] = useState({ message: '', nonce: 0 });
  const [oppId, setOppId] = useState(null);
  const [intakeOpen, setIntakeOpen] = useState(false);

  const showFlash = (message) => setFlash((f) => ({ message, nonce: f.nonce + 1 }));

  const counts = {
    reviews: state.reviews.filter((r) => r.status === 'open').length,
    exceptions: state.ops.open_exceptions,
    opps: state.opportunities.length,
  };

  const attentionItems = useMemo(() => {
    const openRev = state.reviews.filter((r) => r.status === 'open').length;
    const dueSoon = state.opportunities.filter((o) => {
      const d = daysTo(o.due_date);
      return d !== null && d >= 0 && d <= 14 && !['no_go'].includes(o.status);
    }).length;
    return [
      { n: openRev, l: 'bids waiting for your decision', i: '✅', c: openRev ? 'red' : 'green', tab: 'review' },
      { n: state.ops.open_exceptions, l: 'exceptions to triage', i: '⚠️', c: state.ops.open_exceptions ? 'amber' : 'green', tab: 'ops' },
      { n: dueSoon, l: 'deadlines within 14 days', i: '⏰', c: dueSoon ? 'amber' : 'green', tab: 'opps' },
      { n: state.opportunities.length, l: 'opportunities tracked', i: '📁', c: 'indigo', tab: 'opps' },
    ];
  }, [state]);

  const mergedOpp = useMemo(() => {
    if (oppId == null) return null;
    const det = demoData.opp_details[String(oppId)] || {};
    const live = state.opportunities.find((o) => o.id === oppId) || {};
    return {
      ...det,
      ...live,
      events: det.events || [],
      chunks: det.chunks || [],
      analyses: det.analyses || [],
    };
  }, [oppId, state.opportunities]);

  // ---------- actions ----------
  const handleSimulate = () =>
    showFlash('📧 This is a look-only preview — pipeline wiring comes next.');

  const handleDecide = (taskId, decision, notes) => {
    setState((prev) => {
      const next = clone(prev);
      const r = next.reviews.find((x) => x.id === taskId);
      if (r && r.status === 'open') {
        r.status = 'done';
        r.decision = decision;
        r.notes = notes || '';
        r.completed_at = nowIso();
        const o = next.opportunities.find((op) => op.id === r.opp_id);
        if (o) o.status = decision === 'GO' ? 'go_approved' : decision === 'NO-GO' ? 'no_go' : 'conditional';
        next.ops.open_reviews = next.reviews.filter((x) => x.status === 'open').length;
        next.notifications.unshift({
          id: Date.now(),
          type: 'decision',
          message: `${r.sol_number || ''}: human decision ${decision}`,
          read: 0,
          created_at: nowIso(),
        });
      }
      return next;
    });
    showFlash('Decision recorded: ' + decision);
  };

  const handleResolveExc = (id) => {
    setState((prev) => {
      const next = clone(prev);
      const x = next.exceptions.find((e) => e.id === id);
      if (x) {
        x.status = 'resolved';
        next.ops.open_exceptions = next.exceptions.filter((e) => e.status === 'open').length;
      }
      return next;
    });
  };

  const handleApprove = (id) => {
    setState((prev) => {
      const next = clone(prev);
      const o = next.opportunities.find((op) => op.id === id);
      if (o) o.status = 'proposal_phase';
      return next;
    });
    setOppId(null);
    showFlash('🚀 Approved — moved to Proposal Phase');
  };

  const handleSubmitIntake = () => {
    setIntakeOpen(false);
    showFlash('📧 Email submitted — pipeline running');
  };

  return (
    <>
      <Header
        ops={state.ops}
        counts={counts}
        tab={tab}
        onTab={setTab}
        onOpenIntake={() => setIntakeOpen(true)}
      />

      <main>
        <AttentionBar items={attentionItems} onTab={setTab} />

        {tab === 'pipeline' && (
          <PipelineTab emails={state.emails} scenarios={state.scenarios} onSimulate={handleSimulate} />
        )}
        {tab === 'opps' && (
          <OpportunitiesTab
            opportunities={state.opportunities}
            reviews={state.reviews}
            onOpen={setOppId}
          />
        )}
        {tab === 'review' && <ReviewTab reviews={state.reviews} onDecide={handleDecide} />}
        {tab === 'ops' && <OpsTab state={state} onResolveExc={handleResolveExc} />}
      </main>

      <OpportunityDialog
        opp={mergedOpp}
        chunks={demoData.chunks}
        onClose={() => setOppId(null)}
        onApprove={handleApprove}
      />
      <IntakeDialog open={intakeOpen} onClose={() => setIntakeOpen(false)} onSubmit={handleSubmitIntake} />

      <Flash message={flash.message} nonce={flash.nonce} />
    </>
  );
}
