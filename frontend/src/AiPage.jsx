// AI assistant: ask Gemini about text and/or one photo or screenshot. The server holds the Gemini key; this screen only
// needs the teacher's MindTrace session (password or Continue with Google). Same code on the website and in the app.
import { useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import Icon from './Icon.jsx';
import { Button, PageHeading, Panel } from './ui.jsx';

const MAX_BYTES = 10 * 1024 * 1024; // the server's limit too
const TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];
const LABEL = { ask: 'Answer', extract: 'Extracted text', summarize: 'Summary', describe: 'Image description' };
const BUSY = { ask: 'Thinking…', extract: 'Reading the text…', summarize: 'Summarizing…', describe: 'Looking at the image…' };

function checkImage(file) {
  const type = file.type || ({ heic: 'image/heic', heif: 'image/heif' })[file.name.split('.').pop()?.toLowerCase()] || '';
  if (!TYPES.includes(type)) return 'That file isn’t a supported image. Use a JPG, PNG, WebP or HEIC photo or screenshot.';
  if (file.size > MAX_BYTES) return `That image is ${(file.size / 1048576).toFixed(1)} MB; the limit is 10 MB. Use a screenshot or a smaller photo.`;
  return '';
}

async function copy(text, flash) {
  try { await navigator.clipboard.writeText(text); flash('Copied.', 'success'); }
  catch { flash('Couldn’t copy automatically. Select the text and copy it.', 'info'); }
}

export default function AiPage({ flash }) {
  const [prompt, setPrompt] = useState('');
  const [image, setImage] = useState(null); // { file, url, previewFailed }
  const [busy, setBusy] = useState('');
  const [error, setError] = useState(null); // { message, retry: action | null }
  const [replies, setReplies] = useState([]);
  const [gemini, setGemini] = useState(null);
  const fileRef = useRef(null);
  const sending = useRef(false); // blocks a second request while one is loading (double taps too)

  useEffect(() => { api.health().then(h => setGemini(Boolean(h.gemini)), () => setGemini(null)); }, []);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image.url); }, [image]);

  function attach(file) {
    if (!file) return;
    const problem = checkImage(file);
    if (problem) { setError({ message: problem }); return; }
    setError(null);
    setImage({ file, url: URL.createObjectURL(file) });
  }
  function onPaste(e) { // a pasted screenshot becomes the attachment
    const item = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/'));
    if (item) { e.preventDefault(); attach(item.getAsFile()); }
  }

  async function send(action = 'ask') {
    if (sending.current) return;
    const text = prompt.trim();
    if ((action === 'extract' || action === 'describe') && !image) return setError({ message: 'Attach a photo or screenshot first.' });
    if (!text && !image) return setError({ message: 'Type a question or attach an image.' });
    sending.current = true; setBusy(action); setError(null);
    try {
      const form = new FormData();
      form.append('action', action); form.append('prompt', text);
      if (image) form.append('image', image.file, image.file.name || 'image');
      const r = await api.aiAsk(form);
      setReplies(list => [{ id: Date.now(), action, prompt: text, thumb: image && !image.previewFailed ? URL.createObjectURL(image.file) : null, text: r.text, truncated: r.truncated }, ...list]);
      setPrompt(''); // the image stays attached for a follow-up question; remove it with ×
    } catch (e) {
      // keep the prompt and the attachment so Try again sends exactly the same request
      setError({ message: e.offline ? 'You’re offline or the server can’t be reached. Gemini needs an internet connection; your question and image are kept.' : e.message,
        retry: e.offline || e.retryable ? action : null });
    } finally { sending.current = false; setBusy(''); }
  }

  return <>
    <PageHeading eyebrow="AI ASSISTANT · GEMINI" title="Ask about a lesson, a photo or a screenshot."
      description="Type a question, attach an image, or both. Answers are drafts for you to check, never facts about a student." />
    {gemini === false && <div className="note-banner" role="status"><Icon name="shield" size={17} /><p>Gemini isn’t set up on this server yet, so questions will fail. The admin adds the Gemini API key on the server (LLM_API_KEY, AI_MODE=live).</p></div>}
    <Panel className="ai-panel">
      <div className="ai-actions" role="group" aria-label="Quick actions">
        <button type="button" disabled={!!busy || !image} onClick={() => send('extract')}><Icon name="book" size={16} /> Extract text</button>
        <button type="button" disabled={!!busy || (!image && !prompt.trim())} onClick={() => send('summarize')}><Icon name="chart" size={16} /> Summarize</button>
        <button type="button" disabled={!!busy || !image} onClick={() => send('describe')}><Icon name="scan" size={16} /> Describe image</button>
      </div>
      {image && <div className="ai-preview">
        {image.previewFailed ? <span className="ai-file">{image.file.name}<small>Preview not available; it will still be sent.</small></span>
          : <img src={image.url} alt="Attached image preview" onError={() => setImage(i => i && { ...i, previewFailed: true })} />}
        <button type="button" className="ai-remove" aria-label="Remove the attached image" disabled={!!busy} onClick={() => setImage(null)}><Icon name="close" size={16} /></button>
      </div>}
      <form className="ai-form" onSubmit={e => { e.preventDefault(); send('ask'); }}>
        <label className="field ai-prompt">Your question<textarea rows="3" value={prompt} maxLength={4000} onChange={e => setPrompt(e.target.value)} onPaste={onPaste}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send('ask'); }}
          placeholder={image ? 'Ask about the image, or send it by itself' : 'e.g. Explain why 1/3 + 1/3 is not 2/6 for a 12-year-old'} /></label>
        <div className="ai-send-row">
          <button type="button" className="button outline" disabled={!!busy} onClick={() => fileRef.current?.click()}><Icon name="clip" size={16} /> {image ? 'Change image' : 'Attach image'}</button>
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" hidden onChange={e => { attach(e.target.files?.[0]); e.target.value = ''; }} />
          <Button type="submit" disabled={!!busy || (!prompt.trim() && !image)} aria-busy={!!busy} icon="arrow">{busy ? BUSY[busy] : 'Send'}</Button>
        </div>
        <small className="ai-hint">JPG, PNG, WebP or HEIC up to 10 MB. You can also paste a screenshot. Needs an internet connection.</small>
      </form>
      {error && <div className="field-error ai-error" role="alert">{error.message}{error.retry && <button type="button" className="text-button" disabled={!!busy} onClick={() => send(error.retry)}><Icon name="refresh" size={14} /> Try again</button>}</div>}
    </Panel>
    {busy && <p className="busy-hint" role="status">{BUSY[busy]} Usually a few seconds.</p>}
    {replies.map(r => <Panel key={r.id} className="ai-reply">
      <div className="ai-reply-head"><span className="eyebrow">{LABEL[r.action]} · Gemini</span>
        <button type="button" className="text-button" onClick={() => copy(r.text, flash)}><Icon name="copy" size={14} /> Copy</button></div>
      {(r.prompt || r.thumb) && <div className="ai-asked">{r.thumb && <img src={r.thumb} alt="" />}{r.prompt && <p>{r.prompt}</p>}</div>}
      <div className={`ai-text ${r.action === 'extract' ? 'ai-extract' : ''}`}>{r.text}</div>
      {r.truncated && <small className="ai-hint">The answer was cut short. Ask for the rest.</small>}
      {r.action === 'extract' && <small className="ai-hint">[unreadable] marks text Gemini couldn’t read. Check it against the image.</small>}
    </Panel>)}
  </>;
}
