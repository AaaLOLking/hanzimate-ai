import type { JSX, ReactNode } from "react";

interface PanelProps {
  children: ReactNode;
  className?: string;
  /** Frosted-glass surface (backdrop-filter); use sparingly over rich backgrounds. */
  glass?: boolean;
  /** Hover lift + shadow; motion is disabled under prefers-reduced-motion. */
  interactive?: boolean;
  /** Resting shadow for elevated bento tiles. */
  raised?: boolean;
}

/**
 * Shared bento card primitive. The matching `.panelCard` base lives in globals.css;
 * page-specific classes compose on top of it (they win via source order).
 */
export function Panel({
  children,
  className = "",
  glass = false,
  interactive = false,
  raised = false,
}: PanelProps): JSX.Element {
  const classes = [
    "panelCard",
    raised ? "panelCard--raised" : "",
    glass ? "panelCard--glass" : "",
    interactive ? "panelCard--interactive" : "",
    className,
  ].filter(Boolean).join(" ");
  return <section className={classes}>{children}</section>;
}
