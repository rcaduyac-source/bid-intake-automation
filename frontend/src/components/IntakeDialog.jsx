import { useEffect, useRef, useState } from 'react';

export default function IntakeDialog({ open, onClose, onSubmit }) {
  const ref = useRef(null);
  const [from, setFrom] = useState('procurement@agency.example.gov');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);

  return (
    <dialog ref={ref} onClose={onClose}>
      <div className="dlg-head">
        <h2>Submit an email to the pipeline</h2>
        <button className="x" onClick={onClose}>✕</button>
      </div>
      <div className="dlg-body">
        <p className="note" style={{ marginTop: 0 }}>
          Paste a real bid email below (and attach its PDFs) to watch the system process it exactly
          as it would from the inbox.
        </p>
        <div className="frm">
          <div>
            <label>From</label>
            <input type="email" value={from} onChange={(e) => setFrom(e.target.value)} />
          </div>
          <div>
            <label>Attachments (PDF / DOCX / TXT)</label>
            <input type="file" multiple />
          </div>
          <div className="full">
            <label>Subject</label>
            <input
              type="text"
              placeholder="RFP ABC-2026-R-0001 — …"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div className="full">
            <label>Body</label>
            <textarea
              rows="6"
              placeholder="Paste the email body here…"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <div className="full" style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn primary" onClick={() => onSubmit({ from, subject, body })}>
              Run the pipeline →
            </button>
          </div>
        </div>
      </div>
    </dialog>
  );
}
