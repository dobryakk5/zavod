import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Manrope, Merriweather } from "next/font/google";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
  weight: ["400", "500", "600", "700"],
});

const merriweather = Merriweather({
  subsets: ["latin", "cyrillic"],
  variable: "--font-merriweather",
  weight: ["400", "700"],
});

export function GuideShell({
  eyebrow,
  title,
  description,
  children,
  backHref = "/features/functions",
  backLabel = "К индексу описаний",
}: {
  eyebrow: string;
  title: ReactNode;
  description: string;
  children: ReactNode;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <div className={`${manrope.variable} ${merriweather.variable} min-h-screen bg-[#f7f6f2] text-[#1a1c24]`}>
      <header className="sticky top-0 z-30 border-b border-black/5 bg-[rgba(247,246,242,0.88)] backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
          <Link href={backHref} className="inline-flex items-center gap-2 text-sm font-medium text-[#354052]">
            <ArrowLeft className="h-4 w-4" />
            {backLabel}
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center rounded-full bg-[#5c52e0] px-5 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5"
          >
            Попробовать
          </Link>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8 md:py-10">
        <section className="rounded-[32px] border border-black/5 bg-white p-8 shadow-[0_24px_80px_rgba(0,0,0,0.06)] md:p-10">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#5c52e0]/15 bg-[#5c52e0]/[0.07] px-3 py-1 text-xs font-semibold uppercase tracking-[0.08em] text-[#5c52e0]">
            {eyebrow}
          </div>
          <h1 className="mt-5 max-w-4xl font-serif text-4xl leading-tight md:text-6xl">{title}</h1>
          <p className="mt-5 max-w-4xl text-base leading-8 text-[#707585] md:text-lg">{description}</p>
        </section>

        {children}
      </main>
    </div>
  );
}

export function GuideCard({
  title,
  what,
  benefit,
  example,
  impact,
  impactTags,
}: {
  title: string;
  what: string;
  benefit: string;
  example: string;
  impact: string;
  impactTags: string[];
}) {
  return (
    <div className="rounded-[24px] border border-black/5 bg-[#fafaf8] p-5">
      <div className="text-lg font-semibold text-[#1a1c24]">{title}</div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <GuideTextBlock label="Что это" text={what} />
        <GuideTextBlock label="Чем полезно" text={benefit} />
        <GuideTextBlock label="Пример из практики" text={example} />
      </div>
      <div className="mt-4 rounded-2xl border border-[#2f8f7a]/15 bg-[#2f8f7a]/10 px-4 py-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#2f8f7a]">Как помогает в работе</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {impactTags.map((tag) => (
            <span
              key={`${title}-${tag}`}
              className="inline-flex items-center rounded-full border border-[#2f8f7a]/15 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#2f8f7a]"
            >
              {tag}
            </span>
          ))}
        </div>
        <p className="mt-3 text-sm leading-7 text-[#24574d]">{impact}</p>
      </div>
    </div>
  );
}

export function GuideTextBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-2xl border border-black/5 bg-white px-4 py-4">
      <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[#5c52e0]">{label}</div>
      <p className="mt-2 text-sm leading-7 text-[#354052]">{text}</p>
    </div>
  );
}
