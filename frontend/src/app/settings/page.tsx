"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AppSetting } from "@/lib/types";
import { PageHeader, Card, Badge, Button, Input } from "@/components/ui";

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

  if (loading) return <p className="ui-note">Loading settings…</p>;

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        subtitle="API keys and integrations — managed here, never in code or on the server."
      />

      <div className="ui-note" style={{ marginBottom: 18 }}>
        Keys are stored encrypted and never shown again in full. The search provider is pluggable — pick
        one and paste its key; you can switch anytime without touching the code.
      </div>

      {error && <div className="ui-error">{error}</div>}

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {settings.map((s) => (
          <Card key={s.key}>
            <div className="ui-card-pad" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span
                  style={{
                    fontFamily: "var(--font-display), sans-serif",
                    fontWeight: 700,
                    fontSize: 14.5,
                    color: "var(--text)",
                  }}
                >
                  {s.label}
                </span>
                <Badge tone={s.is_set ? "ok" : "muted"}>
                  {s.is_set ? (s.secret ? `set · ${s.masked}` : s.value) : "not set"}
                </Badge>
              </div>
              <p className="ui-note" style={{ margin: 0 }}>
                {s.description}
              </p>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {s.choices ? (
                  <select
                    className="ui-input"
                    style={{ maxWidth: 320 }}
                    value={drafts[s.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
                  >
                    {s.choices.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    style={{ maxWidth: 320 }}
                    type={s.secret ? "password" : "text"}
                    value={drafts[s.key] ?? ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [s.key]: e.target.value }))}
                    placeholder={s.secret ? "Enter a new key to replace" : "Enter a value"}
                    autoComplete="off"
                  />
                )}
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => save(s.key, drafts[s.key] ?? "")}
                  disabled={busy[s.key]}
                >
                  {busy[s.key] ? "Saving…" : "Save"}
                </Button>
                {s.secret && s.is_set && (
                  <Button size="sm" variant="subtle" onClick={() => save(s.key, "")} disabled={busy[s.key]}>
                    Clear
                  </Button>
                )}
                {note[s.key] && (
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ok)" }}>{note[s.key]}</span>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
