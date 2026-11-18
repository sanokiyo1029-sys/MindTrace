import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import Icon from './Icon.jsx';

// /login signs in; /signup creates an account (Get Started). Both keep ?role= and ?next=.
export default function Auth({ signup = false, onSession, onSample, googleSignIn, serverField, note }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const role = params.get('role') === 'student' ? 'student' : 'teacher';
  const teacher = role === 'teacher';
  const [studentCode, setStudentCode] = useState('');
  const [pin, setPin] = useState('');
  const linking = signup && !teacher;
  function openMode(nextRole, nextSignup = false) {
    setStudentCode('');
    setPin('');
    const q = new URLSearchParams(params);
    q.set('role', nextRole);
    q.delete('mode');
    navigate(`${nextSignup ? '/signup' : '/login'}?${q}`, { replace: true });
  }

  return <div className="login-layout teacher-access unified-access">
    <section className="panel student-panel auth-panel unified-auth">
      <div className="student-login">
        <span className="student-lock"><Icon name="shield" size={25} /></span>
        <h1>{signup ? 'Create your MindTrace account' : 'Welcome back to MindTrace'}</h1>
        <p>{signup ? 'Choose who you are to get started.' : 'Sign in to continue.'}</p>
        {note && <p className="auth-note" role="status">{note}</p>}
        <div className="role-select" role="group" aria-label="Choose your role">
          <button type="button" aria-pressed={role === 'teacher'}
            onClick={() => openMode('teacher', signup)}><Icon name="book" /> Teacher</button>
          <button type="button" aria-pressed={role === 'student'}
            onClick={() => openMode('student', signup)}><Icon name="users" /> Student</button>
        </div>
        {signup ? (teacher ? <SignupForm onSession={onSession} serverField={serverField} /> : <>
          <h2 className="auth-role-heading">Student account</h2>
          <p className="auth-role-description">Your teacher creates your student account and gives you a student code and PIN.
            Sign in with those, or enter them below and connect Google so you can use Google next time.</p>
          <div className="student-google-link">
            <label className="field">Student code<input autoComplete="username" value={studentCode} placeholder="e.g. 7A-01"
              onChange={e => setStudentCode(e.target.value)} required /></label>
            <label className="field">PIN<input type="password" inputMode="numeric" autoComplete="current-password" value={pin}
              onChange={e => setPin(e.target.value)} required /></label>
          </div>
          {serverField}
        </>) : <AuthForm key={role} role={role} onSession={onSession} serverField={serverField} />}
        <div className={linking ? 'auth-google-only' : undefined}>{googleSignIn({ role, signup,
          studentLink: linking ? { student_code: studentCode.trim(), pin: pin.trim() } : undefined })}</div>
        <p className="auth-switch">{signup
          ? <>Already have an account? <button type="button" className="text-button" onClick={() => openMode(role, false)}>Sign in</button></>
          : <>New to MindTrace? <button type="button" className="text-button" onClick={() => openMode(role, true)}>{teacher ? 'Create a teacher account' : 'Connect a student account'}</button></>}</p>
        {onSample && role === 'teacher' && <button type="button" className="text-link sample-entry"
          onClick={onSample}>Explore sample workspace <Icon name="arrow" size={16} /></button>}
      </div>
    </section>
  </div>;
}

// Teacher sign-up with email and password. The server checks the same rules; these only give quicker feedback.
function SignupForm({ onSession, serverField }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    if (loading) return;
    const { name, email, password, confirm } = form;
    if (!name.trim() || !email.trim() || !password) return setError('Fill in your name, email and a password.');
    if (password.length < 8 || /^\d+$/.test(password) || /^[a-z]+$/i.test(password)) return setError('Use at least 8 characters, with letters and numbers.');
    if (password !== confirm) return setError('The two passwords don’t match.');
    setError(''); setLoading(true);
    try {
      const reply = await api.teacherSignup({ name: name.trim(), email: email.trim(), password });
      onSession({ role: 'teacher', token: reply.token, teacher: reply.teacher });
    } catch (err) { setError(err.message); setLoading(false); }
  }
  return <>
    <h2 className="auth-role-heading">Teacher account</h2>
    <p className="auth-role-description">Free for your classroom. You’ll set up your first class next.</p>
    <form onSubmit={submit} noValidate>
      <label className="field">Full name<input autoComplete="name" value={form.name} onChange={set('name')} required maxLength={120} placeholder="e.g. Priya Rao" /></label>
      <label className="field">School email<input type="email" autoComplete="email" value={form.email} onChange={set('email')} required placeholder="you@school.org" /></label>
      <div className="field secret-field">
        <label htmlFor="signup-password">Password</label>
        <div>
          <input id="signup-password" type={show ? 'text' : 'password'} autoComplete="new-password" value={form.password} onChange={set('password')}
            required minLength={8} aria-describedby="password-help" />
          <button type="button" aria-label={`${show ? 'Hide' : 'Show'} password`} onClick={() => setShow(!show)}>{show ? 'Hide' : 'Show'}</button>
        </div>
        <small id="password-help">At least 8 characters, with letters and numbers.</small>
      </div>
      <label className="field">Confirm password<input type={show ? 'text' : 'password'} autoComplete="new-password" value={form.confirm} onChange={set('confirm')} required /></label>
      {serverField}
      {error && <p className="field-error" role="alert">{error}</p>}
      <button type="submit" className="button primary" disabled={loading}>
        <Icon name="arrow" size={17} /> {loading ? 'Creating your account…' : 'Create account'}
      </button>
    </form>
  </>;
}

function AuthForm({ role, onSession, serverField }) {
  const teacher = role === 'teacher';
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const active = useRef(true);

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    setError('');
    const identity = identifier.trim();
    if (!identity || !secret) {
      setError(teacher ? 'Enter your email and password.' : 'Enter your student code and PIN.');
      return;
    }
    setLoading(true);
    try {
      const reply = teacher
        ? await api.login({ email: identity, password: secret })
        : await api.studentLogin({ student_code: identity, pin: secret });
      const { token } = reply;
      if (typeof token !== 'string' || !token.trim()) throw new Error('The server did not return a sign-in session.');
      const session = { role, token, teacher: reply.teacher, student: reply.student };
      if (!active.current) return;
      onSession(session);
    } catch (err) {
      if (active.current) setError(err.message);
    } finally {
      if (active.current) setLoading(false);
    }
  }

  return <>
    <h2 className="auth-role-heading">{teacher ? 'Welcome Back, Teacher!' : 'Welcome Back, Learner!'}</h2>
    {!teacher && <p className="auth-role-description">Your learning journey continues here.</p>}
    <form onSubmit={submit}>
      <label className="field">{teacher ? 'Email' : 'Student code'}
        <input type={teacher ? 'email' : 'text'} autoComplete="username" value={identifier}
          onChange={event => setIdentifier(event.target.value)} required placeholder={teacher ? undefined : 'e.g. 7A-01'} />
      </label>
      <div className="field secret-field">
        <label htmlFor="auth-secret">{teacher ? 'Password' : 'PIN'}</label>
        <div>
          <input id="auth-secret" type={showSecret ? 'text' : 'password'} inputMode={teacher ? undefined : 'numeric'}
            autoComplete="current-password" value={secret} onChange={event => setSecret(event.target.value)}
            required placeholder={teacher ? undefined : 'Enter your class PIN'} />
          <button type="button" aria-label={`${showSecret ? 'Hide' : 'Show'} ${teacher ? 'password' : 'PIN'}`}
            onClick={() => setShowSecret(!showSecret)}>{showSecret ? 'Hide' : 'Show'}</button>
        </div>
      </div>
      {serverField}
      {error && <p className="field-error" role="alert">{error}</p>}
      <button type="submit" className="button primary" disabled={loading}>
        <Icon name="arrow" size={17} /> {loading ? 'Signing in…' : 'Sign In'}
      </button>
    </form>
    {!teacher && <div className="signup-state"><small>Your teacher provides your student code and PIN.</small></div>}
  </>;
}
