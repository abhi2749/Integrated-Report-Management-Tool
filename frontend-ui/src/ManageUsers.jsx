import { useCallback, useEffect, useMemo, useState } from "react";
import { API, apiFetch, hasPermission } from "./authClient";

const EMPTY_FORM = { username: "", password: "", role: "report_user", active: true, permissions: [] };

function listFrom(data, key) {
  if (Array.isArray(data)) return data;
  return Array.isArray(data?.[key]) ? data[key] : [];
}

export default function ManageUsers({ currentUser }) {
  const canView = hasPermission(currentUser, "users.view");
  const canCreate = hasPermission(currentUser, "users.create");
  const canEdit = hasPermission(currentUser, "users.edit");
  const canDelete = hasPermission(currentUser, "users.delete");

  const [users, setUsers] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editing, setEditing] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const groups = useMemo(() => {
    const grouped = {};
    permissions.forEach((p) => {
      const g = p.group || "Other";
      (grouped[g] ||= []).push(p);
    });
    return Object.entries(grouped);
  }, [permissions]);

  const errorText = async (response) => {
    let data = {};
    try { data = await response.json(); } catch { /* response body may be empty */ }
    if (Array.isArray(data?.detail)) return data.detail.map(x => x?.msg || x?.message || String(x)).join("; ");
    return data?.message || data?.detail || `Request failed (${response.status})`;
  };

  const load = useCallback(async () => {
    if (!canView) return;

    const [u, p] = await Promise.all([
      apiFetch(`${API}/auth/users`),
      apiFetch(`${API}/auth/permissions`)
    ]);
    if (!u.ok) throw new Error(await errorText(u));
    if (!p.ok) throw new Error(await errorText(p));
    return {
      users: listFrom(await u.json(), "users"),
      permissions: listFrom(await p.json(), "permissions"),
    };
  }, [canView]);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      if (!canView) {
        if (active) setLoading(false);
        return;
      }

      if (active) {
        setLoading(true);
        setError("");
      }

      try {
        const data = await load();
        if (!active || !data) return;
        setUsers(data.users);
        setPermissions(data.permissions);
      } catch (e) {
        if (active) setError(e.message || "Unable to load users.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void refresh();
    return () => { active = false; };
  }, [canView, load]);

  const reset = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
  };

  const editUser = (user) => {
    setEditing(user);
    setForm({
      username: user.username || "",
      password: "",
      role: user.role || "report_user",
      active: user.active !== false,
      permissions: Array.isArray(user.permissions) ? user.permissions : []
    });
    setMessage(""); setError("");
  };

  const toggle = (key) => setForm(f => ({
    ...f,
    permissions: f.permissions.includes(key)
      ? f.permissions.filter(x => x !== key)
      : [...f.permissions, key]
  }));

  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setMessage(""); setError("");
    try {
      const payload = {
        username: form.username.trim(),
        role: form.role,
        active: form.active,
        permissions: form.permissions
      };
      if (form.password.trim()) payload.password = form.password;

      const response = await apiFetch(
        editing ? `${API}/auth/users/${encodeURIComponent(editing.id)}` : `${API}/auth/users`,
        {
          method: editing ? "PUT" : "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload)
        }
      );
      if (!response.ok) throw new Error(await errorText(response));
      setMessage(editing ? "User updated successfully." : "User created successfully.");
      reset();
      await load();
    } catch (e) {
      setError(e.message || "Unable to save user.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (user) => {
    if (!canDelete || user.id === currentUser?.id) return;
    if (!window.confirm(`Delete user "${user.username}"?`)) return;
    setMessage(""); setError("");
    try {
      const response = await apiFetch(`${API}/auth/users/${encodeURIComponent(user.id)}`, {
        method: "DELETE", headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error(await errorText(response));
      setMessage("User deleted successfully.");
      await load();
    } catch (e) {
      setError(e.message || "Unable to delete user.");
    }
  };

  if (!canView) {
    return <section className="card"><h2>Manage Users</h2><p>You do not have permission to view users.</p></section>;
  }

  return (
    <div className="manage-users-page">
      <style>{`
        .mu-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:18px}
        .mu-head h2{margin:0 0 5px}.mu-head p{margin:0;color:#64748b}
        .mu-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin-bottom:16px}
        .mu-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
        .mu-field{display:flex;flex-direction:column;gap:5px}.mu-field label{font-size:11px;font-weight:700;color:#475569}
        .mu-field input,.mu-field select{height:36px;border:1px solid #d8dee8;border-radius:7px;padding:0 10px}
        .mu-full{grid-column:1/-1}.mu-perms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
        .mu-group{border:1px solid #e7ebf0;border-radius:9px;padding:12px}.mu-group h4{margin:0 0 8px;font-size:12px}
        .mu-check{display:flex;gap:8px;margin:7px 0;font-size:12px;color:#475569}.mu-check small{color:#64748b}
        .mu-btn{border:0;border-radius:7px;padding:9px 13px;cursor:pointer;font-weight:700;font-size:12px}
        .mu-primary{background:#2563eb;color:#fff}.mu-secondary{background:#eef2f7;color:#334155}.mu-danger{background:#fee2e2;color:#b91c1c}
        .mu-table{width:100%;border-collapse:collapse}.mu-table th,.mu-table td{padding:11px;border-bottom:1px solid #edf0f4;text-align:left;font-size:13px}
        .mu-table th{font-size:11px;color:#64748b;text-transform:uppercase}.mu-badge{padding:4px 8px;border-radius:999px;background:#eef2ff;color:#3730a3;font-size:11px;font-weight:700}
        .mu-active{color:#15803d;font-weight:700}.mu-inactive{color:#b91c1c;font-weight:700}
        .mu-msg{padding:10px 12px;border-radius:8px;margin-bottom:12px;background:#eff6ff;color:#1d4ed8;font-size:12px}.mu-error{background:#fef2f2;color:#b91c1c}
        .mu-actions{display:flex;gap:7px}.mu-empty{padding:28px;text-align:center;color:#64748b}
        @media(max-width:760px){.mu-form,.mu-perms{grid-template-columns:1fr}.mu-head{flex-direction:column}.mu-table{min-width:700px}}
      `}</style>

      <div className="mu-head">
        <div><h2>Manage Users</h2><p>Create users and assign custom permissions.</p></div>
        {canCreate && <button className="mu-btn mu-primary" onClick={reset}>+ Create User</button>}
      </div>

      {message && <div className="mu-msg">{message}</div>}
      {error && <div className="mu-msg mu-error">{error}</div>}

      {(canCreate || canEdit) && (
        <section className="mu-card">
          <h3>{editing ? "Edit User" : "Create User"}</h3>
          <form onSubmit={save}>
            <div className="mu-form">
              <div className="mu-field"><label>Username</label><input required disabled={!!editing} value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></div>
              <div className="mu-field"><label>{editing ? "New Password (optional)" : "Password"}</label><input type="password" required={!editing} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></div>
              <div className="mu-field"><label>Role</label><select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option value="report_user">Report User</option><option value="admin">Administrator</option></select></div>
              <div className="mu-field"><label>Status</label><select value={form.active?"active":"inactive"} onChange={e=>setForm({...form,active:e.target.value==="active"})}><option value="active">Active</option><option value="inactive">Inactive</option></select></div>
              <div className="mu-field mu-full">
                <label>Custom Permissions</label>
                <div className="mu-perms">
                  {groups.map(([group, items]) => <div className="mu-group" key={group}><h4>{group}</h4>
                    {items.map(p => <label className="mu-check" key={p.key}><input type="checkbox" disabled={form.role==="admin"} checked={form.permissions.includes(p.key)} onChange={()=>toggle(p.key)}/><span><strong>{p.label}</strong><br/><small>{p.description}</small></span></label>)}
                  </div>)}
                </div>
              </div>
            </div>
            <div className="mu-actions" style={{marginTop:14}}>
              <button className="mu-btn mu-primary" disabled={busy}>{busy ? "Saving..." : editing ? "Save Changes" : "Create User"}</button>
              {editing && <button type="button" className="mu-btn mu-secondary" onClick={reset}>Cancel</button>}
            </div>
          </form>
        </section>
      )}

      <section className="mu-card">
        <h3>Users</h3>
        {loading ? <div className="mu-empty">Loading users...</div> : (
          <div style={{overflowX:"auto"}}>
            <table className="mu-table"><thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Permissions</th><th>Actions</th></tr></thead>
              <tbody>{users.map(u=><tr key={u.id||u.username}>
                <td><strong>{u.username}</strong></td>
                <td><span className="mu-badge">{String(u.role||"report_user").replaceAll("_"," ")}</span></td>
                <td><span className={u.active===false?"mu-inactive":"mu-active"}>{u.active===false?"Inactive":"Active"}</span></td>
                <td>{u.role==="admin"?"All permissions":`${Array.isArray(u.permissions)?u.permissions.length:0} assigned`}</td>
                <td><div className="mu-actions">{canEdit&&<button className="mu-btn mu-secondary" onClick={()=>editUser(u)}>Edit</button>}{canDelete&&u.id!==currentUser?.id&&<button className="mu-btn mu-danger" onClick={()=>remove(u)}>Delete</button>}</div></td>
              </tr>)}</tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
