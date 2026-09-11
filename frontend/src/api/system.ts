import { api } from './client';
export const systemApi = { health: () => api<{status:string}>('/health') };
