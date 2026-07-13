import OpportunityCard from './OpportunityCard';

export default function OpportunitiesTab({ opportunities, reviews, onOpen }) {
  return (
    <section>
      <div className="card" style={{ background: 'none', border: 'none', boxShadow: 'none', padding: '0 2px 6px' }}>
        <h3>Bid opportunities</h3>
        <p className="lead">
          Every solicitation the system has captured. Click a card for its timeline, documents, and to
          ask questions.
        </p>
      </div>
      <div className="oppgrid">
        {opportunities.length ? (
          opportunities.map((o) => (
            <OpportunityCard key={o.id} opp={o} reviews={reviews} onOpen={onOpen} />
          ))
        ) : (
          <div className="empty" style={{ gridColumn: '1/-1' }}>
            <b>No opportunities yet</b>
            When a bid email arrives, the opportunity appears here automatically.
          </div>
        )}
      </div>
    </section>
  );
}
