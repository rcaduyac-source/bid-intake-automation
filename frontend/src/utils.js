// Small formatting helpers — mirror the original preview.

export function tShort(iso) {
  if (!iso) return '';
  return iso.replace('T', ' ').replace('Z', '').slice(5, 16);
}

export function daysTo(iso) {
  if (!iso) return null;
  const d = (new Date(iso + 'T23:59:59') - new Date()) / 864e5;
  return Math.floor(d);
}
