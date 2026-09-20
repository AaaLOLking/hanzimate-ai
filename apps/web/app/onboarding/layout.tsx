import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "学习设置 · HanziMate" };

export default function OnboardingLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
