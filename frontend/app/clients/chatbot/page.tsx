import ChatbotPageClient from '../chatbot-page-client';
import { ClientsSectionShell } from '../section-shell';

export default function ClientsChatbotPage() {
  return (
    <ClientsSectionShell
      section="chatbot"
      title="ChatBot"
      description="Цепочки ChatBot вынесены в отдельную страницу со списком переходов."
    >
      <ChatbotPageClient />
    </ClientsSectionShell>
  );
}
