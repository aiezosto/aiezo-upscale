import { Cpu, ExternalLink, FolderOpen, Image as ImageIcon, Layers, Moon, Settings, Sparkles, Sun } from 'lucide-react'

export type Tab = 'single' | 'batch'

interface Props {
  tab: Tab
  setTab: (t: Tab) => void
  theme: 'dark' | 'light'
  toggleTheme: () => void
  deviceLabel: string
  gpu: boolean
  onOpen: () => void
  onSettings: () => void
  busy: boolean
  onAiezo: () => void
}

export function Header({ tab, setTab, theme, toggleTheme, deviceLabel, gpu, onOpen, onSettings, busy, onAiezo }: Props) {
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'single', label: 'Làm nét 1 ảnh', icon: <ImageIcon className="w-4 h-4" /> },
    { id: 'batch', label: 'Hàng loạt', icon: <Layers className="w-4 h-4" /> },
  ]
  return (
    <header className="bg-surface/90 backdrop-blur-md border-b border-border-brand text-primary-text px-4 py-2.5 flex items-center justify-between gap-4 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <img src="./brand/upscale-mark.svg" alt="" className="w-8 h-8 rounded-lg shrink-0" />
        <div className="flex flex-col leading-none">
          <span className="aiezo-wide-title text-sm text-primary-text">UpScale</span>
          <span className="text-[10px] text-muted-text mt-1 tracking-wide">by AIEZO · làm nét & phóng to ảnh</span>
        </div>
      </div>

      <nav className="flex items-center gap-1 shrink-0 bg-elevated-surface p-1 rounded-full border border-border-brand">
        {tabs.map((t) => {
          const active = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              disabled={busy && !active}
              aria-current={active ? 'page' : undefined}
              className={`px-3.5 py-1.5 text-xs font-semibold rounded-full flex items-center gap-1.5 whitespace-nowrap transition-colors ${
                active ? 'bg-accent text-accent-contrast' : 'text-secondary-text hover:text-primary-text hover:bg-surface'
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          )
        })}
      </nav>

      <div className="flex items-center gap-2 shrink-0">
        <button onClick={onAiezo} className="aiezo-btn-secondary !min-h-8" title="Mở web AIEZO (aiezo.net)">
          <Sparkles className="w-4 h-4 text-accent-strong" /> AIEZO <ExternalLink className="w-3.5 h-3.5 text-muted-text" />
        </button>
        <span
          title={gpu ? 'Xử lý bằng GPU trên máy này, không gửi ảnh đi đâu' : 'Không tìm thấy GPU NVIDIA: chạy bằng CPU, chậm hơn nhiều'}
          className={`hidden 2xl:inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border whitespace-nowrap ${
            gpu ? 'border-emerald-500/30 bg-emerald-500/10 text-accent-strong' : 'border-amber-500/30 bg-amber-500/10 text-warning'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          {deviceLabel}
        </span>
        <button
          onClick={toggleTheme}
          title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          className="aiezo-btn-secondary !px-0 w-9"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>
        <button onClick={onSettings} className="aiezo-btn-secondary !px-0 w-9" title="Cài đặt" aria-label="Cài đặt">
          <Settings className="w-4 h-4" />
        </button>
        <button onClick={onOpen} disabled={busy} className="aiezo-btn-secondary">
          <FolderOpen className="w-4 h-4" />
          Mở ảnh
        </button>
      </div>
    </header>
  )
}
