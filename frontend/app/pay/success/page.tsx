import { redirect } from 'next/navigation';

type PaySuccessPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function PaySuccessPage({ searchParams }: PaySuccessPageProps) {
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const params = new URLSearchParams();
  params.set('tab', 'payment');

  if (resolvedSearchParams) {
    const paymentId =
      resolvedSearchParams.payment_id ||
      resolvedSearchParams.paymentId ||
      resolvedSearchParams.orderId;
    if (typeof paymentId === 'string' && paymentId) {
      params.set('payment_id', paymentId);
    }
  }

  redirect(`/settings?${params.toString()}`);
}
