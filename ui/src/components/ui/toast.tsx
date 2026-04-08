import * as React from 'react'

function ToastProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function ToastViewport() {
  return null
}

function Toast({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function ToastTitle({ children }: { children: React.ReactNode }) {
  return <strong>{children}</strong>
}

function ToastDescription({ children }: { children: React.ReactNode }) {
  return <p>{children}</p>
}

function ToastClose({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function ToastAction({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export { ToastProvider, ToastViewport, Toast, ToastTitle, ToastDescription, ToastClose, ToastAction }
