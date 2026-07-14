const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

export function fetchState() {
  return request('/api/state');
}

export function fetchOpportunity(id) {
  return request(`/api/opportunities/${id}`);
}

export function simulate(scenario) {
  return request(`/api/simulate/${scenario}`, { method: 'POST' });
}

export function submitEmail({ from, subject, body, files }) {
  const fd = new FormData();
  fd.append('from_addr', from);
  fd.append('subject', subject);
  fd.append('body', body || '');
  for (const file of files || []) {
    fd.append('files', file);
  }
  return request('/api/emails', { method: 'POST', body: fd });
}

export function decideReview(id, decision, notes) {
  return request(`/api/reviews/${id}/decide`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, notes: notes || '' }),
  });
}

export function resolveException(id) {
  return request(`/api/exceptions/${id}/resolve`, { method: 'POST' });
}

export function approveOpportunity(id) {
  return request(`/api/opportunities/${id}/approve`, { method: 'POST' });
}

export function askOpportunity(id, question) {
  return request(`/api/opportunities/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
}
