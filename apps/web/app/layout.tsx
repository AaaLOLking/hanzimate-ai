import type { Metadata } from "next";
import type { ReactNode } from "react";

import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: "HanziMate AI",
  description: "Your evidence-based Chinese learning workspace",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <a className="skipLink" href="#main-content">跳到主要内容</a>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
