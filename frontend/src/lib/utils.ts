import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatScore(score: number): string {
  return score.toFixed(1)
}

export function getScoreColor(score: number): string {
  if (score >= 90) return "text-emerald-500"
  if (score >= 70) return "text-amber-500"
  return "text-destructive"
}
