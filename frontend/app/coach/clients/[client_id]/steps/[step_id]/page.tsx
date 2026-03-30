import { notFound } from 'next/navigation';
import CoachClientStepPage from './page-client';

type CoachClientStepRouteProps = {
  params: Promise<{ client_id: string; step_id: string }>;
};

export default async function CoachClientStepRoute({ params }: CoachClientStepRouteProps) {
  const { client_id: rawClientId, step_id: rawStepId } = await params;
  const clientId = Number(rawClientId);

  if (!Number.isFinite(clientId) || clientId <= 0 || !String(rawStepId || '').trim()) {
    notFound();
  }

  return <CoachClientStepPage clientId={clientId} stepId={rawStepId} />;
}
