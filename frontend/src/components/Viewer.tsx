import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Columns2, Expand, ImagePlus, Loader2, Maximize, ScanSearch, X } from 'lucide-react'
import { api, type OpenedImage, type ResultPayload } from '../api'

type Mode = 'compare' | 'before' | 'after'

interface Props {
  image: OpenedImage | null
  result: ResultPayload | null
  onOpen: () => void
  busy: boolean
  progress: number
  message: string
}

interface Loupe {
  loading: boolean
  before?: string
  after?: string
  size?: number
  x?: number
  y?: number
  error?: string
}

export function Viewer({ image, result, onOpen, busy, progress, message }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const [nat, setNat] = useState<{ w: number; h: number } | null>(null)
  const [view, setView] = useState({ s: 1, x: 0, y: 0 })
  const [split, setSplit] = useState(0.5)
  const [mode, setMode] = useState<Mode>('compare')
  const [loupeOn, setLoupeOn] = useState(false)
  const [loupe, setLoupe] = useState<Loupe | null>(null)
  const drag = useRef<{ kind: 'pan' | 'split'; sx: number; sy: number; vx: number; vy: number } | null>(null)

  const after = result?.after
  const before = result ? result.before : image?.preview
  const outW = result?.report.out_w ?? image?.width ?? 1

  // Kích thước ảnh xem trước (điểm ảnh) để tính khung
  useEffect(() => {
    setLoupe(null)
    if (result) setNat({ w: result.preview_w, h: result.preview_h })
    else if (image) {
      const im = new Image()
      im.onload = () => setNat({ w: im.naturalWidth, h: im.naturalHeight })
      im.src = image.preview
    } else setNat(null)
  }, [image, result])

  const fit = useCallback(() => {
    const el = box.current
    if (!el || !nat) return
    const cw = el.clientWidth, ch = el.clientHeight
    const s = Math.min(cw / nat.w, ch / nat.h) * 0.95
    setView({ s, x: (cw - nat.w * s) / 2, y: (ch - nat.h * s) / 2 })
  }, [nat])

  useLayoutEffect(() => { fit() }, [fit])
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => fit())
    ro.observe(el)
    return () => ro.disconnect()
  }, [fit])

  const zoomTo = (s: number, cx?: number, cy?: number) => {
    const el = box.current
    if (!el) return
    const px = cx ?? el.clientWidth / 2, py = cy ?? el.clientHeight / 2
    setView((v) => {
      const ns = Math.min(16, Math.max(0.05, s))
      return { s: ns, x: px - ((px - v.x) * ns) / v.s, y: py - ((py - v.y) * ns) / v.s }
    })
  }

  const onWheel = (e: React.WheelEvent) => {
    if (!nat) return
    const r = box.current!.getBoundingClientRect()
    zoomTo(view.s * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX - r.left, e.clientY - r.top)
  }

  const onDown = (e: React.MouseEvent) => {
    if (!nat || e.button !== 0) return
    const r = box.current!.getBoundingClientRect()
    const mx = e.clientX - r.left, my = e.clientY - r.top
    if (loupeOn && result) {
      const ix = (mx - view.x) / view.s, iy = (my - view.y) / view.s
      if (ix >= 0 && iy >= 0 && ix <= nat.w && iy <= nat.h) requestLoupe(ix / nat.w, iy / nat.h)
      return
    }
    const splitX = r.width * split
    const isSplit = result && mode === 'compare' && Math.abs(mx - splitX) < 10
    drag.current = { kind: isSplit ? 'split' : 'pan', sx: e.clientX, sy: e.clientY, vx: view.x, vy: view.y }
  }

  useEffect(() => {
    const move = (e: MouseEvent) => {
      const d = drag.current
      if (!d || !box.current) return
      if (d.kind === 'split') {
        const r = box.current.getBoundingClientRect()
        setSplit(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)))
      } else setView((v) => ({ ...v, x: d.vx + e.clientX - d.sx, y: d.vy + e.clientY - d.sy }))
    }
    const up = () => { drag.current = null }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [])

  const requestLoupe = async (cx: number, cy: number) => {
    setLoupe({ loading: true })
    const r = await api().crop(cx, cy, 420)
    setLoupe(r.ok ? { loading: false, before: r.before, after: r.after, size: r.size, x: r.x, y: r.y } : { loading: false, error: r.error })
  }

  // Phần ảnh "trước" hiện bên trái đường chia: cắt theo toạ độ ảnh
  const boxW = box.current?.clientWidth ?? 0
  const clipRightPct = nat ? Math.min(100, Math.max(0, 100 - (((boxW * split - view.x) / view.s) / nat.w) * 100)) : 50
  const realPct = nat ? Math.round(((view.s * nat.w) / outW) * 100) : 100
  const previewSmaller = !!(result && nat && nat.w < outW)
  const dpr = window.devicePixelRatio || 1

  if (!image) {
    return (
      <div className="flex-1 flex items-center justify-center checker p-6">
        <button
          onClick={onOpen}
          className="group max-w-lg w-full border-2 border-dashed border-border-brand hover:border-accent rounded-3xl p-10 text-center transition-colors bg-surface/60"
        >
          <ImagePlus className="w-12 h-12 mx-auto text-accent-strong mb-4" />
          <p className="font-heading font-semibold text-primary-text text-lg">Kéo thả ảnh vào đây</p>
          <p className="text-sm text-secondary-text mt-1">hoặc bấm để chọn ảnh (PNG, JPG, WEBP, BMP, TIFF)</p>
          <p className="text-xs text-muted-text mt-4">Ảnh được xử lý ngay trên máy này bằng GPU, không tải lên mạng.</p>
        </button>
      </div>
    )
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col checker relative">
      {/* Thanh công cụ xem ảnh */}
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border-brand bg-surface/80 backdrop-blur text-xs">
        <div className="flex items-center gap-1 bg-elevated-surface p-1 rounded-full border border-border-brand">
          {([
            ['compare', 'So sánh trượt', <Columns2 key="c" className="w-3.5 h-3.5" />],
            ['before', 'Ảnh gốc', null],
            ['after', 'Sau khi làm nét', null],
          ] as const).map(([m, label, icon]) => (
            <button
              key={m}
              disabled={!result}
              onClick={() => setMode(m)}
              className={`px-3 py-1 rounded-full font-semibold flex items-center gap-1 transition-colors ${
                (result ? mode : 'before') === m ? 'bg-accent text-accent-contrast' : 'text-secondary-text hover:text-primary-text'
              } disabled:opacity-40`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1">
          <button className="aiezo-btn-ghost !min-h-7 !px-2.5" onClick={fit} title="Vừa khung">
            <Maximize className="w-3.5 h-3.5" /> Vừa khung
          </button>
          <button
            className="aiezo-btn-ghost !min-h-7 !px-2.5"
            onClick={() => nat && zoomTo(outW / nat.w)}
            title="Phóng 100% so với kích thước ảnh kết quả"
          >
            <Expand className="w-3.5 h-3.5" /> 100%
          </button>
          <span className="w-14 text-center tabular-nums text-secondary-text">{realPct}%</span>
          <button
            disabled={!result}
            onClick={() => { setLoupeOn((v) => !v); setLoupe(null) }}
            className={`${loupeOn ? 'aiezo-btn-primary' : 'aiezo-btn-secondary'} !min-h-7 !px-3`}
            title="Bấm vào một điểm trên ảnh để xem điểm ảnh thật 1:1, trước và sau"
          >
            <ScanSearch className="w-3.5 h-3.5" /> Soi 1:1
          </button>
        </div>
      </div>

      <div
        ref={box}
        className={`flex-1 relative overflow-hidden select-none ${loupeOn ? 'cursor-crosshair' : 'cursor-grab active:cursor-grabbing'}`}
        onWheel={onWheel}
        onMouseDown={onDown}
        onDoubleClick={() => !loupeOn && fit()}
      >
        {nat && before && (
          <div
            className="absolute top-0 left-0 origin-top-left"
            style={{ width: nat.w, height: nat.h, transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }}
          >
            {(!result || mode !== 'before') && after && (
              <img src={after} alt="Sau khi làm nét" draggable={false} className="absolute inset-0 w-full h-full" style={{ imageRendering: view.s > 2 ? 'pixelated' : 'auto' }} />
            )}
            {(!result || mode !== 'after') && (
              <img
                src={before}
                alt="Ảnh gốc"
                draggable={false}
                className="absolute inset-0 w-full h-full"
                style={{
                  clipPath: result && mode === 'compare' ? `inset(0 ${clipRightPct}% 0 0)` : undefined,
                  imageRendering: view.s > 2 ? 'pixelated' : 'auto',
                }}
              />
            )}
          </div>
        )}

        {result && mode === 'compare' && (
          <>
            <div className="absolute top-0 bottom-0 w-0.5 bg-accent pointer-events-none" style={{ left: `calc(${split * 100}% - 1px)` }}>
              <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 left-1/2 w-8 h-8 rounded-full bg-accent text-accent-contrast flex items-center justify-center shadow-lg">
                <Columns2 className="w-4 h-4" />
              </div>
            </div>
            <span className="absolute top-3 left-3 text-[11px] font-semibold px-2 py-1 rounded-full bg-black/60 text-white pointer-events-none">Ảnh gốc (phóng thường)</span>
            <span className="absolute top-3 right-3 text-[11px] font-semibold px-2 py-1 rounded-full bg-accent text-accent-contrast pointer-events-none">Sau khi làm nét</span>
          </>
        )}

        {previewSmaller && !loupe && (
          <span className="absolute bottom-3 left-3 text-[11px] px-2 py-1 rounded-full bg-black/60 text-white pointer-events-none">
            Đang xem bản thu nhỏ {nat!.w}×{nat!.h}. Dùng “Soi 1:1” để xem điểm ảnh thật {result!.report.out_w}×{result!.report.out_h}.
          </span>
        )}

        {busy && (
          <div className="absolute inset-0 bg-background-main/50 backdrop-blur-[2px] flex items-center justify-center">
            <div className="glass-card px-6 py-5 w-[420px] max-w-[90%] shadow-2xl">
              <div className="flex items-center gap-2 text-primary-text font-heading font-semibold">
                <Loader2 className="w-4 h-4 animate-spin text-accent-strong" />
                Đang làm nét… {Math.round(progress * 100)}%
              </div>
              <div className="h-2 rounded-full bg-elevated-surface border border-border-brand mt-3 overflow-hidden">
                <div className="h-full bg-accent transition-[width] duration-300" style={{ width: `${Math.max(2, progress * 100)}%` }} />
              </div>
              <p className="text-xs text-secondary-text mt-2 min-h-8">{message}</p>
            </div>
          </div>
        )}
      </div>

      {/* Bảng soi 1:1 */}
      {loupe && (
        <div className="absolute left-3 right-3 bottom-3 glass-card shadow-2xl p-3">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-secondary-text">
              {loupe.loading ? 'Đang cắt vùng ảnh thật…' : loupe.error ? loupe.error : `Vùng ${loupe.size}×${loupe.size} px thật tại (${loupe.x}, ${loupe.y}) · 1 điểm ảnh = 1 điểm màn hình`}
            </p>
            <button className="aiezo-btn-ghost !min-h-7 !px-2" onClick={() => setLoupe(null)} aria-label="Đóng">
              <X className="w-4 h-4" />
            </button>
          </div>
          {loupe.before && loupe.after && (
            <div className="flex gap-3 justify-center overflow-auto">
              {[['Ảnh gốc phóng thường (bicubic)', loupe.before], ['Sau khi làm nét', loupe.after]].map(([label, src]) => (
                <figure key={label} className="shrink-0">
                  <img src={src} alt={label} style={{ width: loupe.size! / dpr, height: loupe.size! / dpr, imageRendering: 'pixelated' }} className="rounded-md border border-border-brand" />
                  <figcaption className="text-[11px] text-center text-secondary-text mt-1">{label}</figcaption>
                </figure>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
