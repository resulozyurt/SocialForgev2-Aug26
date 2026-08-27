"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AppSetting } from "@/lib/types";

const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [note, setNote] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.listAppSettings();
      setSettings(list);
      const d: Record<string, string> = {};
      for (const s of list) d[s.key] = s.secret ? "" : s.value ?? "";
      setDrafts(d);
    } catch (e) {
      setError(msg(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function save(key: string, value: string) {
    setBusy((b) => ({ ...b, [key]: true }));
    setNote((n) => ({ ...n, [key]: "" }));
    setError(null);
    try {
      const res = await api.updateAppSetting(key, value);
      setNote((n) => ({ ...n, [key]: res.is_set ? "Saved." : "Cleared." }));
      await load();
    } catch (e) {
      setError(msg(e));
    } finally {
      setBusy((b) => ({ ...b, [key]: false }));
    }
  }

  if (loading) return <p className="sf-note">Loading settings…</p>;

  return (
    <div>
      <div className="sf-page-head">
        <div>
          <p className="sf-eyebrow">Workspace</p>
          <h1 className="sf-title">Settings</h1>
          <p className="sf-subtitle">
            API keys and integrations — managed here, never in code or the server.
          </p>
        </div>
      </div>

      <div className="sf-info">
        Keys are stored encrypted and never shown again in full. The search
        provider is pluggable — pick one and paste its key; you can switch anytime
        without touching the code.
      </div>

      {error && <div className="sf-error">{error}</div>}

      <section className="sf-section">
        {settings.map((s) => (
          <div className="sf-setting" key={s.key}>
            <div className="sf-setting-head">
              <div>
                <span className="sf-setting-label">{s.label}</span>
                <span className={`sf-badge${s.is_set ? " is-active" : ""}`}>
                  {s.is_set ? (s.secret ? `set · ${s.masked}` : s.value) : "not set"}
                </span>
              </div>
            </div>
            <p className="sf-setting-desc">{s.description}</p>

            <div className="sf-inline-row">
              {s.choices ? (
                <select
                  className="sf-input"
                  value={drafts[s.key] ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
                >
                  {s.choices.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              ) : (
                <input
                  className="sf-input"
                  type={s.secret ? "password" : "text"}
                  value={drafts[s.key] ?? ""}
                  onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
                  placeholder={s.secret ? "Enter a new key to replace" : "Enter a value"}
                  autoComplete="off"
                />
              )}
              <button
                className="sf-btn sf-btn-accent"
                onClick={() => save(s.key, drafts[s.key] ?? "")}
                disabled={busy[s.key]}
              >
                {busy[s.key] ? "Saving…" : "Save"}
              </button>
              {s.secret && s.is_set && (
                <button
                  className="sf-btn"
                  onClick={() => save(s.key, "")}
                  disabled={busy[s.key]}
                >
                  Clear
                </button>
              )}
              {note[s.key] && <span className="sf-test is-ok">{note[s.key]}</span>}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
