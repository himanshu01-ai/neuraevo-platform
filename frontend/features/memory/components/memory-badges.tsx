import {
  MEMORY_STATUS_LABEL,
  MEMORY_STATUS_TONE,
  MEMORY_TYPE_LABEL,
  MEMORY_TYPE_TONE,
  type MemoryStatus,
  type MemoryType,
} from "@/services/memory";
import { Badge } from "@/components/ui/badge";
import { TONE_DOT, TONE_VARIANT } from "@/components/ui/status-badge";
import { cn } from "@/lib/utils";

/**
 * The two toned facets a memory carries.
 *
 * Both compose <Badge> with the tone tables `StatusBadge` exports rather than
 * extending `StatusBadge` itself: that primitive resolves the vocabularies in
 * `types/domain.ts`, and neither of these is one — `MemoryType` mirrors
 * `app/utils/constants.MemoryType`, and status is a projection (see
 * `services/memory/types.ts`). Same primitive, same tones, same pixels.
 *
 * Each says its facet in words as well as colour, so neither is carried by
 * colour alone.
 */

export interface MemoryTypeBadgeProps {
  memoryType: MemoryType;
  className?: string;
}

/**
 * Retention — permanent, working, or learned. This is the backend's
 * `memory_type`, which is about how long a memory lives, not what kind of thing
 * it is; the workspace labels it "Retention" for exactly that reason.
 */
export function MemoryTypeBadge({ memoryType, className }: MemoryTypeBadgeProps) {
  const tone = MEMORY_TYPE_TONE[memoryType];

  return (
    <Badge variant={TONE_VARIANT[tone]} className={className}>
      <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
      {MEMORY_TYPE_LABEL[memoryType]}
    </Badge>
  );
}

export interface MemoryStatusBadgeProps {
  status: MemoryStatus;
  className?: string;
}

export function MemoryStatusBadge({ status, className }: MemoryStatusBadgeProps) {
  const tone = MEMORY_STATUS_TONE[status];

  return (
    <Badge variant={TONE_VARIANT[tone]} className={className}>
      <span aria-hidden="true" className={cn("size-1.5 shrink-0 rounded-full", TONE_DOT[tone])} />
      {MEMORY_STATUS_LABEL[status]}
    </Badge>
  );
}
