// Single data source for the primary navigation rendered by <AppShell>.
// Every migrated page references these keys, so labels/icons/hrefs stay consistent.
export interface NavigationItem {
  key: string;
  label: string;
  icon: string;
  href: string | null;
}

export const navigationItems: NavigationItem[] = [
  { key: "home", label: "今日", icon: "⌂", href: "/" },
  { key: "conversation", label: "对话训练", icon: "◉", href: "/practice" },
  { key: "courses", label: "系统课程", icon: "▤", href: "/courses" },
  { key: "reviews", label: "今日复习", icon: "↻", href: "/reviews" },
  { key: "errors", label: "错误本", icon: "◇", href: "/errors" },
  { key: "profile", label: "学习档案", icon: "◈", href: "/profile" },
  { key: "beta", label: "体验反馈", icon: "✦", href: "/beta" },
];
