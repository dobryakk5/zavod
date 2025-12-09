"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight, Search, MessageCircle, CheckCircle } from "lucide-react";

// LoggedInLanding — страница, которая показывается пользователю после логина.
// Включает пошаговый план и формы ввода для анализа Telegram-канала.
// Меняйте обработчик onSubmit, чтобы интегрировать с вашими API-эндпоинтами.

export default function LoggedInLanding() {
  const [channel, setChannel] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  function normalizeChannel(input: string): string {
    if (!input) return "";
    return input.replace(/^https?:\/\//, "").replace(/\/$/, "");
  }

  async function handleSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setError("");
    const cleaned = normalizeChannel(channel).trim();
    if (!cleaned) {
      setError("Введите ссылку или @username канала");
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      // Пример вызова API. Замените на реальный роут и логику.
      const res = await fetch(`/api/analyze?channel=${encodeURIComponent(cleaned)}`);
      if (!res.ok) throw new Error("Ошибка на сервере");
      const data = await res.json();
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось выполнить анализ");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-slate-900">Добро пожаловать — план действий</h1>
        <p className="mt-2 text-slate-600">Пройдите три простых шага — мы поможем с аналитикой, узнаваемостью и контент-планом.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="rounded-2xl border p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-indigo-600 font-semibold">Шаг 1</div>
              <div className="mt-2 text-lg font-semibold text-slate-900">AI-аналитика</div>
            </div>
            <div className="text-indigo-100 rounded-full bg-indigo-50 p-2">
              <Search className="h-5 w-5 text-indigo-600" />
            </div>
          </div>
          <p className="mt-4 text-sm text-slate-600">Мы проанализируем канал и дадим метрики: вовлечение, охват, наиболее сильный контент.</p>
          <div className="mt-4">
            <Link href="#analyze" className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:underline">Начать анализ <ArrowRight className="h-4 w-4"/></Link>
          </div>
        </div>

        <div className="rounded-2xl border p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-amber-600 font-semibold">Шаг 2</div>
              <div className="mt-2 text-lg font-semibold text-slate-900">Как стать известной компанией</div>
            </div>
            <div className="text-amber-100 rounded-full bg-amber-50 p-2">
              <MessageCircle className="h-5 w-5 text-amber-600" />
            </div>
          </div>
          <p className="mt-4 text-sm text-slate-600">Конкретные рекомендации по позиционированию, тону и каналам продвижения — на основе анализа.</p>
          <div className="mt-4">
            <Link href="#strategy" className="inline-flex items-center gap-2 text-sm font-medium text-amber-600 hover:underline">Получить рекомендации <ArrowRight className="h-4 w-4"/></Link>
          </div>
        </div>

        <div className="rounded-2xl border p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-emerald-600 font-semibold">Шаг 3</div>
              <div className="mt-2 text-lg font-semibold text-slate-900">Контент-план</div>
            </div>
            <div className="text-emerald-100 rounded-full bg-emerald-50 p-2">
              <CheckCircle className="h-5 w-5 text-emerald-600" />
            </div>
          </div>
          <p className="mt-4 text-sm text-slate-600">Готовый план постов на 2 недели с темами, подтемами и CTA — можно сразу копировать.</p>
          <div className="mt-4">
            <Link href="#plan" className="inline-flex items-center gap-2 text-sm font-medium text-emerald-600 hover:underline">Сгенерировать план <ArrowRight className="h-4 w-4"/></Link>
          </div>
        </div>
      </div>

      <div className="mt-10 rounded-2xl bg-white p-8 shadow-md">
        <h2 className="text-xl font-semibold text-slate-900">Давайте знакомиться</h2>
        <p className="mt-2 text-sm text-slate-600">Введите ваш Telegram-канал. Если канала нет — вставьте ссылку на канал конкурента, и я его проанализирую.</p>

        <form id="analyze" onSubmit={handleSubmit} className="mt-6 grid gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-slate-700">Ваше имя (необязательно)</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Например, Ольга" className="mt-2 w-full rounded-lg border px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-200" />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700">Telegram-канал (или канал конкурента)</label>
            <div className="mt-2 flex gap-2">
              <input value={channel} onChange={(e) => setChannel(e.target.value)} placeholder="https://t.me/example или @example" className="flex-1 rounded-lg border px-4 py-2 text-sm focus:ring-2 focus:ring-indigo-200" />
              <button type="submit" disabled={loading} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">
                {loading ? 'Анализ...' : 'Проанализировать'}
                <Search className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">Если у вас нет канала — используйте любой публичный канал конкурента.</p>
          </div>

          <div className="md:col-span-2">
            {error && <div className="mt-2 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

            {result ? (
              <div className="mt-4 rounded-lg border p-4 bg-slate-50">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm text-slate-600">Результаты анализа</div>
                    <div className="mt-1 text-lg font-semibold text-slate-900">{(result as any)?.title || cleanedPreview(channel)}</div>
                  </div>
                  <div className="text-sm text-slate-500">Обновлено: {new Date().toLocaleString()}</div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <div className="rounded-lg bg-white p-3 text-center shadow-sm">
                    <div className="text-xs text-slate-500">Охват</div>
                    <div className="mt-1 text-lg font-semibold">{(result as any)?.reach ?? '—'}</div>
                  </div>
                  <div className="rounded-lg bg-white p-3 text-center shadow-sm">
                    <div className="text-xs text-slate-500">Вовлечение</div>
                    <div className="mt-1 text-lg font-semibold">{(result as any)?.engagement ?? '—'}</div>
                  </div>
                  <div className="rounded-lg bg-white p-3 text-center shadow-sm">
                    <div className="text-xs text-slate-500">Рекомендуемые темы</div>
                    <div className="mt-1 text-sm">{((result as any)?.topics || []).slice(0,3).join(', ') || '—'}</div>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-3">
                  <Link href="/dashboard/content-plan" className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Сгенерировать контент-план</Link>
                  <Link href="/dashboard/strategy" className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm">Посмотреть стратегию</Link>
                </div>
              </div>
            ) : (
              <div className="mt-4 rounded-lg border p-4 bg-slate-50 text-sm text-slate-600">Результаты появятся здесь после запуска анализа.</div>
            )}
          </div>
        </form>
      </div>

      <p className="mt-6 text-xs text-slate-500">Подсказка: система не требует привязки карты для первого анализа.</p>
    </div>
  );
}

// Вспомогательная функция для превью, если результат пустой.
function cleanedPreview(val: string): string {
  if (!val) return 'Канал';
  return val.replace(/^https?:\/\//, '').replace(/^t\.me\//, '');
}
