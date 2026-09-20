import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "封闭体验反馈 · HanziMate",
  description: "查看封闭体验进度，并提交中文学习反馈。",
};

export default function BetaLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
