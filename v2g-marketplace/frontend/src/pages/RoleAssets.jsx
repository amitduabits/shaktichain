import { useState } from 'react';
import AgentMixSlider from '../components/AgentMixSlider';
import { useDemoLedger } from '../context/DemoLedgerContext';

export function RoleAssets({ role }) {
  const { ledger, addVehicle, removeVehicle, updateVehicle, setPortfolio } = useDemoLedger();
  const [error, setError] = useState('');
  const [editing, setEditing] = useState('');
  const [name, setName] = useState('');

  const vehicles = ledger.vehicles || [];
  const sites = ledger.sites || [];
  const feeders = ledger.feeders || [];
  const primary = vehicles[0];

  const handleAdd = () => {
    const result = addVehicle();
    setError(result.success ? '' : result.error);
  };

  const handleRemove = (id) => {
    const result = removeVehicle(id);
    setError(result.success ? '' : result.error);
  };

  if (role === 'fleet') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Vehicles</h2>
        {error && <div className="auth-error" data-testid="auth-error">{error}</div>}
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>City</th>
                <th>SOC</th>
                <th>kWh</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.city}</td>
                  <td>{Math.round(row.soc * 100)}%</td>
                  <td>{row.capacityKwh}</td>
                  <td>
                    <button type="button" className="text-button" onClick={() => handleRemove(row.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className="btn-primary" onClick={handleAdd}>Add vehicle</button>
      </section>
    );
  }

  if (role === 'aggregator') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Agent mix</h2>
        <p className="empty-hint">Changes stay in this demo ledger. They do not start a city-scale job.</p>
        <AgentMixSlider
          values={ledger.portfolio}
          onChange={(mix) => setPortfolio(mix)}
        />
      </section>
    );
  }

  if (role === 'cpo') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Sites</h2>
        {sites.length === 0 && (
          <p className="empty-hint">No sites. Reset demo data.</p>
        )}
        <div className="card-grid">
          {sites.map((site) => (
            <article className="kpi-card" key={site.id}>
              <h3>{site.name}</h3>
              <p>{site.city} · {site.chargers} chargers</p>
              <p>{site.kwhToday} kWh today · {Math.round(site.occupancy * 100)}% occupancy</p>
            </article>
          ))}
        </div>
      </section>
    );
  }

  if (role === 'discom') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Feeders</h2>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Feeder</th>
                <th>City</th>
                <th>Hosting kW</th>
                <th>Curtailment %</th>
              </tr>
            </thead>
            <tbody>
              {feeders.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.city}</td>
                  <td>{row.hostingKw}</td>
                  <td>{row.curtailmentPct.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }

  if (role === 'admin') {
    return (
      <section className="role-panel">
        <h2 className="page-title">Seed snapshot</h2>
        <p className="empty-hint">{vehicles.length} vehicles, {sites.length} sites, {feeders.length} feeders.</p>
      </section>
    );
  }

  return (
    <section className="role-panel">
      <h2 className="page-title">Vehicle</h2>
      {!primary && <p className="empty-hint">No vehicle. Reset demo data.</p>}
      {primary && (
        <article className="kpi-card">
          {editing === primary.id ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                updateVehicle(primary.id, { name: name || primary.name });
                setEditing('');
              }}
            >
              <label htmlFor="vehicle-name">Name</label>
              <input id="vehicle-name" value={name} onChange={(e) => setName(e.target.value)} />
              <button type="submit" className="btn-primary">Save</button>
            </form>
          ) : (
            <>
              <h3>{primary.name}</h3>
              <p>{primary.city} · {primary.capacityKwh} kWh · SOC {Math.round(primary.soc * 100)}%</p>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setEditing(primary.id);
                  setName(primary.name);
                }}
              >
                Edit name
              </button>
            </>
          )}
        </article>
      )}
    </section>
  );
}

export default RoleAssets;
