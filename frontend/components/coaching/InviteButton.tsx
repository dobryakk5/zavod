'use client';

import { useState } from 'react';
import { coachingApiInvites, type CoachInviteLink } from '@/lib/api/coaching';

type InviteStatus = 'idle' | 'loading' | 'ready' | 'copied' | 'revoking' | 'error';

export default function InviteButton({
  clientId,
  clientName,
  clientEmail,
  compact = false,
}: {
  clientId: string | number;
  clientName: string;
  clientEmail?: string;
  compact?: boolean;
}) {
  const [status, setStatus] = useState<InviteStatus>('idle');
  const [link, setLink] = useState<CoachInviteLink | null>(null);
  const [open, setOpen] = useState(false);

  async function handleGenerate() {
    setStatus('loading');
    try {
      const invite = await coachingApiInvites.createInviteLink(clientId);
      setLink(invite);
      setOpen(true);
      setStatus('ready');
    } catch {
      setStatus('error');
      window.setTimeout(() => setStatus('idle'), 2500);
    }
  }

  async function handleRevoke() {
    setStatus('revoking');
    try {
      await coachingApiInvites.revokeInviteLink(clientId);
      setLink(null);
      setOpen(false);
      setStatus('idle');
    } catch {
      setStatus('error');
      window.setTimeout(() => setStatus('idle'), 2500);
    }
  }

  async function handleCopy() {
    if (!link) {
      return;
    }

    try {
      await navigator.clipboard.writeText(link.url);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = link.url;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
    }
    setStatus('copied');
    window.setTimeout(() => setStatus('ready'), 1800);
  }

  const triggerLabel = compact ? '✉ Пригласить' : 'Пригласить клиента по ссылке';
  const firstName = (clientName || '').trim().split(/\s+/)[0] || 'клиента';
  const mailtoHref = link
    ? `mailto:${clientEmail ?? ''}?subject=${encodeURIComponent('Приглашение в CoachSpace')}&body=${encodeURIComponent(
        `Здравствуйте, ${firstName}!\n\nВот ваша персональная ссылка для входа в кабинет:\n${link.url}\n\nЕсли ссылка перестанет работать, напишите мне и я пришлю новую.`
      )}`
    : '#';

  return (
    <div className={compact ? 'relative' : ''}>
      {!open || !link ? (
        <button
          type="button"
          onClick={() => void handleGenerate()}
          disabled={status === 'loading' || status === 'revoking'}
          className={
            compact
              ? 'rounded-[8px] border border-[#d8d4ca] px-3 py-1.5 text-[11px] text-[#73726c] transition-colors hover:border-[#5c52e0] hover:text-[#5c52e0] disabled:opacity-50'
              : 'flex w-full items-center gap-2 rounded-[8px] border-[0.5px] border-dashed border-[#e0ddd6] px-[12px] py-[10px] text-left text-[12px] text-[#73726c] transition-colors hover:border-[#b4b2a9] hover:text-[#1a1a18] disabled:opacity-50'
          }
        >
          {status === 'loading' ? 'Создаю...' : triggerLabel}
        </button>
      ) : null}

      {status === 'error' ? (
        <div className="mt-2 text-[11px] text-[#993C1D]">Не удалось создать ссылку. Попробуйте ещё раз.</div>
      ) : null}

      {open && link ? (
        <div
          className={
            compact
              ? 'absolute right-0 top-[calc(100%+8px)] z-20 w-[360px] rounded-[10px] border border-[#e0ddd6] bg-white p-4 shadow-[0_12px_32px_rgba(26,26,24,0.12)]'
              : 'mt-3 rounded-[10px] border border-[#e0ddd6] bg-white p-4'
          }
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <div className="text-[12px] font-medium text-[#1a1a18]">Персональная ссылка для {firstName}</div>
              <div className="text-[10px] text-[#73726c]">
                {link.usedAt
                  ? `Использована ${formatDate(link.usedAt)}`
                  : link.expiresAt
                    ? `Истекает ${formatDate(link.expiresAt)}`
                    : 'Ссылка ещё не использована'}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="text-[11px] text-[#73726c] hover:text-[#1a1a18]"
            >
              Закрыть
            </button>
          </div>

          <div className="mb-3 flex gap-2">
            <input
              readOnly
              value={link.url}
              className="min-w-0 flex-1 rounded-[6px] border border-[#e0ddd6] bg-[#f5f4f0] px-3 py-2 text-[11px] text-[#1a1a18] outline-none"
            />
            <button
              type="button"
              onClick={() => void handleCopy()}
              className={`shrink-0 rounded-[6px] px-3 py-2 text-[11px] font-medium transition-colors ${
                status === 'copied'
                  ? 'bg-[#E1F5EE] text-[#085041]'
                  : 'bg-[#1D9E75] text-white hover:bg-[#0f6e56]'
              }`}
            >
              {status === 'copied' ? 'Скопировано' : 'Копировать'}
            </button>
          </div>

          <div className="mb-3 flex flex-wrap gap-2">
            {clientEmail ? (
              <a
                href={mailtoHref}
                className="rounded-[6px] border border-[#e0ddd6] px-3 py-[6px] text-[11px] text-[#1a1a18] hover:border-[#b4b2a9]"
              >
                Email
              </a>
            ) : null}
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="rounded-[6px] border border-[#e0ddd6] px-3 py-[6px] text-[11px] text-[#1a1a18] hover:border-[#b4b2a9]"
            >
              Скопировать для мессенджера
            </button>
          </div>

          <div className="flex items-start justify-between gap-4 border-t border-[#e0ddd6] pt-3">
            <div className="text-[10px] leading-relaxed text-[#73726c]">
              Ссылка одноразовая и привязана только к этому клиенту.
            </div>
            <button
              type="button"
              onClick={() => void handleRevoke()}
              disabled={status === 'revoking'}
              className="shrink-0 text-[10px] text-[#73726c] underline decoration-dotted hover:text-[#993C1D] disabled:opacity-50"
            >
              {status === 'revoking' ? 'Отзываю...' : 'Отозвать ссылку'}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}
