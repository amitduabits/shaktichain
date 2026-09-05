/**
 * Browser-local demo accounts for the GitHub Pages build.
 *
 * This is not an identity provider. Digests are demo-only and are not
 * a substitute for bcrypt/JWT on the FastAPI backend.
 */

export const STORE_KEY = 'v2g_local_accounts_v1';
export const LOCAL_TOKEN_PREFIX = 'local:';
export const MIN_PASSWORD_LENGTH = 6;

function getStore() {
  if (typeof localStorage === 'undefined') {
    return null;
  }
  return localStorage;
}

function loadAccounts() {
  const store = getStore();
  if (!store) {
    return [];
  }
  try {
    const raw = store.getItem(STORE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveAccounts(accounts) {
  const store = getStore();
  if (!store) {
    return;
  }
  store.setItem(STORE_KEY, JSON.stringify(accounts));
}

export function normalizeEmail(email) {
  return String(email || '').trim().toLowerCase();
}

export function listLocalAccounts() {
  return loadAccounts();
}

export function findLocalUserById(id) {
  if (!id) {
    return null;
  }
  return loadAccounts().find((account) => account.id === id) || null;
}

export function findLocalUserByEmail(email) {
  const normalized = normalizeEmail(email);
  if (!normalized) {
    return null;
  }
  return loadAccounts().find((account) => account.email === normalized) || null;
}

export function localTokenFor(id) {
  return `${LOCAL_TOKEN_PREFIX}${id}`;
}

export function userFromRecord(record) {
  if (!record) {
    return null;
  }
  return {
    id: record.id,
    email: record.email,
    role: 'user',
    created_at: record.createdAt,
  };
}

/**
 * Demo-only password digest. Not for production.
 * SHA-256 via Web Crypto when available; otherwise a labelled FNV-1a fallback.
 */
export async function digest(password) {
  const payload = `v2g-demo:${password}`;
  if (globalThis.crypto?.subtle && typeof TextEncoder !== 'undefined') {
    const encoded = new TextEncoder().encode(payload);
    const buffer = await globalThis.crypto.subtle.digest('SHA-256', encoded);
    return Array.from(new Uint8Array(buffer))
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('');
  }
  let hash = 2166136261;
  for (let i = 0; i < payload.length; i += 1) {
    hash ^= payload.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `demo-fnv1a-${(hash >>> 0).toString(16).padStart(8, '0')}`;
}

function newLocalId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function toPublicUser(record) {
  return userFromRecord(record);
}

export async function registerLocal({ email, password }) {
  const normalized = normalizeEmail(email);
  if (!normalized || !normalized.includes('@')) {
    return { ok: false, error: 'Please enter a valid email address' };
  }
  if (!password || String(password).length < MIN_PASSWORD_LENGTH) {
    return { ok: false, error: 'Password must be at least 6 characters' };
  }

  const accounts = loadAccounts();
  if (accounts.some((account) => account.email === normalized)) {
    return { ok: false, error: 'Email already registered' };
  }

  const record = {
    id: newLocalId(),
    email: normalized,
    passwordDigest: await digest(password),
    createdAt: new Date().toISOString(),
  };
  accounts.push(record);
  saveAccounts(accounts);
  return { ok: true, user: toPublicUser(record) };
}

export async function loginLocal({ email, password }) {
  const normalized = normalizeEmail(email);
  const record = loadAccounts().find((account) => account.email === normalized);
  if (!record) {
    return { ok: false, error: 'Invalid email or password' };
  }
  const passwordDigest = await digest(password);
  if (passwordDigest !== record.passwordDigest) {
    return { ok: false, error: 'Invalid email or password' };
  }
  return { ok: true, user: toPublicUser(record) };
}
