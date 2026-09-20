import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "今日复习 · HanziMate" };

export default function ReviewsLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
