"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { apiRequest, type OnboardingState } from "@/lib/api";
import { useI18n, type I18nKey } from "@/lib/i18n";
import { navigationItems } from "@/lib/navigation";

const navLabelKeys: Record<string, I18nKey> = {
  home: "nav.home",
  conversation: "nav.conversation",
  courses: "nav.courses",
  reviews: "nav.reviews",
  errors: "nav.errors",
  profile: "nav.profile",
  beta: "nav.beta",
};

interface AppShellProps {
  /** Active key from lib/navigation (single data source for labels/hrefs/icons). */
  active: string;
  children: ReactNode;
  /** Optional right-hand 344px context panel. */
  panel?: ReactNode;
  panelLabel?: string;
  /** Collapse the sidebar into a thin rail (live conversation focus mode). */
  rail?: boolean;
  /** Optional page-specific sidebar content rendered below the primary nav. */
  sidebar?: ReactNode;
}

export function AppShell({ active, children, panel, panelLabel, rail = false, sidebar }: AppShellProps) {
  const { locale, setLocale, t } = useI18n();
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerRef = useRef<HTMLElement | null>(null);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<OnboardingState>("/api/v1/onboarding")
      .then((state) => { if (!cancelled) setOnboarding(state); })
      .catch(() => { /* The profile chip falls back to neutral copy. */ });
    return () => { cancelled = true; };
  }, []);

  // Drawer: lock body scroll, close on Escape, and keep Tab cycling inside.
  useEffect(() => {
    if (!drawerOpen) return;
    document.body.style.overflow = "hidden";
    const focusables = () => {
      const root = drawerRef.current;
      if (!root) return [] as HTMLElement[];
      return [...root.querySelectorAll<HTMLElement>("a, button, input, select, textarea, [tabindex]:not([tabindex='-1'])")]
        .filter((el) => !el.hasAttribute("disabled") && el.getClientRects().length > 0);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setDrawerOpen(false);
        toggleRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      const activeEl = document.activeElement;
      if (event.shiftKey && (activeEl === first || !drawerRef.current?.contains(activeEl))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeEl === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    focusables()[0]?.focus();
    return () => {
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [drawerOpen]);

  const displayName = onboarding?.user.display_name ?? "Alex Morgan";
  const profileBand = onboarding?.profile?.estimated_hsk_band ?? t("shell.profileFallback");
  const shellClass = [
    "appShell",
    panel ? "appShell--panel" : "",
    rail ? "appShell--rail" : "",
    drawerOpen ? "appShell--drawerOpen" : "",
  ].filter(Boolean).join(" ");

  return (
    <main className={shellClass} id="main-content" tabIndex={-1}>
      <button
        aria-controls="app-sidebar"
        aria-expanded={drawerOpen}
        aria-label={drawerOpen ? t("shell.closeNav") : t("shell.openNav")}
        className="drawerToggle"
        onClick={() => setDrawerOpen((current) => !current)}
        ref={toggleRef}
        type="button"
      >
        <span aria-hidden="true">{drawerOpen ? "✕" : "☰"}</span>
      </button>
      {drawerOpen ? (
        <button
          aria-label={t("shell.closeNav")}
          className="drawerBackdrop"
          onClick={() => {
            setDrawerOpen(false);
            toggleRef.current?.focus();
          }}
          tabIndex={-1}
          type="button"
        />
      ) : null}

      <aside className="sidebar" id="app-sidebar" ref={drawerRef}>
        <div className="sidebarInner">
          <div className="brand">
            <span className="brandMark">汉</span>
            <div>
              <strong>HanziMate</strong>
              <span>{t("shell.brandTagline")}</span>
            </div>
          </div>

          <nav aria-label={t("shell.mainNavAria")} className="mainNav">
            {navigationItems.map((item) => item.href ? (
              <Link
                aria-current={item.key === active ? "page" : undefined}
                className={item.key === active ? "navItem active" : "navItem"}
                href={item.href}
                key={item.key}
                onClick={() => setDrawerOpen(false)}
              >
                <span aria-hidden="true" className="navIcon">{item.icon}</span>
                <span className="navLabel">{t(navLabelKeys[item.key] ?? "nav.home")}</span>
              </Link>
            ) : (
              <button
                aria-current={item.key === active ? "page" : undefined}
                className={item.key === active ? "navItem active" : "navItem"}
                disabled
                key={item.key}
                title="从今日仪表盘进入对话"
              >
                <span aria-hidden="true" className="navIcon">{item.icon}</span>
                <span className="navLabel">{item.label}</span>
              </button>
            ))}
          </nav>

          {sidebar ? <div className="sidebarSlot">{sidebar}</div> : null}

          <div className="langSwitch" role="group" aria-label={t("shell.langLabel")}>
            <button
              aria-pressed={locale === "zh"}
              className={locale === "zh" ? "active" : ""}
              lang="zh-CN"
              onClick={() => setLocale("zh")}
              type="button"
            >
              {t("shell.langZh")}
            </button>
            <button
              aria-pressed={locale === "en"}
              className={locale === "en" ? "active" : ""}
              lang="en"
              onClick={() => setLocale("en")}
              type="button"
            >
              {t("shell.langEn")}
            </button>
          </div>

          <div className="profileChip">
            <span className="avatar">{displayName.slice(0, 2).toUpperCase()}</span>
            <span>
              <strong>{displayName}</strong>
              <small>{profileBand}</small>
            </span>
            <Link aria-label={t("shell.openProfile")} href="/profile">•••</Link>
          </div>
        </div>
      </aside>

      <section className="workspace">{children}</section>

      {panel ? (
        <aside aria-label={panelLabel} className="contextPanel">{panel}</aside>
      ) : null}
    </main>
  );
}
