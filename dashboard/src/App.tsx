import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./stores/auth";
import { ToastProvider } from "./components/Toast";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { SidebarLayout } from "./components/SidebarLayout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Agents } from "./pages/Agents";
import { Briefing } from "./pages/Briefing";
import { Scout } from "./pages/Scout";
import { Settings } from "./pages/Settings";
import { Activity } from "./pages/Activity";
import { Setup } from "./pages/Setup";

function ProtectedPage({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <SidebarLayout>{children}</SidebarLayout>
    </ProtectedRoute>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/setup" element={<Setup />} />
            <Route
              path="/"
              element={
                <ProtectedPage>
                  <Dashboard />
                </ProtectedPage>
              }
            />
            <Route
              path="/agents"
              element={
                <ProtectedPage>
                  <Agents />
                </ProtectedPage>
              }
            />
            <Route
              path="/briefing"
              element={
                <ProtectedPage>
                  <Briefing />
                </ProtectedPage>
              }
            />
            <Route
              path="/scout"
              element={
                <ProtectedPage>
                  <Scout />
                </ProtectedPage>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedPage>
                  <Settings />
                </ProtectedPage>
              }
            />
            <Route
              path="/activity"
              element={
                <ProtectedPage>
                  <Activity />
                </ProtectedPage>
              }
            />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
