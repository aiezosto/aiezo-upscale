import { Cloud, Cpu, FolderOpen, Info, Maximize2, SlidersHorizontal, Sparkles, Save, Wand2, X } from 'lucide-react'
import { targetSize, type ContrastMode, type Engine, type InitInfo, type OpenedImage, type TargetKey } from '../api'
import { Card, Segmented, Slider, Toggle } from './ui'

export interface PanelState {
  target: TargetKey
  customLong: number
  model: string
  engine: Engine
  seedvr2: string
  fidelity: number
  sharpen: number
  sharpenAi: number
  fidelityAi: number
  contrast: ContrastMode
  outFormat: 'PNG' | 'JPG' | 'TIFF'
  outDir: string
}

interface Props {
  info: InitInfo
  st: PanelState
  set: (patch: Partial<PanelState>) => void
  image: OpenedImage | null
  batch?: { count: number }
  busy: boolean
  hasResult: boolean
  onStart: () => void
  onCancel: () => void
  onChooseFolder: () => void
  onOpenFolder: () => void
}

export function SettingsPanel({ info, st, set, image, batch, busy, hasResult, onStart, onCancel, onChooseFolder, onOpenFolder }: Props) {
  const out = image ? targetSize(image.width, image.height, st.target, st.customLong, info.targets) : null
  const factor = image && out ? out[0] / image.width : 0
  const googleOn = info.settings.google.enabled
  const falOn = info.settings.fal.has_api_key
  const isAi = st.engine === 'seedvr2' || st.engine === 'fal'
  const sharpenVal = isAi ? st.sharpenAi : st.sharpen
  const fidelityVal = isAi ? st.fidelityAi : st.fidelity
  const outPx = out ? out[0] * out[1] : 0
  const overGpu = st.engine === 'seedvr2' && outPx > info.seedvr2_max_pixels
  const contrastOn = st.contrast === 'on' || (st.contrast === 'auto' && !!image?.suggest_contrast)
  const canStart = batch ? batch.count > 0 : !!image

  return (
    <aside className="w-[380px] shrink-0 border-l border-border-brand bg-background-main flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {image && !batch && (
          <Card title="Ảnh gốc" icon={<Info className="w-4 h-4" />}>
            <p className="text-sm font-semibold text-primary-text truncate" title={image.path}>{image.name}</p>
            <p className="text-xs text-secondary-text mt-0.5">
              {image.width} × {image.height} px · {image.format}{image.has_alpha ? ' · có nền trong suốt' : ''}
            </p>
            {image.effective < 1 && (
              <p className="text-[11px] text-muted-text mt-2 leading-snug">
                Đo được: ảnh thực chất chỉ chứa chi tiết tới khoảng <b className="text-body-text">{image.effective_w} × {image.effective_h} px</b>{' '}
                ({Math.round(image.effective * 100)}%), phần còn lại là nhoè do đã bị phóng to trước đó (ảnh chụp màn hình, ảnh tải lại).
              </p>
            )}
            {image.notes.map((n) => (
              <p key={n} className="text-[11px] text-warning mt-1">{n}</p>
            ))}
          </Card>
        )}

        <Card title="Kích thước đích" icon={<Maximize2 className="w-4 h-4" />}>
          <Segmented<TargetKey>
            value={st.target}
            onChange={(v) => set({ target: v })}
            disabled={busy}
            options={[
              { value: '2K', label: '2K', title: 'Cạnh dài 2560 px' },
              { value: '4K', label: '4K', title: 'Cạnh dài 3840 px (UHD)' },
              { value: '8K', label: '8K', title: 'Cạnh dài 7680 px (UHD)' },
            ]}
          />
          <div className="mt-1.5">
            <Segmented<TargetKey>
              value={st.target}
              onChange={(v) => set({ target: v })}
              disabled={busy}
              options={[
                { value: 'x2', label: 'x2' },
                { value: 'x4', label: 'x4' },
                { value: 'custom', label: 'Tuỳ chỉnh' },
              ]}
            />
          </div>
          {st.target === 'custom' && (
            <label className="flex items-center gap-2 mt-2 text-xs text-secondary-text">
              Cạnh dài
              <input
                type="number"
                min={64}
                max={16384}
                value={st.customLong}
                disabled={busy}
                onChange={(e) => set({ customLong: Number(e.target.value) })}
                className="field !w-28 tabular-nums"
              />
              px
            </label>
          )}
          <p className="text-[11px] text-muted-text mt-2">2K = 2560 px · 4K = 3840 px · 8K = 7680 px (theo cạnh dài, giữ đúng tỉ lệ ảnh).</p>
          {out && (
            <p className="text-xs mt-2 text-primary-text">
              Kết quả: <b className="tabular-nums">{out[0]} × {out[1]} px</b>
              <span className="text-secondary-text"> ({factor >= 1 ? `phóng x${factor.toFixed(2)}` : `thu nhỏ x${factor.toFixed(2)}`})</span>
            </p>
          )}
          {factor > 16 && <p className="text-[11px] text-warning mt-1">Phóng hơn x16: phần vượt chỉ là nội suy, không thêm chi tiết.</p>}
        </Card>

        <Card title="Bộ xử lý" icon={<Cpu className="w-4 h-4" />}>
          <Segmented<Engine>
            value={st.engine}
            onChange={(v) => set({ engine: v })}
            disabled={busy}
            options={[
              { value: 'seedvr2', label: 'SeedVR2', title: 'Diffusion SeedVR2 trên GPU của máy, miễn phí' },
              ...(falOn ? [{ value: 'fal' as const, label: 'SeedVR2 API', title: 'SeedVR2 trên máy chủ fal.ai, 0,001 USD/MP' }] : []),
              { value: 'local', label: 'Cổ điển', title: 'Model x4 cổ điển, nhanh, không vẽ thêm' },
              ...(googleOn ? [{ value: 'google' as const, label: 'Google' }] : []),
            ]}
          />
          {st.engine === 'seedvr2' && (
            <div className="mt-3 space-y-1.5">
              {info.seedvr2.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  disabled={busy || !m.installed}
                  onClick={() => set({ seedvr2: m.key })}
                  className={`w-full text-left rounded-xl border px-3 py-2 transition-colors ${
                    st.seedvr2 === m.key ? 'border-accent bg-emerald-500/10' : 'border-border-brand hover:border-accent/50'
                  } disabled:opacity-50`}
                >
                  <span className="flex items-center gap-2 text-xs font-semibold text-primary-text">
                    <span className={`w-3 h-3 rounded-full border-2 ${st.seedvr2 === m.key ? 'border-accent bg-accent' : 'border-muted-text'}`} />
                    {m.label}
                    {m.key === '7b_sharp' && <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-accent text-accent-contrast">Nét nhất</span>}
                  </span>
                  <span className="block text-[11px] text-muted-text mt-1 leading-snug pl-5">{m.installed ? m.description : 'Thiếu file model, chạy download_models.py.'}</span>
                </button>
              ))}
              <p className="text-[11px] text-muted-text leading-snug pt-1">
                SeedVR2 (ByteDance Seed) — mô hình diffusion một bước: tăng chi tiết mà giữ nguyên người, vật, bố cục.
                Chi tiết nhỏ (sợi tóc, vân vải) do AI tái tạo, có thể không giống hệt thực tế.
              </p>
              {overGpu && (
                <p className="text-[11px] text-warning leading-snug">
                  GPU 12 GB chỉ chạy SeedVR2 tới ~{(info.seedvr2_max_pixels / 1e6).toFixed(1)} MP; phần còn lại tới kích thước đích phóng bằng Real-ESRNet.
                  {falOn ? ' Muốn SeedVR2 trọn vẹn ở 8K: chọn SeedVR2 API.' : ' Muốn SeedVR2 trọn vẹn ở 8K: thêm khoá fal.ai trong Cài đặt.'}
                </p>
              )}
            </div>
          )}
          {st.engine === 'fal' && (
            <p className="text-[11px] text-secondary-text mt-3 leading-snug flex gap-1.5">
              <Cloud className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>
                SeedVR2 chạy trên máy chủ fal.ai, ảnh được gửi lên mạng. Giá 0,001 USD/megapixel ảnh ra
                {out ? <> — ảnh này ≈ <b className="text-primary-text">{(outPx / 1e6 * 0.001).toFixed(3)} USD</b></> : null}.
              </span>
            </p>
          )}
          {st.engine === 'local' ? (
            <div className="mt-3 space-y-1.5">
              {info.models.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  disabled={busy || !m.installed}
                  onClick={() => set({ model: m.key })}
                  className={`w-full text-left rounded-xl border px-3 py-2 transition-colors ${
                    st.model === m.key ? 'border-accent bg-emerald-500/10' : 'border-border-brand hover:border-accent/50'
                  } disabled:opacity-50`}
                >
                  <span className="flex items-center gap-2 text-xs font-semibold text-primary-text">
                    <span className={`w-3 h-3 rounded-full border-2 ${st.model === m.key ? 'border-accent bg-accent' : 'border-muted-text'}`} />
                    {m.label}
                    {m.key === 'restore' && <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-accent text-accent-contrast">Khuyên dùng</span>}
                    {m.key === 'detail' && <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/15 text-warning border border-amber-500/30">Có vẽ thêm</span>}
                  </span>
                  <span className="block text-[11px] text-muted-text mt-1 leading-snug pl-5">{m.installed ? m.description : 'Thiếu file model.'}</span>
                </button>
              ))}
              <p className="text-[11px] text-muted-text leading-snug pt-1">
                Real-ESRNet, SwinIR, HAT-L không qua huấn luyện GAN: không tự vẽ thêm chi tiết. Riêng Real-ESRGAN là GAN: nét “đẹp mắt” hơn
                nhưng có kết cấu tự vẽ, chỉ dùng khi chấp nhận điều đó.
              </p>
            </div>
          ) : st.engine === 'google' && (
            <p className="text-[11px] text-warning mt-3 leading-snug flex gap-1.5">
              <Cloud className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              Gửi ảnh lên Google (≈ 0,06 USD/ảnh, tối đa 17 MP). Imagen là model tạo sinh nên có thể thêm chi tiết; ứng dụng vẫn chạy bước Bám ảnh gốc
              để kéo kết quả về khớp ảnh gốc.
            </p>
          )}
        </Card>

        <Card title="Làm nét & tinh chỉnh" icon={<SlidersHorizontal className="w-4 h-4" />}>
          <div className="space-y-4">
            <Slider
              label={isAi ? 'Làm nét thêm' : 'Làm nét'}
              value={sharpenVal}
              onChange={(v) => set(isAi ? { sharpenAi: v } : { sharpen: v })}
              disabled={busy}
              left="Tắt"
              right="Mạnh"
              hint={isAi
                ? 'SeedVR2 đã nét sẵn, mặc định tắt. Tăng nếu muốn sắc hơn nữa (giải chập Richardson–Lucy).'
                : 'Giải chập Richardson–Lucy: khôi phục độ sắc bị nhoè từ chính dữ liệu ảnh, không vẽ thêm. Mạnh quá có thể gợn quanh cạnh.'}
            />
            <Slider
              label="Bám ảnh gốc"
              value={fidelityVal}
              onChange={(v) => set(isAi ? { fidelityAi: v } : { fidelity: v })}
              disabled={busy}
              left="Tự do"
              right="Sát gốc"
              hint="Kéo hình khối, màu, vị trí về khớp ảnh gốc. 50% cho kết quả đúng nhất khi thử có đáp án."
            />
            <Toggle
              checked={contrastOn}
              onChange={(v) => set({ contrast: v ? 'on' : 'off' })}
              disabled={busy}
              label="Khử bạc màu (tăng tương phản)"
              hint={
                batch
                  ? st.contrast === 'auto'
                    ? 'Tự bật cho từng ảnh bị bạc màu.'
                    : undefined
                  : image?.suggest_contrast
                    ? `Ảnh này bị bạc màu (điểm đen ${Math.round(image.luma_lo * 100)}%, điểm trắng ${Math.round(image.luma_hi * 100)}%): nên bật.`
                    : 'Kéo điểm đen/trắng về chuẩn. Không đổi tông màu, không thêm chi tiết.'
              }
            />
            {batch && st.contrast !== 'auto' && (
              <button className="text-[11px] text-accent-strong underline" onClick={() => set({ contrast: 'auto' })}>Đặt lại: tự động theo từng ảnh</button>
            )}
          </div>
          {hasResult && !busy && (
            <p className="text-[11px] text-info mt-3 leading-snug flex gap-1.5">
              <Wand2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              Đổi Làm nét / Bám ảnh gốc / Khử bạc màu rồi bấm chạy lại: chỉ mất vài giây vì không phải chạy lại AI.
            </p>
          )}
        </Card>

        <Card title="Lưu ảnh" icon={<Save className="w-4 h-4" />}>
          <Segmented<'PNG' | 'JPG' | 'TIFF'>
            value={st.outFormat}
            onChange={(v) => set({ outFormat: v })}
            options={[
              { value: 'PNG', label: 'PNG', title: 'Không nén mất dữ liệu (khuyên dùng)' },
              { value: 'JPG', label: 'JPG 95%', title: 'File nhỏ hơn, nén nhẹ' },
              { value: 'TIFF', label: 'TIFF', title: 'Không nén mất dữ liệu, dùng cho in ấn' },
            ]}
          />
          <div className="flex items-center gap-2 mt-2">
            <button className="field !w-auto flex-1 text-left truncate" onClick={onChooseFolder} title={st.outDir}>
              {st.outDir}
            </button>
            <button className="aiezo-btn-secondary !px-0 w-9 shrink-0" onClick={onOpenFolder} title="Mở thư mục" aria-label="Mở thư mục">
              <FolderOpen className="w-4 h-4" />
            </button>
          </div>
        </Card>
      </div>

      <div className="p-3 border-t border-border-brand bg-surface">
        {busy ? (
          <button className="aiezo-btn-danger w-full !min-h-11" onClick={onCancel}>
            <X className="w-4 h-4" /> Huỷ
          </button>
        ) : (
          <button className="aiezo-btn-primary w-full !min-h-11 !text-sm" disabled={!canStart} onClick={onStart}>
            <Sparkles className="w-4 h-4" />
            {batch ? `Làm nét ${batch.count} ảnh` : hasResult ? 'Chạy lại với cài đặt mới' : 'Làm nét & phóng to'}
          </button>
        )}
      </div>
    </aside>
  )
}
