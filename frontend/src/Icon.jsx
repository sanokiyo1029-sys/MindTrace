const paths = {
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  plus: 'M12 5v14M5 12h14',
  book: 'M4 5.5A2.5 2.5 0 016.5 3H20v17H6.5A2.5 2.5 0 014 17.5zM4 5v13',
  scan: 'M4 7V4h3M17 4h3v3M20 17v3h-3M7 20H4v-3M7 12h10',
  chart: 'M4 19V5m0 14h17M8 15l3-4 3 2 5-7',
  users: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2m7-10a4 4 0 100-8 4 4 0 000 8zm13 10v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75',
  arrow: 'M5 12h14m-7-7 7 7-7 7',
  down: 'M12 5v14m-6-6 6 6 6-6',
  left: 'M19 12H5m7 7-7-7 7-7',
  play: 'm8 5 11 7-11 7z',
  pause: 'M9 5v14m6-14v14',
  check: 'm5 12 4 4L19 6',
  shield: 'M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z',
  printer: 'M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2m-12-4h12v8H6z',
  close: 'M18 6 6 18M6 6l12 12',
  refresh: 'M20 7v5h-5M4 17v-5h5m11-2a8 8 0 00-14-3M4 14a8 8 0 0014 3',
  clock: 'M12 8v4l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z',
};

export default function Icon({ name, size = 19 }) {
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>;
}
