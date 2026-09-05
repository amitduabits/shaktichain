import { listLocalAccounts } from '../auth/localAccounts';
import { roleLabel } from '../auth/roles';
import { useDemoLedger } from '../context/DemoLedgerContext';

export function AdminPage() {
  const { ledger, resetDemoState } = useDemoLedger();
  const users = listLocalAccounts();

  return (
    <section className="role-panel">
      <h2 className="page-title">Admin</h2>
      <p className="empty-hint">Local demo accounts only. Digests are not shown.</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 && (
              <tr>
                <td colSpan={3}>No local accounts yet. Register on this browser.</td>
              </tr>
            )}
            {users.map((row) => (
              <tr key={row.id}>
                <td>{row.email}</td>
                <td>{roleLabel(row.role)}</td>
                <td>{row.createdAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>Open round #{ledger.market?.currentRound ?? '—'}. Last job: none.</p>
      <button type="button" className="btn-primary" onClick={() => resetDemoState()}>
        Reset Demo Data
      </button>
    </section>
  );
}

export default AdminPage;
