import { PortalClient } from "./portal-client";

export default async function PortalPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <PortalClient slug={slug} />;
}
