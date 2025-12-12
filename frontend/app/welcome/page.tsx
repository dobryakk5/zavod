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
            <Link href="/analytics" className="inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:underline">Начать анализ <ArrowRight className="h-4 w-4"/></Link>
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

    </div>
  );
}
