import PublicCoachingStepPage from './page-client';

type PublicCoachingStepRouteProps = {
  params: Promise<{
    client_id: string;
    step_id: string;
  }>;
};

export default async function PublicCoachingStepRoute({ params }: PublicCoachingStepRouteProps) {
  const { client_id, step_id } = await params;
  return <PublicCoachingStepPage clientId={Number(client_id)} stepId={step_id} />;
}
