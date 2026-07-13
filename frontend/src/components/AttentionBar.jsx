export default function AttentionBar({ items, onTab }) {
  return (
    <div className="attention">
      {items.map((a, i) => (
        <div key={i} className={`att ${a.c}`} onClick={() => onTab(a.tab)}>
          <div className="aic">{a.i}</div>
          <div>
            <b>{a.n}</b>
            <span>{a.l}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
