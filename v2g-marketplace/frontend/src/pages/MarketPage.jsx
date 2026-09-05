import { useState } from 'react';
import { BidForm, AuctionRoundViewer, DemoActivityPanel } from '../components/web3';
import { useDemoLedger } from '../context/DemoLedgerContext';
import { getRoundTimeRemaining } from '../demo/ledger';

export function MarketPage({ role }) {
  const { ledger, placeBulkAsks } = useDemoLedger();
  const [qty, setQty] = useState('5');
  const [price, setPrice] = useState('4.85');
  const [bulkError, setBulkError] = useState('');
  const [bulkOk, setBulkOk] = useState('');
  const demoRound = ledger?.market?.currentRound ?? 1;
  const demoRoundRemaining = getRoundTimeRemaining(ledger);
  const count = (ledger.vehicles || []).length;

  const handleBulk = (event) => {
    event.preventDefault();
    const result = placeBulkAsks(qty, price, count);
    if (result.success) {
      setBulkError('');
      setBulkOk(`Placed ${result.vehicleCount || count} sell orders.`);
    } else {
      setBulkOk('');
      setBulkError(result.error);
    }
  };

  const book = (ledger.recentOrders || []).slice(0, 8).map((row) => ({
    side: row.side,
    qty: row.quantity,
    price: row.price,
  }));

  return (
    <section className="role-panel">
      <h2 className="page-title">Market</h2>
      {role === 'fleet' && (
        <form className="bulk-form" onSubmit={handleBulk}>
          <h3>Bulk bid</h3>
          <p className="empty-hint">Apply one sell ticket to {count} vehicles.</p>
          {bulkError && <div className="auth-error">{bulkError}</div>}
          {bulkOk && <p className="empty-hint">{bulkOk}</p>}
          <label htmlFor="bulk-qty">Quantity (kWh each)</label>
          <input id="bulk-qty" type="number" min="0.1" step="0.1" value={qty} onChange={(e) => setQty(e.target.value)} />
          <label htmlFor="bulk-price">Price (SHAKTI/kWh)</label>
          <input id="bulk-price" type="number" min="0.01" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} />
          <button type="submit" className="btn-primary">Apply to {count} vehicles</button>
        </form>
      )}
      <BidForm
        defaultSide={role === 'cpo' ? 'ask' : 'bid'}
        simulatedData={{
          currentRound: demoRound,
          timeRemaining: demoRoundRemaining,
          isOpen: true,
        }}
      />
      {role === 'aggregator' && (
        <div className="anonymised-book">
          <h3>Book (anonymised)</h3>
          {book.length === 0 && <p className="empty-hint">No visible orders yet.</p>}
          <ul className="plain-list">
            {book.map((row, index) => (
              <li key={`${row.side}-${index}`}>{row.side} {row.qty} kWh @ {row.price}</li>
            ))}
          </ul>
        </div>
      )}
      <AuctionRoundViewer />
      <DemoActivityPanel />
    </section>
  );
}

export default MarketPage;
