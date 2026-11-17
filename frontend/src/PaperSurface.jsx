import { useEffect, useRef } from 'react';

export default function PaperSurface({ as: Element = 'section', className = '', children }) {
  const pointer = useRef({ rect: null, frame: 0, x: 0, y: 0 });
  useEffect(() => () => cancelAnimationFrame(pointer.current.frame), []);

  function move(event) {
    if (event.pointerType !== 'mouse') return;
    const state = pointer.current;
    if (!state.rect) {
      if (!window.matchMedia('(any-hover: hover) and (any-pointer: fine) and (prefers-reduced-motion: no-preference)').matches) return;
      state.rect = event.currentTarget.getBoundingClientRect();
    }
    state.x = event.clientX - state.rect.left;
    state.y = event.clientY - state.rect.top;
    if (state.frame) return;
    const element = event.currentTarget;
    state.frame = requestAnimationFrame(() => {
      element.style.setProperty('--pointer-x', `${state.x}px`);
      element.style.setProperty('--pointer-y', `${state.y}px`);
      element.dataset.pointer = 'on';
      state.frame = 0;
    });
  }

  function leave(event) {
    cancelAnimationFrame(pointer.current.frame);
    pointer.current.frame = 0;
    pointer.current.rect = null;
    delete event.currentTarget.dataset.pointer;
  }

  return <Element className={`pointer-card ${className}`}
    onPointerEnter={move} onPointerMove={move} onPointerLeave={leave} onPointerCancel={leave}>
    <span className="paper-highlight" aria-hidden="true" />{children}
  </Element>;
}
