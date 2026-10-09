import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { api, onBackendEvent, type FileItem, type InitInfo, type JobSettings, type OpenedImage, type ResultPayload } from './api'
import { Header, type Tab } from './components/Header'
import { Viewer } from './components/Viewer'
import { SettingsPanel, type PanelState } from './components/SettingsPanel'
import { ResultBar } from './components/ResultBar'
import { BatchView, type BatchRow } from './components/BatchView'
import { SettingsModal } from './components/SettingsModal'
import { AiezoPromo, bumpCounter } from './components/AiezoPromo'

export default function App({ initial }: { initial: InitInfo }) {
  // Giới thiệu AIEZO: lần mở app thứ 1, 6, 11…; sau lần làm ảnh thứ 2, 5, 8…
  const [promo, setPromo] = useState<number | null>(() => {
    const n = bumpCounter('aiezo_launches')
    return n % 5 === 1 ? 0 : null  // câu 0: giới thiệu AIEZO
  })
  const [info, setInfo] = useState(initial)
  const [theme, setTheme] = useState<'dark' | 'light'>(initial.settings.theme)
  const [tab, setTab] = useState<Tab>('single')
  const [showSettings, setShowSettings] = useState(false)
  const s0 = initial.settings
  const [st, setSt] = useState<PanelState>({
    target: s0.target, customLong: s0.custom_long, model: s0.model,
    engine: s0.engine === 'fal' && !s0.fal.has_api_key ? 'seedvr2' : s0.engine === 'google' && !s0.google.enabled ? 'seedvr2' : s0.engine,
    seedvr2: s0.seedvr2, fidelity: s0.fidelity, sharpen: s0.sharpen, sharpenAi: s0.sharpen_ai, fidelityAi: s0.fidelity_ai,
    contrast: 'auto', outFormat: s0.out_format, outDir: s0.out_dir,
  })
  const [image, setImage] = useState<OpenedImage | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ResultPayload | null>(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [savedPath, setSavedPath] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [rows, setRows] = useState<BatchRow[]>([])
  const tabRef = useRef(tab)
  tabRef.current = tab

  // Giao diện sáng/tối
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.classList.toggle('light', theme === 'light')
  }, [theme])
  const toggleTheme = () => {
    const t = theme === 'dark' ? 'light' : 'dark'
    setTheme(t)
    api().save_settings({ theme: t })
  }

  // Lưu lựa chọn để lần sau mở lại giữ nguyên
  const set = (patch: Partial<PanelState>) => {
    setSt((p) => ({ ...p, ...patch }))
    setSavedPath(null)
    const map: Record<string, string> = {
      target: 'target', customLong: 'custom_long', model: 'model', fidelity: 'fidelity', sharpen: 'sharpen',
      sharpenAi: 'sharpen_ai', fidelityAi: 'fidelity_ai', engine: 'engine', seedvr2: 'seedvr2', outFormat: 'out_format',
    }
    const save: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(patch)) if (map[k]) save[map[k]] = v
    if (Object.keys(save).length) api().save_settings(save)
  }

  const isAiEngine = st.engine === 'seedvr2' || st.engine === 'fal'
  const jobSettings = (contrast: boolean | 'auto'): JobSettings => ({
    target: st.target, custom_long: st.customLong, model: st.model, engine: st.engine, seedvr2: st.seedvr2,
    fidelity: isAiEngine ? st.fidelityAi : st.fidelity, sharpen: isAiEngine ? st.sharpenAi : st.sharpen, contrast,
    out_format: st.outFormat, jpeg_quality: 95, out_dir: st.outDir,
  })

  const openOne = useCallback(async (item: FileItem) => {
    if (item.error) return setError(item.error)
    setLoading(true)
    setResult(null)
    setSavedPath(null)
    const r = await api().open_image(item.path)
    setLoading(false)
    if (!r.ok) return setError(r.error || 'Không mở được ảnh')
    setImage(r)
    setSt((p) => ({ ...p, contrast: 'auto' }))
  }, [])

  const addToBatch = (items: FileItem[]) =>
    setRows((prev) => {
      const seen = new Set(prev.map((r) => r.path))
      return [...prev, ...items.filter((i) => !seen.has(i.path)).map((i) => ({ ...i, status: 'pending' as const }))]
    })

  const handleItems = useCallback((items: FileItem[]) => {
    if (!items.length) return
    if (tabRef.current === 'batch' || items.length > 1) {
      addToBatch(items)
      if (items.length > 1) setTab('batch')
    } else openOne(items[0])
  }, [openOne])

  const onOpen = async () => handleItems(await api().pick_images())

  // Sự kiện từ Python
  useEffect(() => onBackendEvent((e) => {
    switch (e.type) {
      case 'progress':
        setProgress(e.value); setMessage(e.message); break
      case 'done': {
        setBusy(false); setProgress(1); setResult(e)
        const n = bumpCounter('aiezo_done')
        if (n % 3 === 2) setPromo(n)
        break
      }
      case 'error':
        setBusy(false); setError(e.message); break
      case 'cancelled':
        setBusy(false); setMessage('Đã huỷ'); break
      case 'dropped':
        handleItems(e.items); break
      case 'batch_item':
        setRows((rs) => rs.map((r, i) => i !== e.index ? r : {
          ...r, status: e.status, out: e.path, outW: e.out_w, outH: e.out_h, psnr: e.psnr, ssim: e.ssim, level: e.level, message: e.error,
        }))
        break
      case 'batch_done':
        setBusy(false); setMessage(`Xong. Ảnh đã lưu trong ${e.out_dir}`); setPromo(bumpCounter('aiezo_done')); break
    }
  }), [handleItems])

  const contrastFor = (img: OpenedImage | null) => st.contrast === 'on' || (st.contrast === 'auto' && !!img?.suggest_contrast)

  const start = async () => {
    setError(null)
    setSavedPath(null)
    setProgress(0)
    setMessage('Đang chuẩn bị')
    if (tab === 'single') {
      if (!image) return
      setBusy(true)
      const r = await api().start(image.path, jobSettings(contrastFor(image)))
      if (!r.ok) { setBusy(false); setError(r.error || 'Không chạy được') }
    } else {
      const todo = rows.filter((r) => !r.error)
      if (!todo.length) return
      setRows(rows.map((r) => (r.error ? r : { ...r, status: 'pending', out: undefined, psnr: undefined, ssim: undefined, outW: undefined, outH: undefined })))
      setBusy(true)
      const r = await api().start_batch(rows.filter((x) => !x.error).map((x) => x.path),
        jobSettings(st.contrast === 'auto' ? 'auto' : st.contrast === 'on'))
      if (!r.ok) { setBusy(false); setError(r.error || 'Không chạy được') }
    }
  }

  const save = async () => {
    setSaving(true)
    const r = await api().save_result(jobSettings(contrastFor(image)))
    setSaving(false)
    if (r.ok) setSavedPath(r.path!)
    else setError(r.error || 'Không lưu được')
  }

  const chooseFolder = async () => {
    const p = await api().choose_folder()
    if (p) setSt((s) => ({ ...s, outDir: p }))
  }

  return (
    <div className="h-full flex flex-col">
      <Header
        tab={tab}
        setTab={setTab}
        theme={theme}
        toggleTheme={toggleTheme}
        deviceLabel={info.device.label}
        gpu={info.device.type === 'cuda'}
        onOpen={onOpen}
        onSettings={() => setShowSettings(true)}
        busy={busy}
        onAiezo={() => api().open_aiezo('/')}
      />

      {error && (
        <div className="flex items-start gap-2 px-4 py-2 bg-red-500/10 border-b border-red-500/30 text-danger text-xs">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="flex-1 break-words">{error}</span>
          <button onClick={() => setError(null)} aria-label="Đóng"><X className="w-4 h-4" /></button>
        </div>
      )}

      <div className="flex-1 flex min-h-0">
        {tab === 'single' ? (
          <div className="flex-1 min-w-0 flex flex-col">
            <Viewer image={image} result={result} onOpen={onOpen} busy={busy || loading} progress={loading ? 0 : progress} message={loading ? 'Đang đọc và phân tích ảnh…' : message} />
            {result && !busy && (
              <ResultBar result={result} savedPath={savedPath} onSave={save} saving={saving} onReveal={(p) => api().open_path(p)} />
            )}
          </div>
        ) : (
          <BatchView
            info={info}
            rows={rows}
            target={st.target}
            customLong={st.customLong}
            busy={busy}
            progress={progress}
            message={message}
            onAdd={onOpen}
            onRemove={(i) => setRows((rs) => rs.filter((_, j) => j !== i))}
            onClear={() => setRows([])}
            onReveal={(p) => api().open_path(p)}
          />
        )}

        <SettingsPanel
          info={info}
          st={st}
          set={set}
          image={tab === 'single' ? image : null}
          batch={tab === 'batch' ? { count: rows.filter((r) => !r.error).length } : undefined}
          busy={busy}
          hasResult={tab === 'single' && !!result}
          onStart={start}
          onCancel={() => api().cancel()}
          onChooseFolder={chooseFolder}
          onOpenFolder={() => api().open_path(st.outDir)}
        />
      </div>

      {promo !== null && !busy && <AiezoPromo index={promo} onClose={() => setPromo(null)} />}

      {showSettings && (
        <SettingsModal
          info={info}
          onClose={() => setShowSettings(false)}
          onChanged={(i) => {
            setInfo(i)
            if ((st.engine === 'google' && !i.settings.google.enabled) || (st.engine === 'fal' && !i.settings.fal.has_api_key))
              setSt((s) => ({ ...s, engine: 'seedvr2' }))
          }}
        />
      )}
    </div>
  )
}
