import Link from 'next/link';
import { notFound } from 'next/navigation';
import ChainEditor from '@/components/chain-editor';

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
    <div className="container mx-auto py-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Редактор цепочки</h1>
          <p className="text-sm text-muted-foreground mt-1">ID: {chainId}</p>
        </div>
        <Link href="/clients" className="text-sm text-blue-600 hover:underline">
          Назад к списку цепочек
        </Link>
      </div>

      <div className="bg-white rounded-lg p-4 h-[75vh]">
        <ChainEditor className="h-full" chainId={chainId} />
      </div>
    </div>
  );
}
