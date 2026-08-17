"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export interface WizardNavProps {
  onBack?: () => void;
  showBack?: boolean;
  nextLabel?: string;
  /** When true the primary button submits the surrounding form; else calls onNext. */
  isSubmit?: boolean;
  onNext?: () => void;
  loading?: boolean;
}

/** Shared Back / Continue footer for onboarding steps. */
export function WizardNav({
  onBack,
  showBack = true,
  nextLabel = "Continue",
  isSubmit = true,
  onNext,
  loading = false,
}: WizardNavProps) {
  return (
    <div className="flex items-center justify-between gap-3 pt-2">
      {showBack ? (
        <Button type="button" variant="ghost" onClick={onBack} disabled={loading}>
          <ArrowLeft className="size-4" aria-hidden="true" />
          Back
        </Button>
      ) : (
        <span />
      )}
      <Button
        type={isSubmit ? "submit" : "button"}
        onClick={isSubmit ? undefined : onNext}
        disabled={loading}
        className="min-w-36"
      >
        {loading ? <Spinner /> : null}
        {nextLabel}
        {!loading ? <ArrowRight className="size-4" aria-hidden="true" /> : null}
      </Button>
    </div>
  );
}
