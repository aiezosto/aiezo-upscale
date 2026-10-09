import { CheckCircle2, FolderOpen, ImagePlus, Loader2, Trash2, XCircle } from 'lucide-react'
import { fmtBytes, targetSize, type FileItem, type InitInfo, type TargetKey } from '../api'

export interface BatchRow extends FileItem {
  status: 'pending' | 'running' | 'done' | 'error' | 'cancelled'
  out?: string
  outW?: number
  outH?: number
  psnr?: number
  ssim?: number
  level?: string
  message?: string
}

interface Props {
  info: InitInfo
  rows: BatchRow[]
  target: TargetKey
  customLong: number
  busy: boolean
  progress: number
  message: string
  onAdd: () => void
  onRemove: (i: number) => void
  onClear: () => void
  onReveal: (p: string) => void
}

export function BatchView({ info, rows, target, customLong, busy, progress, message, onAdd, onRemove, onClear, onReveal }: Props) {
  const done = rows.filter((r) => r.status === 'done').length
  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <div className="flex items-center justify-between gap-2 px-4 py-2.5 border-b border-border-brand bg-surface/80">
        <p className="text-sm text-primary-text font-heading font-semibold">
          {rows.length} ảnh {rows.length > 0 && <span className="text-secondary-text font-normal text-xs">· xong {done}</span>}
        </p>
        <div className="flex gap-2">
          <button className="aiezo-btn-secondary !min-h-8" onClick={onAdd} disabled={busy}><ImagePlus className="w-4 h-4" /> Thêm ảnh</button>
          <button className="aiezo-btn-ghost !min-h-8" onClick={onClear} disabled={busy || rows.length === 0}><Trash2 className="w-4 h-4" /> Xoá danh sách</button>
        </div>
      </div>
      {busy && (
        <div className="px-4 py-2 border-b border-border-brand bg-surface">
          <div className="h-1.5 rounded-full bg-elevated-surface overflow-hidden">
            <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${Math.max(1, progress * 100)}%` }} />
          </div>
          <p className="text-[11px] text-secondary-text mt-1 truncate">{message}</p>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        {rows.length === 0 ? (
          <div className="h-full flex items-center justify-center p-6">
            <button onClick={onAdd} className="max-w-md w-full border-2 border-dashed border-border-brand hover:border-accent rounded-3xl p-10 text-center transition-colors">
              <ImagePlus className="w-10 h-10 mx-auto text-accent-strong mb-3" />
              <p className="font-heading font-semibold text-primary-text">Kéo thả nhiều ảnh hoặc cả thư mục vào đây</p>
              <p className="text-xs text-secondary-text mt-1">Tất cả ảnh dùng chung cài đặt bên phải và tự lưu vào thư mục kết quả.</p>
            </button>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-elevated-surface text-secondary-text">
              <tr className="text-left">
                <th className="px-4 py-2 font-semibold">Ảnh</th>
                <th className="px-2 py-2 font-semibold">Kích thước gốc</th>
                <th className="px-2 py-2 font-semibold">Kết quả</th>
                <th className="px-2 py-2 font-semibold">Độ khớp</th>
                <th className="px-2 py-2 font-semibold">Trạng thái</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const t = r.width && r.height ? targetSize(r.width, r.height, target, customLong, info.targets) : null
                return (
                  <tr key={r.path} className="border-b border-border-brand">
                    <td className="px-4 py-2 max-w-[260px]">
                      <p className="truncate text-primary-text font-medium" title={r.path}>{r.name}</p>
                      <p className="text-muted-text">{fmtBytes(r.bytes)}</p>
                    </td>
                    <td className="px-2 py-2 tabular-nums text-secondary-text">{r.width ? `${r.width} × ${r.height}` : '—'}</td>
                    <td className="px-2 py-2 tabular-nums text-primary-text">{r.outW ? `${r.outW} × ${r.outH}` : t ? `${t[0]} × ${t[1]}` : '—'}</td>
                    <td className={`px-2 py-2 tabular-nums ${r.level === 'good' ? 'text-success' : r.level === 'ok' ? 'text-info' : 'text-warning'}`}>
                      {r.psnr !== undefined ? `${r.psnr} dB · ${r.ssim?.toFixed(3)}` : ''}
                    </td>
                    <td className="px-2 py-2">
                      {r.error || r.status === 'error' ? (
                        <span className="text-danger flex items-center gap-1" title={r.error || r.message}><XCircle className="w-3.5 h-3.5" /> Lỗi: {r.error || r.message}</span>
                      ) : r.status === 'running' ? (
                        <span className="text-accent-strong flex items-center gap-1"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Đang xử lý</span>
                      ) : r.status === 'done' ? (
                        <button className="text-success flex items-center gap-1 hover:underline" onClick={() => r.out && onReveal(r.out)} title={r.out}>
                          <CheckCircle2 className="w-3.5 h-3.5" /> Đã lưu <FolderOpen className="w-3 h-3" />
                        </button>
                      ) : r.status === 'cancelled' ? (
                        <span className="text-muted-text">Đã huỷ</span>
                      ) : (
                        <span className="text-muted-text">Chờ</span>
                      )}
                    </td>
                    <td className="pr-3">
                      <button className="aiezo-btn-ghost !min-h-7 !px-1.5" disabled={busy} onClick={() => onRemove(i)} aria-label="Bỏ ảnh">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
