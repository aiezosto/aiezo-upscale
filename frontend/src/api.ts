// Cầu nối tới Python (pywebview js_api). Mọi hàm trả Promise.

export type TargetKey = '2K' | '4K' | '8K' | 'x2' | 'x4' | 'custom'
export type ContrastMode = 'auto' | 'on' | 'off'
export type Engine = 'seedvr2' | 'fal' | 'local' | 'google'

export interface SeedVariant {
  key: string
  label: string
  description: string
  installed: boolean
}

export interface ModelInfo {
  key: string
  label: string
  description: string
  installed: boolean
  license: string
  source: string
}

export interface GoogleSettings {
  enabled: boolean
  auth: 'api_key' | 'service_account'
  has_api_key: boolean
  service_account_file: string
  project: string
  location: string
  preservation: number
  enhance_input: boolean
}

export interface AppSettings {
  theme: 'dark' | 'light'
  out_dir: string
  out_format: 'PNG' | 'JPG' | 'TIFF'
  jpeg_quality: number
  target: TargetKey
  custom_long: number
  engine: Engine
  seedvr2: string
  model: string
  fidelity: number
  sharpen: number
  sharpen_ai: number
  fidelity_ai: number
  google: GoogleSettings
  fal: { has_api_key: boolean }
}

export interface InitInfo {
  app: string
  version: string
  device: { type: string; name: string; vram_gb: number; label: string }
  models: ModelInfo[]
  seedvr2: SeedVariant[]
  settings: AppSettings
  targets: Record<string, number>
  seedvr2_max_pixels: number
}

export interface FileItem {
  path: string
  name: string
  width?: number
  height?: number
  bytes?: number
  error?: string
}

export interface OpenedImage {
  ok: boolean
  error?: string
  path: string
  name: string
  width: number
  height: number
  format: string
  has_alpha: boolean
  notes: string[]
  preview: string
  effective: number
  effective_w: number
  effective_h: number
  luma_lo: number
  luma_hi: number
  suggest_contrast: boolean
}

export interface Report {
  src_w: number
  src_h: number
  out_w: number
  out_h: number
  ref_w: number
  ref_h: number
  effective: number
  psnr: number
  ssim: number
  sharp_gain: number | null
  level: 'good' | 'ok' | 'low'
  verdict: string
  steps: string[]
  ai_seconds: number
  ai_time: string
}

export interface ResultPayload {
  report: Report
  notes: string[]
  before: string
  after: string
  preview_w: number
  preview_h: number
  total_seconds: number
}

export interface JobSettings {
  target: TargetKey
  custom_long: number
  model: string
  engine: Engine
  seedvr2: string
  fidelity: number
  sharpen: number
  contrast: boolean | 'auto'
  out_format: string
  jpeg_quality: number
  out_dir: string
}

export type BackendEvent =
  | { type: 'progress'; value: number; message: string }
  | ({ type: 'done' } & ResultPayload)
  | { type: 'error'; message: string }
  | { type: 'cancelled' }
  | { type: 'dropped'; items: FileItem[] }
  | { type: 'batch_item'; index: number; status: 'running' | 'done' | 'error' | 'cancelled'; path?: string; out_w?: number; out_h?: number; psnr?: number; ssim?: number; level?: string; error?: string }
  | { type: 'batch_done'; out_dir: string }

interface PyApi {
  init(): Promise<InitInfo>
  save_settings(patch: Partial<AppSettings>): Promise<{ ok: boolean }>
  pick_images(): Promise<FileItem[]>
  describe(paths: string[]): Promise<FileItem[]>
  open_image(path: string): Promise<OpenedImage>
  output_size(path: string, s: JobSettings): Promise<{ width?: number; height?: number }>
  start(path: string, s: JobSettings): Promise<{ ok: boolean; error?: string }>
  cancel(): Promise<{ ok: boolean }>
  crop(cx: number, cy: number, size: number): Promise<{ ok: boolean; before?: string; after?: string; x?: number; y?: number; size?: number; error?: string }>
  save_result(s: JobSettings): Promise<{ ok: boolean; path?: string; error?: string }>
  start_batch(paths: string[], s: JobSettings): Promise<{ ok: boolean; error?: string }>
  choose_folder(): Promise<string | null>
  open_path(path: string): Promise<void>
  set_google(patch: Partial<GoogleSettings> & { api_key?: string }): Promise<{ ok: boolean; settings: AppSettings }>
  pick_service_account(): Promise<string | null>
  set_fal(apiKey: string): Promise<{ ok: boolean; settings: AppSettings }>
  test_fal(): Promise<{ ok: boolean; message?: string; error?: string }>
  test_google(): Promise<{ ok: boolean; message?: string; error?: string }>
  open_aiezo(path: string): Promise<{ ok: boolean }>
}

declare global {
  interface Window {
    pywebview?: { api: PyApi }
    __upscale?: { onEvent: (e: BackendEvent) => void }
  }
}

/** Đợi pywebview sẵn sàng (sự kiện pywebviewready) */
export function ready(): Promise<PyApi> {
  return new Promise((resolve, reject) => {
    if (window.pywebview?.api?.init) return resolve(window.pywebview.api)
    const t = setTimeout(() => reject(new Error('Không kết nối được lõi xử lý (chỉ chạy trong ứng dụng desktop).')), 20000)
    window.addEventListener('pywebviewready', () => {
      clearTimeout(t)
      resolve(window.pywebview!.api)
    })
  })
}

export const api = (): PyApi => window.pywebview!.api

const listeners = new Set<(e: BackendEvent) => void>()
window.__upscale = { onEvent: (e) => listeners.forEach((l) => l(e)) }
export function onBackendEvent(fn: (e: BackendEvent) => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export const fmtBytes = (b?: number) =>
  b === undefined ? '' : b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`

/** Kích thước đích tính ở giao diện (giống pipeline.target_size) để hiện ngay khi đổi lựa chọn */
export function targetSize(w: number, h: number, target: TargetKey, customLong: number, targets: Record<string, number>): [number, number] {
  let long = 0
  if (target in targets) long = targets[target]
  else if (target === 'x2') long = Math.max(w, h) * 2
  else if (target === 'x4') long = Math.max(w, h) * 4
  else long = Math.min(16384, Math.max(64, Math.round(customLong) || 0))
  return w >= h ? [long, Math.max(1, Math.round((h * long) / w))] : [Math.max(1, Math.round((w * long) / h)), long]
}
