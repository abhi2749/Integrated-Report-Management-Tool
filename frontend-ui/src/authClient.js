const configuredApiBase = import.meta.env?.VITE_API_BASE_URL;
const API = (configuredApiBase ?? "").replace(/\/$/, "");

const TOKEN_KEY = "crt_access_token";
const USER_KEY = "crt_current_user";

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(accessToken, user) {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user || null));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function notifyAuthExpired() {
  window.dispatchEvent(new CustomEvent("crt-auth-expired"));
}

export async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    clearSession();
    notifyAuthExpired();
  }

  return response;
}

export { API };


export function hasPermission(user, permission) {
  if (!user) return false;
  if (String(user.role || "").toLowerCase() === "admin") return true;
  return Array.isArray(user.permissions) && user.permissions.includes(permission);
}

export function hasAnyPermission(user, permissions = []) {
  return permissions.some((permission) => hasPermission(user, permission));
}

export function hasAllPermissions(user, permissions = []) {
  return permissions.every((permission) => hasPermission(user, permission));
}
