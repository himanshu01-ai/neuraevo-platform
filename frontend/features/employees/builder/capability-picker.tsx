"use client";

import {
  CAPABILITY_AVAILABILITY_CATALOG,
  EMPLOYEE_CAPABILITIES,
  type EmployeeCapability,
} from "@/services/employees";
import { OptionCard } from "@/components/ui/option-card";
import { AVAILABILITY_LABEL, CAPABILITY_META } from "../models/employee-capabilities";

export interface CapabilityPickerProps {
  selected: readonly EmployeeCapability[];
  onToggle: (capability: EmployeeCapability) => void;
}

/**
 * What this employee is allowed to reach for.
 *
 * Every capability is offered, including the ones still in preview — granting
 * one describes intent, and nothing here runs, so there's nothing to gate. The
 * availability note says what the platform can actually do with the grant today.
 *
 * Backed by native checkboxes through <OptionCard>, so the group is keyboard
 * operable and announces its own state without any of it being re-implemented.
 */
export function CapabilityPicker({ selected, onToggle }: CapabilityPickerProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {EMPLOYEE_CAPABILITIES.map((capability) => {
        const meta = CAPABILITY_META[capability];
        const availability = CAPABILITY_AVAILABILITY_CATALOG[capability];
        const note = availability === "GENERAL" ? "" : ` · ${AVAILABILITY_LABEL[availability]}`;

        return (
          <OptionCard
            key={capability}
            title={meta.label}
            description={`${meta.description}${note}`}
            icon={meta.icon}
            inputProps={{
              type: "checkbox",
              value: capability,
              checked: selected.includes(capability),
              onChange: () => onToggle(capability),
            }}
          />
        );
      })}
    </div>
  );
}
