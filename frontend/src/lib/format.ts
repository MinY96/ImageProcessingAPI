import type { EncodedImage } from '../api';

export function imageDataUrl(image?: EncodedImage | null): string | undefined {
  if (!image?.data || !image.media_type) return undefined;
  return `data:${image.media_type};base64,${image.data}`;
}

export function pct(value?: number | null, digits = 1): string {
  return value == null || Number.isNaN(value) ? '-' : `${(value * 100).toFixed(digits)}%`;
}

export function number(value?: number | null, digits = 2): string {
  return value == null || Number.isNaN(value) ? '-' : value.toFixed(digits);
}

export function shortDate(value?: string | null): string {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function parseJsonObject(text: string): Record<string, unknown> {
  const trimmed = text.trim();
  if (!trimmed) return {};
  const value = JSON.parse(trimmed);
  if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error('JSON object가 필요합니다.');
  return value as Record<string, unknown>;
}
