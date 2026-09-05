import SimulationPanel from '../components/SimulationPanel';
import { useDemoLedger } from '../context/DemoLedgerContext';

export function RoleReports({ role, onNavigate }) {
  const { ledger } = useDemoLedger();
  const fills = (ledger.recentActions || []).filter((row) =>
    ['buy', 'sell', 'bulk_ask', 'order'].includes(row.type) || row.side
  ).slice(0, 10);
  const sites = ledger.sites || [];

  if (role === 'discom' || role === 'admin') {
    return (
      <section className="role-panel">
        <h2 className="page-title">City run</h2>
        <p className="measured-note">
          IEEE r2 simulation (MEASURED): feeder wrapper curtailed 0.16% welfare. That is context, not this feeder&apos;s live value.
        </p>
        <SimulationPanel />
      </section>
    );
  }

  if (role === 'cpo') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Throughput</h2>
        {sites.length === 0 && (
          <p className="empty-hint">No throughput recorded. Reset demo data.</p>
        )}
        <ul className="plain-list">
          {sites.map((site) => (
            <li key={site.id}>{site.name}: {site.kwhToday} kWh today</li>
          ))}
        </ul>
      </section>
    );
  }

  if (role === 'aggregator') {
    const trades = Number(ledger.market?.totalTrades || 0);
    const volume = Number(ledger.market?.totalVolumeKwh || 0);
    return (
      <section className="role-panel">
        <h2 className="page-title">Round report</h2>
        <p>Matched volume this demo: {volume.toFixed(2)} kWh across {trades} fills.</p>
        <p className="measured-note">
          IEEE r2 simulation (MEASURED) allocative efficiency 97.3% is a paper result, not this round.
        </p>
      </section>
    );
  }

  if (role === 'fleet') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Fleet fills</h2>
        {fills.length === 0 && (
          <p className="empty-hint">
            No fleet fills yet.{' '}
            <button type="button" className="text-button" onClick={() => onNavigate('/market')}>Place a bulk bid</button>
          </p>
        )}
        <ul className="plain-list">
          {fills.map((row) => (
            <li key={row.id}>
              {row.type} {row.vehicleCount ? `×${row.vehicleCount}` : ''} {row.quantity ?? ''} {row.createdAt}
            </li>
          ))}
        </ul>
      </section>
    );
  }

  return (
    <section className="role-panel">
      <h2 className="page-title">Your fills</h2>
      {fills.length === 0 && (
        <p className="empty-hint">
          No fills yet.{' '}
          <button type="button" className="text-button" onClick={() => onNavigate('/market')}>Place an order</button>
        </p>
      )}
      <ul className="plain-list">
        {fills.map((row) => (
          <li key={row.id}>{row.type} {row.quantity ?? ''} {row.createdAt}</li>
        ))}
      </ul>
    </section>
  );
}

export default RoleReports;
