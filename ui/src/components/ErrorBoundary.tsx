import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 rounded-lg border border-red-900/40 bg-red-950/20 p-8 text-center">
          <div className="text-lg font-semibold text-red-100">Something went wrong</div>
          <Button type="button" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
