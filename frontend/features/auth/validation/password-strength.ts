export interface PasswordStrength {
  /** 0 (empty) – 4 (strong). */
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
}

const LABELS = ["Too short", "Weak", "Fair", "Good", "Strong"] as const;

/** Lightweight, deterministic password-strength heuristic (UI feedback only). */
export function getPasswordStrength(password: string): PasswordStrength {
  if (!password) return { score: 0, label: LABELS[0] };

  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password)) score++;

  const clamped = Math.min(4, score) as PasswordStrength["score"];
  return { score: clamped, label: LABELS[clamped] };
}
