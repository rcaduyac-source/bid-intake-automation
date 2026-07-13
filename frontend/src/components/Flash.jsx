import { useEffect, useState } from 'react';

export default function Flash({ message, nonce }) {
  // `show` is derived: visible while the latest nonce hasn't been dismissed yet.
  const [dismissed, setDismissed] = useState(0);

  useEffect(() => {
    if (!nonce) return undefined;
    const t = setTimeout(() => setDismissed(nonce), 2600);
    return () => clearTimeout(t);
  }, [nonce]);

  const show = nonce !== 0 && nonce !== dismissed;
  return <div className={`flash ${show ? 'show' : ''}`}>{message}</div>;
}
