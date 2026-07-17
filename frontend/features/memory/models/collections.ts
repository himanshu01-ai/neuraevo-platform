import {
  Briefcase,
  Code,
  Folder,
  FolderOpen,
  Headset,
  Megaphone,
  Search,
  User,
  type LucideIcon,
} from "lucide-react";
import { COLLECTIONS, COLLECTION_LABEL, type Collection } from "@/services/memory";

/**
 * What each collection is and how it looks. The labels come from
 * `COLLECTION_LABEL` in `services/memory` rather than being restated — that
 * table is the source, and a shelf named two different things is a shelf nobody
 * trusts.
 */

export interface CollectionMeta {
  collection: Collection;
  label: string;
  icon: LucideIcon;
}

export const COLLECTION_META: Record<Collection, CollectionMeta> = {
  general: { collection: "general", label: COLLECTION_LABEL.general, icon: Folder },
  projects: { collection: "projects", label: COLLECTION_LABEL.projects, icon: Briefcase },
  research: { collection: "research", label: COLLECTION_LABEL.research, icon: Search },
  engineering: { collection: "engineering", label: COLLECTION_LABEL.engineering, icon: Code },
  marketing: { collection: "marketing", label: COLLECTION_LABEL.marketing, icon: Megaphone },
  support: { collection: "support", label: COLLECTION_LABEL.support, icon: Headset },
  personal: { collection: "personal", label: COLLECTION_LABEL.personal, icon: User },
  custom: { collection: "custom", label: COLLECTION_LABEL.custom, icon: FolderOpen },
};

/** Every collection in canonical order. */
export const COLLECTION_LIST: readonly CollectionMeta[] = COLLECTIONS.map(
  (collection) => COLLECTION_META[collection]
);

/**
 * The name a memory's shelf should read as. A `custom` collection shows the name
 * the user gave it; every other shows its own label. The one place this choice
 * is made, so a card and a tree can't disagree.
 */
export function collectionLabel(collection: Collection, customCollection: string): string {
  if (collection === "custom") return customCollection.trim() || COLLECTION_LABEL.custom;
  return COLLECTION_LABEL[collection];
}
