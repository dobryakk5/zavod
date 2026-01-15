import { redirect } from 'next/navigation';

type PaySuccessPageProps = {
  searchParams?: Record<string, string | string[] | undefined>;
};

export default function PaySuccessPage({ searchParams }: PaySuccessPageProps) {
  const params = new URLSearchParams();
  params.set('tab', 'payment');

  if (searchParams) {
    const paymentId = searchParams.payment_id || searchParams.paymentId || searchParams.orderId;
    if (typeof paymentId === 'string' && paymentId) {
      params.set('payment_id', paymentId);
    }
  }

  redirect(`/settings?${params.toString()}`);
}
