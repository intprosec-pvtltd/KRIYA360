// Keep Vite's local proxy; production uses a direct HTTPS API origin.
const origin = (import.meta.env.VITE_API_URL || (import.meta.env.PROD ? 'https://kriya360.onrender.com' : '')).replace(/\/+$/, '');
export const API = origin + '/api';
export function apiAsset(path) { return typeof path === 'string' && path.startsWith('/api/') ? origin + path : path; }
export async function apiFetch(url, options = {}) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (options.signal?.aborted) abort();
  options.signal?.addEventListener('abort', abort, {once:true});
  const timer = setTimeout(abort, 45000);
  try {
    const response = await fetch(url, {...options, signal:controller.signal, redirect:'error'});
    if (response.status >= 500) { const e = new Error('Service temporarily unavailable. Please try again.'); e.status = response.status; throw e; }
    return response;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out. Please try again.');
    if (e instanceof TypeError) throw new Error('Unable to connect. Check your internet connection and try again.');
    throw e;
  } finally { clearTimeout(timer); options.signal?.removeEventListener('abort', abort); }
}
