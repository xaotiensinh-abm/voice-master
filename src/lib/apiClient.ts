import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  HealthResponse,
  VoiceListResponse,
  VoicePreviewRequest,
  VoicePreviewResponse,
  JobCreateRequest,
  JobCreateResponse,
  Job,
  Settings,
  SettingsUpdateRequest,
  GPUInfo,
  BenchmarkRequest,
  BenchmarkResult,
  APIError,
  EngineName,
  VoiceStyle,
  ModelStatus,
  ModelProgress,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8757';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<APIError>) => {
        if (error.response?.data) {
          const raw = error.response.data as any;
          const detail =
            raw?.detail && typeof raw.detail === 'object' ? raw.detail : raw;
          return Promise.reject({
            code: detail?.code || detail?.error_code || raw?.code || 'WORKER_CRASHED',
            message:
              detail?.message ||
              raw?.message ||
              error.message ||
              'Lỗi kết nối không xác định.',
            detail: detail?.detail,
          } as APIError);
        }
        if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
          return Promise.reject({
            code: 'ENGINE_UNAVAILABLE',
            message: 'Backend chưa khởi động. Vui lòng đợi hoặc kiểm tra Chẩn đoán.',
          } as APIError);
        }
        return Promise.reject({
          code: 'WORKER_CRASHED',
          message: error.message || 'Lỗi kết nối không xác định.',
        } as APIError);
      }
    );
  }

  // ── Health ──────────────────────────────────────────────
  async getHealth(): Promise<HealthResponse> {
    const { data } = await this.client.get<HealthResponse>('/health');
    return data;
  }

  // ── Voices ─────────────────────────────────────────────
  async getVoices(params?: {
    engine?: EngineName;
    style?: VoiceStyle;
    available_only?: boolean;
  }): Promise<VoiceListResponse> {
    const { data } = await this.client.get<VoiceListResponse>('/v1/voices', {
      params,
    });
    return data;
  }

  async previewVoice(req: VoicePreviewRequest): Promise<VoicePreviewResponse> {
    const { data } = await this.client.post<VoicePreviewResponse>(
      '/v1/voices/preview',
      req
    );
    return data;
  }

  getPreviewAudioUrl(previewId: string): string {
    return `${BASE_URL}/v1/previews/${previewId}/audio`;
  }

  // ── Jobs ───────────────────────────────────────────────
  async createJob(req: JobCreateRequest): Promise<JobCreateResponse> {
    const { data } = await this.client.post<JobCreateResponse>(
      '/v1/tts/jobs',
      req
    );
    return data;
  }

  async getJob(jobId: string): Promise<Job> {
    const { data } = await this.client.get<Job>(`/v1/tts/jobs/${jobId}`);
    return data;
  }

  async getJobs(): Promise<Job[]> {
    const { data } = await this.client.get<{ jobs: Job[] }>('/v1/tts/jobs');
    return data.jobs || [];
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.client.post(`/v1/tts/jobs/${jobId}/cancel`);
  }

  async deleteJob(jobId: string): Promise<void> {
    await this.client.delete(`/v1/tts/jobs/${jobId}`);
  }

  async retryJob(jobId: string): Promise<JobCreateResponse> {
    const { data } = await this.client.post<JobCreateResponse>(
      `/v1/tts/jobs/${jobId}/retry`
    );
    return data;
  }

  getJobAudioUrl(jobId: string): string {
    return `${BASE_URL}/v1/tts/jobs/${jobId}/audio`;
  }

  // ── Settings ───────────────────────────────────────────
  async getSettings(): Promise<Settings> {
    const { data } = await this.client.get<Settings>('/v1/settings');
    return data;
  }

  async updateSettings(req: SettingsUpdateRequest): Promise<{ status: string }> {
    const { data } = await this.client.patch<{ status: string }>(
      '/v1/settings',
      req
    );
    return data;
  }

  // ── Model download ─────────────────────────────────────
  async getModelStatus(): Promise<ModelStatus> {
    const { data } = await this.client.get<ModelStatus>('/models/status');
    return data;
  }

  async startModelDownload(): Promise<ModelProgress> {
    const { data } = await this.client.post<ModelProgress>('/models/download');
    return data;
  }

  async getModelProgress(): Promise<ModelProgress> {
    const { data } = await this.client.get<ModelProgress>('/models/download/progress');
    return data;
  }

  async deleteModel(): Promise<ModelStatus> {
    const { data } = await this.client.delete<ModelStatus>('/models');
    return data;
  }

  // ── Diagnostics ────────────────────────────────────────
  async getGPUInfo(): Promise<GPUInfo> {
    const { data } = await this.client.get<GPUInfo>('/v1/diagnostics/gpu');
    return data;
  }

  async runBenchmark(req: BenchmarkRequest): Promise<BenchmarkResult[]> {
    const { data } = await this.client.post<{ results: BenchmarkResult[] }>(
      '/v1/diagnostics/benchmark',
      req
    );
    return data.results.map((result: any) => ({
      ...result,
      success: result.ok,
      text_length: result.text_label,
      duration_seconds: result.duration_sec,
    }));
  }
}

export const apiClient = new ApiClient();
export default apiClient;
