const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API ${status}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`);
    this.status = status;
    this.detail = detail;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail: unknown;
    try { detail = await response.json(); } catch { detail = await response.text(); }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) return response.json() as Promise<T>;
  return response.blob() as Promise<T>;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  return parseResponse<T>(response);
}

export async function apiMultipart<T>(
  path: string,
  payload: unknown,
  files: File[] = [],
  fileField = 'files',
): Promise<T> {
  const form = new FormData();
  form.append('payload', JSON.stringify(payload));
  for (const file of files) form.append(fileField, file);
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: form });
  return parseResponse<T>(response);
}

export async function apiForm<T>(path: string, form: FormData, method = 'POST'): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method, body: form });
  return parseResponse<T>(response);
}

export async function apiBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  return parseResponse<Blob>(response);
}

export const apiBaseUrl = API_BASE_URL;
