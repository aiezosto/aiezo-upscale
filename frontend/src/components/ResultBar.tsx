import { useState } from 'react'
import { CheckCircle2, ChevronDown, Download, FolderOpen, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { ResultPayload } from '../api'

interface Props {
  result: ResultPayload
  savedPath: string | null
  onSave: () => void
  onReveal: (p: string) => void
  saving: boolean
}

export function ResultBar({ result, savedPath, onSave, onReveal, saving }: Props) {
  const [open, setOpen] = useState(false)
  const r = result.report
  const tone = r.level === 'good' ? 'text-success' : r.level === 'ok' ? 'text-info' : 'text-warning'
  const Icon = r.level === 'low' ? ShieldAlert : ShieldCheck
  return (
    <div className="border-t border-border-brand bg-surface">
      <div className="flex items-center gap-4 px-4 py-2.5 text-xs">
        <div>
          <p className="text-muted-text">Kết quả</p>
          <p className="font-semibold text-primary-text tabular-nums">{r.out_w} × {r.out_h} px</p>
        </div>
        <div title="Thu kết quả về độ phân giải thực của ảnh gốc rồi so với ảnh gốc. PSNR càng cao càng khớp (≥ 36 dB: rất khớp). SSIM tối đa 1.">
          <p className="text-muted-text">Độ khớp ảnh gốc</p>
          <p className={`font-semibold tabular-nums ${tone}`}>PSNR {r.psnr} dB · SSIM {r.ssim.toFixed(3)}</p>
        </div>
        {r.sharp_gain !== null && (
          <div title="Năng lượng cạnh (độ nét) của kết quả so với ảnh gốc phóng to thường, cùng kích thước.">
            <p className="text-muted-text">Độ nét so với phóng thường</p>
            <p className="font-semibold tabular-nums text-primary-text">x{r.sharp_gain.toFixed(2)}</p>
          </div>
        )}
        <div>
          <p className="text-muted-text">Thời gian</p>
          <p className="font-semibold tabular-nums text-primary-text">{result.total_seconds} giây</p>
        </div>
        <p className={`flex-1 min-w-0 flex items-center gap-1.5 ${tone}`}>
          <Icon className="w-4 h-4 shrink-0" />
          <span className="truncate" title={r.verdict}>{r.verdict}</span>
        </p>
        <button className="aiezo-btn-ghost !min-h-8 !px-2.5" onClick={() => setOpen((v) => !v)}>
          Các bước <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {savedPath ? (
          <button className="aiezo-btn-secondary !min-h-8" onClick={() => onReveal(savedPath)} title={savedPath}>
            <CheckCircle2 className="w-4 h-4 text-success" /> Đã lưu · Mở thư mục <FolderOpen className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button className="aiezo-btn-primary !min-h-8" onClick={onSave} disabled={saving}>
            <Download className="w-4 h-4" /> {saving ? 'Đang lưu…' : 'Lưu ảnh'}
          </button>
        )}
      </div>
      {open && (
        <ol className="px-4 pb-3 text-[11px] text-secondary-text space-y-1 list-decimal list-inside">
          {r.steps.map((s) => <li key={s}>{s}</li>)}
          {result.notes.map((n) => <li key={n} className="text-warning">{n}</li>)}
        </ol>
      )}
    </div>
  )
}
