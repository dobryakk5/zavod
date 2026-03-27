"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { GuideShell } from "./guide-shell";

const pages = [
  {
    href: "/features/functions/start",
    title: "Начало работы и навигация",
    desc: "Как зайти в систему, что вы увидите первым и как не потеряться в разделах.",
    tags: ["Экономия времени", "Лояльность"],
  },
  {
    href: "/features/functions/clients",
    title: "Клиенты, карточка и встречи",
    desc: "Как вести клиентов, хранить контекст и готовиться к сессиям без хаоса.",
    tags: ["Удержание клиентов", "Лояльность", "Экономия времени"],
  },
  {
    href: "/features/functions/client-space",
    title: "Кабинет клиента и видимый прогресс",
    desc: "Как клиент видит задачи, материалы и свой путь между сессиями.",
    tags: ["Удержание клиентов", "Лояльность"],
  },
  {
    href: "/features/functions/programs",
    title: "Программы, пакеты, оплата и курсы",
    desc: "Как собрать свои форматы работы и связать оплату с сопровождением.",
    tags: ["Получение клиентов", "Удержание клиентов", "Лояльность"],
  },
  {
    href: "/features/functions/materials",
    title: "Материалы, база знаний и автоматизации",
    desc: "Как хранить документы, делиться материалами и снимать с себя рутину.",
    tags: ["Экономия времени", "Лояльность", "Удержание клиентов"],
  },
];

const legendItems = [
  {
    title: "Получение клиентов",
    desc: "Функции, которые помогают понятнее упаковать работу, упростить оплату и снизить трение на входе.",
  },
  {
    title: "Удержание клиентов",
    desc: "Функции, которые поддерживают процесс между встречами и уменьшают выпадение клиента из работы.",
  },
  {
    title: "Лояльность",
    desc: "Функции, которые усиливают ощущение порядка, заботы, внимания и ценности вашей работы.",
  },
  {
    title: "Экономия времени",
    desc: "Функции, которые снимают рутину, повторные объяснения и ручное администрирование.",
  },
];

export default function FeatureFunctionsIndexPage() {
  const [activeFilter, setActiveFilter] = useState<string>("Все");

  const filteredPages =
    activeFilter === "Все"
      ? pages
      : pages.filter((page) => page.tags.includes(activeFilter));

  return (
    <GuideShell
      eyebrow="Полное описание функций"
      title={
        <>
          Индекс страниц
          <br />
          с описанием функций
          <br />
          простым языком
        </>
      }
      description="Это оглавление пользовательской версии документации. Здесь собраны страницы не для технического специалиста, а для коуча, психолога или эксперта с частной практикой: что делает система, как это выглядит в работе и зачем это нужно."
      backHref="/features"
      backLabel="К странице возможностей"
    >
      <section className="rounded-[28px] border border-black/5 bg-white p-6 shadow-sm md:p-8">
        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">Легенда по пользе</div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {legendItems.map((item) => (
            <div key={item.title} className="rounded-2xl border border-black/5 bg-[#fafaf8] p-4">
              <div className="inline-flex items-center rounded-full border border-[#2f8f7a]/15 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#2f8f7a]">
                {item.title}
              </div>
              <p className="mt-3 text-sm leading-7 text-[#354052]">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-[28px] border border-black/5 bg-white p-6 shadow-sm md:p-8">
        <div className="flex flex-col gap-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">Фильтр страниц</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {["Все", ...legendItems.map((item) => item.title)].map((filter) => {
                const isActive = activeFilter === filter;
                return (
                  <button
                    key={filter}
                    type="button"
                    onClick={() => setActiveFilter(filter)}
                    className={`inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                      isActive
                        ? "border-[#5c52e0]/20 bg-[#5c52e0]/[0.08] text-[#5c52e0]"
                        : "border-black/10 bg-[#fafaf8] text-[#354052] hover:border-[#5c52e0]/20 hover:text-[#5c52e0]"
                    }`}
                  >
                    {filter}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 text-sm text-[#707585]">
              {activeFilter === "Все"
                ? `Показаны все страницы: ${filteredPages.length}.`
                : `Показаны страницы по категории «${activeFilter}»: ${filteredPages.length}.`}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {filteredPages.map((page) => (
            <Link
              key={page.href}
              href={page.href}
              className="rounded-[24px] border border-black/5 bg-[#fafaf8] p-5 transition hover:-translate-y-0.5 hover:border-[#5c52e0]/20 hover:bg-white"
            >
              <div className="text-lg font-semibold text-[#1a1c24]">{page.title}</div>
              <p className="mt-3 text-sm leading-7 text-[#707585]">{page.desc}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {page.tags.map((tag) => (
                  <span
                    key={`${page.href}-${tag}`}
                    className="inline-flex items-center rounded-full border border-[#2f8f7a]/15 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#2f8f7a]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <div className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#5c52e0]">
                Открыть страницу
                <ArrowRight className="h-4 w-4" />
              </div>
            </Link>
            ))}
          </div>

          {filteredPages.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-black/10 bg-[#fafaf8] px-4 py-5 text-sm leading-7 text-[#707585]">
              Под выбранный фильтр пока нет страниц.
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-[28px] border border-black/5 bg-white p-6 shadow-sm md:p-8">
        <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">Как читать эту документацию</div>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-black/5 bg-[#fafaf8] p-4 text-sm leading-7 text-[#354052]">
            На каждой странице объясняется не интерфейс сам по себе, а рабочий смысл функции.
          </div>
          <div className="rounded-2xl border border-black/5 bg-[#fafaf8] p-4 text-sm leading-7 text-[#354052]">
            Вместо технических терминов используется язык обычной практики: клиент, встреча, задача, прогресс, материалы.
          </div>
          <div className="rounded-2xl border border-black/5 bg-[#fafaf8] p-4 text-sm leading-7 text-[#354052]">
            Если нужно, вы сможете дать эти страницы ассистенту, куратору или самому клиенту как понятное объяснение.
          </div>
        </div>
      </section>
    </GuideShell>
  );
}
