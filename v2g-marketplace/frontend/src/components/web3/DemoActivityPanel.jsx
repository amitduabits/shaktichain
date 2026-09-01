import { useMemo, useState } from 'react';
import { useDemoLedger } from '../../context/DemoLedgerContext';
import { getRoundTimeRemaining } from '../../demo/ledger';

function formatSignedAmount(value, suffix = '') {
  const numeric = Number(value ?? 0);
  const sign = numeric >= 0 ? '+' : '-';
  return `${sign}${Math.abs(numeric).toFixed(4)}${suffix}`;
}

function formatSeconds(seconds) {
  const safeSeconds = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`;
}

export function DemoActivityPanel() {
  const { ledger, resetDemoState } = useDemoLedger();
  const [resetNotice, setResetNotice] = useState('');

  const summary = useMemo(() => {
    const market = ledger?.market ?? {};
    return {
      round: market.currentRound ?? 0,
      isOpen: market.isOpen ?? false,
      totalTrades: market.totalTrades ?? 0,
      totalVolumeKwh: market.totalVolumeKwh ?? 0,
      feeBurned: market.feeBurned ?? 0,
      feeToStakers: market.feeToStakers ?? 0,
      timeRemaining: getRoundTimeRemaining(ledger),
    };
  }, [ledger]);

  const orders = ledger?.recentOrders ?? [];

  const handleReset = () => {
    resetDemoState();
    setResetNotice('Demo state reset to seed values.');
  };

  return (
    <div className="demo-activity-panel">
      <div className="demo-activity-header">
        <div>
          <h2>Demo Activity</h2>
          <p>Instant-fill orders with fee burn and staking distribution tracking.</p>
        </div>
        <button className="reset-demo-button" onClick={handleReset}>
          Reset Demo Data
        </button>
      </div>

      {resetNotice && <div className="demo-notice">{resetNotice}</div>}

      <div className="demo-summary-grid">
        <div className="demo-summary-card">
          <span className="label">Round</span>
          <span className="value">#{summary.round}</span>
          <span className={`tag ${summary.isOpen ? 'open' : 'closed'}`}>
            {summary.isOpen ? 'Open' : 'Closed'}
          </span>
        </div>
        <div className="demo-summary-card">
          <span className="label">Time Remaining</span>
          <span className="value mono">{formatSeconds(summary.timeRemaining)}</span>
        </div>
        <div className="demo-summary-card">
          <span className="label">Total Trades</span>
          <span className="value">{summary.totalTrades}</span>
        </div>
        <div className="demo-summary-card">
          <span className="label">Volume Traded</span>
          <span className="value">{Number(summary.totalVolumeKwh).toFixed(2)} kWh</span>
        </div>
        <div className="demo-summary-card">
          <span className="label">Fee Burned</span>
          <span className="value">{Number(summary.feeBurned).toFixed(4)} SHAKTI</span>
        </div>
        <div className="demo-summary-card">
          <span className="label">Fee to Stakers</span>
          <span className="value">{Number(summary.feeToStakers).toFixed(4)} SHAKTI</span>
        </div>
      </div>

      <div className="demo-orders">
        <div className="orders-header">
          <h3>Recent Filled Orders</h3>
          <span>{orders.length} tracked</span>
        </div>

        {orders.length === 0 ? (
          <div className="orders-empty">No trades yet. Place a buy or sell order to populate activity.</div>
        ) : (
          <div className="orders-list">
            {orders.slice(0, 8).map((order) => (
              <div key={order.id} className="order-row">
                <div className="order-main">
                  <span className={`side ${order.side}`}>{order.side.toUpperCase()}</span>
                  <span>{Number(order.quantity).toFixed(2)} kWh</span>
                  <span>@ {Number(order.price).toFixed(2)} SHAKTI</span>
                </div>
                <div className="order-meta">
                  <span>Fee {Number(order.fee).toFixed(4)}</span>
                  <span>{formatSignedAmount(order.tokenDelta, ' SHAKTI')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const styles = `
.demo-activity-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.demo-activity-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.demo-activity-header h2 {
  margin: 0;
  font-size: 19px;
  color: #f8fafc;
}

.demo-activity-header p {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #94a3b8;
}

.reset-demo-button {
  border: 1px solid rgba(239, 68, 68, 0.45);
  background: rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.reset-demo-button:hover {
  background: rgba(239, 68, 68, 0.15);
}

.demo-notice {
  border: 1px solid rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.12);
  color: #6ee7b7;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
}

.demo-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}

.demo-summary-card {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.demo-summary-card .label {
  font-size: 11px;
  color: #94a3b8;
  text-transform: uppercase;
}

.demo-summary-card .value {
  font-size: 16px;
  font-weight: 700;
  color: #f8fafc;
}

.demo-summary-card .value.mono {
  font-family: monospace;
  color: #fbbf24;
}

.demo-summary-card .tag {
  display: inline-flex;
  width: fit-content;
  font-size: 10px;
  border-radius: 999px;
  padding: 2px 8px;
  text-transform: uppercase;
}

.demo-summary-card .tag.open {
  color: #6ee7b7;
  background: rgba(16, 185, 129, 0.15);
}

.demo-summary-card .tag.closed {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.15);
}

.demo-orders {
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(71, 85, 105, 0.35);
  border-radius: 10px;
  padding: 12px;
}

.orders-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.orders-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e2e8f0;
}

.orders-header span {
  font-size: 11px;
  color: #64748b;
}

.orders-empty {
  color: #64748b;
  font-size: 13px;
  padding: 4px 0;
}

.orders-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.order-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.7);
}

.order-main,
.order-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #cbd5e1;
}

.order-meta {
  justify-content: flex-end;
}

.side {
  font-weight: 700;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
}

.side.buy {
  color: #6ee7b7;
  background: rgba(16, 185, 129, 0.15);
}

.side.sell {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.15);
}

@media (max-width: 768px) {
  .demo-activity-header {
    flex-direction: column;
    align-items: stretch;
  }

  .order-row {
    flex-direction: column;
  }

  .order-meta {
    justify-content: flex-start;
  }
}
`;

if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = styles;
  document.head.appendChild(styleSheet);
}

export default DemoActivityPanel;
