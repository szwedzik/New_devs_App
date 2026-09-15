// API base URL utilities

export const getApiBase = (): string => {
  // A deployed build is served from the same origin as the API, so relative
  // URLs are right there. Locally the API lives on its own port and
  // VITE_BACKEND_URL is not baked into the image, so it needs a fallback -
  // without one the requests go back to the dev server and return index.html.
  if (typeof window !== 'undefined' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1') {
    return '';
  }

  return import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
};

export const getApiUrl = (path: string): string => {
  const base = getApiBase();
  return `${base}${path}`;
};