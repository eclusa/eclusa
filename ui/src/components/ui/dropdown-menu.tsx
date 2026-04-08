import * as React from 'react'

function DropdownMenu({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuTrigger({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuContent({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DropdownMenuItem({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DropdownMenuCheckboxItem({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DropdownMenuRadioItem({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DropdownMenuLabel({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>
}

function DropdownMenuSeparator() {
  return <hr />
}

function DropdownMenuShortcut({ children }: { children: React.ReactNode }) {
  return <span>{children}</span>
}

function DropdownMenuGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuPortal({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuSub({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuSubTrigger({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuSubContent({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function DropdownMenuRadioGroup({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuRadioGroup,
}
