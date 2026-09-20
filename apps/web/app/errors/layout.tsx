import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "错误本 · HanziMate" };

export default function ErrorsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
