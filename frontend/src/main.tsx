import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { ready } from './api'

const root = ReactDOM.createRoot(document.getElementById('root')!)
document.documentElement.classList.add('dark')

function Startup({ error }: { error?: string }) {
  return (
    <div className="h-full flex items-center justify-center bg-background-main p-6">
      <div className="max-w-md text-center space-y-3">
        <img src="./brand/upscale-mark.svg" alt="" className="w-16 h-16 mx-auto rounded-xl" />
        <p className="aiezo-wide-title text-primary-text text-lg">AIEZO UpScale</p>
        {error ? (
          <>
            <p className="text-sm text-danger">Không khởi động được ứng dụng.</p>
            <p className="text-xs text-secondary-text break-words">{error}</p>
          </>
        ) : (
          <p className="text-sm text-secondary-text">Đang khởi động, kiểm tra GPU…</p>
        )}
      </div>
    </div>
  )
}

root.render(<Startup />)

ready()
  .then((py) => py.init())
  .then((info) => {
    document.documentElement.classList.toggle('dark', info.settings.theme === 'dark')
    root.render(
      <React.StrictMode>
        <App initial={info} />
      </React.StrictMode>,
    )
  })
  .catch((e: unknown) => root.render(<Startup error={String(e)} />))
