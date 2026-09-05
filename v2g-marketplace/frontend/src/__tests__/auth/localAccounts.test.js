import { beforeEach, describe, expect, it } from 'vitest';
import {
  registerLocal,
  loginLocal,
  listLocalAccounts,
  STORE_KEY,
} from '../../auth/localAccounts';

describe('localAccounts', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('registers then logs in with the same pair', async () => {
    const registered = await registerLocal({
      email: 'qa@v2g.local',
      password: 'testpass1',
    });
    expect(registered.ok).toBe(true);
    expect(registered.user.email).toBe('qa@v2g.local');
    expect(registered.user.role).toBe('user');
    expect(registered.user).not.toHaveProperty('passwordDigest');

    const loggedIn = await loginLocal({
      email: 'qa@v2g.local',
      password: 'testpass1',
    });
    expect(loggedIn.ok).toBe(true);
    expect(loggedIn.user.id).toBe(registered.user.id);
    expect(loggedIn.user.email).toBe('qa@v2g.local');
  });

  it('rejects a duplicate email', async () => {
    const first = await registerLocal({
      email: 'dup@v2g.local',
      password: 'testpass1',
    });
    expect(first.ok).toBe(true);

    const second = await registerLocal({
      email: 'dup@v2g.local',
      password: 'testpass1',
    });
    expect(second.ok).toBe(false);
    expect(second.error).toBe('Email already registered');
  });

  it('rejects a short password', async () => {
    const result = await registerLocal({
      email: 'short@v2g.local',
      password: '12345',
    });
    expect(result.ok).toBe(false);
    expect(result.error).toBe('Password must be at least 6 characters');
    expect(listLocalAccounts()).toHaveLength(0);
  });

  it('rejects a wrong password without leaking whether the email exists', async () => {
    await registerLocal({ email: 'user@v2g.local', password: 'testpass1' });

    const missing = await loginLocal({
      email: 'missing@v2g.local',
      password: 'testpass1',
    });
    const wrong = await loginLocal({
      email: 'user@v2g.local',
      password: 'wrongpass',
    });
    expect(missing.ok).toBe(false);
    expect(wrong.ok).toBe(false);
    expect(missing.error).toBe('Invalid email or password');
    expect(wrong.error).toBe(missing.error);
  });

  it('treats email as case-insensitive', async () => {
    const registered = await registerLocal({
      email: '  Casey@V2G.Local ',
      password: 'testpass1',
    });
    expect(registered.ok).toBe(true);
    expect(registered.user.email).toBe('casey@v2g.local');

    const loggedIn = await loginLocal({
      email: 'CASEY@v2g.local',
      password: 'testpass1',
    });
    expect(loggedIn.ok).toBe(true);
    expect(loggedIn.user.id).toBe(registered.user.id);
  });

  it('does not require a guest record for Enter Demo', async () => {
    expect(listLocalAccounts()).toEqual([]);
    expect(localStorage.getItem(STORE_KEY)).toBeNull();
    const guest = await loginLocal({
      email: 'demo@v2g.local',
      password: 'unused',
    });
    expect(guest.ok).toBe(false);
  });
});
