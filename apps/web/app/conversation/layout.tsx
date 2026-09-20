import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = { title: "实时对话训练 · HanziMate" };

export default function ConversationLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
