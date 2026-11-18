// Gemini, without any MindTrace API key: MindTrace prepares the question (and image) and opens gemini.google.com in a
// popup signed in as the teacher's own Google account. Whatever that account's plan includes (for example a Gemini
// subscription) is what they get: Google applies it, not MindTrace. Google sign-in doesn't tell apps whether an account
// has a subscription, so MindTrace can't check it; it only makes sure Gemini opens as the account the teacher signed in with.
import { useEffect, useRef, useState } from 'react';
import { isNative } from './api.js';
import Icon from './Icon.jsx';
import { Button, PageHeading, Panel } from './ui.jsx';

const MAX_BYTES = 10 * 1024 * 1024;
const TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const ACTIONS = {
  extract: 'Extract all text from the attached image exactly as written. Keep the wording and line breaks. Mark anything you cannot read as [unreadable].',
  summarize: 'Summarize the attached image (or the text below) in a few short bullet points a teacher can act on.',
  describe: 'Describe what the attached image shows, clearly and factually. Mention any visible text.',
};

export const geminiUrl = (account) => `https://gemini.google.com/app${account ? `?authuser=${encodeURIComponent(account)}` : ''}`;

// Images go to the clipboard as PNG (what browsers allow), so the teacher can paste them into Gemini or Lens.
export async function toPng(blob) {
  if (blob.type === 'image/png') return blob;
  const bitmap = await createImageBitmap(blob);
  const canvas = Object.assign(document.createElement('canvas'), { width: bitmap.width, height: bitmap.height });
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  return new Promise((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(new Error('Couldn’t prepare the image.')), 'image/png'));
}
export function copyImage(blobPromise) { // call straight from a click, before opening any window
  if (!window.ClipboardItem || !navigator.clipboard?.write) return Promise.reject(new Error('This browser can’t copy images.'));
  return navigator.clipboard.write([new ClipboardItem({ 'image/png': Promise.resolve(blobPromise).then(toPng) })]);
}

export default function AiPage({ account, flash, onSignOut }) {
  const [prompt, setPrompt] = useState('');
  const [image, setImage] = useState(null); // { file, url }
  const [step, setStep] = useState('');
  const fileRef = useRef(null);
  useEffect(() => () => { if (image) URL.revokeObjectURL(image.url); }, [image]);

  if (!account) return <>
    <PageHeading eyebrow="GEMINI" title="Use Gemini with your own Google account." description="MindTrace doesn’t use an API key for Gemini. It opens Gemini as the Google account you sign in with, so your own plan applies." />
    <Panel className="ai-panel"><h2>Sign in with Google to use Gemini</h2>
      <p>You signed in with an email and password. Sign out, then choose “Continue with Google” with the Google account that has your Gemini plan.</p>
      <Button onClick={onSignOut} icon="arrow">Sign out and continue with Google</Button></Panel>
  </>;

  function attach(file) {
    if (!file) return;
    if (!TYPES.includes(file.type)) return flash('Use a JPG, PNG or WebP image.');
    if (file.size > MAX_BYTES) return flash('That image is over 10 MB. Use a screenshot or a smaller photo.');
    setImage({ file, url: URL.createObjectURL(file) });
  }
  function onPaste(e) {
    const item = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/'));
    if (item) { e.preventDefault(); attach(item.getAsFile()); }
  }
  function openGemini(text) {
    // Copy first (needs this page focused), then open the popup in the same click.
    const copied = text ? navigator.clipboard?.writeText(text) : copyImage(image.file);
    window.open(geminiUrl(account), isNative ? '_blank' : 'mindtrace-gemini', isNative ? undefined : 'popup,width=560,height=820');
    Promise.resolve(copied).then(() => setStep(text ? (image ? 'text-then-image' : 'text') : 'image'),
      () => setStep('manual'));
  }
  const question = (action) => [ACTIONS[action], prompt.trim()].filter(Boolean).join('\n\n');

  return <>
    <PageHeading eyebrow="GEMINI · YOUR GOOGLE ACCOUNT" title="Ask Gemini about a lesson, a photo or a screenshot."
      description={`Opens Gemini as ${account}. No MindTrace API key; your Google plan applies.`} />
    <Panel className="ai-panel">
      <div className="ai-actions" role="group" aria-label="Quick actions">
        <button type="button" disabled={!image} onClick={() => openGemini(question('extract'))}><Icon name="book" size={16} /> Extract text</button>
        <button type="button" disabled={!image && !prompt.trim()} onClick={() => openGemini(question('summarize'))}><Icon name="chart" size={16} /> Summarize</button>
        <button type="button" disabled={!image} onClick={() => openGemini(question('describe'))}><Icon name="scan" size={16} /> Describe image</button>
      </div>
      {image && <div className="ai-preview"><img src={image.url} alt="Attached image preview" />
        <button type="button" className="ai-remove" aria-label="Remove the attached image" onClick={() => setImage(null)}><Icon name="close" size={16} /></button></div>}
      <label className="field ai-prompt">Your question<textarea rows="3" value={prompt} maxLength={4000} onChange={e => setPrompt(e.target.value)} onPaste={onPaste}
        placeholder={image ? 'Ask about the image (optional)' : 'e.g. Explain why 1/3 + 1/3 is not 2/6 for a 12-year-old'} /></label>
      <div className="ai-send-row">
        <button type="button" className="button outline" onClick={() => fileRef.current?.click()}><Icon name="clip" size={16} /> {image ? 'Change image' : 'Attach image'}</button>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e => { attach(e.target.files?.[0]); e.target.value = ''; }} />
        {image && <button type="button" className="button outline" onClick={() => copyImage(image.file).then(() => flash('Image copied. Paste it into Gemini.', 'success'), e => flash(e.message))}><Icon name="copy" size={16} /> Copy image</button>}
        <Button type="button" disabled={!prompt.trim() && !image} onClick={() => openGemini(prompt.trim())} icon="spark">Open in Gemini</Button>
      </div>
      {step && <div className="note-banner" role="status"><Icon name="spark" size={17} /><p>{{
        text: 'Gemini is open. Your question is copied: click the Gemini box and paste it (Ctrl+V, or long-press → Paste).',
        'text-then-image': 'Gemini is open and your question is copied. Paste it, then come back, click Copy image and paste the image too.',
        image: 'Gemini is open and the image is copied. Paste it into Gemini (Ctrl+V, or long-press → Paste) and ask your question.',
        manual: 'Gemini is open. Copying didn’t work here, so type your question and attach the image in Gemini directly.',
      }[step]}</p></div>}
      <small className="ai-hint">Gemini opens in a separate window (or the Gemini app on phones). If nothing opens, allow pop-ups for this site.</small>
    </Panel>
  </>;
}
