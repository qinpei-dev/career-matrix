import { AppShell } from "@/components/app-shell";
import { PageHeading } from "@/components/ui";
import { ProfileOnboarding } from "./profile-onboarding";

export const dynamic = "force-dynamic";

export default async function ProfilePage({
  searchParams,
}: {
  searchParams: Promise<{ document_id?: string | string[] }>;
}) {
  const query = await searchParams;
  const documentId = typeof query.document_id === "string" ? query.document_id : undefined;

  return <AppShell><div className="animate-rise pb-20 lg:pb-0">
    <PageHeading
      eyebrow="Profile onboarding"
      title="候选人资料"
      description="从已解析的简历生成资料草稿，确认并编辑后再保存。"
    />
    <ProfileOnboarding documentId={documentId} />
  </div></AppShell>;
}
