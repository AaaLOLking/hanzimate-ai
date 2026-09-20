export type ReviewRating = "again" | "hard" | "good" | "easy";

export interface ReviewPreferences {
  timezone: string;
  study_days: number[];
  reminder_time: string;
  reminder_enabled: boolean;
  schedule_mode: "adaptive" | "fixed";
  fixed_interval_days: number;
  desired_retention: number;
}

export interface ReviewAttempt {
  id: string;
  card_id: string;
  response: string;
  prompt: string;
  reference_answer: string;
  explanation: string;
  feedback: string;
  rule_matched: boolean | null;
  created_at: string;
}

export interface ReviewCard {
  id: string;
  error_cluster_id: string;
  title: string;
  prompt: string;
  revision: number;
  due_at: string;
  pending_attempt: ReviewAttempt | null;
}

export interface ReviewReceipt {
  id: string;
  card_id: string;
  attempt_id: string;
  rating: ReviewRating;
  due_at: string;
  algorithm_due_at: string;
  reviewed_at: string;
}

export interface ReviewDashboard {
  preferences: ReviewPreferences;
  due_count: number;
  active_count: number;
  reviewed_today: number;
  cards: ReviewCard[];
  upcoming: ReviewCard[];
  history: ReviewReceipt[];
  reminder: { id: string; due_count: number; scheduled_at: string } | null;
}

export const ratingLabels: Record<ReviewRating, string> = {
  again: "忘记了", hard: "有点难", good: "记得", easy: "很轻松",
};

export function reviewDate(value: string, timezone: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    timeZone: timezone, month: "long", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}
