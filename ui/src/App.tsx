import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { AuthProvider } from '@/auth/AuthProvider'
import { useAuth } from '@/auth/useAuth'
import { DashboardPage } from '@/pages/DashboardPage'
import { GatesPage } from '@/pages/GatesPage'
import { CascadeDetailPage } from '@/pages/CascadeDetailPage'
import MetricsPage from '@/pages/MetricsPage'
import { LedgerPage } from '@/pages/LedgerPage'
import { KnowledgePage } from '@/pages/KnowledgePage'
import { SessionPage } from '@/pages/SessionPage'
import { CostsPage } from '@/pages/CostsPage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ChatPage } from '@/pages/ChatPage'

const queryClient = new QueryClient()

function ProtectedRoute() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Navigate to="/cascades" replace />} />
          <Route path="cascades" element={<DashboardPage />} />
          <Route path="cascades/:id" element={<CascadeDetailPage />} />
          <Route path="gates" element={<GatesPage />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="sessions/:id?" element={<ErrorBoundary><SessionPage /></ErrorBoundary>} />
          <Route path="costs" element={<CostsPage />} />
          <Route path="ledger" element={<LedgerPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="metrics" element={<MetricsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
