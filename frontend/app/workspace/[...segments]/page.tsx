import { ComingSoon } from "@/features/workspace/components/coming-soon";

export default async function WorkspaceSectionPage({
  params,
}: {
  params: Promise<{ segments: string[] }>;
}) {
  const { segments } = await params;
  return <ComingSoon segments={segments} />;
}
