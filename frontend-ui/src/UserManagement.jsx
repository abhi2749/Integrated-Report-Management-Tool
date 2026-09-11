import { useEffect, useMemo, useState } from "react";
import { API, apiFetch } from "./authClient";

const USER_MANAGEMENT_CSS = `
.user-admin-page{max-width:1380px;margin:0 auto;padding:28px 36px 42px;box-sizing:border-box}
.user-admin-kicker{font-size:10px;font-weight:800;letter-spacing:.12em;color:#98a2b3;text-transform:uppercase}
.user-admin-title{margin:4px 0 6px;color:#101828;font-size:28px;line-height:1.2}
.user-admin-subtitle{margin:0 0 24px;color:#667085;font-size:12px;line-height:1.5}
.user-admin-grid{display:grid;grid-template-columns:minmax(0,1fr) 430px;gap:16px;align-items:start}
.user-admin-card{border:1px solid #dfe5ee;border-radius:12px;background:#fff;overflow:hidden;box-shadow:0 3px 14px rgba(16,24,40,.04)}
.user-admin-card-head{padding:16px 18px;border-bottom:1px solid #eaecf0}
.user-admin-card-head h3{margin:0;color:#101828;font-size:14px}.user-admin-card-head p{margin:4px 0 0;color:#667085;font-size:10px}
.user-admin-table-wrap{overflow:auto}.user-admin-table{width:100%;border-collapse:collapse;min-width:620px}
.user-admin-table th{padding:11px 14px;text-align:left;background:#f8fafc;color:#667085;font-size:9px;letter-spacing:.06em;text-transform:uppercase;border-bottom:1px solid #eaecf0}
.user-admin-table td{padding:12px 14px;color:#344054;font-size:11px;border-bottom:1px solid #f0f2f5;vertical-align:middle}
.user-admin-table tr:last-child td{border-bottom:0}
.user-admin-user{font-weight:750;color:#101828}.user-admin-meta{margin-top:3px;color:#98a2b3;font-size:9px}
.user-admin-pill{display:inline-flex;padding:4px 7px;border-radius:999px;background:#eef4ff;color:#175cd3;font-size:8px;font-weight:800;text-transform:uppercase}
.user-admin-pill.custom{background:#f4f3ff;color:#6938ef}.user-admin-pill.inactive{background:#f2f4f7;color:#667085}
.user-admin-actions{display:flex;gap:6px;flex-wrap:wrap}
.user-admin-btn{height:31px;padding:0 10px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;color:#344054;font-size:9px;font-weight:750;cursor:pointer}
.user-admin-btn:hover{background:#f8fafc}.user-admin-btn.primary{border-color:#175cd3;background:#175cd3;color:#fff}.user-admin-btn.danger{border-color:#fecdca;color:#b42318;background:#fff}
.user-admin-form{padding:18px}
.user-admin-field{margin-bottom:13px}.user-admin-field label{display:block;margin-bottom:5px;color:#344054;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}
.user-admin-field input,.user-admin-field select{width:100%;height:37px;padding:0 10px;border:1px solid #d0d5dd;border-radius:7px;background:#fff;color:#101828;box-sizing:border-box;font:inherit;font-size:10px}
.user-admin-field input:focus,.user-admin-field select:focus{outline:none;border-color:#84adf7;box-shadow:0 0 0 3px rgba(37,99,235,.08)}
.user-admin-perm-head{display:flex;justify-content:space-between;align-items:center;margin:17px 0 8px}
.user-admin-perm-head strong{font-size:10px;color:#344054}.user-admin-perm-head button{border:0;background:none;color:#175cd3;font-size:9px;font-weight:750;cursor:pointer}
.user-admin-group{margin-bottom:12px;border:1px solid #eaecf0;border-radius:8px;overflow:hidden}
.user-admin-group-title{padding:8px 10px;background:#f8fafc;color:#667085;font-size:8px;font-weight:850;letter-spacing:.08em;text-transform:uppercase}
.user-admin-perm{display:flex;gap:8px;padding:8px 10px;border-top:1px solid #f2f4f7;cursor:pointer}
.user-admin-perm input{margin:1px 0 0;accent-color:#175cd3}.user-admin-perm span{display:flex;flex-direction:column;gap:2px}
.user-admin-perm strong{font-size:9px;color:#344054}.user-admin-perm small{font-size:8px;color:#98a2b3;line-height:1.35}
.user-admin-notice{margin:0 18px 14px;padding:9px 10px;border-radius:7px;background:#f8fafc;color:#667085;font-size:9px;line-height:1.4}
.user-admin-error{margin:0 18px 14px;padding:9px 10px;border:1px solid #fecdca;border-radius:7px;background:#fff7f7;color:#b42318;font-size:9px}
.user-admin-success{margin:0 18px 14px;padding:9px 10px;border:1px solid #abefc6;border-radius:7px;background:#f6fef9;color:#067647;font-size:9px}
.user-admin-footer{display:flex;justify-content:flex-end;gap:7px;padding-top:5px}
@media(max-width:1050px){.user-admin-grid{grid-template-columns:1fr}.user-admin-page{padding:24px 20px 36px}}
`;

const emptyForm = { username:"", password:"", role:"custom", permissions:[] };

export default function UserManagement({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [permissionDefs, setPermissionDefs] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [editPassword, setEditPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const groups = useMemo(() => {
    const result = {};
    permissionDefs.forEach((item) => {
      (result[item.group] ||= []).push(item);
    });
    return result;
  }, [permissionDefs]);

  const load = async () => {
    setBusy(true); setError("");
    try {
      const [usersResponse, permsResponse] = await Promise.all([
        apiFetch(`${API}/auth/users`),
        apiFetch(`${API}/auth/permissions`),
      ]);
      const usersData = await usersResponse.json();
      const permsData = await permsResponse.json();
      if (!usersResponse.ok) throw new Error(usersData.detail || "Unable to load users.");
      if (!permsResponse.ok) throw new Error(permsData.detail || "Unable to load permissions.");
      setUsers(usersData.users || []);
      setPermissionDefs(permsData.permissions || []);
    } catch (e) {
      setError(e.message || "Unable to load user management.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    // Intentional initial user-management data load.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, []);

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
    setEditPassword("");
    setMessage("");
    setError("");
  };

  const togglePermission = (key) => {
    setForm((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(key)
        ? prev.permissions.filter((item) => item !== key)
        : [...prev.permissions, key],
    }));
  };

  const selectAll = () => {
    setForm((prev) => ({ ...prev, permissions: permissionDefs.map((item) => item.key) }));
  };

  const clearAll = () => setForm((prev) => ({ ...prev, permissions: [] }));

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");

    try {
      const isEdit = Boolean(editingId);
      const body = isEdit
        ? {
            role: form.role,
            permissions: form.role === "admin" ? [] : form.permissions,
            ...(editPassword ? { password: editPassword } : {}),
          }
        : {
            username: form.username.trim(),
            password: form.password,
            role: form.role,
            permissions: form.role === "admin" ? [] : form.permissions,
          };

      const response = await apiFetch(
        isEdit ? `${API}/auth/users/${editingId}` : `${API}/auth/users`,
        {
          method: isEdit ? "PUT" : "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(body),
        }
      );

      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.detail || data.message || "Operation failed.");

      setMessage(isEdit ? "User updated successfully." : "User created successfully.");
      await load();
      resetForm();
    } catch (e) {
      setError(e.message || "Operation failed.");
    } finally {
      setBusy(false);
    }
  };

  const editUser = (user) => {
    setEditingId(user.id);
    setForm({
      username: user.username || "",
      password: "",
      role: user.role || "custom",
      permissions: user.permissions || [],
    });
    setEditPassword("");
    setError(""); setMessage("");
  };

  const toggleActive = async (user) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${API}/auth/users/${user.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ active: !user.active }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.detail || "Unable to update user.");
      setMessage(`User "${user.username}" ${user.active ? "deactivated" : "activated"}.`);
      await load();
    } catch (e) {
      setError(e.message || "Unable to update user.");
    } finally {
      setBusy(false);
    }
  };

  const removeUser = async (user) => {
    if (!window.confirm(`Delete user "${user.username}"? This cannot be undone.`)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await apiFetch(`${API}/auth/users/${user.id}`, {
        method: "DELETE",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.detail || "Unable to delete user.");
      setMessage(`User "${user.username}" deleted.`);
      await load();
      if (editingId === user.id) resetForm();
    } catch (e) {
      setError(e.message || "Unable to delete user.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="user-admin-page">
      <style>{USER_MANAGEMENT_CSS}</style>
      <div className="user-admin-kicker">Administration</div>
      <h2 className="user-admin-title">User Management</h2>
      <p className="user-admin-subtitle">
        Create users and assign exactly which reporting capabilities they are allowed to use.
        Permissions are enforced by the backend.
      </p>

      {error && <div className="user-admin-error" role="alert">{error}</div>}
      {message && <div className="user-admin-success">{message}</div>}

      <div className="user-admin-grid">
        <section className="user-admin-card">
          <div className="user-admin-card-head">
            <h3>Users</h3>
            <p>{users.length} user(s) registered</p>
          </div>
          <div className="user-admin-table-wrap">
            <table className="user-admin-table">
              <thead>
                <tr><th>User</th><th>Role</th><th>Permissions</th><th>Status</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className="user-admin-user">{user.username}</div>
                      <div className="user-admin-meta">{user.id}</div>
                    </td>
                    <td><span className={`user-admin-pill ${user.role === "custom" ? "custom" : ""}`}>{user.role}</span></td>
                    <td>{user.role === "admin" ? "All permissions" : `${(user.permissions || []).length} assigned`}</td>
                    <td><span className={`user-admin-pill ${user.active ? "" : "inactive"}`}>{user.active ? "Active" : "Inactive"}</span></td>
                    <td>
                      <div className="user-admin-actions">
                        <button className="user-admin-btn" onClick={() => editUser(user)} disabled={busy}>Edit</button>
                        {user.id !== currentUser?.id && (
                          <>
                            <button className="user-admin-btn" onClick={() => toggleActive(user)} disabled={busy}>
                              {user.active ? "Disable" : "Enable"}
                            </button>
                            <button className="user-admin-btn danger" onClick={() => removeUser(user)} disabled={busy}>Delete</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {!users.length && !busy && <tr><td colSpan="5">No users found.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="user-admin-card">
          <div className="user-admin-card-head">
            <h3>{editingId ? "Edit User" : "Create Custom User"}</h3>
            <p>{editingId ? "Change role, password or permissions." : "Assign only the capabilities this user needs."}</p>
          </div>

          <form className="user-admin-form" onSubmit={submit}>
            {!editingId && (
              <>
                <div className="user-admin-field">
                  <label>Username</label>
                  <input value={form.username} onChange={(e) => setForm({...form, username:e.target.value})} autoComplete="off" />
                </div>
                <div className="user-admin-field">
                  <label>Password</label>
                  <input type="password" value={form.password} onChange={(e) => setForm({...form, password:e.target.value})} autoComplete="new-password" />
                </div>
              </>
            )}

            {editingId && (
              <div className="user-admin-field">
                <label>Username</label>
                <input value={form.username} disabled />
              </div>
            )}

            <div className="user-admin-field">
              <label>Role</label>
              <select value={form.role} onChange={(e) => setForm({...form, role:e.target.value})}>
                <option value="custom">Custom User</option>
                <option value="report_user">Report User</option>
                <option value="admin">Administrator</option>
              </select>
            </div>

            {editingId && (
              <div className="user-admin-field">
                <label>New Password (optional)</label>
                <input type="password" value={editPassword} onChange={(e) => setEditPassword(e.target.value)} autoComplete="new-password" placeholder="Leave blank to keep current password" />
              </div>
            )}

            {form.role === "admin" ? (
              <div className="user-admin-notice">Administrators automatically receive all permissions. Individual permission selection is not required.</div>
            ) : (
              <>
                <div className="user-admin-perm-head">
                  <strong>Custom Permissions ({form.permissions.length})</strong>
                  <div>
                    <button type="button" onClick={selectAll}>Select All</button>
                    <button type="button" onClick={clearAll} style={{marginLeft:8}}>Clear</button>
                  </div>
                </div>

                {Object.entries(groups).map(([group, items]) => (
                  <div className="user-admin-group" key={group}>
                    <div className="user-admin-group-title">{group}</div>
                    {items.map((item) => (
                      <label className="user-admin-perm" key={item.key}>
                        <input
                          type="checkbox"
                          checked={form.permissions.includes(item.key)}
                          onChange={() => togglePermission(item.key)}
                        />
                        <span>
                          <strong>{item.label}</strong>
                          <small>{item.description}</small>
                        </span>
                      </label>
                    ))}
                  </div>
                ))}
              </>
            )}

            <div className="user-admin-footer">
              {editingId && <button type="button" className="user-admin-btn" onClick={resetForm} disabled={busy}>Cancel</button>}
              <button type="submit" className="user-admin-btn primary" disabled={busy}>
                {busy ? "Saving..." : editingId ? "Save Changes" : "Create User"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
