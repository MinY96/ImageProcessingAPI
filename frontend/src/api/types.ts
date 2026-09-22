export type JsonMap = Record<string, unknown>;

export type ParameterChoice = { value: unknown; label: string; description?: string | null };
export type ParameterSpec = {
  title: string;
  description?: string | null;
  required?: boolean;
  unit?: string | null;
  order?: number;
  type: 'continuous' | 'discrete' | 'category';
  min_value?: number | null;
  max_value?: number | null;
  step?: number | null;
  values?: unknown[] | null;
  choices?: ParameterChoice[];
  default?: unknown;
};

export type InputSlotSpec = {
  name: string;
  kind: string;
  required: boolean;
  description?: string | null;
};

export type OutputSlotSpec = { name: string; kind: string; description?: string | null };

export type OperationSpec = {
  name: string;
  display_name: string;
  category: string;
  description?: string | null;
  version: string;
  inputs: InputSlotSpec[];
  parameters: Record<string, ParameterSpec>;
  outputs: OutputSlotSpec[];
  constraints: JsonMap[];
};


export type WorkflowPortSpec = {
  name: string;
  kind: string;
  required: boolean;
  description?: string | null;
};

export type FeatureSpec = {
  name: string;
  display_name: string;
  category: string;
  description?: string | null;
  version: string;
  inputs: WorkflowPortSpec[];
  parameters: Record<string, ParameterSpec>;
  outputs: WorkflowPortSpec[];
};

export type ScalarOperatorSpec = {
  name: string;
  display_name: string;
  description?: string | null;
  min_inputs: number;
  max_inputs?: number | null;
  required_input_names: string[];
  parameters: Record<string, JsonMap>;
};

export type PipelineInputReference = { type: 'pipeline_input'; input_name: string };
export type StepOutputReference = { type: 'step_output'; step_id: string; output_name: string };
export type PipelineValueReference = PipelineInputReference | StepOutputReference;

export type GraphInputReference = { type: 'graph_input'; input_name: string };
export type NodeOutputReference = { type: 'node_output'; node_id: string; output_name: string };
export type GraphValueReference = GraphInputReference | NodeOutputReference;

export type PipelineStepSpec = {
  id: string;
  operation: string;
  inputs?: Record<string, PipelineValueReference>;
  params?: JsonMap;
};

export type PipelineSpec = {
  name: string;
  display_name: string;
  description?: string | null;
  version: string;
  inputs: InputSlotSpec[];
  steps: PipelineStepSpec[];
  outputs: Record<string, PipelineValueReference>;
};

export type GraphNodeSpec = {
  id: string;
  node_type: string;
  inputs?: Record<string, GraphValueReference>;
  params?: JsonMap;
  operation?: string;
  feature?: string;
  operator?: string;
  recipe?: string;
  recipe_kind?: string;
  recipe_version?: string;
};

export type GraphRecipeSpec = {
  name: string;
  display_name: string;
  description?: string | null;
  version: string;
  inputs: InputSlotSpec[];
  nodes: GraphNodeSpec[];
  outputs: Record<string, GraphValueReference>;
};

export type RecipeSummary = {
  name: string;
  kind: 'linear' | 'graph';
  display_name: string;
  description?: string | null;
  version: string;
  source: 'builtin' | 'user';
  readonly: boolean;
  tags: string[];
  revision: number;
  step_count: number;
  node_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type RecipeRecord = {
  name: string;
  kind: 'linear' | 'graph';
  pipeline?: PipelineSpec | null;
  graph?: GraphRecipeSpec | null;
  source: 'builtin' | 'user';
  readonly: boolean;
  tags: string[];
  revision: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type EncodedImage = {
  media_type: string;
  size_bytes: number;
  width: number;
  height: number;
  channels: number;
  dtype: string;
  color_space: string;
  shape: number[];
  name?: string | null;
  encoding?: 'base64';
  data?: string;
  analysis?: ImageAnalysisResult;
};

export type EncodedOutput = { images: Record<string, EncodedImage>; data: JsonMap };
export type ExecutionResponse = {
  success: boolean;
  operation?: string;
  pipeline?: string;
  recipe?: string;
  metadata?: Record<string, unknown>;
  output: EncodedOutput;
  intermediates?: Record<string, EncodedOutput>;
  error?: { code?: string; message?: string; details?: unknown } | null;
};

export type NumericStatistics = {
  minimum: number; maximum: number; mean: number; median: number; std: number; variance: number;
  dynamic_range: number; percentile_01: number; percentile_05: number; percentile_25: number;
  percentile_50: number; percentile_75: number; percentile_95: number; percentile_99: number;
  skewness: number; excess_kurtosis: number; total_count: number; sample_count: number; quantiles_sampled: boolean;
};
export type HistogramData = { channel: string; bins: number; counts: number[]; probabilities: number[]; range_min: number; range_max: number };
export type ImageAnalysisResult = {
  metadata: { name?: string | null; width: number; height: number; channels: number; pixel_count: number; dtype: string; bit_depth_per_channel: number; bits_per_pixel: number; color_space: string; shape: number[]; aspect_ratio: number; decoded_size_bytes: number; source_size_bytes?: number | null };
  intensity_statistics: NumericStatistics;
  channel_statistics: Record<string, NumericStatistics>;
  histograms: { gray?: HistogramData | null; rgb: Record<string, HistogramData>; hsv: Record<string, HistogramData> };
  features?: Record<string, number | boolean | null> | null;
  profiles: JsonMap;
};

export type TestDatasetSummary = {
  dataset_id: string; name: string; description?: string | null; root_path?: string | null;
  image_count: number; ok_count: number; ng_count: number; unlabeled_count: number; revision: number; updated_at: string;
};
export type TestDatasetImage = {
  image_id: string; file_path: string; relative_path?: string | null; ground_truth?: 'OK' | 'NG' | null;
  file_size_bytes?: number | null; tags: string[]; metadata: JsonMap;
};
export type TestDatasetImagePage = { items: TestDatasetImage[]; total: number; offset: number; limit: number };

export type LabelSummary = {
  image_id: string; image_name: string; width: number; height: number; tags: string[]; annotation_count: number;
  labels: string[]; revision: number; updated_at: string;
};
export type LabelListResponse = { items: LabelSummary[]; total: number; offset: number; limit: number };
export type Annotation = { id?: string; annotation_id?: string; type: string; label: string; tags?: string[]; [key: string]: unknown };
export type LabelDocument = {
  image_id: string; image_name: string; source_uri?: string | null; width: number; height: number; tags: string[];
  metadata: JsonMap; annotations: Annotation[]; revision: number; created_at: string; updated_at: string;
};
export type LabelClassSummary = { label: string; annotation_count: number; image_count: number };

export type EvaluationStatus = 'queued'|'running'|'completed'|'failed'|'cancel_requested'|'cancelled';
export type EvaluationProgress = { total: number; processed: number; percent: number };
export type EvaluationSummaryMetrics = { accuracy?: number | null; precision?: number | null; recall?: number | null; specificity?: number | null; f1?: number | null };
export type EvaluationSummary = {
  total_images: number; labeled_images: number; evaluated_images: number; error_images: number; execution_success_rate: number;
  confusion_matrix: { tp: number; tn: number; fp: number; fn: number };
  metrics: EvaluationSummaryMetrics;
  latency: { mean_ms?: number | null; median_ms?: number | null; p95_ms?: number | null; max_ms?: number | null };
  [key: string]: unknown;
};
export type EvaluationRunSummary = {
  evaluation_id: string; status: EvaluationStatus; progress: EvaluationProgress;
  dataset: { dataset_id: string; name: string; revision: number; image_count: number };
  recipe: { name: string; kind: string; version: string; revision: number };
  summary?: EvaluationSummary | null;
  failure?: { code: string; message: string } | null;
  created_at: string; started_at?: string | null; finished_at?: string | null;
};
export type EvaluationRun = EvaluationRunSummary & { request: JsonMap; results: EvaluationItemResult[] };
export type EvaluationItemResult = {
  image_id: string; file_path: string; relative_path?: string | null; ground_truth: 'OK'|'NG';
  prediction: 'OK'|'NG'|'ERROR'; score?: number | null; correct?: boolean | null; duration_ms: number;
  feature_values?: JsonMap; error?: { code: string; message: string } | null;
};
export type EvaluationResultPage = { items: EvaluationItemResult[]; total: number; offset: number; limit: number };

export type ModelSpec = { model_id: string; version: string; algorithm: string; feature_schema: string; labels: Record<string,string>; metadata: JsonMap };

export type SyntheticMethodInfo = {
  method: string; display_name: string; description: string; requires_asset: boolean; supports_asset: boolean;
  supports_uploaded_mask: boolean; supports_generated_mask: boolean; optional_dependencies: string[];
};
export type DiffusionModelStatus = {
  model: string; display_name: string; provider: string; model_id: string; dependency_available: boolean; loaded: boolean;
  local_files_only: boolean; cache_dir?: string | null; device: string; notes?: string | null;
};
export type SyntheticAssetSummary = {
  asset_id: string; name: string; category: string; description?: string | null; tags: string[]; has_mask: boolean;
  width: number; height: number; created_at: string; metadata: JsonMap;
};
export type SyntheticGenerateRequest = {
  method: string; defect_type: string; severity: number; count: number; seed?: number | null;
  mask?: { type: string; center_x?: number; center_y?: number; width_ratio?: number; height_ratio?: number; rotation_deg?: number; polygon?: [number,number][]; feather_px?: number; parameters?: JsonMap } | null;
  asset_id?: string | null; parameters: JsonMap;
};
export type SyntheticCandidate = {
  index: number; seed: number; metadata: { quality?: { changed_area_ratio: number; outside_mask_mean_abs_diff: number; outside_mask_max_abs_diff: number; inside_mask_mean_abs_diff: number }; [key:string]: unknown };
  images: Record<'image'|'mask'|'difference', EncodedImage>;
};
export type SyntheticGenerationResponse = { success: boolean; request: JsonMap; candidates: SyntheticCandidate[] };
