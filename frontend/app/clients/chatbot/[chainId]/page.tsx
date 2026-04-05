import { notFound } from 'next/navigation';
import ChatbotChainPageClient from '../chatbot-chain-page-client';
import { ClientsSectionShell } from '../../section-shell';

type ChatbotChainPageProps = {
  params: Promise<{
    chainId: string;
  }>;
};

export default async function ChatbotChainPage({ params }: ChatbotChainPageProps) {
  const { chainId: rawChainId } = await params;
  const chainId = Number(rawChainId);
  if (!Number.isInteger(chainId) || chainId <= 0) {
    notFound();
  }

  return (
    <ClientsSectionShell
      section="chatbot"
      title="Редактор цепочки"
      description={`Цепочка #${chainId}. На мобильном показывается краткая сводка, canvas-редактор доступен с планшета и десктопа.`}
      backHref="/clients/chatbot"
      backLabel="К списку цепочек"
    >
      <ChatbotChainPageClient chainId={chainId} />
    </ClientsSectionShell>
  );
}
