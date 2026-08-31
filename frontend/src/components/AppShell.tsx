"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Brand } from "@/lib/types";

type Theme = "light" | "dark";
type AccentKey = "fieldpie" | "evatro";

function accentOf(b?: Brand | null): AccentKey {
  return b && (b.slug || "").toLowerCase().includes("evatro") ? "evatro" : "fieldpie";
}

function IconGrid() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  );
}
function IconBrand() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </svg>
  );
}
function IconPipeline() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 6h16M4 12h16M4 18h10" />
      <circle cx="19" cy="18" r="2.4" fill="currentColor" stroke="none" />
    </svg>
  );
}
function IconSettings() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
    </svg>
  );
}
function IconMoon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
    </svg>
  );
}
function IconSun() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M19.4 4.6l-1.8 1.8M6.4 17.6l-1.8 1.8" />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    api.listBrands().then(setBrands).catch(() => {});
  }, []);

  // Read the theme the no-flash init script applied to <html>.
  useEffect(() => {
    const root = document.documentElement;
    const explicit = root.getAttribute("data-theme") as Theme | null;
    const isDark = explicit
      ? explicit === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    setTheme(isDark ? "dark" : "light");
    setMounted(true);
  }, []);

  const brandMatch = pathname.match(/^\/brands\/([^/]+)(.*)$/);
  const currentBrandId = brandMatch ? brandMatch[1] : null;
  const suffix = brandMatch ? brandMatch[2] : "";
  const currentBrand = brands.find((b) => b.id === currentBrandId) || null;

  // Accent follows the brand you are viewing; otherwise the last-used one.
  useEffect(() => {
    const root = document.documentElement;
    let key: AccentKey;
    if (currentBrand) {
      key = accentOf(currentBrand);
    } else {
      let stored: string | null = null;
      try {
        stored = localStorage.getItem("sf-brand");
      } catch {}
      key = stored === "evatro" ? "evatro" : "fieldpie";
    }
    root.setAttribute("data-brand", key);
    try {
      localStorage.setItem("sf-brand", key);
    } catch {}
  }, [currentBrand]);

  function switchBrand(b: Brand) {
    if (b.id === currentBrandId) return;
    router.push(brandMatch ? `/brands/${b.id}${suffix}` : `/brands/${b.id}`);
  }

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("sf-theme", next);
    } catch {}
  }

  const onDash = pathname === "/";
  const onOverview = !!brandMatch && suffix === "";
  const onPipeline = !!brandMatch && suffix.startsWith("/pipeline");
  const onSettings = pathname.startsWith("/settings");
  const section = onSettings ? "Settings" : onPipeline ? "Pipeline" : brandMatch ? "Brand" : "Dashboard";

  const switcherBrands = brands.slice(0, 4);

  return (
    <div className="sfx-app">
      <aside className="sfx-side">
        <div className="sfx-brandpick">
          <Link href="/" className="sfx-logo" aria-label="Dashboard">
            S
          </Link>
          <div className="sfx-wordmark">
            SocialForge
            <small>Content Studio</small>
          </div>
        </div>

        {switcherBrands.length > 0 && (
          <div className="sfx-brandtabs" role="group" aria-label="Switch brand">
            {switcherBrands.map((b) => (
              <button
                key={b.id}
                className={`sfx-brandtab ${accentOf(b) === "evatro" ? "ev" : "fp"}`}
                aria-pressed={b.id === currentBrandId}
                onClick={() => switchBrand(b)}
                title={`Switch to ${b.display_name}`}
              >
                <span className="sfx-dot" />
                {b.display_name}
              </button>
            ))}
          </div>
        )}

        <div className="sfx-navsec">Workspace</div>
        <nav className="sfx-nav">
          <Link href="/" className={`sfx-navitem${onDash ? " active" : ""}`}>
            <IconGrid />
            Dashboard
          </Link>
          {brandMatch && (
            <>
              <Link
                href={`/brands/${currentBrandId}`}
                className={`sfx-navitem${onOverview ? " active" : ""}`}
              >
                <IconBrand />
                {currentBrand ? currentBrand.display_name : "Brand"}
              </Link>
              <Link
                href={`/brands/${currentBrandId}/pipeline`}
                className={`sfx-navitem${onPipeline ? " active" : ""}`}
              >
                <IconPipeline />
                Content Pipeline
              </Link>
            </>
          )}
        </nav>

        <div className="sfx-navsec">Configure</div>
        <nav className="sfx-nav">
          <Link href="/settings" className={`sfx-navitem${onSettings ? " active" : ""}`}>
            <IconSettings />
            Settings
          </Link>
        </nav>

        <div className="sfx-foot">
          <div className="sfx-avatar">R</div>
          <div>
            <div className="nm">Resul</div>
            <small>Admin</small>
          </div>
        </div>
      </aside>

      <div className="sfx-main">
        <header className="sfx-topbar">
          <div className="sfx-crumb">
            <span>SocialForge</span>
            <span className="sep">/</span>
            <b>{section}</b>
            {currentBrand && (
              <>
                <span className="sep">/</span>
                <span>{currentBrand.display_name}</span>
              </>
            )}
          </div>
          {currentBrand && (
            <span className="sfx-brandchip">
              <span className="sfx-dot" />
              {currentBrand.display_name}
              {currentBrand.language ? ` · ${currentBrand.language.toUpperCase()}` : ""}
            </span>
          )}
          <div className="sfx-spacer" />
          <button
            className="sfx-tbtn"
            onClick={toggleTheme}
            aria-label="Toggle color theme"
            suppressHydrationWarning
          >
            {mounted && theme === "dark" ? <IconSun /> : <IconMoon />}
            <span suppressHydrationWarning>
              {mounted ? (theme === "dark" ? "Light" : "Dark") : "Theme"}
            </span>
          </button>
        </header>

        <main className="sfx-content">{children}</main>
      </div>
    </div>
  );
}
