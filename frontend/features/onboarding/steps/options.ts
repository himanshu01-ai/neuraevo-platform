import {
  Globe,
  SquareTerminal,
  Folder,
  Mail,
  Calendar,
  Github,
  MessageSquare,
  Sparkles,
  Zap,
  ShieldQuestion,
  Scale,
  Rocket,
  type LucideIcon,
} from "lucide-react";

export interface Choice {
  value: string;
  title: string;
  description?: string;
  icon?: LucideIcon;
}

export const ROLES = [
  "Founder / CEO",
  "Engineering",
  "Product",
  "Operations",
  "Sales / Marketing",
  "Other",
] as const;

export const COMPANY_SIZES = ["Just me", "2–10", "11–50", "51–200", "200+"] as const;

export const INDUSTRIES = [
  "Software / SaaS",
  "Finance",
  "Healthcare",
  "E-commerce",
  "Education",
  "Other",
] as const;

export const TONES: Choice[] = [
  { value: "professional", title: "Professional", description: "Precise, formal, to the point.", icon: Sparkles },
  { value: "friendly", title: "Friendly", description: "Warm and conversational.", icon: MessageSquare },
  { value: "concise", title: "Concise", description: "Minimal words, maximum signal.", icon: Zap },
];

export const AUTONOMY: Choice[] = [
  { value: "ask", title: "Ask first", description: "Check with me before acting.", icon: ShieldQuestion },
  { value: "balanced", title: "Balanced", description: "Act, but pause on anything risky.", icon: Scale },
  { value: "autonomous", title: "Autonomous", description: "Run end-to-end; approvals only when required.", icon: Rocket },
];

export const CAPABILITIES: Choice[] = [
  { value: "browser", title: "Browser", description: "Navigate and act on the web.", icon: Globe },
  { value: "python", title: "Python", description: "Analyze data in a sandbox.", icon: SquareTerminal },
  { value: "files", title: "Files", description: "Read and write documents.", icon: Folder },
  { value: "email", title: "Email", description: "Draft and send with approval.", icon: Mail },
  { value: "calendar", title: "Calendar", description: "Schedule and manage events.", icon: Calendar },
  { value: "github", title: "GitHub", description: "Review repos and open PRs.", icon: Github },
];

export const DENSITIES: Choice[] = [
  { value: "comfortable", title: "Comfortable", description: "Roomy spacing, easy scanning." },
  { value: "compact", title: "Compact", description: "Dense layout, more on screen." },
];

export const NOTIFICATIONS: Choice[] = [
  { value: "approvals", title: "Approval requests", description: "When the AI needs your sign-off." },
  { value: "completions", title: "Task completions", description: "When delegated work finishes." },
  { value: "summary", title: "Weekly summary", description: "A digest of what got done." },
];

export const THEMES: Choice[] = [
  { value: "system", title: "System" },
  { value: "light", title: "Light" },
  { value: "dark", title: "Dark" },
];
