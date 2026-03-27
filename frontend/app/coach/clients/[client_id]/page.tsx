import { notFound } from 'next/navigation';
import CoachClientWorkspace from './workspace';

type CoachClientRouteProps = {
  params: Promise<{ client_id: string }>;
};

export default async function CoachClientRoute({ params }: CoachClientRouteProps) {
  const { client_id: rawClientId } = await params;
  const clientId = Number(rawClientId);

  if (!Number.isFinite(clientId) || clientId <= 0) {
    notFound();
  }

  return <CoachClientWorkspace clientId={clientId} />;
}
