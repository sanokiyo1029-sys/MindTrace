// Changes saved on this device first, then sent to the server: question edits and scan-review edits.
// One entry per thing being edited (later edits replace the body but keep the version the edit started from), so a
// retry never sends the same change twice and the server's version check refuses a stale edit instead of silently
// overwriting someone else's. Entries are kept per signed-in teacher and survive reloads and expired sessions.
import { api, getTeacherId, store } from './api.js';

const key = () => `mt_outbox:${getTeacherId() || 'signed-out'}`;
const listeners = new Set();
let flushing = null;

export function outbox() {
  try { return JSON.parse(store.get(key()) || '[]'); } catch { return []; }
}
function save(items) { store.set(key(), items.length ? JSON.stringify(items) : ''); listeners.forEach(fn => fn(items)); }
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export const entry = (id) => outbox().find(e => e.id === id);

// id: "question:q_1" | "scan:sc_1". baseVersion: the server version this edit started from.
export function queue({ id, label, method, path, body, baseVersion }) {
  const items = outbox();
  const old = items.find(e => e.id === id);
  const next = { id, label, method, path, body, base_version: old?.status === 'conflict' ? baseVersion : old?.base_version ?? baseVersion,
    status: 'pending', error: '', current: null, saved_at: new Date().toISOString() };
  save(old ? items.map(e => e.id === id ? next : e) : [...items, next]);
  return next;
}
export function drop(id) { save(outbox().filter(e => e.id !== id)); }

// Send everything pending. onSynced(entry, serverResult) lets the screens pick up the new versions.
export function flush(onSynced = () => {}) {
  if (flushing) return flushing;
  flushing = (async () => {
    for (const e of outbox().filter(x => x.status === 'pending')) {
      try {
        const result = await api.send(e.method, e.path, { ...e.body, base_version: e.base_version });
        drop(e.id);
        onSynced(e, result);
      } catch (error) {
        if (error.offline) break; // still offline: keep everything, try again on reconnect
        const status = error.code === 'conflict' ? 'conflict' : error.status === 401 ? 'blocked' : 'failed';
        save(outbox().map(x => x.id === e.id ? { ...x, status, error: error.message, current: error.current || null } : x));
        if (status === 'blocked') break; // session ended: keep the rest for after sign-in
      }
    }
  })().finally(() => { flushing = null; });
  return flushing;
}

// After a conflict: keep my version on top of the newer server copy, or throw mine away.
export function keepMine(id, currentVersion) {
  save(outbox().map(x => x.id === id ? { ...x, status: 'pending', base_version: currentVersion, current: null, error: '' } : x));
}
export function retryBlocked() { save(outbox().map(x => x.status === 'blocked' || x.status === 'failed' ? { ...x, status: 'pending' } : x)); }

export function summary(items = outbox()) {
  const count = (s) => items.filter(e => e.status === s).length;
  return { pending: count('pending'), conflict: count('conflict'), blocked: count('blocked'), failed: count('failed'), total: items.length };
}
