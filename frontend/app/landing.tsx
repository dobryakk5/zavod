"use client";
import React from "react";
import Link from "next/link";

export default function SolarLabLanding() {
  return (
    <div className="min-h-screen font-sans text-gray-900 bg-white">
      {/* Header */}
      <header className="w-full max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-300 via-yellow-200 to-orange-200 flex items-center justify-center shadow-md">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="5" fill="white" />
                <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" stroke="#F59E0B" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <div className="text-lg font-semibold">SolarLab</div>
              <div className="text-xs text-gray-500">Media · AI Lab</div>
            </div>
          </div>
        </div>

        <nav className="flex items-center gap-4">
          <a href="#services" className="text-sm text-gray-700 hover:underline">Услуги</a>
          <a href="#process" className="text-sm text-gray-700 hover:underline">Как мы работаем</a>
          <a href="#demos" className="text-sm text-gray-700 hover:underline">Демонстрации</a>
          <a href="#pricing" className="text-sm text-gray-700 hover:underline">Прайс</a>
          <Link href="/login" className="ml-4 inline-flex items-center px-4 py-2 border border-gray-200 rounded-md text-sm font-medium hover:shadow focus:outline-none">
            Личный кабинет
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <main className="w-full max-w-6xl mx-auto px-6">
        <section className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center py-12">
          <div>
            <h1 className="text-4xl md:text-5xl font-extrabold leading-tight">
              AI‑медиа лаборатория для предпринимателей
            </h1>
            <p className="mt-6 text-lg text-gray-600 max-w-xl">
              Создаём контент, который продаёт: фото, видео, тексты, автоматизации и рост соцсетей. Быстро, системно, с научным подходом.
            </p>

            <div className="mt-8 flex gap-4">
              <a href="#demos" className="inline-flex items-center justify-center px-5 py-3 rounded-md bg-yellow-400 text-black font-semibold shadow">Запросить демонстрацию</a>
              <a href="#pricing" className="inline-flex items-center justify-center px-5 py-3 rounded-md border border-gray-200 text-sm text-gray-700">Узнать прайс</a>
            </div>

            <div className="mt-8 grid grid-cols-2 gap-3 max-w-md text-sm text-gray-600">
              <div className="p-4 border rounded-md">
                <div className="font-semibold">AI-ускорение</div>
                <div className="mt-1">Контент за часы, не недели.</div>
              </div>
              <div className="p-4 border rounded-md">
                <div className="font-semibold">A/B тесты</div>
                <div className="mt-1">Научный подход к росту.</div>
              </div>
              <div className="p-4 border rounded-md">
                <div className="font-semibold">Автоматизация</div>
                <div className="mt-1">Контент‑пайплайн под ключ.</div>
              </div>
              <div className="p-4 border rounded-md">
                <div className="font-semibold">Telegram</div>
                <div className="mt-1">Ведение и прогревы.</div>
              </div>
            </div>
          </div>

          <div className="relative">
            <div className="w-full h-80 bg-gradient-to-br from-yellow-50 to-white rounded-2xl border border-gray-100 shadow-sm flex items-center justify-center">
              {/* Mockup visualization */}
              <svg width="360" height="220" viewBox="0 0 360 220" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="0" y="0" width="360" height="220" rx="18" fill="url(#g)"/>
                <defs>
                  <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
                    <stop stopColor="#FFFBEA" offset="0" />
                    <stop stopColor="#FFF3E0" offset="1" />
                  </linearGradient>
                </defs>
                <g>
                  <circle cx="56" cy="56" r="24" fill="#fff" opacity="0.9" />
                  <rect x="96" y="30" width="220" height="40" rx="8" fill="#ffffff" opacity="0.95" />
                  <rect x="96" y="86" width="140" height="18" rx="6" fill="#fff" opacity="0.95" />
                  <rect x="96" y="110" width="220" height="86" rx="10" fill="#fff" opacity="0.98" />
                </g>
              </svg>
            </div>
            <div className="absolute -bottom-8 right-6 w-48 p-3 bg-white border rounded-lg shadow-md">
              <div className="text-xs text-gray-500">Pipeline</div>
              <div className="mt-1 font-medium">AI → Test → Scale</div>
            </div>
          </div>
        </section>

        {/* Services */}
        <section id="services" className="py-10">
          <h2 className="text-2xl font-semibold">Контент завод 2.0</h2>
          <p className="mt-2 text-gray-600 max-w-2xl">Полный набор от генерации до автоматизации: делаем медиа как инженерный продукт.</p>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card title="AI-контент" items={["Фото", "Видео", "Тексты", "Виральные посты", "Telegram"]} />
            <Card title="Маркетинг & SMM" items={["Telegram-ведение", "SEO", "Медиапланирование", "Ведение контент-календаря"]} />
            <Card title="Аналитика & Исследования" items={["Аналитика трендов", "A/B тесты", "Продуктовые инсайты"]} />
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card title="Автоматизация" items={["Контент-пайплайн", "Автопостинг", "Нейро-боты", "Скрипты"]} />
            <Card title="Медиапланирование" items={["Стратегия", "Кампании", "Оптимизация" ]} />
          </div>
        </section>

        {/* Process */}
        <section id="process" className="py-10">
          <h2 className="text-2xl font-semibold">Как мы работаем</h2>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-6">
            <ProcessStep num={1} title="Исследуем" desc="Аудит, цели, тренды" />
            <ProcessStep num={2} title="Проектируем" desc="Гипотезы, AI-pipeline" />
            <ProcessStep num={3} title="Создаём" desc="Фото, видео, тексты" />
            <ProcessStep num={4} title="Улучшаем" desc="A/B тесты, масштаб" />
          </div>
        </section>

        {/* Demos */}
        <section id="demos" className="py-10">
          <h2 className="text-2xl font-semibold">Демонстрации</h2>
          <p className="mt-2 text-gray-600">Небольшая подборка контента, сгенерированного нашей лабораторией.</p>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            {demoItems.map((d) => (
              <div key={d.id} className="border rounded-lg overflow-hidden">
                <div className="w-full h-40 bg-gray-50 flex items-center justify-center">{d.media}</div>
                <div className="p-4">
                  <div className="font-semibold">{d.title}</div>
                  <div className="mt-2 text-sm text-gray-600">{d.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="py-10">
          <h2 className="text-2xl font-semibold">Пакеты</h2>
          <p className="mt-2 text-gray-600">Простые пакеты для быстрого старта и масштабирования.</p>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <PriceCard name="Start" price="900–1200€ / мес" bullets={["Генерация контента","Демо‑пакет","Минимал поддержка"]} />
            <PriceCard name="Growth" price="1500–2500€ / мес" bullets={["Контент + ведение","A/B тесты","SEO базовый"]} important />
            <PriceCard name="Pro Lab" price="3000–5000€ / мес" bullets={["Полный pipeline","Автоматизация","Полный SMM + анализ"]} />
          </div>
        </section>

        {/* CTA */}
        <section className="py-12 text-center">
          <h3 className="text-2xl font-semibold">Готовы запустить свою медиа-лабораторию?</h3>
          <p className="mt-3 text-gray-600">Запросите демонстрацию — покажем pipeline и первые генерации.</p>
          <div className="mt-6 flex justify-center gap-4">
            <a href="#demos" className="inline-flex items-center px-6 py-3 rounded-md bg-yellow-400 text-black font-semibold">Запросить демонстрацию</a>
            <a href="#pricing" className="inline-flex items-center px-6 py-3 rounded-md border border-gray-200">Получить предложение</a>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="w-full mt-12 border-t">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col md:flex-row justify-between items-start gap-6">
          <div>
            <div className="text-lg font-semibold">SolarLab</div>
            <div className="text-sm text-gray-600 mt-1">Media · AI Lab</div>
          </div>
          <div className="flex gap-8 text-sm text-gray-600">
            <div>
              <div className="font-semibold">Услуги</div>
              <div className="mt-2">AI-контент<br/>SMM<br/>Аналитика</div>
            </div>
            <div>
              <div className="font-semibold">Контакты</div>
              <div className="mt-2">hello@solarlab.media<br/>Telegram: @solarlab</div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Card({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="p-6 border rounded-lg">
      <div className="font-semibold mb-3">{title}</div>
      <ul className="text-gray-600 space-y-2">
        {items.map((it) => (
          <li key={it} className="flex items-start gap-2">
            <div className="w-3 h-3 mt-1 bg-yellow-300 rounded-full" />
            <div>{it}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProcessStep({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div className="p-6 border rounded-lg text-center">
      <div className="text-3xl font-bold text-yellow-400">{num}</div>
      <div className="mt-3 font-semibold">{title}</div>
      <div className="mt-2 text-sm text-gray-600">{desc}</div>
    </div>
  );
}

function PriceCard({ name, price, bullets, important }: { name: string; price: string; bullets: string[]; important?: boolean }) {
  return (
    <div className={`p-6 rounded-lg border ${important ? "border-yellow-300 bg-yellow-50" : "border-gray-100"}`}>
      <div className="font-semibold text-lg">{name}</div>
      <div className="mt-2 text-2xl font-bold">{price}</div>
      <ul className="mt-4 text-gray-600 space-y-2">
        {bullets.map((b) => (
          <li key={b} className="flex items-start gap-2">
            <div className="w-2 h-2 bg-black rounded-full mt-2" />
            <div>{b}</div>
          </li>
        ))}
      </ul>
      <div className="mt-6">
        <a href="#" className={`inline-block w-full text-center px-4 py-2 rounded-md ${important ? "bg-black text-white" : "border border-gray-200"}`}>Выбрать</a>
      </div>
    </div>
  );
}

const demoItems = [
  { id: 1, title: "AI Фото — брендовый стиль", desc: "Минималистичные кадры для лендинга и соцсетей", media: <svg width="80" height="60" viewBox="0 0 80 60" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" rx="8" fill="#FFF5E1"/><circle cx="20" cy="20" r="8" fill="#FFF"/><rect x="36" y="12" width="34" height="12" rx="4" fill="#FFF"/></svg> },
  { id: 2, title: "Короткое видео", desc: "Версия для Reels / Shorts с динамикой и текстом", media: <svg width="80" height="60" viewBox="0 0 80 60" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" rx="8" fill="#F0F9FF"/><path d="M26 18v24l20-12L26 18z" fill="#fff"/></svg> },
  { id: 3, title: "Пост для Telegram", desc: "Структура поста + эмодзи + CTA", media: <svg width="80" height="60" viewBox="0 0 80 60" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="80" height="60" rx="8" fill="#F6FEF5"/><rect x="12" y="12" width="56" height="8" rx="4" fill="#fff"/><rect x="12" y="26" width="40" height="8" rx="4" fill="#fff"/></svg> },
];
