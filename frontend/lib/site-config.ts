import {
  Globe,
  SquareTerminal,
  Folder,
  Mail,
  Calendar,
  Github,
  ClipboardList,
  Waypoints,
  Cpu,
  ShieldCheck,
  Brain,
  Sparkles,
  Lock,
  Layers,
  GitBranch,
  ScrollText,
  type LucideIcon,
} from "lucide-react";

/**
 * Static presentational configuration for the landing experience.
 * This is marketing copy + navigation structure — not a data layer, not
 * business logic, and never fetched. Feature sprints must not put runtime data
 * here.
 */

export type NavItem = { label: string; href: string };
export type IconItem = { title: string; description: string; icon: LucideIcon };
export type WorkflowStep = { step: string; title: string; description: string; icon: LucideIcon };

export const siteConfig = {
  name: "NeuraEvo",
  tagline: "The AI Employee platform",
  description:
    "NeuraEvo is a voice-first AI employee that plans, executes across real tools, and asks for approval — so you can delegate complete work, not just chat.",
  nav: [
    { label: "Capabilities", href: "#capabilities" },
    { label: "How it works", href: "#workflow" },
    { label: "Enterprise", href: "#enterprise" },
  ] satisfies NavItem[],
  primaryCta: { label: "Get started", href: "#get-started" } satisfies NavItem,
  secondaryCta: { label: "See how it works", href: "#workflow" } satisfies NavItem,

  capabilities: [
    { title: "Browser", description: "Navigates, extracts, and acts on the live web — tabs, forms, downloads, screenshots.", icon: Globe },
    { title: "Python", description: "Runs analysis in a secure sandbox — pandas, NumPy, charts, and typed artifacts.", icon: SquareTerminal },
    { title: "Files", description: "Reads, writes, and organizes documents inside an isolated workspace.", icon: Folder },
    { title: "Email", description: "Drafts and threads messages, then waits for your approval before sending.", icon: Mail },
    { title: "Calendar", description: "Reads availability and schedules meetings with approval gates.", icon: Calendar },
    { title: "GitHub", description: "Reviews repos, opens pull requests, and comments — safely, with sign-off.", icon: Github },
  ] satisfies IconItem[],

  workflow: [
    { step: "01", title: "Task", description: "Delegate complete work in plain language.", icon: ClipboardList },
    { step: "02", title: "Planning", description: "The AI decomposes it into a dependency-aware plan.", icon: Waypoints },
    { step: "03", title: "Execution", description: "Capabilities run the plan across real tools.", icon: Cpu },
    { step: "04", title: "Approvals", description: "Irreversible actions pause for your sign-off.", icon: ShieldCheck },
    { step: "05", title: "Memory", description: "What it learns is stored through approved architecture.", icon: Brain },
    { step: "06", title: "Results", description: "You get artifacts and outcomes, not a transcript.", icon: Sparkles },
  ] satisfies WorkflowStep[],

  enterprise: [
    { title: "Deterministic execution", description: "Stateless services and frozen contracts make behavior reproducible.", icon: Cpu },
    { title: "Human approval gates", description: "Every irreversible action requires explicit sign-off.", icon: ShieldCheck },
    { title: "Isolated capabilities", description: "Each tool is sandboxed behind a single execution contract.", icon: Layers },
    { title: "Provider independence", description: "Swap AI providers without touching the platform.", icon: GitBranch },
    { title: "Complete audit trail", description: "Plans, runs, and approvals are fully traceable.", icon: ScrollText },
    { title: "Privacy-first memory", description: "The AI remembers only through the approved memory engine.", icon: Lock },
  ] satisfies IconItem[],

  footer: {
    product: [
      { label: "Capabilities", href: "#capabilities" },
      { label: "How it works", href: "#workflow" },
      { label: "Enterprise", href: "#enterprise" },
    ],
    company: [
      { label: "About", href: "#" },
      { label: "Careers", href: "#" },
      { label: "Contact", href: "#" },
    ],
    legal: [
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
      { label: "Security", href: "#" },
    ],
  },
} as const;

export type SiteConfig = typeof siteConfig;
