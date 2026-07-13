// Plain-language vocabulary shared across the UI — mirrors the original preview.

export const OUTCOMES = {
  new_solicitation: { cls: 'green', icon: '✓', text: 'New bid captured' },
  existing_update: { cls: 'blue', icon: '↻', text: 'Existing bid updated' },
  not_bid_related: { cls: 'gray', icon: '—', text: 'Not a bid · archived' },
  uncertain: { cls: 'red', icon: '?', text: 'Needs human triage' },
};

export const OPP_STATUS = {
  new: { cls: 'indigo', text: 'New', border: 'var(--indigo)' },
  updated: { cls: 'blue', text: 'Updated', border: 'var(--blue)' },
  in_review: { cls: 'amber', text: 'Awaiting review', border: 'var(--amber)' },
  go_approved: { cls: 'green', text: 'GO approved', border: 'var(--green)' },
  conditional: { cls: 'amber', text: 'Conditional GO', border: 'var(--amber)' },
  no_go: { cls: 'red', text: 'No-Go', border: 'var(--red)' },
  proposal_phase: { cls: 'green', text: '🚀 Proposal phase', border: 'var(--green)' },
};

export const STAGES = [
  { match: ['Email Intake'], lbl: 'Intake', c: '#5548d9' },
  { match: ['Secure Intake'], lbl: 'Files', c: '#2467d6' },
  { match: ['Document Extraction'], lbl: 'Extract', c: '#2467d6' },
  { match: ['AI Classification'], lbl: 'AI read', c: '#0e8f7e' },
  { match: ['Validation & Decision'], lbl: 'Route', c: '#d9930d' },
  { match: ['Create Opportunity', 'Update Opportunity'], lbl: 'Record', c: '#2e9e4f' },
  { match: ['Document Indexing'], lbl: 'Index', c: '#2467d6' },
  { match: ['AI Bid Analysis'], lbl: 'Analyze', c: '#0e8f7e' },
];

export const NTYPE = {
  assignment: { cls: 'green', icon: '📁' },
  review: { cls: 'amber', icon: '✅' },
  exception: { cls: 'red', icon: '⚠️' },
  update: { cls: 'blue', icon: '↻' },
  decision: { cls: 'indigo', icon: '🧑‍⚖️' },
};

export const EVT_STYLE = {
  created: ['green', '📁'],
  update: ['blue', '↻'],
  calendar: ['indigo', '🗓️'],
  decision: ['amber', '🧑‍⚖️'],
  approved: ['green', '🚀'],
};

// How-it-works ribbon steps
export const HOWTO_STEPS = [
  { icon: '📧', bg: 'var(--indigo-bg)', label: 'Email arrives' },
  { icon: '🛡️', bg: 'var(--blue-bg)', label: 'Files checked' },
  { icon: '📄', bg: 'var(--blue-bg)', label: 'Text extracted' },
  { icon: '🧠', bg: 'var(--teal-bg)', label: 'AI reads it' },
  { icon: '🔀', bg: 'var(--amber-bg)', label: 'Routed' },
  { icon: '🗂️', bg: 'var(--green-bg)', label: 'Bid recorded' },
  { icon: '📊', bg: 'var(--teal-bg)', label: 'AI analyzes' },
  { icon: '👤', bg: 'var(--red-bg)', label: 'You decide' },
];
