import { api, apiBlob, apiForm } from './client';
import type { DiffusionModelStatus, SyntheticAssetSummary, SyntheticGenerateRequest, SyntheticGenerationResponse, SyntheticMethodInfo } from './types';

export const syntheticApi = {
  methods: () => api<SyntheticMethodInfo[]>('/synthetic/methods'),
  diffusionModels: () => api<DiffusionModelStatus[]>('/synthetic/diffusion/models'),
  unloadDiffusion: (model?: string) => api<void>(`/synthetic/diffusion/unload${model ? `?model=${encodeURIComponent(model)}` : ''}`, { method:'POST' }),
  assets: (filters: {category?: string; search?: string} = {}) => {
    const p = new URLSearchParams();
    if (filters.category) p.set('category', filters.category);
    if (filters.search) p.set('search', filters.search);
    const q = p.toString();
    return api<SyntheticAssetSummary[]>(`/synthetic/assets${q ? `?${q}` : ''}`);
  },
  getAsset: (assetId: string) => api<SyntheticAssetSummary>(`/synthetic/assets/${encodeURIComponent(assetId)}`),
  assetImage: (assetId: string) => apiBlob(`/synthetic/assets/${encodeURIComponent(assetId)}/image`),
  assetMask: (assetId: string) => apiBlob(`/synthetic/assets/${encodeURIComponent(assetId)}/mask`),
  createAsset: (payload: unknown, image: File, mask?: File | null) => {
    const form = new FormData();
    form.append('payload', JSON.stringify(payload));
    form.append('image', image);
    if (mask) form.append('mask', mask);
    return apiForm<SyntheticAssetSummary>('/synthetic/assets', form);
  },
  deleteAsset: (assetId: string) => api<void>(`/synthetic/assets/${encodeURIComponent(assetId)}`, { method:'DELETE' }),
  generate: (request: SyntheticGenerateRequest, files: {sourceImage:File; targetMask?:File|null; assetImage?:File|null; assetMask?:File|null}, responseFormat:'json'|'zip'='json') => {
    const form = new FormData();
    form.append('payload', JSON.stringify(request));
    form.append('source_image', files.sourceImage);
    if (files.targetMask) form.append('target_mask', files.targetMask);
    if (files.assetImage) form.append('asset_image', files.assetImage);
    if (files.assetMask) form.append('asset_mask', files.assetMask);
    return apiForm<SyntheticGenerationResponse | Blob>(`/synthetic/generate?response_format=${responseFormat}`, form);
  },
};
