// Phase 1 account screens: student sign-up with a class code, forgot/reset password, profile, joining another class,
// and the teacher's class page (join code + roster). Same look as the rest of MindTrace (fields, panels, buttons).
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from './api.js';
import Icon from './Icon.jsx';
import { Button, PageHeading, Panel } from './ui.jsx';

const weak = (pw) => pw.length < 8 || /^\d+$/.test(pw) || /^[a-z]+$/i.test(pw);

function Secret({ id, label, value, onChange, autoComplete = 'new-password', help }) {
  const [show, setShow] = useState(false);
  return <div className="field secret-field">
    <label htmlFor={id}>{label}</label>
    <div><input id={id} type={show ? 'text' : 'password'} autoComplete={autoComplete} value={value} onChange={onChange} required />
      <button type="button" aria-label={`${show ? 'Hide' : 'Show'} ${label.toLowerCase()}`} onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'}</button></div>
    {help && <small>{help}</small>}
  </div>;
}

// ------------------------------------------------------------------ student sign-up (class code + roll number)
export function StudentSignupForm({ onSession, serverField }) {
  const [f, setF] = useState({ name: '', email: '', password: '', confirm: '', class_code: '', roll_no: '' });
  const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setF(v => ({ ...v, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    if (loading) return;
    if (Object.entries(f).some(([k, v]) => k !== 'confirm' && !v.trim())) return setError('Fill in every field.');
    if (weak(f.password)) return setError('Use at least 8 characters, with letters and numbers.');
    if (f.password !== f.confirm) return setError('The two passwords don’t match.');
    setError(''); setLoading(true);
    try {
      const r = await api.studentSignup({ name: f.name.trim(), email: f.email.trim(), password: f.password, class_code: f.class_code.trim(), roll_no: f.roll_no.trim() });
      onSession({ role: 'student', token: r.token, student: r.student });
    } catch (err) { setError(err.message); setLoading(false); }
  }
  return <>
    <h2 className="auth-role-heading">Student account</h2>
    <p className="auth-role-description">Ask your teacher for your class code. Your roll number is the one you write on class papers.</p>
    <form onSubmit={submit} noValidate>
      <label className="field">Full name<input autoComplete="name" value={f.name} onChange={set('name')} maxLength={120} required /></label>
      <label className="field">Email<input type="email" autoComplete="email" value={f.email} onChange={set('email')} required /></label>
      <div className="field-row">
        <label className="field">Class code<input value={f.class_code} onChange={set('class_code')} placeholder="e.g. K7Q-3MP" autoCapitalize="characters" required /></label>
        <label className="field">Roll number<input value={f.roll_no} onChange={set('roll_no')} placeholder="e.g. 07" maxLength={12} required /></label>
      </div>
      <Secret id="student-password" label="Password" value={f.password} onChange={set('password')} help="At least 8 characters, with letters and numbers." />
      <Secret id="student-confirm" label="Confirm password" value={f.confirm} onChange={set('confirm')} />
      {serverField}
      {error && <p className="field-error" role="alert">{error}</p>}
      <button type="submit" className="button primary" disabled={loading}><Icon name="arrow" size={17} /> {loading ? 'Creating your account…' : 'Create account'}</button>
    </form>
  </>;
}

// ------------------------------------------------------------------ forgot / reset password (public pages)
export function ForgotPassword() {
  const [email, setEmail] = useState(''); const [state, setState] = useState(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (!email.trim()) return setError('Enter the email you signed up with.');
    setBusy(true); setError('');
    try { setState(await api.forgotPassword(email.trim())); } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel student-panel auth-panel unified-auth"><div className="student-login">
    <span className="student-lock"><Icon name="shield" size={25} /></span>
    <h1>Reset your password</h1>
    {state ? (state.email_enabled
      ? <p role="status">If an account uses that email, a reset link is on its way. It works once, for 30 minutes.</p>
      : <p role="status">Email isn’t set up on this MindTrace server. <b>Students:</b> ask your teacher to reset your password from the class page. <b>Teachers:</b> ask the site admin for a reset link.</p>)
      : <form onSubmit={submit} noValidate>
        <p>Enter the email you use for MindTrace. Students who sign in with a student code and PIN: ask your teacher for a new PIN.</p>
        <label className="field">Email<input type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required /></label>
        {error && <p className="field-error" role="alert">{error}</p>}
        <button type="submit" className="button primary" disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</button>
      </form>}
    <p className="auth-switch"><Link className="text-link" to="/login">Back to sign in</Link></p>
  </div></section>;
}

export function ResetPassword() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token') || '';
  const [pw, setPw] = useState(''); const [confirm, setConfirm] = useState(''); const [done, setDone] = useState(false);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (weak(pw)) return setError('Use at least 8 characters, with letters and numbers.');
    if (pw !== confirm) return setError('The two passwords don’t match.');
    setBusy(true); setError('');
    try { await api.resetPassword(token, pw); setDone(true); window.history.replaceState(null, '', '/reset-password'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel student-panel auth-panel unified-auth"><div className="student-login">
    <span className="student-lock"><Icon name="shield" size={25} /></span>
    <h1>Choose a new password</h1>
    {done ? <p role="status">Password changed. You were signed out everywhere. <Link className="text-link" to="/login">Sign in</Link></p>
      : !token ? <p role="alert">This page needs the link from your reset email. <Link className="text-link" to="/forgot-password">Ask for a new link</Link></p>
        : <form onSubmit={submit} noValidate>
          <Secret id="reset-pw" label="New password" value={pw} onChange={e => setPw(e.target.value)} help="At least 8 characters, with letters and numbers." />
          <Secret id="reset-confirm" label="Confirm password" value={confirm} onChange={e => setConfirm(e.target.value)} />
          {error && <p className="field-error" role="alert">{error}</p>}
          <button type="submit" className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save new password'}</button>
        </form>}
  </div></section>;
}

// ------------------------------------------------------------------ profile (teacher and student)
export function ProfilePanel({ token, flash = () => {} }) {
  const [p, setP] = useState(null); const [name, setName] = useState(''); const [email, setEmail] = useState('');
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [msg, setMsg] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { api.profile(token).then(r => { setP(r); setName(r.name); setEmail(r.email || ''); }, e => setError(e.message)); }, [token]);
  async function save(e) {
    e.preventDefault(); setMsg(''); setError('');
    const body = { name };
    if (p.has_password && email.trim() && email.trim() !== p.email) body.email = email.trim();
    if (next) { if (weak(next)) return setError('Use at least 8 characters, with letters and numbers.'); body.new_password = next; }
    if (body.email || body.new_password) body.current_password = current;
    setBusy(true);
    try { const r = await api.editProfile(body, token); setP(r); setCurrent(''); setNext(''); setMsg(body.new_password ? 'Saved. Other devices were signed out.' : 'Saved.'); flash('Profile saved.', 'success'); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  if (!p) return <Panel className="profile-panel">{error ? <p className="field-error" role="alert">{error}</p> : <p className="list-empty" role="status">Loading your profile…</p>}</Panel>;
  return <Panel className="profile-panel"><form onSubmit={save} noValidate>
    <span className="eyebrow">PROFILE · {p.role === 'teacher' ? 'TEACHER' : 'STUDENT'}</span>
    <label className="field">Name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} autoComplete="name" /></label>
    {p.has_password ? <>
      <label className="field">Email<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label>
      <Secret id="profile-new" label="New password (optional)" value={next} onChange={e => setNext(e.target.value)} />
      {(next || (email.trim() && email.trim() !== p.email)) && <Secret id="profile-current" label="Current password" value={current} onChange={e => setCurrent(e.target.value)} autoComplete="current-password" help="Needed to change your email or password." />}
    </> : <p className="list-empty">You sign in with student code <b>{p.student_code}</b> and a PIN from your teacher. Ask your teacher for a new PIN.</p>}
    {p.google_linked && <p className="list-empty">Google sign-in is linked to this account.</p>}
    {error && <p className="field-error" role="alert">{error}</p>}
    {msg && <p role="status" className="profile-msg">{msg}</p>}
    <Button type="submit" disabled={busy} icon="check">{busy ? 'Saving…' : 'Save profile'}</Button>
  </form></Panel>;
}

// ------------------------------------------------------------------ student: my classes + join another
export function MyClasses({ token, onJoined }) {
  const [rows, setRows] = useState(null); const [code, setCode] = useState(''); const [roll, setRoll] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { api.studentClasses(token).then(setRows, () => setRows([])); }, [token]);
  async function join(e) {
    e.preventDefault();
    if (!code.trim() || !roll.trim()) return setError('Enter the class code and your roll number.');
    setBusy(true); setError('');
    try { setRows(await api.joinClass(token, { class_code: code.trim(), roll_no: roll.trim() })); setCode(''); setRoll(''); onJoined?.(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <section className="panel student-result-card">
    {rows === null ? <p role="status">Loading your classes…</p> : <ul className="my-classes">{rows.map(c => <li key={c.class_id}><b>Class {c.name}</b><span>{c.teacher} · roll {c.roll_no}</span></li>)}</ul>}
    <form className="join-class" onSubmit={join} noValidate>
      <div className="field-row">
        <label className="field">Class code<input value={code} onChange={e => setCode(e.target.value)} placeholder="e.g. K7Q-3MP" /></label>
        <label className="field">Roll number in that class<input value={roll} onChange={e => setRoll(e.target.value)} maxLength={12} /></label>
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
      <button type="submit" className="button outline" disabled={busy}>{busy ? 'Joining…' : 'Join class'}</button>
    </form>
  </section>;
}

// ------------------------------------------------------------------ teacher: class page (join code + roster)
export function ClassManage({ classes, classId, setClassId, loadClasses, flash }) {
  const cls = classes.find(c => c.id === classId);
  const [roster, setRoster] = useState(null); const [name, setName] = useState(''); const [roll, setRoll] = useState('');
  const [shown, setShown] = useState(null); // a newly issued code + PIN / password, shown once
  const [busy, setBusy] = useState('');
  const load = () => { setRoster(null); api.students(classId).then(setRoster, () => setRoster('error')); };
  useEffect(() => { if (classId) load(); }, [classId]);
  if (!cls) return <><PageHeading eyebrow="CLASS" title="No class yet" description="Create your first class from the Overview." /><Link to="/workspace" className="button outline">Go to Overview</Link></>;
  async function run(kind, fn) { setBusy(kind); try { return await fn(); } catch (e) { flash(e.message); return null; } finally { setBusy(''); } }
  const copy = (text) => navigator.clipboard?.writeText(text).then(() => flash('Copied.', 'success'), () => flash('Select the code and copy it.', 'info'));
  async function add(e) {
    e.preventDefault();
    if (!name.trim() || !roll.trim()) return flash('Enter the student’s name and roll number.');
    const s = await run('add', () => api.addStudent(classId, { display_name: name.trim(), roll_no: roll.trim() }));
    if (s) { setShown({ who: s.display_name, code: s.student_code, pin: s.pin }); setName(''); setRoll(''); load(); }
  }
  return <>
    <PageHeading eyebrow="CLASS & STUDENTS" title={`Class ${cls.name}`} description="Share the class code so students can create accounts and join. You can also add students yourself and hand out a code and PIN."
      action={<select aria-label="Class" value={classId} onChange={e => setClassId(e.target.value)}>{classes.map(c => <option key={c.id} value={c.id}>Class {c.name}</option>)}</select>} />
    <div className="class-manage">
      <Panel className="join-code-card"><span className="eyebrow">CLASS CODE</span>
        <div className="join-code"><code>{cls.join_code || '—'}</code>
          <button type="button" className="text-button" onClick={() => copy(cls.join_code)}><Icon name="copy" size={14} /> Copy</button></div>
        <p>Students go to <b>Get Started → Student</b>, enter this code and their roll number.</p>
        <Button variant="outline" disabled={busy === 'code'} onClick={() => run('code', async () => { await api.newJoinCode(classId); loadClasses(); flash('New class code made. The old one no longer works.', 'success'); })}>{busy === 'code' ? 'Making…' : 'Make a new code'}</Button>
      </Panel>
      <Panel className="add-student-card"><span className="eyebrow">ADD A STUDENT</span>
        <form onSubmit={add} noValidate><div className="field-row">
          <label className="field">Name<input value={name} onChange={e => setName(e.target.value)} maxLength={120} /></label>
          <label className="field">Roll number<input value={roll} onChange={e => setRoll(e.target.value)} maxLength={12} placeholder="e.g. 07" /></label>
        </div><Button type="submit" disabled={busy === 'add'} icon="plus">{busy === 'add' ? 'Adding…' : 'Add student'}</Button></form>
        {shown && <div className="note-banner issued" role="status" ref={el => el?.scrollIntoView({ block: 'center', behavior: 'smooth' })}><Icon name="shield" size={17} /><p>
          <b>{shown.who}</b>: student code <code>{shown.code}</code>{shown.pin && <> · PIN <code>{shown.pin}</code></>}{shown.password && <> · temporary password <code>{shown.password}</code></>}.
          Write it down now; it isn’t shown again.</p><button type="button" className="text-button" onClick={() => setShown(null)}>Done</button></div>}
      </Panel>
    </div>
    <Panel className="list-panel"><span className="eyebrow">ROSTER</span><h2>{roster && roster !== 'error' ? `${roster.length} student${roster.length === 1 ? '' : 's'}` : 'Students'}</h2>
      {roster === null ? <p className="list-empty" role="status">Loading…</p> : roster === 'error' ? <p className="list-empty" role="alert">Couldn’t load the class list. <button className="text-button" onClick={load}>Try again</button></p>
        : !roster.length ? <p className="list-empty">No students yet. Share the class code or add students above.</p>
          : <div className="table-scroll"><table className="results-table"><thead><tr><th>Roll</th><th>Name</th><th>Login</th><th></th></tr></thead><tbody>
            {roster.map(s => <tr key={s.id}><td>{s.roll_no}</td><td><Link to={`/students/${s.id}`} className="text-link">{s.display_name}</Link></td>
              <td>{s.has_account ? 'Own account' : <code>{s.student_code}</code>}</td>
              <td className="roster-actions">
                <button type="button" className="text-button" disabled={!!busy} onClick={() => run('reset' + s.id, async () => { if (!window.confirm(`Reset ${s.display_name}'s sign-in? Their current PIN${s.has_account ? ' and password' : ''} stop working.`)) return; const r = await api.resetStudent(classId, s.id); setShown({ who: s.display_name, code: r.student_code, pin: r.pin, password: r.temporary_password }); })}>Reset sign-in</button>
                <button type="button" className="text-button" disabled={!!busy} onClick={() => run('rm' + s.id, async () => { if (!window.confirm(`Remove ${s.display_name} from class ${cls.name}?`)) return; await api.removeStudent(classId, s.id); flash(`${s.display_name} removed.`, 'success'); load(); })}>Remove</button>
              </td></tr>)}
          </tbody></table></div>}
    </Panel>
  </>;
}
