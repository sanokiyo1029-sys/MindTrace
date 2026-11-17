import demo from './fixtures/demo.json';

const base = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
export const isMock = import.meta.env.VITE_MOCK !== 'false';
let teacherToken = '';
export const setTeacherToken = (token) => { teacherToken = token; };

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (teacherToken && !path.includes('/auth/') && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${teacherToken}`);
  const response = await fetch(`${base}${path}`, { ...options, headers });
  const type = response.headers.get('content-type') || '';
  if (!response.ok) {
    const body = type.includes('json') ? await response.json() : null;
    const error = new Error(body?.message || `Request failed (${response.status}). Check the connection and try again.`);
    error.validationErrors = body?.questions;
    throw error;
  }
  return type.includes('application/pdf') ? response.blob() : response.json();
}

export const api = {
  login: (body) => request('/auth/teacher/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  students: (classId) => request(`/classes/${classId}/students`),
  generate: (body) => request('/assessments/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  editQuestion: (id, body) => request(`/questions/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  approve: (id) => request(`/assessments/${id}/approve`, { method: 'POST' }),
  print: (id) => request(`/assessments/${id}/print`),
  scans: (id) => request(`/assessments/${id}/scans`),
  uploadScan: (id, file) => { const form = new FormData(); form.append('image', file); return request(`/assessments/${id}/scans`, { method: 'POST', body: form }); },
  reviewScan: (id, body) => request(`/scans/${id}/review`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  confirm: (id) => request(`/assessments/${id}/confirm`, { method: 'POST' }),
  insights: (id) => request(`/assessments/${id}/insights`),
  followup: (id, body) => request(`/assessments/${id}/followup`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  studentLogin: (body) => request('/auth/student/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  studentResults: (token) => request('/student/me/results', { headers: { Authorization: `Bearer ${token}` } }),
};

export { demo };
