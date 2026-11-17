import demo from './fixtures/demo.json';

// localStorage can throw (private mode, blocked storage): never let that break the app.
export const store = {
  get: (key) => { try { return localStorage.getItem(key) || ''; } catch { return ''; } },
  set: (key, value) => { try { if (value) localStorage.setItem(key, value); else localStorage.removeItem(key); } catch { /* storage unavailable */ } },
};

// Live mode is the default. Mock (labelled fixture) mode only with VITE_MOCK=true.
export const isMock = import.meta.env.VITE_MOCK === 'true';
// Inside the Android app (Capacitor) the page runs on https://localhost, so the backend needs a full address.
export const isNative = Boolean(window.Capacitor?.isNativePlatform?.());

export const getServer = () => store.get('mt_server');
export const setServer = (url) => store.set('mt_server', url.trim().replace(/\/+$/, '').replace(/\/api$/, ''));
const apiBase = () => getServer() ? `${getServer()}/api` : (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
// The sheet PDF is opened directly by the browser (or the phone's browser), so it authenticates with ?token= (CONTRACTS).
export const printUrl = (id) => `${apiBase()}/assessments/${id}/print?token=${encodeURIComponent(teacherToken)}`;
// Media URLs from the API start with /api/media/...; point them at the saved server when there is one.
export const mediaUrl = (url) => url?.startsWith('/') && getServer() ? `${getServer()}${url}` : url;

let teacherToken = store.get('mt_token');
let onAuthLost = () => {};
export const getTeacherToken = () => teacherToken;
export const setTeacherToken = (token) => { teacherToken = token; store.set('mt_token', token); };
export const setOnAuthLost = (fn) => { onAuthLost = fn; };

// How many requests are in flight; the app shows a thin loading line while any are.
let pending = 0;
let busyListener = () => {};
export const onBusy = (fn) => { busyListener = fn; return () => { busyListener = () => {}; }; };

async function request(path, options = {}) {
  pending += 1; busyListener(true);
  try { return await send(path, options); }
  finally { pending -= 1; busyListener(pending > 0); }
}

async function send(path, options) {
  if (isNative && !getServer()) throw new Error('Set the Server address first (for example https://….trycloudflare.com).');
  const headers = new Headers(options.headers || {});
  const usesTeacherToken = teacherToken && !path.includes('/auth/') && !headers.has('Authorization');
  if (usesTeacherToken) headers.set('Authorization', `Bearer ${teacherToken}`);
  let response;
  try { response = await fetch(`${apiBase()}${path}`, { ...options, headers, signal: AbortSignal.timeout(70000) }); }
  catch (error) {
    if (error.name === 'TimeoutError') throw new Error('The server took too long to answer. Please try again.');
    throw new Error(isNative ? `Could not reach the MindTrace server at ${getServer()}. Check the Server address and that the backend is running.` : 'Could not reach the MindTrace server. Check your connection and that the backend is running.');
  }
  const type = response.headers.get('content-type') || '';
  if (!response.ok) {
    const body = type.includes('json') ? await response.json() : null;
    if (response.status === 401 && usesTeacherToken) { setTeacherToken(''); onAuthLost(); }
    const error = new Error(body?.message || `Request failed (${response.status}). Check the connection and try again.`);
    error.validationErrors = body?.questions;
    throw error;
  }
  return response.json();
}

const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  health: () => request('/health'),
  login: (body) => request('/auth/teacher/login', json('POST', body)),
  students: (classId) => request(`/classes/${classId}/students`),
  assessments: () => request('/assessments'),
  assessment: (id) => request(`/assessments/${id}`),
  results: (id) => request(`/assessments/${id}/results`),
  generate: (body) => request('/assessments/generate', json('POST', body)),
  editQuestion: (id, body) => request(`/questions/${id}`, json('PATCH', body)),
  approve: (id) => request(`/assessments/${id}/approve`, { method: 'POST' }),
  scans: (id) => request(`/assessments/${id}/scans`),
  uploadScan: (id, file) => { const form = new FormData(); form.append('image', file); return request(`/assessments/${id}/scans`, { method: 'POST', body: form }); },
  reviewScan: (id, body) => request(`/scans/${id}/review`, json('PATCH', body)),
  confirm: (id) => request(`/assessments/${id}/confirm`, { method: 'POST' }),
  insights: (id) => request(`/assessments/${id}/insights`),
  followup: (id, body) => request(`/assessments/${id}/followup`, json('POST', body)),
  studentLogin: (body) => request('/auth/student/login', json('POST', body)),
  studentResults: (token) => request('/student/me/results', { headers: { Authorization: `Bearer ${token}` } }),
};

export { demo };
