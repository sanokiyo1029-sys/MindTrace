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

// Only the Android app needs a server address. The website always talks to the server it was loaded from,
// so there is never a separate Cloudflare URL to copy (and an old saved address can't break sign-in).
// VITE_SERVER_URL (optional, set when building the APK) is the app's default; the Server address field overrides it.
const DEFAULT_SERVER = (import.meta.env.VITE_SERVER_URL || '').replace(/\/+$/, '');
export const getServer = () => isNative ? (store.get('mt_server') || DEFAULT_SERVER) : '';
export const setServer = (url) => { store.set('mt_server', url.trim().replace(/\/+$/, '').replace(/\/api$/, '')); window.dispatchEvent(new Event('mt-server')); };
const apiBase = () => getServer() ? `${getServer()}/api` : (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
// The sheet PDF is opened directly by the browser (or the phone's browser), so it authenticates with ?token= (CONTRACTS).
export const printUrl = (id) => `${apiBase()}/assessments/${id}/print?token=${encodeURIComponent(teacherToken)}`;
// Media URLs from the API start with /api/media/...; point them at the saved server when there is one. Scan images
// are private (teacher who owns it, or the student once released), so <img> tags carry the token like the PDF link.
export const mediaUrl = (url, token = teacherToken) => {
  if (!url) return url;
  const full = url.startsWith('/') && getServer() ? `${getServer()}${url}` : url;
  return token && url.startsWith('/api/media/') ? `${full}?token=${encodeURIComponent(token)}` : full;
};

let teacherToken = store.get('mt_token');
let onAuthLost = () => {};
export const getTeacherToken = () => teacherToken;
export const setTeacherToken = (token) => { teacherToken = token; store.set('mt_token', token); };
// Who is signed in (scopes work saved on this device) and the student's own session, both kept across refreshes.
export const getTeacherId = () => store.get('mt_teacher_id');
export const setTeacherId = (id) => store.set('mt_teacher_id', id);
export const readStudentSession = () => {
  try {
    const saved = JSON.parse(store.get('mt_student_session') || 'null');
    if (saved?.token) return { role: 'student', ...saved };
  } catch { /* Older sessions use the token-only key. */ }
  const token = store.get('mt_student_token');
  return token ? { role: 'student', token } : null;
};
export const setStudentToken = (token, student) => {
  store.set('mt_student_session', token ? JSON.stringify({ token, student: student?.id ? { id: student.id } : undefined }) : '');
  store.set('mt_student_token', '');
};
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
  if (import.meta.env.MODE === 'android') headers.set('X-MindTrace-Mode', 'lens-only');
  const isSignIn = /\/login$|\/signup$|^\/auth\/google$|^\/auth\/password\//.test(path);
  const usesTeacherToken = teacherToken && !isSignIn && !headers.has('Authorization');
  if (usesTeacherToken) headers.set('Authorization', `Bearer ${teacherToken}`);
  let response;
  try { response = await fetch(`${apiBase()}${path}`, { ...options, headers, signal: AbortSignal.timeout(70000) }); }
  catch (error) {
    if (error.name === 'TimeoutError') throw Object.assign(new Error('The server took too long to answer. Please try again.'), { offline: true });
    throw Object.assign(new Error(!navigator.onLine ? 'You are offline. This needs an internet connection.' : isNative ? `Could not reach the MindTrace server at ${getServer()}. Check the Server address and that the backend is running.` : 'Could not reach the MindTrace server. Check your connection and that the backend is running.'), { offline: true });
  }
  const type = response.headers.get('content-type') || '';
  if (!response.ok) {
    const body = type.includes('json') ? await response.json() : null;
    if (response.status === 401 && usesTeacherToken) { setTeacherToken(''); onAuthLost(); }
    const error = new Error(body?.message || `Request failed (${response.status}). Check the connection and try again.`);
    error.validationErrors = body?.questions;
    Object.assign(error, { status: response.status, code: body?.error, current: body?.current, retryable: body?.retryable });
    throw error;
  }
  return options.raw ? response.blob() : response.json();
}

const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const studentExamRequest = (token, path, options = {}) => request(`/student/me/exams${path}`, {
  ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` },
});

export const api = {
  health: () => request('/health'),
  login: (body) => request('/auth/teacher/login', json('POST', body)),
  authConfig: () => request('/auth/config'),
  googleLogin: (body) => request('/auth/google', json('POST', body)),
  teacherSignup: (body) => request('/auth/teacher/signup', json('POST', body)),
  createClass: (body) => request('/classes', json('POST', body)),
  // Phase 1 accounts. Student calls take the student's token explicitly (the teacher token is the default).
  studentSignup: (body) => request('/auth/student/signup', json('POST', body)),
  forgotPassword: (email) => request('/auth/password/forgot', json('POST', { email })),
  resetPassword: (token, password) => request('/auth/password/reset', json('POST', { token, password })),
  profile: (token) => request('/auth/profile', token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
  editProfile: (body, token) => request('/auth/profile', { ...json('PATCH', body), ...(token && { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } }) }),
  studentClasses: (token) => request('/student/classes', { headers: { Authorization: `Bearer ${token}` } }),
  joinClass: (token, body) => request('/student/classes/join', { ...json('POST', body), headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } }),
  newJoinCode: (classId) => request(`/classes/${classId}/join-code`, { method: 'POST' }),
  addStudent: (classId, body) => request(`/classes/${classId}/students`, json('POST', body)),
  removeStudent: (classId, id) => request(`/classes/${classId}/students/${id}`, { method: 'DELETE' }),
  resetStudent: (classId, id) => request(`/classes/${classId}/students/${id}/reset`, { method: 'POST' }),
  logout: (studentToken) => request('/auth/logout', {
    method: 'POST',
    ...(studentToken && { headers: { Authorization: `Bearer ${studentToken}` } }),
  }),
  classes: () => request('/classes'),
  students: (classId) => request(`/classes/${classId}/students`),
  assessments: () => request('/assessments'),
  assessment: (id) => request(`/assessments/${id}`),
  results: (id) => request(`/assessments/${id}/results`),
  generate: (body) => request('/assessments/generate', json('POST', body)),
  editQuestion: (id, body) => request(`/questions/${id}`, json('PATCH', body)),
  approve: (id) => request(`/assessments/${id}/approve`, { method: 'POST' }),
  scans: (id) => request(`/assessments/${id}/scans`),
  uploadScan: (id, file, rollNumber) => { const form = new FormData(); form.append('image', file); if (rollNumber?.trim()) form.append('roll_number', rollNumber.trim()); return request(`/assessments/${id}/scans`, { method: 'POST', body: form }); },
  reviewScan: (id, body) => request(`/scans/${id}/review`, json('PATCH', body)),
  confirm: (id) => request(`/assessments/${id}/confirm`, { method: 'POST' }),
  insights: (id) => request(`/assessments/${id}/insights`),
  followup: (id, body) => request(`/assessments/${id}/followup`, json('POST', body)),
  studentLogin: (body) => request('/auth/student/login', json('POST', body)),
  studentResults: (token) => request('/student/me/results', { headers: { Authorization: `Bearer ${token}` } }),
  me: (token) => request('/auth/me', token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
  printPdf: (id) => request(`/assessments/${id}/print`, { raw: true }),
  overview: (classId, subject, understanding = false) => request(`/classes/${classId}/overview?subject=${encodeURIComponent(subject)}${understanding ? '&include_understanding=true' : ''}`),
  studentReport: (id) => request(`/students/${id}/report`),
  addQuestion: (id, body) => request(`/assessments/${id}/questions`, json('POST', body)),
  questionImage: (id, file) => { const form = new FormData(); form.append('image', file); return request(`/questions/${id}/image`, { method: 'POST', body: form }); },
  removeQuestionImage: (id) => request(`/questions/${id}/image`, { method: 'DELETE' }),
  feedback: (id) => request(`/assessments/${id}/feedback`),
  suggestFeedback: (id) => request(`/assessments/${id}/feedback/suggest`, { method: 'POST' }),
  editFeedback: (id, body) => request(`/feedback/${id}`, json('PATCH', body)),
  editPlan: (id, mid, body) => request(`/assessments/${id}/plan/${mid}`, json('PUT', body)),
  assign: (id) => request(`/assessments/${id}/assign`, { method: 'POST' }),
  practiceStatus: (id) => request(`/assessments/${id}/practice`),
  studentPractice: (token) => request('/student/me/practice', { headers: { Authorization: `Bearer ${token}` } }),
  submitPractice: (token, id, body) => request(`/student/me/practice/${id}`, { ...json('POST', body), headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` } }),
  exams: () => request('/exams'),
  publishExam: (body) => request('/exams', json('POST', body)),
  examReport: (id) => request(`/exams/${id}`),
  reviewExam: (id, attempt, body) => request(`/exams/${id}/attempts/${attempt}`, json('PATCH', body)),
  studentExams: (token) => studentExamRequest(token, ''),
  studentExam: (token, id) => studentExamRequest(token, `/${id}`),
  startExam: (token, id) => studentExamRequest(token, `/${id}/start`, { method: 'POST' }),
  saveExam: (token, id, body) => studentExamRequest(token, `/${id}/attempt`, json('PUT', body)),
  examImage: (token, url) => {
    if (!/^\/api\/media\/questions\/q_[a-z0-9_]+\.jpg$/.test(url)) throw new Error('This question image can’t be downloaded.');
    return request(url.slice(4), { headers: { Authorization: `Bearer ${token}` }, raw: true });
  },
  // generic call used by the offline outbox to replay a saved change
  send: (method, path, body) => request(path, json(method, body)),
};

export { demo };
