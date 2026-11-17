import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
// Bundled so the Android app looks the same offline (no Google Fonts request).
import '@fontsource/comic-neue/latin-400.css';
import '@fontsource/comic-neue/latin-700.css';
import '@fontsource/comic-neue/latin-400-italic.css';
import '@fontsource/comic-neue/latin-700-italic.css';
import './styles.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><BrowserRouter><App /></BrowserRouter></React.StrictMode>);
