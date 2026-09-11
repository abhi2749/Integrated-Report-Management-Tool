import { lazy, Suspense, useEffect, useState } from "react";
import { API, apiFetch, clearSession, getAccessToken, getStoredUser, saveSession } from "./authClient";
// Workspace pages are loaded on demand so the initial application bundle stays small.
const JoinDesigner = lazy(() => import("./JoinDesigner"));
const DataPreview = lazy(() => import("./DataPreview"));
const DataSourceManager = lazy(() => import("./DataSourceManager"));
const ReportBuilder = lazy(() => import("./ReportBuilder"));
const ManageUsers = lazy(() => import("./ManageUsers"));
const SavedReports = lazy(() => import("./SavedReports"));
const Dashboard = lazy(() => import("./Dashboard"));
const SavedDashboards = lazy(() => import("./SavedDashboards"));
const ImportData = lazy(() => import("./ImportData"));

/*
 * ============================================================
 * APP-OWNED CSS
 * ============================================================
 * Application shell styles only. Child components own their own CSS.
 * ReportBuilder is imported as a standalone component and does not
 * depend on App-owned ReportBuilder styles.
 */
const APP_CSS = `
.app-shell {
  min-height: 100vh;
}
.page-loading {
  min-height: 320px;
  display: grid;
  place-items: center;
  color: #667085;
  font-size: 12px;
}
/* ============================================================
   FRONT PAGE + COLLAPSING NAVIGATION
   App-owned styles only. The existing page/component styling
   remains unchanged below.
   ============================================================ */
.app-shell {
  min-height: 100vh;
  background: #f8fafc;
}
.app-topbar-shell {
  position: sticky;
  top: 0;
  z-index: 1200;
}
.app-menu-button {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  display: grid;
  place-items: center;
  border: 1px solid #d0d5dd;
  border-radius: 10px;
  background: #fff;
  color: #344054;
  cursor: pointer;
  font-size: 21px;
  line-height: 1;
  box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.app-menu-button:hover {
  border-color: #98a2b3;
  background: #f8fafc;
}
.app-brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.app-brand-mark {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(135deg, #175cd3, #0b4aa2);
  color: #fff;
  font-size: 19px;
  font-weight: 900;
  box-shadow: 0 5px 14px rgba(23,92,211,.20);
}
.app-side-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1290;
  background: rgba(15,23,42,.28);
  opacity: 0;
  pointer-events: none;
  transition: opacity .22s ease;
}
.app-side-backdrop.open {
  opacity: 1;
  pointer-events: auto;
}
.app-sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 1300;
  width: 285px;
  padding: 18px 14px;
  box-sizing: border-box;
  background: #fff;
  border-right: 1px solid #e4e7ec;
  box-shadow: 10px 0 30px rgba(15,23,42,.10);
  transform: translateX(-102%);
  transition: transform .24s ease;
  overflow-y: auto;
}
.app-sidebar.open {
  transform: translateX(0);
}
.app-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 3px 5px 18px;
  border-bottom: 1px solid #eef2f6;
}
.app-sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.app-sidebar-brand-mark {
  width: 38px;
  height: 38px;
  display: block;
  object-fit: contain;
  border-radius: 9px;
}
.app-sidebar-brand strong {
  display: block;
  color: #101828;
  font-size: 13px;
}
.app-sidebar-brand span {
  display: block;
  margin-top: 2px;
  color: #667085;
  font-size: 10px;
}
.app-sidebar-close {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: #f2f4f7;
  color: #475467;
  cursor: pointer;
  font-size: 18px;
}
.app-sidebar-close:hover { background: #e4e7ec; }
.app-sidebar-section-label {
  margin: 20px 8px 8px;
  color: #98a2b3;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.app-sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.app-sidebar-nav button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 45px;
  padding: 0 11px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: #475467;
  text-align: left;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}
.app-sidebar-nav button:hover {
  background: #f8fafc;
  color: #175cd3;
}
.app-sidebar-nav button.active {
  background: #eef4ff;
  border-color: #dbe7ff;
  color: #175cd3;
}
.app-sidebar-nav .nav-icon {
  width: 25px;
  height: 25px;
  flex: 0 0 25px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  background: #f2f4f7;
  font-size: 13px;
}
.app-sidebar-nav button.active .nav-icon {
  background: #dbe7ff;
}
.app-sidebar-footer {
  margin: 22px 4px 4px;
  padding: 12px;
  border: 1px solid #eaecf0;
  border-radius: 10px;
  background: #f8fafc;
}
.app-sidebar-footer strong {
  display: block;
  color: #344054;
  font-size: 10px;
}
.app-sidebar-footer span {
  display: block;
  margin-top: 4px;
  color: #667085;
  font-size: 9px;
  line-height: 1.45;
}
.welcome-page {
  min-height: calc(100vh - 76px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 34px 32px 64px;
  box-sizing: border-box;
}
.welcome-shell {
  width: min(1080px, 100%);
  text-align: center;
}
.welcome-kicker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 11px;
  border: 1px solid #dbe7ff;
  border-radius: 999px;
  background: #eef4ff;
  color: #175cd3;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .09em;
  text-transform: uppercase;
}
.welcome-kicker-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #12b76a;
}
.welcome-title {
  max-width: 850px;
  margin: 22px auto 0;
  color: #101828;
  font-size: clamp(38px, 6vw, 68px);
  line-height: 1.02;
  letter-spacing: -.045em;
  font-weight: 850;
}
.welcome-title span {
  color: #175cd3;
}
.welcome-subtitle {
  max-width: 690px;
  margin: 18px auto 0;
  color: #667085;
  font-size: 15px;
  line-height: 1.65;
}
.welcome-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 26px;
  flex-wrap: wrap;
}
.welcome-primary {
  min-height: 44px;
  padding: 0 18px;
  border: 1px solid #175cd3;
  border-radius: 9px;
  background: #175cd3;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: 0 7px 18px rgba(23,92,211,.18);
}
.welcome-primary:hover { background: #0f4fbf; }
.welcome-secondary {
  min-height: 44px;
  padding: 0 18px;
  border: 1px solid #d0d5dd;
  border-radius: 9px;
  background: #fff;
  color: #344054;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.welcome-secondary:hover { background: #f8fafc; }
.welcome-features {
  display: grid;
  grid-template-columns: repeat(4, minmax(0,1fr));
  gap: 12px;
  margin-top: 42px;
  text-align: left;
}
.welcome-feature {
  padding: 17px;
  border: 1px solid #e4e7ec;
  border-radius: 12px;
  background: rgba(255,255,255,.92);
  box-shadow: 0 3px 12px rgba(16,24,40,.035);
}
.welcome-feature-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  margin-bottom: 12px;
  border-radius: 9px;
  background: #f2f4f7;
  color: #175cd3;
  font-weight: 900;
}
.welcome-feature strong {
  display: block;
  color: #101828;
  font-size: 12px;
}
.welcome-feature p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 10px;
  line-height: 1.5;
}
.welcome-footer-note {
  margin-top: 20px;
  color: #98a2b3;
  font-size: 10px;
}
@media (max-width: 800px) {
  .welcome-page { padding: 28px 18px 45px; }
  .welcome-features { grid-template-columns: repeat(2, minmax(0,1fr)); }
}
@media (max-width: 520px) {
  .welcome-features { grid-template-columns: 1fr; }
  .welcome-title { font-size: 40px; }
  .topbar { padding-left: 16px; padding-right: 16px; }
  .topbar p { display: none; }
}

.topbar {
  min-height: 76px;
  background: #fff;
  border-bottom: 1px solid #e4e7ec;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.topbar h1 {
  margin: 0;
  font-size: 21px;
}
.topbar p {
  margin: 5px 0 0;
  color: #667085;
  font-size: 13px;
}
.version-badge {
  background: #eef4ff;
  color: #175cd3;
  border-radius: 20px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 700;
}
.tabs {
  background: #fff;
  border-bottom: 1px solid #e4e7ec;
  padding: 0 32px;
  display: flex;
  gap: 6px;
}
.page {
  max-width: 1500px;
  margin: 0 auto;
  padding: 30px 32px 60px;
}
.page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}
.page-heading h2 {
  margin: 0;
  font-size: 25px;
}
.page-heading p,
.card p {
  color: #667085;
  font-size: 13px;
}
.card {
  background: #fff;
  border: 1px solid #e4e7ec;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03);
}
.card h3 {
  margin: 0 0 7px;
}
.field,
.action-field,
.join-side,
.join-center {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.field label,
.join-side label,
.join-center label,
.execution-controls label {
  font-size: 12px;
  color: #475467;
  font-weight: 700;
}
.field input,
.field select,
.join-side select,
.join-center select,
.execution-controls input {
  width: 100%;
  min-height: 40px;
  border: 1px solid #d0d5dd;
  border-radius: 7px;
  padding: 0 10px;
  background: #fff;
  outline: none;
}
.primary,
.secondary,
.danger-outline {
  border-radius: 7px;
  padding: 10px 15px;
  font-weight: 700;
  white-space: nowrap;
}
.primary {
  border: 1px solid #175cd3;
  background: #175cd3;
  color: #fff;
}
.primary:disabled {
  opacity: .55;
}
.secondary {
  border: 1px solid #d0d5dd;
  background: #fff;
  color: #344054;
}
.danger-outline {
  border: 1px solid #fda29b;
  background: #fff;
  color: #b42318;
}
.status {
  margin-top: 18px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  font-size: 13px;
}
.section-title-row,
.button-row,
.execution-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.table-scroll {
  overflow: auto;
  max-height: 650px;
  margin-top: 16px;
}
@(max-width: 600px){
.topbar,
  .tabs {
    padding-left: 16px;
    padding-right: 16px;
  }
.page {
    padding: 20px 16px 40px;
  }
.button-row {
    flex-wrap: wrap;
  }
}
@(max-width: 1100px){
.calc-row .danger-outline { width: 100%; }
}
@print{
.topbar,
  .tabs,
  .page-heading,
  .report-management-card,
  .execution-card,
  .card:not(:has(.table-scroll)) {
    display: none !important;
  }
.page {
    max-width: none !important;
    padding: 0 !important;
  }
.card:has(.table-scroll) {
    border: 0 !important;
    box-shadow: none !important;
  }
.table-scroll {
    overflow: visible !important;
  }
}
@(max-width: 900px){
.preview-toolbar .primary {
    grid-column: 1 / -1;
    width: 100%;
  }
}
.data-source-manager .card{
  border-color:#dce4ef;
  border-radius:12px;
  box-shadow:0 2px 8px rgba(15,23,42,.035);
}
.data-source-manager .primary,
.data-source-manager .secondary,
.data-source-manager .danger-outline{
  min-height:36px;
  box-sizing:border-box;
  font-size:10px;
}
.data-source-manager .primary{padding:0 13px}
.data-source-manager .secondary{padding:0 13px}
.data-source-manager .danger-outline{padding:0 13px}

/* Additive authentication UI. Existing workspace styling is unchanged. */
.auth-page{min-height:100vh;display:grid;place-items:center;padding:28px;box-sizing:border-box;background:#f8fafc}
.auth-card{width:min(430px,100%);padding:30px;border:1px solid #e4e7ec;border-radius:16px;background:#fff;box-shadow:0 14px 40px rgba(15,23,42,.08);box-sizing:border-box}
.auth-mark{width:46px;height:46px;display:block;object-fit:contain;margin-bottom:18px;border-radius:12px}
.auth-card h2{margin:0;color:#101828;font-size:23px}.auth-card p{margin:7px 0 22px;color:#667085;font-size:12px;line-height:1.5}
.auth-field{margin-bottom:14px}.auth-field label{display:block;margin-bottom:6px;color:#344054;font-size:11px;font-weight:700}
.auth-field input{width:100%;height:42px;padding:0 12px;border:1px solid #d0d5dd;border-radius:8px;outline:none;box-sizing:border-box;color:#101828;background:#fff;font:inherit;font-size:12px}
.auth-field input:focus{border-color:#84adf7;box-shadow:0 0 0 3px rgba(37,99,235,.10)}
.auth-submit{width:100%;height:42px;margin-top:5px;border:1px solid #175cd3;border-radius:8px;background:#175cd3;color:#fff;cursor:pointer;font:inherit;font-size:12px;font-weight:800}
.auth-submit:hover:not(:disabled){background:#124bb0}.auth-submit:disabled{opacity:.6;cursor:not-allowed}
.auth-error{margin-bottom:13px;padding:9px 11px;border:1px solid #f2c7c7;border-radius:8px;background:#fff7f7;color:#b42318;font-size:10px;line-height:1.45}
.app-user-area{display:flex;align-items:center;gap:9px;margin-left:auto}.app-user-info{display:flex;flex-direction:column;align-items:flex-end;min-width:0}
.app-user-info strong{color:#344054;font-size:10px}.app-user-info span{margin-top:2px;color:#98a2b3;font-size:8px;text-transform:uppercase;letter-spacing:.05em}
.app-logout-button{min-height:32px;padding:0 10px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;color:#475467;cursor:pointer;font:inherit;font-size:9px;font-weight:750}
.app-logout-button:hover{background:#f8fafc;border-color:#98a2b3}
@media(max-width:640px){.app-user-info{display:none}.app-user-area{gap:5px}}
`;



function App() {
  const [activeTab, setActiveTab] = useState("home");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [reportResult, setReportResult] = useState(null);
  const [savedReportToLoad, setSavedReportToLoad] = useState("");
  const [savedDashboardToLoad, setSavedDashboardToLoad] = useState(null);

  const [authUser, setAuthUser] = useState(() => getStoredUser());
  const [authReady, setAuthReady] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState("");

  useEffect(() => {
    let mounted = true;

    const handleAuthExpired = () => {
      if (!mounted) return;
      setAuthUser(null);
      setLoginPassword("");
      setLoginError("Your session has expired. Please sign in again.");
      setAuthReady(true);
    };

    window.addEventListener("crt-auth-expired", handleAuthExpired);

    const validateSession = async () => {
      const token = getAccessToken();

      if (!token) {
        if (mounted) setAuthReady(true);
        return;
      }

      try {
        const response = await apiFetch(`${API}/auth/me`, {
          headers: { Accept: "application/json" },
        });

        if (!mounted) return;

        if (!response.ok) {
          clearSession();
          setAuthUser(null);
        } else {
          const data = await response.json();
          if (data?.success && data?.user) {
            saveSession(token, data.user);
            setAuthUser(data.user);
          } else {
            clearSession();
            setAuthUser(null);
          }
        }
      } catch {
        if (mounted) setLoginError("Unable to verify the session. Please sign in.");
      } finally {
        if (mounted) setAuthReady(true);
      }
    };

    validateSession();

    return () => {
      mounted = false;
      window.removeEventListener("crt-auth-expired", handleAuthExpired);
    };
  }, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    const username = loginUsername.trim();

    if (!username || !loginPassword) {
      setLoginError("Enter your username and password.");
      return;
    }

    setLoginBusy(true);
    setLoginError("");

    try {
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ username, password: loginPassword }),
      });

      let data = {};
      try { data = await response.json(); } catch { /* response body may be empty */ }

      if (!response.ok || !data.success || !data.access_token) {
        throw new Error(data.detail || data.message || "Invalid username or password.");
      }

      saveSession(data.access_token, data.user);
      setAuthUser(data.user);
      setLoginPassword("");
      setLoginError("");
    } catch (error) {
      setLoginError(error.message || "Unable to sign in.");
    } finally {
      setLoginBusy(false);
      setAuthReady(true);
    }
  };

  const handleLogout = async () => {
    try {
      if (getAccessToken()) {
        await apiFetch(`${API}/auth/logout`, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
      }
    } catch { /* logout may already be unavailable */ }

    clearSession();
    setAuthUser(null);
    setLoginPassword("");
    setLoginError("");
    setActiveTab("home");
    setSidebarOpen(false);
  };

  if (!authReady) {
    return (
      <div className="auth-page">
        <style>{APP_CSS}</style>
        <div className="auth-card">
          <img className="auth-mark" src="/favicon.svg" alt="Integrated Report Management Tool" />
          <h2>Integrated Report Management Tool</h2>
          <p>Verifying your secure session...</p>
        </div>
      </div>
    );
  }

  if (!authUser) {
    return (
      <div className="auth-page">
        <style>{APP_CSS}</style>
        <form className="auth-card" onSubmit={handleLogin}>
          <img className="auth-mark" src="/favicon.svg" alt="Integrated Report Management Tool" />
          <h2>Sign in</h2>
          <p>Sign in to access your reporting workspace.</p>

          {loginError && <div className="auth-error" role="alert">{loginError}</div>}

          <div className="auth-field">
            <label htmlFor="crt-login-username">Username</label>
            <input id="crt-login-username" type="text" value={loginUsername}
              onChange={(event) => setLoginUsername(event.target.value)}
              autoComplete="username" autoFocus disabled={loginBusy} />
          </div>

          <div className="auth-field">
            <label htmlFor="crt-login-password">Password</label>
            <input id="crt-login-password" type="password" value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              autoComplete="current-password" disabled={loginBusy} />
          </div>

          <button type="submit" className="auth-submit" disabled={loginBusy}>
            {loginBusy ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <style>{APP_CSS}</style>
      <div className="app-topbar-shell">
        <header className="topbar">
          <div className="app-brand-block">
            <button
              type="button"
              className="app-menu-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
              title="Open navigation"
            >
              ☰
            </button>
            <div>
              <h1>Integrated Report Management Tool</h1>
              <p>Multi-source reporting and data integration</p>
            </div>
          </div>
          <div className="app-user-area">
            <div className="app-user-info">
              <strong>{authUser?.username || "User"}</strong>
              <span>{authUser?.role || "report_user"}</span>
            </div>
            <button type="button" className="app-logout-button" onClick={handleLogout} title="Sign out">
              Logout
            </button>
          </div>
          <span className="version-badge">v0.5</span>
        </header>
      </div>

      <div
        className={sidebarOpen ? "app-side-backdrop open" : "app-side-backdrop"}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />

      <aside className={sidebarOpen ? "app-sidebar open" : "app-sidebar"}>
        <div className="app-sidebar-header">
          <div className="app-sidebar-brand" aria-label="Integrated Report Management Tool">
            <img
              className="app-sidebar-brand-mark"
              src="/favicon.svg"
              alt="Integrated Report Management Tool"
              title="Integrated Report Management Tool"
            />
          </div>
          <button
            type="button"
            className="app-sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close navigation"
          >
            ×
          </button>
        </div>

        <div className="app-sidebar-section-label">Workspace</div>
        <nav className="app-sidebar-nav">
          {[
            ["home", "⌂", "Home"],
            ["sources", "◈", "Data Sources"],
            ["import", "⇩", "Import Data"],
            ["preview", "▦", "Data Preview"],
            ["join", "⇄", "Join Designer"],
            ["report", "▤", "Report Builder"],
            ["saved-reports", "▥", "Saved Reports"],
            ["saved-dashboards", "▥", "Saved Dashboards"],
            ["dashboard", "▤", "Dashboard"],
            ["users", "♙", "Manage Users"],
          ].map(([id, icon, label]) => (
            <button
              key={id}
              type="button"
              className={activeTab === id ? "active" : ""}
              onClick={() => {
                if (id === "report") setSavedReportToLoad("");
                if (id === "dashboard") setSavedDashboardToLoad(null);
                setActiveTab(id);
                setSidebarOpen(false);
              }}
            >
              <span className="nav-icon">{icon}</span>
              <span>{label}</span>
            </button>
          ))}
        </nav>

        <div className="app-sidebar-section-label">About</div>
        <div className="app-sidebar-footer">
          <strong>Build reports without the complexity.</strong>
          <span>Connect data, combine datasets, refine results and turn them into useful reports.</span>
        </div>
      </aside>

      <main className={activeTab === "home" ? "page app-main-page" : "page app-main-page"}>
        {activeTab === "home" && (
          <section className="welcome-page">
            <div className="welcome-shell">
              <div className="welcome-kicker">
                <span className="welcome-kicker-dot" />
                Your reporting workspace is ready
              </div>

              <h2 className="welcome-title">
                Welcome to <span>Integrated Report Management Tool</span>
              </h2>

              <p className="welcome-subtitle">
                Bring data together, build smarter queries and create clear reports — all from one simple visual workspace.
              </p>

              <div className="welcome-actions">
                <button
                  type="button"
                  className="welcome-primary"
                  onClick={() => {
                    setActiveTab("sources");
                    setSidebarOpen(false);
                  }}
                >
                  Start with Data Sources →
                </button>
                <button
                  type="button"
                  className="welcome-secondary"
                  onClick={() => setSidebarOpen(true)}
                >
                  Explore Workspace
                </button>
              </div>

              <div className="welcome-features">
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">◈</div>
                  <strong>Connect Your Data</strong>
                  <p>Manage your reporting connections and datasets in one place.</p>
                </div>
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">⇄</div>
                  <strong>Combine Datasets</strong>
                  <p>Visually connect multiple datasets with flexible JOIN relationships.</p>
                </div>
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">⌕</div>
                  <strong>Refine Results</strong>
                  <p>Filter, group, sort, aggregate and calculate exactly what you need.</p>
                </div>
                <div className="welcome-feature">
                  <div className="welcome-feature-icon">▤</div>
                  <strong>Build Reports</strong>
                  <p>Turn your final dataset into a clean, reusable reporting output.</p>
                </div>
              </div>

              <div className="welcome-footer-note">
                Select a workspace from the menu whenever you are ready.
              </div>
            </div>
          </section>
        )}
        <Suspense fallback={<div className="page-loading" role="status">Loading workspace…</div>}>
          {activeTab === "import" && (
            <ImportData />
          )}

        {activeTab === "sources" && (
          <DataSourceManager
            datasets={datasets}
            setDatasets={setDatasets}
            setReportResult={setReportResult}
          />
        )}

        {activeTab === "preview" && (
          <DataPreview
            datasets={datasets}
            onBack={() => setActiveTab("sources")}
            onSendToReportBuilder={(result) => {
              setReportResult(result);
              setActiveTab("report");
            }}
            onSendToDashboard={(result) => {
              setReportResult(result);
              setActiveTab("dashboard");
            }}
          />
        )}

        {activeTab === "join" && (
          <JoinDesigner
            datasets={datasets}
            onDatasetsChange={setDatasets}
            onReportResult={(result) => {
              setReportResult(result);
              setActiveTab("report");
            }}
          />
        )}

        {activeTab === "report" && (
          <ReportBuilder
            datasets={datasets}
            initialResult={reportResult}
            initialSavedReportId={savedReportToLoad}
            onBack={() => setActiveTab("join")}
            onOpenDashboard={(result) => { if (result) setReportResult(result); setSavedDashboardToLoad(null); setActiveTab("dashboard"); }}
          />
        )}

        {activeTab === "dashboard" && (
          <Dashboard
            key={savedDashboardToLoad?.id || "new-dashboard"}
            result={reportResult}
            initialDashboard={savedDashboardToLoad}
            onOpenDataSources={() => setActiveTab("join")}
            onOpenDataPreview={() => setActiveTab("preview")}
            onOpenReportBuilder={() => setActiveTab("report")}
          />
        )}

        {activeTab === "saved-reports" && (
          <SavedReports
            currentUser={authUser}
            onOpenReportBuilder={(reportId = "") => {
              setSavedReportToLoad(reportId || "");
              setActiveTab("report");
              setSidebarOpen(false);
            }}
          />
        )}

          {activeTab === "saved-dashboards" && (
          <SavedDashboards
            currentUser={authUser}
            onOpenDashboard={(dashboard) => {
              setSavedDashboardToLoad(dashboard || { id: "", definition: {} });
              setActiveTab("dashboard");
              setSidebarOpen(false);
            }}
          />
        )}

          {activeTab === "users" && (
            <ManageUsers currentUser={authUser} />
          )}
        </Suspense>
      </main>
    </div>
  );
}

export default App;
