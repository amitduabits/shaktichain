import { roleLabel } from '../auth/roles';
import { useAuth } from '../context/AuthContext';
import { useRoleView } from '../context/RoleViewContext';

export function SettingsPage({ onNavigate, onLogout }) {
  const { user } = useAuth();
  const { effectiveRole } = useRoleView();

  return (
    <section className="role-panel">
      <h2 className="page-title">Settings</h2>
      <p><strong>Email (user id):</strong> {user?.email}</p>
      <p><strong>Role:</strong> {roleLabel(effectiveRole)}</p>
      <p className="empty-hint">Simulation. Not connected to a live DISCOM.</p>
      <p>
        <button type="button" className="text-button" onClick={() => onNavigate('/settlement')}>
          Settlement
        </button>
      </p>
      <button type="button" className="logout-button" onClick={onLogout}>Logout</button>
    </section>
  );
}

export default SettingsPage;
