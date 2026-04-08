import * as React from 'react'

function Dialog({ open, children }: { open?: boolean; children: React.ReactNode }) {
  if (!open) return null
  return <div role="dialog">{children}</div>
}

function DialogTrigger({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DialogPortal({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DialogOverlay({ children }: { children?: React.ReactNode }) {
  return <>{children}</>
}

function DialogContent({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DialogHeader({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DialogFooter({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DialogTitle({ children }: { children: React.ReactNode }) {
  return <h2>{children}</h2>
}

function DialogDescription({ children }: { children: React.ReactNode }) {
  return <p>{children}</p>
}

function DialogClose({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogClose,
}
