import { useState } from 'react'
import { Cloud, Cpu, KeyRound, X } from 'lucide-react'
import { api, type InitInfo } from '../api'
import { Segmented, Slider, Toggle } from './ui'

interface Props {
  info: InitInfo
  onClose: () => void
  onChanged: (info: InitInfo) => void
}

export function SettingsModal({ info, onClose, onChanged }: Props) {
  const g0 = info.settings.google
  const [g, setG] = useState({ ...g0 })
  const [key, setKey] = useState('')
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [falKey, setFalKey] = useState('')
  const [falMsg, setFalMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [falTesting, setFalTesting] = useState(false)

  const saveFal = async () => {
    if (!falKey.trim()) return
    const r = await api().set_fal(falKey)
    onChanged({ ...info, settings: r.settings })
    setFalKey('')
    setFalMsg({ ok: true, text: 'Đã lưu khoá fal.ai (mã hoá bằng Windows).' })
  }
  const testFal = async () => {
    setFalTesting(true)
    setFalMsg(null)
    if (falKey.trim()) await saveFal()
    const r = await api().test_fal()
    setFalMsg(r.ok ? { ok: true, text: r.message! } : { ok: false, text: r.error! })
    setFalTesting(false)
  }

  const save = async () => {
    const r = await api().set_google({
      enabled: g.enabled, auth: g.auth, service_account_file: g.service_account_file, project: g.project,
      location: g.location, preservation: g.preservation, enhance_input: g.enhance_input,
      ...(key ? { api_key: key } : {}),
    })
    onChanged({ ...info, settings: r.settings })
    setKey('')
    setG({ ...r.settings.google })
    setMsg({ ok: true, text: 'Đã lưu cài đặt Google.' })
  }

  const test = async () => {
    setTesting(true)
    setMsg(null)
    await save()
    const r = await api().test_google()
    setMsg(r.ok ? { ok: true, text: r.message! } : { ok: false, text: r.error! })
    setTesting(false)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6" onMouseDown={onClose}>
      <div className="glass-card w-[640px] max-h-full overflow-y-auto shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-brand">
          <h2 className="font-heading font-bold text-base">Cài đặt</h2>
          <button className="aiezo-btn-ghost !px-2" onClick={onClose} aria-label="Đóng"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-5 space-y-6">
          <section>
            <h3 className="font-heading font-semibold text-sm flex items-center gap-2 mb-2"><Cpu className="w-4 h-4 text-accent-strong" />Xử lý trên máy (mặc định)</h3>
            <p className="text-xs text-secondary-text">Thiết bị: <b className="text-primary-text">{info.device.label}</b>. Ảnh không rời khỏi máy, không cần mạng, không tốn phí.</p>
            <table className="w-full text-[11px] mt-2">
              <tbody>
                {info.models.map((m) => (
                  <tr key={m.key} className="border-b border-border-brand">
                    <td className="py-1.5 font-semibold text-primary-text">{m.label}</td>
                    <td className="py-1.5 text-secondary-text">{m.license}</td>
                    <td className="py-1.5 text-muted-text">{m.source}</td>
                    <td className={`py-1.5 ${m.installed ? 'text-success' : 'text-danger'}`}>{m.installed ? 'Có sẵn' : 'Thiếu file'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="font-heading font-semibold text-sm flex items-center gap-2 mb-2"><Cloud className="w-4 h-4 text-accent-strong" />SeedVR2 qua API fal.ai (tuỳ chọn, trả phí)</h3>
            <ul className="text-[11px] text-secondary-text space-y-1 list-disc pl-4 mb-3">
              <li>Cùng model SeedVR2 nhưng chạy trên máy chủ: làm 8K trọn vẹn (GPU 12 GB không đủ), hoặc dùng trên máy không có GPU.</li>
              <li>Giá công bố 0,001 USD/megapixel ảnh ra: 4K ≈ 0,008 USD, 8K ≈ 0,033 USD. Tạo tài khoản và khoá tại fal.ai (bạn tự đăng ký, nạp tiền).</li>
              <li>Ảnh được gửi lên máy chủ fal.ai. Chưa kiểm thử với khoá thật; nếu lỗi, thông báo của fal.ai hiện nguyên văn.</li>
            </ul>
            <label className="block text-xs text-secondary-text">
              <span className="flex items-center gap-1 mb-1"><KeyRound className="w-3.5 h-3.5" /> Khoá API fal.ai {info.settings.fal.has_api_key && <span className="text-success">(đã lưu)</span>}</span>
              <input type="password" className="field" value={falKey} onChange={(e) => setFalKey(e.target.value)} placeholder={info.settings.fal.has_api_key ? 'Nhập khoá mới để thay' : 'Dán khoá fal.ai'} />
            </label>
            <div className="flex items-center gap-2 pt-2">
              <button className="aiezo-btn-primary" onClick={saveFal} disabled={!falKey.trim()}>Lưu khoá</button>
              <button className="aiezo-btn-secondary" onClick={testFal} disabled={falTesting || (!falKey.trim() && !info.settings.fal.has_api_key)}>
                {falTesting ? 'Đang kiểm tra…' : 'Kiểm tra kết nối (≈ 0,00002 USD)'}
              </button>
            </div>
            {falMsg && <p className={`text-xs mt-2 ${falMsg.ok ? 'text-success' : 'text-danger'} break-words`}>{falMsg.text}</p>}
          </section>

          <section>
            <h3 className="font-heading font-semibold text-sm flex items-center gap-2 mb-2"><Cloud className="w-4 h-4 text-accent-strong" />Google Imagen Upscale (tuỳ chọn, trả phí)</h3>
            <ul className="text-[11px] text-secondary-text space-y-1 list-disc pl-4 mb-3">
              <li>Model <code>imagen-4.0-upscale-preview</code> trên Vertex AI (Google Cloud), giá công bố khoảng 0,06 USD mỗi ảnh. Cần tài khoản Google Cloud có bật thanh toán.</li>
              <li>Chỉ phóng x2 / x4, ảnh ra tối đa 17 MP: đủ cho 2K, 4K; không đạt 8K.</li>
              <li>Imagen là model tạo sinh, có thể thêm chi tiết không có trong ảnh gốc. Với yêu cầu không bịa chi tiết, nên dùng bộ xử lý trên máy.</li>
              <li>Tính năng này chưa được kiểm thử với tài khoản thật; nếu lỗi, thông báo của Google sẽ hiện nguyên văn.</li>
            </ul>
            <div className="space-y-3">
              <Toggle checked={g.enabled} onChange={(v) => setG({ ...g, enabled: v })} label="Bật Google Imagen trong mục Bộ xử lý" />
              <Segmented<'api_key' | 'service_account'>
                value={g.auth}
                onChange={(v) => setG({ ...g, auth: v })}
                options={[
                  { value: 'api_key', label: 'Khoá API (Vertex AI express)' },
                  { value: 'service_account', label: 'Tài khoản dịch vụ (JSON)' },
                ]}
              />
              {g.auth === 'api_key' ? (
                <label className="block text-xs text-secondary-text">
                  <span className="flex items-center gap-1 mb-1"><KeyRound className="w-3.5 h-3.5" /> Khoá API {g.has_api_key && <span className="text-success">(đã lưu, mã hoá bằng Windows)</span>}</span>
                  <input type="password" className="field" value={key} onChange={(e) => setKey(e.target.value)} placeholder={g.has_api_key ? 'Nhập khoá mới để thay' : 'Dán khoá API Vertex AI'} />
                </label>
              ) : (
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <input className="field flex-1" value={g.service_account_file} readOnly placeholder="Chọn file khoá JSON" />
                    <button className="aiezo-btn-secondary" onClick={async () => { const p = await api().pick_service_account(); if (p) setG({ ...g, service_account_file: p }) }}>Chọn file</button>
                  </div>
                  <div className="flex gap-2">
                    <input className="field" value={g.project} onChange={(e) => setG({ ...g, project: e.target.value })} placeholder="Project ID (để trống: lấy trong file)" />
                    <input className="field !w-40" value={g.location} onChange={(e) => setG({ ...g, location: e.target.value })} placeholder="us-central1" />
                  </div>
                </div>
              )}
              <Slider label="Giữ ảnh gốc (image_preservation_factor)" value={g.preservation} onChange={(v) => setG({ ...g, preservation: v })} hint="Cao = Google tôn trọng điểm ảnh gốc hơn, ít thêm chi tiết." />
              <Toggle checked={g.enhance_input} onChange={(v) => setG({ ...g, enhance_input: v })} label="Khử nhiễu nén trước khi phóng (enhance_input_image)" />
              <div className="flex items-center gap-2 pt-1">
                <button className="aiezo-btn-primary" onClick={save}>Lưu</button>
                <button className="aiezo-btn-secondary" onClick={test} disabled={testing}>{testing ? 'Đang kiểm tra…' : 'Kiểm tra kết nối (tính phí 1 ảnh)'}</button>
              </div>
              {msg && <p className={`text-xs ${msg.ok ? 'text-success' : 'text-danger'} break-words`}>{msg.text}</p>}
            </div>
          </section>

          <p className="text-[11px] text-muted-text">{info.app} {info.version} · AIEZO</p>
        </div>
      </div>
    </div>
  )
}
