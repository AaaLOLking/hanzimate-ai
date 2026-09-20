import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "课程学习 · HanziMate" };

export default function LessonsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
