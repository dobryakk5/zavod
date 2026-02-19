'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { kbSearchApi } from '@/lib/api/knowledgeBase';

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  model?: string;
  sources?: Array<{ document_id: number; title: string; chunk_index: number }>;
};

export function RagChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const history = useMemo(
    () => messages.map((item) => ({ role: item.role, content: item.content })),
    [messages],
  );

  useEffect(() => {
    if (!isOpen) return;
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, isLoading, isOpen]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    setError(null);
    setIsLoading(true);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setInput('');

    try {
      const response = await kbSearchApi.chat({
        message: text,
        history,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.reply,
          model: response.model,
          sources: response.sources.map((src) => ({
            document_id: src.document_id,
            title: src.title,
            chunk_index: src.chunk_index,
          })),
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Не удалось получить ответ';
      setError(message);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Не удалось получить ответ. Попробуйте еще раз.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-[80]">
      {isOpen && (
        <div className="mb-2 flex h-[460px] w-[340px] flex-col overflow-hidden rounded-xl border bg-white shadow-xl">
          <div className="border-b px-4 py-3">
            <div className="text-sm font-semibold">Ассистент по базе знаний</div>
            <div className="text-xs text-gray-500">RAG + default AI model</div>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {messages.length === 0 && (
              <div className="rounded-lg border border-dashed p-3 text-xs text-gray-500">
                Задайте вопрос по документам вашей базы знаний.
              </div>
            )}
            {messages.map((message, index) => (
              <div key={`${message.role}-${index}`} className={message.role === 'user' ? 'text-right' : 'text-left'}>
                <div
                  className={
                    message.role === 'user'
                      ? 'inline-block max-w-[90%] rounded-lg bg-blue-600 px-3 py-2 text-sm text-white'
                      : 'inline-block max-w-[90%] rounded-lg bg-gray-100 px-3 py-2 text-sm text-gray-900'
                  }
                >
                  {message.content}
                </div>
                {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                  <div className="mt-1 text-[11px] text-gray-500">
                    Источники: {message.sources.slice(0, 2).map((src) => src.title || `#${src.document_id}`).join(', ')}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="border-t p-3">
            {error && <div className="mb-2 text-xs text-red-600">{error}</div>}
            <div className="flex items-center gap-2">
              <input
                className="h-9 flex-1 rounded border px-2 text-sm outline-none focus:border-blue-500"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void sendMessage();
                  }
                }}
                placeholder="Ваш вопрос..."
                disabled={isLoading}
              />
              <button
                className="h-9 min-w-12 rounded bg-blue-600 px-3 text-sm font-medium text-white disabled:opacity-60"
                onClick={() => void sendMessage()}
                disabled={isLoading || !input.trim()}
                type="button"
              >
                {isLoading ? '...' : 'OK'}
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        className="h-12 w-12 rounded-full bg-blue-600 text-sm font-semibold text-white shadow-lg"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        AI
      </button>
    </div>
  );
}
