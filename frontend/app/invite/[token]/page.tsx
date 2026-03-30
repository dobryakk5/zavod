import InvitePageClient from './page-client';

type InviteRouteProps = {
  params: Promise<{ token: string }>;
};

export default async function InviteRoute({ params }: InviteRouteProps) {
  const { token } = await params;
  return <InvitePageClient token={token} />;
}
