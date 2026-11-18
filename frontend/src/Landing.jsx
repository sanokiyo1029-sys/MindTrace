import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Icon from './Icon.jsx';
import PaperSurface from './PaperSurface.jsx';

export function Wordmark() {
  return <span className="wordmark" aria-label="MindTrace" role="img">
    {[...'MINDTRACE'].map((letter, index) => <span aria-hidden="true" key={index}>{letter}</span>)}
  </span>;
}

function PublicWordmark() {
  return <span className="mindtrace-wordmark">Mind<span>Trace</span></span>;
}

export function SiteHeader({ page, home, onSignOut }) {
  return <header className="site-header">
    <div className="site-header-inner">
      <Link className="site-home" to="/" aria-label="MindTrace home"><PublicWordmark /></Link>
      <nav className="site-links" aria-label="Site navigation">
        {page === 'landing' ? <>
          <Link to="/" className="site-home-link">Home</Link>
          <a href="#how-it-works" className="site-how-link">How It Works</a>
          {!home && <Link to="/login" className="site-login-link">Log in</Link>}
          <Link className="site-get-started" to={home || '/signup'}>{home ? 'My Workspace' : 'Get Started'} <Icon name="arrow" size={17} /></Link>
        </> : <Link to="/">Home</Link>}
        {page === 'student' && <button type="button" className="text-link" onClick={onSignOut}>Sign out</button>}
      </nav>
    </div>
  </header>;
}

const steps = [
  {
    icon: 'book', title: 'Give a paper quiz.',
    detail: 'Start with the concepts you taught. Review the questions, then print the answer sheets for your class.',
  },
  {
    icon: 'scan', title: 'Scan the answer sheets.',
    detail: 'Use one phone to read the marked bubbles. Check unclear marks before confirming the class results.',
  },
  {
    icon: 'chart', title: 'See what to reteach.',
    detail: 'Review what the repeated answers suggest. Try a teaching activity and check understanding again.',
  },
];

const story = [
  ['The question', 'Add one third and one third.', 1700],
  ['A wrong answer', 'A student writes two sixths.', 1950],
  ['Look closer', 'Why did the denominator change?', 2050],
  ['A repeated mistake', 'Several sheets show the same answer.', 2150],
  ['Scan the sheets', 'The teacher scans the marked answer bubbles.', 2300],
  ['A possible misconception', 'The answers suggest students may be adding the denominators.', 2800],
  ['A teaching action', 'Two one-third pieces make two thirds. Each piece is still one third.', 2950],
  ['A follow-up', 'Try a new question: one fourth plus two fourths.', 2700],
];

function Fraction({ top, bottom }) {
  return <span className="fraction"><span>{top}</span><span>{bottom}</span></span>;
}

function MathPaper({ scene }) {
  return <div className={`story-paper math-paper math-phase-${scene}`}>
    <span className="story-type">Class 7 · Fractions</span>
    <p className="story-prompt">Add the fractions.</p>
    <div className="story-equation">
      <span className="story-operand"><Fraction top={1} bottom={3} /> + <Fraction top={1} bottom={3} /> =</span>
      {scene === 0 ? <span className="story-blank">?</span> :
        <span className="story-result" key="wrong"><Fraction top={2} bottom={6} /><i className="quiz-cross" /></span>}
    </div>
    {scene > 0 && <p className="story-annotation" key={scene}>
      <span className="marker-text">{scene === 1 ? 'Something isn’t right…' : 'Why did this happen?'}</span>
    </p>}
  </div>;
}

function BubbleSheet() {
  return <div className="bubble-sheet">
    <span className="story-type">Fraction check</span>
    <div className="bubble-question">⅓ + ⅓ = ?</div>
    <div className="quiz-choices">{['2/6', '2/3', '1/9', '1/3'].map(value => <span key={value}>
      <i className={value === '2/6' ? 'quiz-filled' : ''} />{value}
    </span>)}</div>
    <div className="bubble-rule" /><div className="bubble-rule" />
  </div>;
}

function StoryBeat({ index }) {
  if (index === 3) return <div className="story-repeat">
    <div className="repeat-sheets"><BubbleSheet /><BubbleSheet /><BubbleSheet /></div>
    <p className="story-annotation">Same mistake. Multiple students.</p>
  </div>;

  if (index === 4) return <div className="phone-preview story-phone">
    <div className="phone-handle" />
    <div className="phone-screen">
      <div className="phone-label"><Icon name="scan" size={15} /> Sheet capture</div>
      <div className="phone-capture"><BubbleSheet /><div className="phone-guide" /><div className="phone-sweep" /></div>
      <div className="phone-label phone-verified"><Icon name="check" size={15} /> Bubbles read</div>
    </div>
  </div>;

  if (index === 5) return <div className="story-paper story-insight">
    <span className="story-type possible-label">Possible Misconception</span>
    <strong>Adding denominators when combining fractions.</strong>
    <div className="story-evidence"><span>Repeated answer</span><b>2/6</b></div>
  </div>;

  if (index === 6) return <div className="story-paper story-teaching">
    <span className="story-type">Reteach the concept.</span>
    <div className="story-strips"><span>⅓</span><span>⅓</span><span /></div>
    <strong className="story-equation"><Fraction top={1} bottom={3} /> + <Fraction top={1} bottom={3} /> = <Fraction top={2} bottom={3} /></strong>
    <p>Each piece is still one third.</p>
  </div>;

  return <div className="story-paper story-teaching story-followup">
    <span className="story-type">A follow-up question</span>
    <p className="story-prompt">Can you apply the same idea?</p>
    <strong className="story-equation"><Fraction top={1} bottom={4} /> + <Fraction top={2} bottom={4} /> = ?</strong>
  </div>;
}

function StoryAnimation() {
  const figure = useRef(null);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [scene, setScene] = useState(() => reduced ? 5 : 0);
  const [paused, setPaused] = useState(false);
  const [inView, setInView] = useState(false);
  const [visible, setVisible] = useState(() => !document.hidden);
  const playing = !paused && !reduced && inView && visible;
  const rememberedMath = scene < 3 ? scene : 2;

  useEffect(() => {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotion = ({ matches }) => {
      setReduced(matches);
      if (matches) setScene(5);
    };
    const updateVisibility = () => setVisible(!document.hidden);
    const observer = 'IntersectionObserver' in window
      ? new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.2 })
      : null;
    if (observer) observer.observe(figure.current);
    else setInView(true);
    motion.addEventListener('change', updateMotion);
    document.addEventListener('visibilitychange', updateVisibility);
    return () => {
      observer?.disconnect();
      motion.removeEventListener('change', updateMotion);
      document.removeEventListener('visibilitychange', updateVisibility);
    };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => setScene(index => (index + 1) % story.length), story[scene][2]);
    return () => window.clearTimeout(timer);
  }, [playing, scene]);

  function step(offset) {
    setPaused(true);
    setScene(index => (index + offset + story.length) % story.length);
  }

  return <figure className="workflow-preview hero-story" ref={figure} data-scene={scene} aria-label="How MindTrace traces a mistake">
    <div className="story-stage" aria-hidden="true">
      <div className="story-viewport">
        <div className={`story-layer ${scene < 3 ? 'is-current' : ''}`} data-beat="math"><MathPaper scene={rememberedMath} /></div>
        {[3, 4, 5, 6, 7].map(index => <div key={index} data-beat={index}
          className={`story-layer ${scene === index ? 'is-current' : ''}`}><StoryBeat index={index} /></div>)}
      </div>
    </div>
    <figcaption className="hero-story-player">
      <span className="preview-caption">
        <span>Classroom example <span aria-hidden="true">·</span> {story[scene][0]}</span>
        <span className="sr-only" aria-live={playing ? 'off' : 'polite'}>{story[scene][1]}</span>
      </span>
      <div className="story-controls">
        <button type="button" aria-label="Previous scene" onClick={() => step(-1)}><Icon name="left" size={18} /></button>
        <div className="story-progress" role="img" aria-label={`Scene ${scene + 1} of ${story.length}`}>
          {story.map(([title], index) => <span key={title} data-current={index === scene} />)}
        </div>
        {!reduced && <button type="button" aria-label={paused ? 'Play story' : 'Pause story'} onClick={() => setPaused(!paused)}>
          <Icon name={paused ? 'play' : 'pause'} size={17} />
        </button>}
        <button type="button" aria-label="Next scene" onClick={() => step(1)}><Icon name="arrow" size={18} /></button>
      </div>
    </figcaption>
  </figure>;
}

export default function Landing({ home }) {
  return <>
    <section className="landing-hero">
      <div className="hero-copy">
        <p className="landing-kicker">Paper-first assessment. Teacher-led insights.</p>
        <h1>Every Wrong Answer<br /> <span className="marker-text">Has a Story.</span></h1>
        <p className="hero-description">MindTrace helps teachers understand possible misconceptions behind repeated mistakes and discover what to teach next.</p>
      </div>
      <StoryAnimation />
      <div className="hero-actions">
        <Link to={home || '/signup'} className="button primary">{home ? 'Open My Workspace' : 'GET STARTED'} <Icon name="arrow" size={20} /></Link>
        <a href="#how-it-works" className="hero-secondary">Explore How It Works <Icon name="down" size={17} /></a>
      </div>
    </section>
    <section id="how-it-works" className="landing-workflow" tabIndex={-1}>
      <div className="landing-workflow-inner">
        <h2>From paper to your next lesson.</h2>
        <ol className="landing-steps">
          {steps.map(({ icon, title, detail }) => <PaperSurface as="li" key={title}>
            <div className="landing-step-icon"><Icon name={icon} size={25} /></div>
            <h3><span className="hover-marker">{title}</span></h3>
            <p>{detail}</p>
          </PaperSurface>)}
        </ol>
      </div>
    </section>
    <footer className="landing-footer">
      <PublicWordmark />
      <Link to="/student" className="text-link">Find my student results <Icon name="arrow" size={17} /></Link>
    </footer>
  </>;
}
