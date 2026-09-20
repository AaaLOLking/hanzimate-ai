import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "学习档案与数据 · HanziMate",
  description: "查看中文学习档案、AI 使用记录，并管理个人数据。",
};

export default function ProfileLayout({ children }: Readonly<{ children: ReactNode }>) {
  return children;
}
