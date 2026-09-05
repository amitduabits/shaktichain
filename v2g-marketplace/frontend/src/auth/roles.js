export const ALL_ROLES = ['ev_owner', 'fleet', 'aggregator', 'cpo', 'discom', 'admin'];
export const PUBLIC_ROLES = ['ev_owner', 'fleet', 'aggregator', 'cpo', 'discom'];
export const TRADER_ROLES = ['ev_owner', 'fleet', 'aggregator', 'cpo', 'admin'];

export const ROLE_LABELS = {
  ev_owner: 'EV owner',
  fleet: 'Fleet',
  aggregator: 'Aggregator',
  cpo: 'Charge-point operator',
  discom: 'DISCOM',
  admin: 'Admin',
};

export const VIEW_ROLE_KEY = 'v2g_view_role';

export function normalizeRole(role) {
  if (!role || role === 'user' || role === 'trader') {
    return 'ev_owner';
  }
  if (ALL_ROLES.includes(role)) {
    return role;
  }
  return 'ev_owner';
}

export function isPublicRole(role) {
  return PUBLIC_ROLES.includes(role);
}

export function roleLabel(role) {
  return ROLE_LABELS[normalizeRole(role)] || ROLE_LABELS.ev_owner;
}

const ACCESS = {
  '/home': ALL_ROLES,
  '/assets': ALL_ROLES,
  '/reports': ALL_ROLES,
  '/settings': ALL_ROLES,
  '/403': ALL_ROLES,
  '/404': ALL_ROLES,
  '/market': TRADER_ROLES,
  '/settlement': TRADER_ROLES,
  '/admin': ['admin'],
};

export function canAccess(path, role) {
  const allowed = ACCESS[path];
  if (!allowed) {
    return false;
  }
  return allowed.includes(normalizeRole(role));
}

export function knownAppPath(path) {
  return Boolean(ACCESS[path]) || path === '/login' || path === '/register' || path === '/dashboard';
}

export function navItems(role, compact = false) {
  const r = normalizeRole(role);
  const items = [{ path: '/home', label: 'Home' }];
  if (r === 'discom') {
    items.push({ path: '/assets', label: 'Feeders' });
    items.push({ path: '/reports', label: 'Reports' });
    items.push({ path: '/settings', label: compact ? 'More' : 'Settings' });
    return items;
  }
  items.push({ path: '/market', label: 'Market' });
  items.push({ path: '/assets', label: 'Assets' });
  if (!compact) {
    items.push({ path: '/settlement', label: 'Settlement' });
  }
  items.push({ path: '/reports', label: 'Reports' });
  if (r === 'admin' && !compact) {
    items.push({ path: '/admin', label: 'Admin' });
  }
  items.push({ path: '/settings', label: compact ? 'More' : 'Settings' });
  return items.slice(0, compact ? 5 : 8);
}

export function screenTitle(path, role) {
  const r = normalizeRole(role);
  if (path === '/home') return 'Home';
  if (path === '/market') return 'Market';
  if (path === '/assets') return r === 'discom' ? 'Feeders' : 'Assets';
  if (path === '/settlement') return 'Settlement';
  if (path === '/reports') return 'Reports';
  if (path === '/admin') return 'Admin';
  if (path === '/settings') return 'Settings';
  if (path === '/403') return 'Forbidden';
  if (path === '/404') return 'Not found';
  if (path === '/login') return 'Login';
  if (path === '/register') return 'Register';
  return 'Shakti-Chain';
}

export function setDocumentTitle(screen) {
  if (typeof document === 'undefined') {
    return;
  }
  document.title = `${screen} · Shakti-Chain`;
}

export function isDemoOnlyFlag() {
  const value = String(import.meta.env.VITE_DEMO_ONLY || '').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(value);
}
