import { useCallback, useEffect, useMemo, useState } from 'react';
import * as api from './api';
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

const emptyState = {
  emails: [],
  opportunities: [],
  reviews: [],
  exceptions: [],
  notifications: [],
  audit: [],
  ops: {
    ai_mode: 'mock',
    ai_model: '',
    ai_last_error: '',
    server_started: null,
    flows_active: true,
    emails_24h: 0,
    executions_24h: 0,
    errors_24h: 0,
    open_exceptions: 0,
    open_reviews: 0,
  },
  scenarios: {
    new_bid: 'New solicitation (RFP w/ PDF)',
    amendment: 'Amendment (existing update)',
    not_bid: 'Non-bid email (archived)',
    uncertain: 'Ambiguous (low confidence)',
  },
};

export default function App() {
  const [state, setState] = useState(emptyState);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('pipeline');
  const [flash, setFlash] = useState({ message: '', nonce: 0 });
  const [oppId, setOppId] = useState(null);
  const [oppDetail, setOppDetail] = useState(null);
  const [intakeOpen, setIntakeOpen] = useState(false);

  const showFlash = (message) => setFlash((f) => ({ message, nonce: f.nonce + 1 }));

  const refresh = useCallback(async () => {
    const next = await api.fetchState();
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await api.fetchState();
        if (!cancelled) setState(next);
      } catch (err) {
        if (!cancelled) showFlash(`API error: ${err.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Keep UI in sync with Gmail poller / background pipeline without a manual reload
  useEffect(() => {
    if (loading) return undefined;
    const id = window.setInterval(() => {
      api
        .fetchState()
        .then((next) => setState(next))
        .catch(() => {
          /* ignore transient poll errors */
        });
    }, 2500);
    return () => window.clearInterval(id);
  }, [loading]);

  useEffect(() => {
    if (oppId == null) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.fetchOpportunity(oppId);
        if (!cancelled) setOppDetail(data.opportunity);
      } catch (err) {
        if (!cancelled) showFlash(`Failed to load opportunity: ${err.message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [oppId, state.opportunities]);

  const dialogOpp = oppId == null ? null : oppDetail;

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

  const handleSimulate = async (scenarioKey) => {
    try {
      showFlash('📧 Running sample through the pipeline…');
      await api.simulate(scenarioKey);
      await refresh();
      showFlash('Sample processed');
    } catch (err) {
      showFlash(`Simulate failed: ${err.message}`);
    }
  };

  const handleDecide = async (taskId, decision, notes) => {
    try {
      await api.decideReview(taskId, decision, notes);
      await refresh();
      showFlash('Decision recorded: ' + decision);
    } catch (err) {
      showFlash(`Decision failed: ${err.message}`);
    }
  };

  const handleResolveExc = async (id) => {
    try {
      await api.resolveException(id);
      await refresh();
    } catch (err) {
      showFlash(`Resolve failed: ${err.message}`);
    }
  };

  const handleApprove = async (id) => {
    try {
      await api.approveOpportunity(id);
      setOppId(null);
      await refresh();
      showFlash('🚀 Approved — moved to Proposal Phase');
    } catch (err) {
      showFlash(`Approve failed: ${err.message}`);
    }
  };

  const handleSubmitIntake = async ({ from, subject, body, files }) => {
    try {
      setIntakeOpen(false);
      showFlash('📧 Email submitted — pipeline running');
      await api.submitEmail({ from, subject, body, files });
      // The pipeline now runs in the background; reflect the email right away
      // and let the /api/state polling stream in each stage as it completes.
      await refresh();
      showFlash('📧 Received — watch the pipeline process it live');
    } catch (err) {
      showFlash(`Intake failed: ${err.message}`);
    }
  };

  const handleAsk = (id, question) => api.askOpportunity(id, question);

  if (loading) {
    return (
      <main style={{ padding: 40 }}>
        <p className="muted">Loading bid intake…</p>
      </main>
    );
  }

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
        opp={dialogOpp}
        onClose={() => setOppId(null)}
        onApprove={handleApprove}
        onAsk={handleAsk}
      />
      <IntakeDialog open={intakeOpen} onClose={() => setIntakeOpen(false)} onSubmit={handleSubmitIntake} />

      <Flash message={flash.message} nonce={flash.nonce} />
    </>
  );
}
