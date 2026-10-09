import { ExternalLink, Sparkles, X } from 'lucide-react'
import { api } from '../api'

// Lời giới thiệu AIEZO: hiện thỉnh thoảng (sau một số lần làm ảnh / khi mở app), đóng được, không chặn thao tác
const MESSAGES = [
  { title: 'AIEZO UpScale là sản phẩm miễn phí của AIEZO', body: 'Xem thêm các ứng dụng AI khác của AIEZO.' },
  { title: 'Thấy ảnh nét hơn chưa?', body: 'Ghé web AIEZO để theo dõi bản cập nhật mới và các công cụ AI khác.' },
  { title: 'Cần giải pháp AI riêng cho công việc?', body: 'Liên hệ AIEZO qua website để được tư vấn.' },
]

export function AiezoPromo({ index, onClose }: { index: number; onClose: () => void }) {
  const m = MESSAGES[index % MESSAGES.length]
  return (
    <div className="fixed left-4 bottom-4 z-40 w-[340px] glass-card shadow-2xl p-4 border-accent/40">
      <button className="absolute right-2 top-2 aiezo-btn-ghost !min-h-7 !px-1.5" onClick={onClose} aria-label="Đóng giới thiệu">
        <X className="w-4 h-4" />
      </button>
      <div className="flex gap-3">
        <img src="./brand/upscale-mark.svg" alt="" className="w-10 h-10 rounded-lg shrink-0" />
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-wide text-accent-strong flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> AIEZO
          </p>
          <p className="font-heading font-semibold text-sm text-primary-text mt-0.5 pr-5">{m.title}</p>
          <p className="text-xs text-secondary-text mt-1">{m.body}</p>
          <button className="aiezo-btn-primary !min-h-8 mt-3" onClick={() => { api().open_aiezo('/'); onClose() }}>
            Ghé aiezo.netlify.app <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}

/** Đếm số lần (lưu trên máy) để quyết định lúc hiện: lần mở app thứ 1, 6, 11… và lần làm ảnh thứ 2, 5, 8… */
export function bumpCounter(key: string): number {
  let n = 0
  try {
    n = Number(localStorage.getItem(key) || '0') + 1
    localStorage.setItem(key, String(n))
  } catch {
    n = 1
  }
  return n
}
