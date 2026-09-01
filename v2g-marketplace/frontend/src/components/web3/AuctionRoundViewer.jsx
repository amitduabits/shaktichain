import { useMemo, useState } from 'react';
import {
  auctionCommit,
  auctionReveal,
  settleAuctionBatch,
  getAuctionRound,
  getAuctionOrderbook,
} from '../../services/api';

function toFixedSix(value) {
  return Number(value).toFixed(6);
}

async function sha256Hex(input) {
  const encoder = new TextEncoder();
  const bytes = encoder.encode(input);
  const digest = await window.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function buildCommitHash(roundId, prosumerId, side, quantity, price, nonce) {
  const payload = `${roundId}|${prosumerId}|${side}|${toFixedSix(quantity)}|${toFixedSix(price)}|${nonce}`;
  return sha256Hex(payload);
}

function formatPrice(value) {
  if (value === null || value === undefined) {
    return 'Hidden';
  }
  return Number(value).toFixed(4);
}

export function AuctionRoundViewer() {
  const [roundIdInput, setRoundIdInput] = useState('');
  const [activeRoundId, setActiveRoundId] = useState('');
  const [roundData, setRoundData] = useState(null);
  const [orderbook, setOrderbook] = useState({ bids: [], asks: [], status: 'open' });
  const [commits, setCommits] = useState([]);
  const [commitForm, setCommitForm] = useState({
    prosumerId: 'demo-user-1',
    side: 'buy',
    quantity: '20',
    price: '7.2',
    nonce: 'nonce-1',
  });
  const [statusMessage, setStatusMessage] = useState('');
  const [statusType, setStatusType] = useState('info');
  const [busy, setBusy] = useState(false);

  const roundId = activeRoundId || roundIdInput.trim();

  const revealedCount = useMemo(
    () => commits.filter((item) => item.status === 'revealed' || item.status === 'settled').length,
    [commits]
  );

  const setMessage = (type, text) => {
    setStatusType(type);
    setStatusMessage(text);
  };

  const refreshRoundData = async (targetRoundId) => {
    if (!targetRoundId) {
      return;
    }

    const [round, book] = await Promise.all([
      getAuctionRound(targetRoundId),
      getAuctionOrderbook(targetRoundId),
    ]);

    setRoundData(round);
    setOrderbook(book);
  };

  const handleCommit = async (event) => {
    event.preventDefault();

    const prosumerId = commitForm.prosumerId.trim();
    const side = commitForm.side;
    const quantity = Number(commitForm.quantity);
    const price = Number(commitForm.price);
    const nonce = commitForm.nonce.trim();
    const seededRound = roundIdInput.trim();

    if (!prosumerId || !nonce || !Number.isFinite(quantity) || !Number.isFinite(price) || quantity <= 0 || price <= 0) {
      setMessage('error', 'Invalid commit values. Provide prosumer, nonce, positive quantity, and price.');
      return;
    }

    setBusy(true);
    setStatusMessage('');
    try {
      const hashRoundId = seededRound || `demo-round-${Date.now()}`;
      const commitHash = await buildCommitHash(hashRoundId, prosumerId, side, quantity, price, nonce);

      const response = await auctionCommit({
        round_id: seededRound || undefined,
        prosumer_id: prosumerId,
        side,
        quantity,
        commit_hash: commitHash,
        reveal_window_minutes: 5,
      });

      const nextRoundId = response.round_id;
      setActiveRoundId(nextRoundId);
      if (!seededRound) {
        setRoundIdInput(nextRoundId);
      }

      setCommits((previous) => [
        ...previous,
        {
          orderId: response.order_id,
          roundId: nextRoundId,
          prosumerId,
          side,
          quantity,
          price,
          nonce,
          status: 'committed',
        },
      ]);

      await refreshRoundData(nextRoundId);
      setMessage('success', `Committed ${side.toUpperCase()} order ${response.order_id} in round ${nextRoundId}.`);
    } catch (error) {
      setMessage('error', error.message || 'Commit failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleReveal = async (commitEntry) => {
    setBusy(true);
    setStatusMessage('');
    try {
      await auctionReveal({
        round_id: commitEntry.roundId,
        order_id: commitEntry.orderId,
        prosumer_id: commitEntry.prosumerId,
        side: commitEntry.side,
        quantity: commitEntry.quantity,
        price: commitEntry.price,
        nonce: commitEntry.nonce,
      });

      setCommits((previous) =>
        previous.map((entry) =>
          entry.orderId === commitEntry.orderId
            ? { ...entry, status: 'revealed' }
            : entry
        )
      );

      await refreshRoundData(commitEntry.roundId);
      setMessage('success', `Revealed order ${commitEntry.orderId}.`);
    } catch (error) {
      setMessage('error', error.message || 'Reveal failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleSettle = async () => {
    if (!roundId) {
      setMessage('error', 'Set a round ID first.');
      return;
    }

    setBusy(true);
    setStatusMessage('');
    try {
      const result = await settleAuctionBatch({
        round_id: roundId,
        max_matches: 20,
      });

      setCommits((previous) =>
        previous.map((entry) =>
          entry.roundId === roundId ? { ...entry, status: 'settled' } : entry
        )
      );

      await refreshRoundData(roundId);
      setMessage(
        'success',
        `Round settled at ${Number(result.clearing_price || 0).toFixed(4)} with ${result.matched_orders} matched orders.`
      );
    } catch (error) {
      setMessage('error', error.message || 'Settle failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleRefresh = async () => {
    if (!roundId) {
      setMessage('error', 'Set a round ID first.');
      return;
    }

    setBusy(true);
    setStatusMessage('');
    try {
      await refreshRoundData(roundId);
      setMessage('info', `Round ${roundId} refreshed.`);
    } catch (error) {
      setMessage('error', error.message || 'Unable to load round.');
    } finally {
      setBusy(false);
    }
  };

  const handleRunSample = async () => {
    const sampleRound = `demo-round-${Date.now()}`;

    setBusy(true);
    setStatusMessage('');
    setCommits([]);

    try {
      const samples = [
        { prosumerId: 'demo-buyer', side: 'buy', quantity: 20, price: 7.2, nonce: 'nonce-buy-1' },
        { prosumerId: 'demo-seller', side: 'sell', quantity: 20, price: 6.4, nonce: 'nonce-sell-1' },
      ];

      const committed = [];
      for (const item of samples) {
        const commitHash = await buildCommitHash(
          sampleRound,
          item.prosumerId,
          item.side,
          item.quantity,
          item.price,
          item.nonce
        );

        const commitResponse = await auctionCommit({
          round_id: sampleRound,
          prosumer_id: item.prosumerId,
          side: item.side,
          quantity: item.quantity,
          commit_hash: commitHash,
          reveal_window_minutes: 5,
        });

        committed.push({
          orderId: commitResponse.order_id,
          roundId: sampleRound,
          prosumerId: item.prosumerId,
          side: item.side,
          quantity: item.quantity,
          price: item.price,
          nonce: item.nonce,
          status: 'committed',
        });
      }

      setCommits(committed);
      setActiveRoundId(sampleRound);
      setRoundIdInput(sampleRound);

      for (const entry of committed) {
        await auctionReveal({
          round_id: entry.roundId,
          order_id: entry.orderId,
          prosumer_id: entry.prosumerId,
          side: entry.side,
          quantity: entry.quantity,
          price: entry.price,
          nonce: entry.nonce,
        });
      }

      await settleAuctionBatch({
        round_id: sampleRound,
        max_matches: 20,
      });

      setCommits((previous) =>
        previous.map((entry) => ({ ...entry, status: 'settled' }))
      );
      await refreshRoundData(sampleRound);
      setMessage('success', `Sample double-auction flow completed for ${sampleRound}.`);
    } catch (error) {
      setMessage('error', error.message || 'Sample round failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auction-viewer">
      <div className="auction-viewer-header">
        <div>
          <h2>Double Auction Viewer</h2>
          <p>Commit {'->'} Reveal {'->'} Settle flow backed by live API endpoints.</p>
        </div>
        <button className="auction-primary" onClick={handleRunSample} disabled={busy}>
          {busy ? 'Processing...' : 'Run Sample Round'}
        </button>
      </div>

      <div className="auction-toolbar">
        <label htmlFor="auction-round-id">Round ID</label>
        <input
          id="auction-round-id"
          type="text"
          value={roundIdInput}
          onChange={(event) => setRoundIdInput(event.target.value)}
          placeholder="demo-round-001"
          disabled={busy}
        />
        <button className="auction-secondary" onClick={handleRefresh} disabled={busy}>
          Refresh
        </button>
        <button className="auction-secondary" onClick={handleSettle} disabled={busy || !roundId}>
          Settle Round
        </button>
      </div>

      <form className="auction-commit-form" onSubmit={handleCommit}>
        <div className="field">
          <label>Prosumer ID</label>
          <input
            type="text"
            value={commitForm.prosumerId}
            onChange={(event) => setCommitForm((prev) => ({ ...prev, prosumerId: event.target.value }))}
            disabled={busy}
          />
        </div>
        <div className="field">
          <label>Side</label>
          <select
            value={commitForm.side}
            onChange={(event) => setCommitForm((prev) => ({ ...prev, side: event.target.value }))}
            disabled={busy}
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>
        <div className="field">
          <label>Quantity</label>
          <input
            type="number"
            min="0"
            step="0.1"
            value={commitForm.quantity}
            onChange={(event) => setCommitForm((prev) => ({ ...prev, quantity: event.target.value }))}
            disabled={busy}
          />
        </div>
        <div className="field">
          <label>Price</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={commitForm.price}
            onChange={(event) => setCommitForm((prev) => ({ ...prev, price: event.target.value }))}
            disabled={busy}
          />
        </div>
        <div className="field">
          <label>Nonce</label>
          <input
            type="text"
            value={commitForm.nonce}
            onChange={(event) => setCommitForm((prev) => ({ ...prev, nonce: event.target.value }))}
            disabled={busy}
          />
        </div>
        <div className="field action">
          <button className="auction-primary" type="submit" disabled={busy}>
            Commit Order
          </button>
        </div>
      </form>

      {statusMessage && (
        <div className={`auction-status ${statusType}`}>
          {statusMessage}
        </div>
      )}

      <div className="auction-grid">
        <div className="auction-card">
          <h3>Round Snapshot</h3>
          {roundData ? (
            <div className="kv">
              <span>Round</span>
              <strong>{roundData.id}</strong>
              <span>Status</span>
              <strong>{roundData.status}</strong>
              <span>Clearing Price</span>
              <strong>{Number(roundData.clearing_price || 0).toFixed(4)}</strong>
              <span>Orders</span>
              <strong>{roundData.orders_total}</strong>
              <span>Revealed</span>
              <strong>{roundData.orders_revealed}</strong>
              <span>Matches</span>
              <strong>{roundData.matches_total}</strong>
            </div>
          ) : (
            <p className="muted">No round loaded yet.</p>
          )}
        </div>

        <div className="auction-card">
          <h3>Committed Orders</h3>
          {commits.length === 0 ? (
            <p className="muted">No local commits yet.</p>
          ) : (
            <div className="commit-list">
              {commits.map((entry) => (
                <div key={entry.orderId} className="commit-row">
                  <div>
                    <strong>{entry.orderId}</strong>
                    <span>{entry.side.toUpperCase()} | {entry.quantity} @ {entry.price}</span>
                    <span>{entry.prosumerId}</span>
                  </div>
                  <div className="commit-actions">
                    <span className={`pill ${entry.status}`}>{entry.status}</span>
                    {entry.status === 'committed' && (
                      <button
                        className="auction-secondary"
                        onClick={() => handleReveal(entry)}
                        disabled={busy}
                      >
                        Reveal
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="muted small">Revealed locally: {revealedCount}</p>
        </div>
      </div>

      <div className="auction-grid">
        <div className="auction-card">
          <h3>Bids</h3>
          {orderbook.bids?.length ? (
            <table className="auction-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orderbook.bids.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{Number(item.quantity).toFixed(2)}</td>
                    <td>{formatPrice(item.price)}</td>
                    <td>{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No bid orders loaded.</p>
          )}
        </div>

        <div className="auction-card">
          <h3>Asks</h3>
          {orderbook.asks?.length ? (
            <table className="auction-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {orderbook.asks.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{Number(item.quantity).toFixed(2)}</td>
                    <td>{formatPrice(item.price)}</td>
                    <td>{item.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">No ask orders loaded.</p>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = `
.auction-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.auction-viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.auction-viewer-header h2 {
  margin: 0;
  font-size: 20px;
  color: #f8fafc;
}

.auction-viewer-header p {
  margin: 4px 0 0 0;
  color: #94a3b8;
  font-size: 13px;
}

.auction-toolbar {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 8px;
  align-items: center;
}

.auction-toolbar label {
  font-size: 12px;
  color: #94a3b8;
}

.auction-toolbar input {
  min-width: 240px;
}

.auction-toolbar input,
.auction-commit-form input,
.auction-commit-form select {
  background: rgba(15, 23, 42, 0.7);
  color: #e2e8f0;
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.auction-toolbar input:focus,
.auction-commit-form input:focus,
.auction-commit-form select:focus {
  outline: none;
  border-color: #22c55e;
}

.auction-commit-form {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 8px;
}

.auction-commit-form .field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.auction-commit-form label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
}

.auction-commit-form .field.action {
  justify-content: flex-end;
}

.auction-primary,
.auction-secondary {
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}

.auction-primary {
  background: linear-gradient(135deg, #16a34a, #15803d);
  color: #f8fafc;
}

.auction-secondary {
  background: rgba(30, 41, 59, 0.9);
  color: #e2e8f0;
  border: 1px solid rgba(71, 85, 105, 0.6);
}

.auction-primary:disabled,
.auction-secondary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.auction-status {
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.auction-status.info {
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.35);
}

.auction-status.success {
  color: #86efac;
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.35);
}

.auction-status.error {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.35);
}

.auction-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.auction-card {
  background: rgba(15, 23, 42, 0.55);
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 10px;
  padding: 10px;
}

.auction-card h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #e2e8f0;
}

.kv {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px 8px;
  font-size: 12px;
}

.kv span {
  color: #94a3b8;
}

.kv strong {
  color: #f8fafc;
  font-weight: 600;
}

.commit-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.commit-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.75);
}

.commit-row div:first-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.commit-row strong {
  font-size: 12px;
  color: #f8fafc;
}

.commit-row span {
  font-size: 12px;
  color: #cbd5e1;
}

.commit-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-end;
}

.pill {
  display: inline-flex;
  font-size: 10px;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 2px 8px;
  font-weight: 700;
}

.pill.committed {
  background: rgba(59, 130, 246, 0.2);
  color: #93c5fd;
}

.pill.revealed {
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
}

.pill.settled {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
}

.auction-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.auction-table th,
.auction-table td {
  text-align: left;
  padding: 6px 4px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.35);
}

.auction-table th {
  color: #94a3b8;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}

.auction-table td {
  color: #e2e8f0;
}

.muted {
  color: #94a3b8;
  font-size: 12px;
}

.muted.small {
  margin: 8px 0 0;
}

@media (max-width: 980px) {
  .auction-toolbar {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .auction-toolbar input {
    min-width: 0;
  }

  .auction-commit-form {
    grid-template-columns: 1fr;
  }

  .auction-grid {
    grid-template-columns: 1fr;
  }
}
`;

if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default AuctionRoundViewer;
