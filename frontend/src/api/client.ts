const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown;
    try { detail = await response.json(); } catch { detail = await response.text(); }
    throw new Error(`API ${response.status}: ${JSON.stringify(detail)}`);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) return response.json() as Promise<T>;
  return response.blob() as Promise<T>;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  return parseResponse<T>(response);
}

export async function apiMultipart<T>(path: string, payload: unknown, files: File[] = [], fileField = 'files'): Promise<T> {
  const form = new FormData();
  form.append('payload', JSON.stringify(payload));
  for (const file of files) form.append(fileField, file);
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: form });
  return parseResponse<T>(response);
}

export const apiBaseUrl = API_BASE_URL;
