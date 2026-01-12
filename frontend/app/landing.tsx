"use client";
import React from "react";
import Link from "next/link";
import Image from "next/image";
import { Rocket, BarChart2, FileText, Zap, Brain, Workflow, Bot } from "lucide-react";
import LandingFooter from "./footer";


export default function FibonattyNewLanding() {
  return (
    <div className="min-h-screen font-sans text-gray-900 bg-white">
      {/* Header */}
      <header className="w-full max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Image src="/fibonatty.jpeg" alt="Fibonatty" width={120} height={120} className="object-contain" />
        </div>
        <nav className="flex items-center gap-5">
          <a href="#platform" className="text-sm text-gray-700 hover:underline">Платформа</a>
          <a href="#process" className="text-sm text-gray-700 hover:underline">Pipeline</a>
          <a href="#pricing" className="text-sm text-gray-700 hover:underline">Тарифы</a>
          <Link href="/login" className="ml-4 inline-flex items-center px-4 py-2 border border-gray-200 rounded-md text-sm font-medium hover:shadow">
            Войти
          </Link>
        </nav>
      </header>

      <main className="w-full max-w-7xl mx-auto px-6">
        {/* SEO Intro */}
        <section className="py-10">
          <h2 className="text-3xl font-semibold">AI-маркетинговая платформа для роста бизнеса</h2>
          <p className="mt-4 text-gray-600 max-w-3xl">
            Fibonatty — это AI-платформа для маркетинга, контента и аналитики.
            Она помогает предпринимателям, экспертам и командам системно привлекать клиентов
            через данные, гипотезы и автоматизированный контент.
          </p>
        </section>

        {/* Hero */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-14 items-center py-16">
          <div>
            <h1 className="text-4xl md:text-6xl font-extrabold leading-tight">
              AI‑платформа
              <br />
              для системного маркетинга
            </h1>
            <p className="mt-6 text-xl text-gray-600 max-w-xl">
              Fibonatty — это не агентство и не генератор постов.
              <br />
              Это маркетинговая операционная система: анализ → гипотезы → контент → рост.
            </p>
            <div className="mt-10 flex gap-4">
              <a href="#demo" className="inline-flex items-center justify-center px-6 py-4 rounded-xl bg-yellow-400 text-black font-semibold shadow">Запустить демо</a>
              <a href="#pricing" className="inline-flex items-center justify-center px-6 py-4 rounded-xl border border-gray-200">Посмотреть тарифы</a>
            </div>
          </div>
          <div className="relative">
            <div className="relative w-full h-96 rounded-3xl overflow-hidden border shadow-lg">
              <Image src="/fist_screen.jpg" alt="Dashboard" fill className="object-contain" />
            </div>
          </div>
        </section>

        {/* Platform */}
        <section id="platform" className="py-16">
          <h2 className="text-3xl font-semibold">Что внутри платформы</h2>
          <p className="mt-3 text-gray-600 max-w-2xl">
            Платформа выросла из контент‑лаборатории в полноценный AI‑маркетинг стек.
          </p>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-8">
            <Feature icon={<Brain />} title="AI‑аналитик" desc="Анализ ниш, конкурентов, контента и воронок." />
            <Feature icon={<Workflow />} title="Контент‑pipeline" desc="Генерация, редактура, A/B тесты, масштабирование." />
            <Feature icon={<Bot />} title="Автоматизация" desc="Боты, автопостинг, интеграции, сценарии роста." />
          </div>
        </section>

        {/* Process */}
        {/* Audience */}
        {/* Why not ChatGPT */}
        <section id="why" className="py-20">
          <h2 className="text-3xl font-semibold">Почему Fibonatty ≠ ChatGPT, агентство или маркетолог</h2>
          <p className="mt-4 text-gray-600 max-w-3xl">
            Большинство инструментов и услуг закрывают только часть маркетинга. Fibonatty построен как система,
            которая соединяет данные, мышление и масштабирование.
          </p>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 border rounded-2xl">
              <div className="text-xl font-semibold">ChatGPT</div>
              <p className="mt-3 text-gray-600">Отвечает на запросы, но не понимает ваш бизнес целиком.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Нет контекста рынка</li>
                <li>• Нет стратегии</li>
                <li>• Нет роста как системы</li>
              </ul>
            </div>
            <div className="p-6 border rounded-2xl bg-yellow-50 border-yellow-300">
              <div className="text-xl font-semibold">Fibonatty</div>
              <p className="mt-3 text-gray-600">Маркетинговая операционная система с AI-ядром.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Анализ рынка и ЦА</li>
                <li>• Генерация и тест гипотез</li>
                <li>• Контент → рост → автоматизация</li>
              </ul>
            </div>
            <div className="p-6 border rounded-2xl">
              <div className="text-xl font-semibold">Агентства / маркетологи</div>
              <p className="mt-3 text-gray-600">Зависят от людей, сроков и бюджета.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Медленно масштабируются</li>
                <li>• Непрозрачная логика</li>
                <li>• Нет накопления знаний</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="audience" className="py-20">
          <h2 className="text-3xl font-semibold">Для кого платформа</h2>
          <p className="mt-4 text-gray-600 max-w-2xl">
            Fibonatty подходит тем, кто хочет выстроить маркетинг как систему, а не набор разрозненных действий.
          </p>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="p-6 border rounded-2xl">
              <div className="text-xl font-semibold">Предприниматели</div>
              <p className="mt-3 text-gray-600">Для владельцев бизнеса, которым нужен поток лидов и понятная картина роста без погружения в рутину маркетинга.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Аналитика рынка и конкурентов</li>
                <li>• Контент под продукт и продажи</li>
                <li>• Автоматизация маркетинга</li>
              </ul>
            </div>
            <div className="p-6 border rounded-2xl">
              <div className="text-xl font-semibold">Эксперты и блогеры</div>
              <p className="mt-3 text-gray-600">Для тех, кто развивает личный бренд, Telegram-канал или онлайн-продукты.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Темы и форматы под ЦА</li>
                <li>• Прогревы и воронки</li>
                <li>• Рост без выгорания</li>
              </ul>
            </div>
            <div className="p-6 border rounded-2xl">
              <div className="text-xl font-semibold">Маркетинг-команды</div>
              <p className="mt-3 text-gray-600">Для команд и агентств, которым важно ускорить производство и тестирование гипотез.</p>
              <ul className="mt-4 text-sm text-gray-600 space-y-2">
                <li>• Единый pipeline</li>
                <li>• A/B тесты и отчёты</li>
                <li>• Масштабирование контента</li>
              </ul>
            </div>
          </div>
        </section>

        <section id="process" className="py-16">
          <h2 className="text-3xl font-semibold">Как работает Fibonatty</h2>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-5 gap-6">
            <Step num={1} title="Данные" desc="Профиль, конкуренты, рынок" />
            <Step num={2} title="Анализ" desc="AI‑инсайты и точки роста" />
            <Step num={3} title="Гипотезы" desc="Идеи контента и офферов" />
            <Step num={4} title="Контент" desc="Тексты, видео, визуал" />
            <Step num={5} title="Рост" desc="Тесты, масштаб, автоматизация" />
          </div>
        </section>

        {/* Demo */}
        <section id="demo" className="py-16 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="text-3xl font-semibold">Демо-доступ</h2>
            <p className="mt-4 text-gray-600">
              За 15 минут вы получите аналитику аккаунта и первые AI‑гипотезы роста.
            </p>
            <ul className="mt-6 space-y-4">
              <DemoItem icon={<BarChart2 />} title="Анализ" desc="Охваты, ЦА, лучшие форматы" />
              <DemoItem icon={<Zap />} title="Гипотезы" desc="Темы, углы, CTA" />
              <DemoItem icon={<FileText />} title="Контент" desc="Готовые посты и сценарии" />
            </ul>
            <div className="mt-8">
              <Link href="/login" className="inline-flex items-center gap-2 px-6 py-4 rounded-xl bg-black text-white font-semibold">
                <Rocket className="h-4 w-4" />
                Попробовать бесплатно
              </Link>
            </div>
          </div>
          <div className="rounded-3xl border shadow-lg p-6">
            <Image src="/trial.jpeg" alt="Demo" width={600} height={400} />
          </div>
        </section>

        {/* Pricing */}
        {/* FAQ */}
        <section id="faq" className="py-20">
          <h2 className="text-3xl font-semibold">Частые вопросы</h2>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-8">
            <FAQItem q="Это агентство или SaaS?" a="Fibonatty — это SaaS-платформа. Вы получаете систему, а не разовую услугу. Контент, аналитика и рост работают как единый pipeline." />
            <FAQItem q="Чем отличается от ChatGPT?" a="ChatGPT — это инструмент. Fibonatty — маркетинговая система: анализ рынка, генерация гипотез, контент, тесты и масштабирование." />
            <FAQItem q="Нужна ли команда маркетологов?" a="Нет. Платформа закрывает 70–80% задач соло-предпринимателя и ускоряет команды в 2–3 раза." />
            <FAQItem q="Можно ли использовать для Telegram и SEO?" a="Да. Платформа изначально заточена под Telegram, SEO-контент и воронки прогрева." />
            <FAQItem q="Есть ли бесплатный доступ?" a="Да. Вы можете начать с демо-доступа без карты и обязательств." />
          </div>
        </section>

        <section id="pricing" className="py-20">
          <h2 className="text-3xl font-semibold">Тарифы</h2>
          <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-8">
            <Price name="Starter" desc="Для теста и понимания" bullets={["Аналитика","AI‑контент","Ограничения"]} />
            <Price name="Growth" desc="Для роста" bullets={["Pipeline","Продуктовая линейка","Автоматизация"]} highlight />
            <Price name="Lab" desc="Для команд" bullets={["Кастом AI","Интеграции","RAG база знаний"]} />
          </div>
        </section>
      </main>
      <LandingFooter />
    </div>
  );
}

function Feature({ icon, title, desc }: any) {
  return (
    <div className="p-6 border rounded-2xl">
      <div className="mb-4">{icon}</div>
      <div className="font-semibold text-lg">{title}</div>
      <div className="mt-2 text-gray-600">{desc}</div>
    </div>
  );
}

function Step({ num, title, desc }: any) {
  return (
    <div className="p-5 border rounded-xl text-center">
      <div className="text-2xl font-bold text-yellow-400">{num}</div>
      <div className="mt-2 font-semibold">{title}</div>
      <div className="mt-1 text-sm text-gray-600">{desc}</div>
    </div>
  );
}

function DemoItem({ icon, title, desc }: any) {
  return (
    <li className="flex gap-4 items-start">
      <div className="p-2 bg-yellow-100 rounded-lg">{icon}</div>
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-sm text-gray-600">{desc}</div>
      </div>
    </li>
  );
}

function FAQItem({ q, a }: any) {
  return (
    <div className="p-6 border rounded-2xl">
      <div className="font-semibold">{q}</div>
      <div className="mt-2 text-sm text-gray-600">{a}</div>
    </div>
  );
}

function Price({ name, desc, bullets, highlight }: any) {
  return (
    <div className={`p-8 rounded-3xl border ${highlight ? "bg-yellow-50 border-yellow-300" : ""}`}>
      <div className="text-xl font-semibold">{name}</div>
      <div className="mt-1 text-sm text-gray-600">{desc}</div>
      <ul className="mt-4 space-y-2">
        {bullets.map((b: string) => (
          <li key={b} className="text-gray-600">• {b}</li>
        ))}
      </ul>
      <a href="#" className={`mt-6 block text-center px-4 py-3 rounded-xl ${highlight ? "bg-black text-white" : "border"}`}>Выбрать</a>
    </div>
  );
}
