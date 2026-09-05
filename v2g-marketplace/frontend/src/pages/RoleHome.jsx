import { useDemoLedger } from '../context/DemoLedgerContext';
import { getRoundTimeRemaining } from '../demo/ledger';
import { roleLabel } from '../auth/roles';

function meanSoc(vehicles) {
  if (!vehicles?.length) return 0;
  return vehicles.reduce((sum, row) => sum + Number(row.soc || 0), 0) / vehicles.length;
}

function HomeCard({ role, title, kpis, ctaLabel, onCta, children }) {
  return (
    <div className="role-home" data-testid="role-home" data-role={role}>
      <p className="role-kicker">{roleLabel(role)}</p>
      <h2 className="page-title">{title}</h2>
      <div className="kpi-row">
        {kpis.map((kpi) => (
          <div className="kpi-card" key={kpi.label}>
            <span className="stat-label">{kpi.label}</span>
            <span className="stat-value">{kpi.value}</span>
          </div>
        ))}
      </div>
      {ctaLabel && (
        <button type="button" className="btn-primary home-cta" data-testid="home-cta" onClick={onCta}>
          {ctaLabel}
        </button>
      )}
      {children}
    </div>
  );
}

export function RoleHome({ role, onNavigate }) {
  const { ledger } = useDemoLedger();
  const vehicles = ledger.vehicles || [];
  const sites = ledger.sites || [];
  const feeders = ledger.feeders || [];
  const portfolio = ledger.portfolio || { residential: 50, commercial: 30, fleet: 20 };
  const remaining = getRoundTimeRemaining(ledger);
  const primary = vehicles[0];

  if (role === 'fleet') {
    return (
      <HomeCard
        role={role}
        title="Fleet depot"
        kpis={[
          { label: 'Vehicles', value: vehicles.length },
          { label: 'Mean SOC', value: `${Math.round(meanSoc(vehicles) * 100)}%` },
          { label: 'Sold this round', value: `${Number(ledger.market?.totalVolumeKwh || 0).toFixed(1)} kWh` },
        ]}
        ctaLabel="Bulk bid"
        onCta={() => onNavigate('/market')}
      />
    );
  }

  if (role === 'aggregator') {
    return (
      <HomeCard
        role={role}
        title="Portfolio"
        kpis={[
          { label: 'Residential', value: `${portfolio.residential}%` },
          { label: 'Commercial', value: `${portfolio.commercial}%` },
          { label: 'Fleet', value: `${portfolio.fleet}%` },
          { label: 'Matched', value: `${Number(ledger.market?.totalVolumeKwh || 0).toFixed(1)} kWh` },
        ]}
        ctaLabel="View round"
        onCta={() => onNavigate('/market')}
      >
        <div className="mix-bars" aria-hidden="true">
          <span className="mix-bar residential" style={{ width: `${portfolio.residential}%` }} />
          <span className="mix-bar commercial" style={{ width: `${portfolio.commercial}%` }} />
          <span className="mix-bar fleet" style={{ width: `${portfolio.fleet}%` }} />
        </div>
      </HomeCard>
    );
  }

  if (role === 'cpo') {
    const kwh = sites.reduce((sum, site) => sum + Number(site.kwhToday || 0), 0);
    const occ = sites.length
      ? sites.reduce((sum, site) => sum + Number(site.occupancy || 0), 0) / sites.length
      : 0;
    return (
      <HomeCard
        role={role}
        title="Charge sites"
        kpis={[
          { label: 'Sites', value: sites.length },
          { label: 'kWh today', value: kwh.toFixed(0) },
          { label: 'Occupancy', value: `${Math.round(occ * 100)}%` },
        ]}
        ctaLabel="Open sites"
        onCta={() => onNavigate('/assets')}
      />
    );
  }

  if (role === 'discom') {
    const lastCurtail = feeders.length
      ? feeders.reduce((sum, row) => sum + Number(row.curtailmentPct || 0), 0) / feeders.length
      : 0;
    return (
      <HomeCard
        role={role}
        title="Feeder wrapper"
        kpis={[
          { label: 'City', value: feeders[0]?.city || 'Delhi' },
          { label: 'Feeders', value: feeders.length },
          { label: 'Last curtailment', value: `${lastCurtail.toFixed(2)}%` },
        ]}
      >
        <p className="empty-hint">DISCOM accounts do not place market orders.</p>
      </HomeCard>
    );
  }

  if (role === 'admin') {
    return (
      <HomeCard
        role={role}
        title="Operator"
        kpis={[
          { label: 'Round', value: `#${ledger.market?.currentRound ?? '—'}` },
          { label: 'Trades', value: ledger.market?.totalTrades ?? 0 },
          { label: 'Last job', value: 'None' },
        ]}
        ctaLabel="Open admin"
        onCta={() => onNavigate('/admin')}
      />
    );
  }

  return (
    <HomeCard
      role="ev_owner"
      title="Your next round"
      kpis={[
        { label: 'SOC', value: `${Math.round(Number(primary?.soc || 0) * 100)}%` },
        { label: 'Inventory', value: `${Number(ledger.account?.energyInventory || 0).toFixed(1)} kWh` },
        { label: 'Tokens', value: `${Number(ledger.account?.tokenBalance || 0).toFixed(0)} SHAKTI` },
        { label: 'Round in', value: `${Math.round(remaining / 60)} min` },
      ]}
      ctaLabel="Place order"
      onCta={() => onNavigate('/market')}
    />
  );
}

export default RoleHome;
