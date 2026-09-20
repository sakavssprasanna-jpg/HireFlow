import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const API_BASE_URL = ((import.meta as any).env?.VITE_API_BASE_URL || 'https://hireflow-wnko.onrender.com').replace(/\/$/, '');

const originalFetch = window.fetch;
window.fetch = function (input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (typeof input === 'string' && input.startsWith('/api')) {
    return originalFetch(`${API_BASE_URL}${input}`, init);
  }
  if (input instanceof URL && input.pathname.startsWith('/api')) {
    return originalFetch(new URL(`${API_BASE_URL}${input.pathname}${input.search}`), init);
  }
  if (input instanceof Request && input.url.startsWith('/api')) {
    return originalFetch(new Request(`${API_BASE_URL}${input.url}`, input), init);
  }
  return originalFetch(input, init);
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
