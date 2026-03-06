"use client";

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence, Reorder } from "framer-motion";
import * as Popover from "@radix-ui/react-popover";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { quizBuilderApi } from "@/lib/api/quiz-builder";

// ─── Types ────────────────────────────────────────────────────────────────────

type QuestionType = "single" | "multiple" | "rating" | "text" | "date" | "slider";
type ScreenKind = "intro" | "question" | "lead" | "result";

interface OptionItem {
  id: string;
  label: string;
  emoji: string;
  nextScreenId?: string;
  nextSpecial?: "__lead" | "__end";
}

interface ResultCondition {
  id: string;
  screenId: string;
  operator: "includes" | "not_includes" | "gte" | "lte" | "equals";
  value: string[];
}

interface ResultRule {
  id: string;
  conditions: ResultCondition[];
}

interface Screen {
  id: string;
  kind: ScreenKind;
  title: string;
  subtitle: string;
  questionType?: QuestionType;
  options?: OptionItem[];
  placeholder?: string;
  minVal?: number;
  maxVal?: number;
  maxRating?: number;
  required?: boolean;
  rules?: ResultRule[];
  isDefaultResult?: boolean;
}

const uid = () => Math.random().toString(36).slice(2, 8);

const QUESTION_TYPES: { type: QuestionType; label: string; icon: string; desc: string }[] = [
  { type: "single",   label: "Один ответ",    icon: "◉", desc: "Карточки с одним выбором" },
  { type: "multiple", label: "Несколько",      icon: "☑", desc: "Можно выбрать несколько" },
  { type: "rating",   label: "Оценка",         icon: "★", desc: "Шкала от 1 до N" },
  { type: "text",     label: "Текст",          icon: "✎", desc: "Свободный ввод" },
  { type: "date",     label: "Дата",           icon: "▦", desc: "Выбор даты" },
  { type: "slider",   label: "Слайдер",        icon: "⇄", desc: "Числовой диапазон" },
];

const EMOJIS = [
  "📈", "🎯", "💎", "🚀", "✨", "💰", "🔍", "📢", "📱", "📧",
  "✍️", "🎬", "🏠", "🌿", "⚡", "🎵", "🛒", "💡", "🔥", "🎓",
  "🏆", "📊", "📚", "🧠", "🧩", "🗓️", "⏰", "✅", "❗", "⭐",
  "🌟", "📦", "📸", "🎨", "🛠️", "🧭", "🤝", "👑", "💬", "🧾",
  "💼", "📍", "🌍", "🧪", "🔒", "🔓", "📎", "🧲", "🎁", "🍀",
  "☕", "🍕", "🥇", "🥈", "🥉", "🎉", "🎪", "📝", "📌", "🪄",
  "💥", "🫶", "🤖", "🛰️", "🛡️", "🔔", "📞", "🧵", "🪙", "🧰",
];

const ACCENT = "#5b5ef4";
const ACCENT2 = "#ec4899";

// ─── Default screens ──────────────────────────────────────────────────────────

const defaultScreens = (): Screen[] => [
  {
    id: uid(),
    kind: "intro",
    title: "Подберём решение для вас",
    subtitle: "Ответьте на несколько вопросов и получите персональное предложение",
  },
  {
    id: uid(),
    kind: "question",
    title: "Какая у вас главная цель?",
    subtitle: "Выберите один вариант",
    questionType: "single",
    options: [
      { id: uid(), label: "Увеличить продажи", emoji: "📈" },
      { id: uid(), label: "Собрать лиды", emoji: "🎯" },
      { id: uid(), label: "Повысить узнаваемость", emoji: "✨" },
    ],
  },
  {
    id: uid(),
    kind: "lead",
    title: "Куда отправить результат?",
    subtitle: "Мы свяжемся с вами в течение 15 минут",
  },
  {
    id: uid(),
    kind: "result",
    title: "Заявка отправлена! 🎉",
    subtitle: "Мы изучим ваши ответы и подготовим персональное предложение",
    rules: [],
    isDefaultResult: true,
  },
];

// ─── Screen Preview ───────────────────────────────────────────────────────────

function ScreenPreview({
  screen,
  accent,
  interactive = false,
}: {
  screen: Screen;
  accent: string;
  interactive?: boolean;
}) {
  const kindMeta: Record<ScreenKind, { badge: string; color: string }> = {
    intro:    { badge: "Обложка",  color: "#10b981" },
    question: { badge: "Вопрос",   color: accent },
    lead:     { badge: "Контакты", color: "#f59e0b" },
    result:   { badge: "Финал",    color: "#ec4899" },
  };
  const meta = kindMeta[screen.kind];
  const [selectedOptionIds, setSelectedOptionIds] = useState<string[]>([]);

  useEffect(() => {
    setSelectedOptionIds([]);
  }, [screen.id]);

  const toggleOption = (optionId: string) => {
    if (!interactive || screen.kind !== "question") return;
    if (screen.questionType === "multiple") {
      setSelectedOptionIds((prev) =>
        prev.includes(optionId) ? prev.filter((id) => id !== optionId) : [...prev, optionId],
      );
      return;
    }
    if (screen.questionType === "single") {
      setSelectedOptionIds([optionId]);
    }
  };

  return (
    <div
      className="rounded-2xl overflow-hidden flex flex-col"
      style={{
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        minHeight: 320,
        position: "relative",
      }}
    >
      {/* Top accent line */}
      <div className="h-0.5 w-full" style={{ background: `linear-gradient(90deg, transparent, ${meta.color}, transparent)` }} />

      <div className="p-6 flex-1 flex flex-col">
        {/* Badge */}
        <div className="flex items-center gap-2 mb-5">
          <span
            className="text-xs font-bold px-2 py-0.5 rounded-full"
            style={{ background: `${meta.color}22`, color: meta.color }}
          >
            {meta.badge}
          </span>
          {screen.kind === "question" && screen.questionType && (
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#f1f5f9", color: "#64748b" }}>
              {QUESTION_TYPES.find(q => q.type === screen.questionType)?.label}
            </span>
          )}
        </div>

        {/* Title */}
        <h3 className="text-slate-900 font-bold text-lg mb-1 leading-snug">
          {screen.title || <span style={{ color: "#475569" }}>Заголовок не задан</span>}
        </h3>
        {screen.subtitle && (
          <p className="text-sm mb-5" style={{ color: "#64748b" }}>{screen.subtitle}</p>
        )}

        {/* Content preview */}
        {screen.kind === "question" && screen.questionType === "single" && screen.options && (
          <div className="grid grid-cols-2 gap-2 mt-auto">
            {screen.options.slice(0, 4).map(opt => (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleOption(opt.id)}
                className="rounded-xl px-3 py-2.5 text-sm flex items-center gap-2"
                style={{
                  background: selectedOptionIds.includes(opt.id) ? `${meta.color}22` : "#ffffff",
                  border: `1px solid ${selectedOptionIds.includes(opt.id) ? meta.color : "#e2e8f0"}`,
                  color: selectedOptionIds.includes(opt.id) ? "#0f172a" : "#334155",
                  cursor: interactive ? "pointer" : "default",
                }}
                disabled={!interactive}
              >
                <span>{opt.emoji}</span>
                <span className="truncate">{opt.label || "Вариант"}</span>
              </button>
            ))}
          </div>
        )}

        {screen.kind === "question" && screen.questionType === "multiple" && screen.options && (
          <div className="flex flex-col gap-2 mt-auto">
            {screen.options.slice(0, 3).map(opt => (
              <button
                key={opt.id}
                type="button"
                onClick={() => toggleOption(opt.id)}
                className="rounded-xl px-3 py-2 text-sm flex items-center gap-2"
                style={{
                  background: selectedOptionIds.includes(opt.id) ? `${meta.color}22` : "#ffffff",
                  border: `1px solid ${selectedOptionIds.includes(opt.id) ? meta.color : "#e2e8f0"}`,
                  color: selectedOptionIds.includes(opt.id) ? "#0f172a" : "#334155",
                  cursor: interactive ? "pointer" : "default",
                }}
                disabled={!interactive}
              >
                <div
                  className="w-4 h-4 rounded border flex items-center justify-center text-[10px] font-bold"
                  style={{
                    borderColor: selectedOptionIds.includes(opt.id) ? meta.color : "#64748b",
                    color: selectedOptionIds.includes(opt.id) ? meta.color : "transparent",
                  }}
                >
                  ✓
                </div>
                <span>{opt.emoji}</span>
                <span className="truncate">{opt.label || "Вариант"}</span>
              </button>
            ))}
          </div>
        )}

        {screen.kind === "question" && screen.questionType === "rating" && (
          <div className="flex gap-2 mt-auto">
            {Array.from({ length: screen.maxRating ?? 5 }, (_, i) => (
              <div
                key={i}
                className="rounded-full flex items-center justify-center text-sm font-bold"
                style={{
                  width: 40, height: 40,
                  background: i === 0 ? meta.color : "#ffffff",
                  color: i === 0 ? "#fff" : "#475569",
                  border: `1px solid ${i === 0 ? meta.color : "#e2e8f0"}`,
                }}
              >
                {i + 1}
              </div>
            ))}
          </div>
        )}

        {screen.kind === "question" && screen.questionType === "text" && (
          <div
            className="mt-auto rounded-xl px-4 py-3 text-sm"
            style={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#475569" }}
          >
            {screen.placeholder || "Введите ваш ответ..."}
          </div>
        )}

        {screen.kind === "question" && screen.questionType === "slider" && (
          <div className="mt-auto">
            <div className="flex justify-between text-xs mb-2" style={{ color: "#64748b" }}>
              <span>{screen.minVal ?? 0}</span>
              <span>{screen.maxVal ?? 100}</span>
            </div>
            <div className="relative h-2 rounded-full" style={{ background: "#e2e8f0" }}>
              <div className="absolute left-0 top-0 h-full w-1/3 rounded-full" style={{ background: meta.color }} />
              <div
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full border-2 bg-white"
                style={{ left: "calc(33% - 8px)", borderColor: meta.color }}
              />
            </div>
          </div>
        )}

        {screen.kind === "question" && screen.questionType === "date" && (
          <div
            className="mt-auto rounded-xl px-4 py-3 text-sm flex items-center gap-2"
            style={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#475569" }}
          >
            <span>▦</span> <span>дд.мм.гггг</span>
          </div>
        )}

        {screen.kind === "lead" && (
          <div className="flex flex-col gap-2 mt-auto">
            {["Ваше имя", "Телефон", "Email"].map(f => (
              <div
                key={f}
                className="rounded-xl px-4 py-2.5 text-sm"
                style={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#475569" }}
              >
                {f}
              </div>
            ))}
            <div
              className="rounded-xl py-2.5 text-center text-sm font-bold mt-1"
              style={{ background: meta.color, color: "#fff" }}
            >
              Получить результат →
            </div>
          </div>
        )}

        {screen.kind === "result" && (
          <div className="flex flex-col items-center mt-auto gap-3">
            <div className="text-5xl">🎉</div>
            <div
              className="rounded-xl py-2 px-6 text-sm font-bold"
              style={{ background: "#ffffff", border: "1px solid #e2e8f0", color: "#64748b" }}
            >
              Менеджер уже уведомлён
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Slide Thumbnail ──────────────────────────────────────────────────────────

function SlideThumbnail({
  screen,
  index,
  isActive,
  onClick,
  onDelete,
}: {
  screen: Screen;
  index: number;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const kindColors: Record<ScreenKind, string> = {
    intro: "#10b981",
    question: ACCENT,
    lead: "#f59e0b",
    result: "#ec4899",
  };
  const kindIcons: Record<ScreenKind, string> = {
    intro: "⚡",
    question: "?",
    lead: "✉",
    result: "✓",
  };
  const color = kindColors[screen.kind];

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -16, scale: 0.95 }}
      className="group relative cursor-pointer rounded-xl overflow-hidden border-2 transition-all"
      style={{
        borderColor: isActive ? color : "transparent",
        background: isActive ? `${color}12` : "#ffffff",
      }}
      onClick={onClick}
      whileHover={{ x: 2 }}
    >
      <div className="flex items-center gap-3 px-3 py-2.5">
        {/* Icon */}
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0"
          style={{ background: `${color}22`, color }}
        >
          {kindIcons[screen.kind]}
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="text-xs font-semibold truncate" style={{ color: "#334155" }}>
            {screen.title || "Без заголовка"}
          </div>
          <div className="text-xs mt-0.5" style={{ color: "#475569" }}>
            {screen.kind === "question" && screen.questionType
              ? QUESTION_TYPES.find(q => q.type === screen.questionType)?.label
              : { intro: "Обложка", lead: "Контакты", result: "Финал", question: "" }[screen.kind]}
          </div>
        </div>

        {/* Delete */}
        {screen.kind === "question" && (
          <motion.button
            initial={{ opacity: 0 }}
            whileHover={{ scale: 1.1 }}
            className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded flex items-center justify-center text-xs flex-shrink-0 transition-opacity"
            style={{ background: "#f1f5f9", color: "#ef4444" }}
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
          >
            ✕
          </motion.button>
        )}
      </div>

      {/* Active indicator */}
      {isActive && (
        <motion.div
          layoutId="activeBar"
          className="absolute left-0 top-0 bottom-0 w-0.5 rounded-r"
          style={{ background: color }}
        />
      )}
    </motion.div>
  );
}

function NextScreenSelect({
  value,
  onChange,
  screens,
  currentScreenId,
  accent,
}: {
  value: { nextScreenId?: string; nextSpecial?: "__lead" | "__end" };
  onChange: (target: { nextScreenId?: string; nextSpecial?: "__lead" | "__end" }) => void;
  screens: Screen[];
  currentScreenId: string;
  accent: string;
}) {
  const questions = screens.filter((item) => item.kind === "question" && item.id !== currentScreenId);
  const hasLead = screens.some((item) => item.kind === "lead");
  const hasResult = screens.some((item) => item.kind === "result");
  const selected = value.nextSpecial ?? value.nextScreenId ?? "";

  return (
    <select
      value={selected}
      onChange={(event) => {
        const nextValue = event.target.value;
        if (!nextValue) {
          onChange({});
          return;
        }
        if (nextValue === "__lead" || nextValue === "__end") {
          onChange({ nextSpecial: nextValue });
          return;
        }
        onChange({ nextScreenId: nextValue });
      }}
      style={{
        background: "#ffffff",
        border: `1px solid ${selected ? `${accent}66` : "#e2e8f0"}`,
        borderRadius: 8,
        color: selected ? "#0f172a" : "#64748b",
        padding: "6px 8px",
        fontSize: 11,
        outline: "none",
        cursor: "pointer",
        width: "100%",
        marginTop: 4,
      }}
    >
      <option value="">→ Следующий вопрос</option>
      {questions.map((question) => (
        <option key={question.id} value={question.id}>
          → {question.title || "Без заголовка"}
        </option>
      ))}
      {hasLead ? <option value="__lead">→ Форма контактов</option> : null}
      {hasResult ? <option value="__end">→ Финал</option> : null}
    </select>
  );
}

function ResultRulesBuilder({
  screen,
  allScreens,
  onChange,
  accent,
}: {
  screen: Screen;
  allScreens: Screen[];
  onChange: (patch: Partial<Screen>) => void;
  accent: string;
}) {
  const rules = screen.rules ?? [];
  const questionScreens = allScreens.filter(
    (item) => item.kind === "question" && (item.questionType === "single" || item.questionType === "multiple"),
  );

  const addRule = () => {
    onChange({ rules: [...rules, { id: uid(), conditions: [] }] });
  };

  const removeRule = (ruleId: string) => {
    onChange({ rules: rules.filter((rule) => rule.id !== ruleId) });
  };

  const addCondition = (ruleId: string) => {
    const firstQuestion = questionScreens[0];
    if (!firstQuestion) return;
    onChange({
      rules: rules.map((rule) =>
        rule.id === ruleId
          ? {
              ...rule,
              conditions: [
                ...rule.conditions,
                {
                  id: uid(),
                  screenId: firstQuestion.id,
                  operator: "includes",
                  value: [],
                },
              ],
            }
          : rule,
      ),
    });
  };

  const updateCondition = (ruleId: string, conditionId: string, patch: Partial<ResultCondition>) => {
    onChange({
      rules: rules.map((rule) =>
        rule.id === ruleId
          ? {
              ...rule,
              conditions: rule.conditions.map((condition) =>
                condition.id === conditionId ? { ...condition, ...patch } : condition,
              ),
            }
          : rule,
      ),
    });
  };

  const removeCondition = (ruleId: string, conditionId: string) => {
    onChange({
      rules: rules.map((rule) =>
        rule.id === ruleId
          ? { ...rule, conditions: rule.conditions.filter((condition) => condition.id !== conditionId) }
          : rule,
      ),
    });
  };

  const toggleConditionOption = (ruleId: string, conditionId: string, optionId: string, currentValues: string[]) => {
    const nextValues = currentValues.includes(optionId)
      ? currentValues.filter((item) => item !== optionId)
      : [...currentValues, optionId];
    updateCondition(ruleId, conditionId, { value: nextValues });
  };

  if (screen.isDefaultResult) {
    return (
      <div
        className="rounded-xl p-3 text-xs text-center"
        style={{ background: "#f8fafc", border: "1px dashed #e2e8f0", color: "#64748b" }}
      >
        Экран по умолчанию: показывается, если другие правила не совпали.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {questionScreens.length === 0 ? (
        <div
          className="rounded-xl p-3 text-xs text-center"
          style={{ background: "#f8fafc", border: "1px dashed #e2e8f0", color: "#64748b" }}
        >
          Добавьте вопрос типа «Один ответ» или «Несколько», чтобы настроить правила.
        </div>
      ) : null}

      <AnimatePresence>
        {rules.map((rule, ruleIndex) => (
          <motion.div
            key={rule.id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            className="rounded-xl overflow-hidden"
            style={{ border: `1px solid ${accent}44`, background: `${accent}08` }}
          >
            <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: `1px solid ${accent}22` }}>
              <span className="text-xs font-bold" style={{ color: accent }}>
                Правило {ruleIndex + 1}
              </span>
              <button type="button" onClick={() => removeRule(rule.id)} className="text-xs" style={{ color: "#ef4444" }}>
                удалить
              </button>
            </div>

            <div className="p-3 flex flex-col gap-2">
              {rule.conditions.map((condition, conditionIndex) => {
                const conditionQuestion = questionScreens.find((item) => item.id === condition.screenId) ?? questionScreens[0];
                const conditionOptions = conditionQuestion?.options ?? [];
                return (
                  <div
                    key={condition.id}
                    className="flex flex-col gap-1.5 pb-2"
                    style={{ borderBottom: conditionIndex < rule.conditions.length - 1 ? "1px dashed #dbeafe" : "none" }}
                  >
                    <div className="flex items-center gap-1.5">
                      <select
                        value={condition.screenId}
                        onChange={(event) => updateCondition(rule.id, condition.id, { screenId: event.target.value, value: [] })}
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: 6,
                          color: "#334155",
                          padding: "4px 6px",
                          fontSize: 11,
                          outline: "none",
                          flex: 1,
                        }}
                      >
                        {questionScreens.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.title || "Без заголовка"}
                          </option>
                        ))}
                      </select>

                      <select
                        value={condition.operator}
                        onChange={(event) =>
                          updateCondition(rule.id, condition.id, { operator: event.target.value as ResultCondition["operator"] })
                        }
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e2e8f0",
                          borderRadius: 6,
                          color: "#334155",
                          padding: "4px 6px",
                          fontSize: 11,
                          outline: "none",
                        }}
                      >
                        <option value="includes">выбрали</option>
                        <option value="not_includes">не выбрали</option>
                      </select>

                      <button
                        type="button"
                        onClick={() => removeCondition(rule.id, condition.id)}
                        className="text-xs px-2 py-1 rounded"
                        style={{ background: "#ffffff", color: "#ef4444", border: "1px solid #e2e8f0" }}
                      >
                        ✕
                      </button>
                    </div>

                    <div className="flex flex-wrap gap-1">
                      {conditionOptions.map((option) => {
                        const selected = condition.value.includes(option.id);
                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => toggleConditionOption(rule.id, condition.id, option.id, condition.value)}
                            className="text-[11px] px-2 py-1 rounded border"
                            style={{
                              borderColor: selected ? accent : "#e2e8f0",
                              background: selected ? `${accent}22` : "#ffffff",
                              color: selected ? accent : "#64748b",
                            }}
                          >
                            {option.emoji} {option.label || "Вариант"}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => addCondition(rule.id)}
                  className="text-xs px-2 py-1 rounded border"
                  style={{ borderColor: "#e2e8f0", color: "#334155", background: "#ffffff" }}
                >
                  + Условие
                </button>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      <button
        type="button"
        onClick={addRule}
        className="w-full rounded-xl py-2 text-xs font-bold border-2 border-dashed"
        style={{ borderColor: "#e2e8f0", color: "#475569", background: "#ffffff" }}
      >
        + Добавить правило
      </button>
    </div>
  );
}

// ─── Right Panel: Settings ────────────────────────────────────────────────────

function SettingsPanel({
  screen,
  allScreens,
  onChange,
  accent,
}: {
  screen: Screen;
  allScreens: Screen[];
  onChange: (patch: Partial<Screen>) => void;
  accent: string;
}) {
  const inputStyle = {
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    color: "#0f172a",
    padding: "8px 12px",
    fontSize: 13,
    width: "100%",
    outline: "none",
  };

  const label = (text: string) => (
    <div className="text-xs font-semibold mb-1.5 mt-4" style={{ color: "#64748b" }}>
      {text.toUpperCase()}
    </div>
  );

  const addOption = () => {
    onChange({
      options: [
        ...(screen.options ?? []),
        { id: uid(), label: "", emoji: EMOJIS[Math.floor(Math.random() * EMOJIS.length)] },
      ],
    });
  };

  const updateOption = (id: string, patch: Partial<OptionItem>) => {
    onChange({
      options: screen.options?.map(o => o.id === id ? { ...o, ...patch } : o),
    });
  };

  const removeOption = (id: string) => {
    onChange({ options: screen.options?.filter(o => o.id !== id) });
  };
  const hasBranching = Boolean(
    (screen.options || []).some((option) => option.nextScreenId || option.nextSpecial),
  );

  return (
    <div className="flex flex-col gap-0 overflow-y-auto h-full" style={{ color: "#0f172a" }}>
      {/* Screen header info */}
      <div
        className="px-4 py-3 border-b text-xs font-bold"
        style={{ borderColor: "#e2e8f0", color: "#64748b" }}
      >
        {({ intro: "⚡ ОБЛОЖКА", question: "❓ ВОПРОС", lead: "✉ КОНТАКТЫ", result: "✓ ФИНАЛ" })[screen.kind]}
      </div>

      <div className="px-4 pb-6">
        {/* Title */}
        {label("Заголовок")}
        <textarea
          value={screen.title}
          onChange={e => onChange({ title: e.target.value })}
          rows={2}
          style={{ ...inputStyle, resize: "none", lineHeight: 1.5 }}
          placeholder="Введите заголовок..."
        />

        {/* Subtitle */}
        {label("Подзаголовок")}
        <textarea
          value={screen.subtitle}
          onChange={e => onChange({ subtitle: e.target.value })}
          rows={2}
          style={{ ...inputStyle, resize: "none", lineHeight: 1.5 }}
          placeholder="Дополнительный текст..."
        />

        {/* Question type selector */}
        {screen.kind === "question" && (
          <>
            {label("Тип вопроса")}
            <div className="grid grid-cols-2 gap-1.5">
              {QUESTION_TYPES.map(qt => (
                <motion.button
                  key={qt.type}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => onChange({ questionType: qt.type })}
                  className="text-left rounded-lg p-2.5 border transition-colors cursor-pointer"
                  style={{
                    borderColor: screen.questionType === qt.type ? accent : "#e2e8f0",
                    background: screen.questionType === qt.type ? `${accent}18` : "#ffffff",
                    color: screen.questionType === qt.type ? "#fff" : "#64748b",
                  }}
                >
                  <div className="text-base mb-0.5">{qt.icon}</div>
                  <div className="text-xs font-semibold">{qt.label}</div>
                </motion.button>
              ))}
            </div>
          </>
        )}

        {/* Options (single/multiple) */}
        {screen.kind === "question" && (screen.questionType === "single" || screen.questionType === "multiple") && (
          <>
            <div className="flex items-center justify-between mt-4">
              <div className="text-xs font-semibold" style={{ color: "#64748b" }}>
                ВАРИАНТЫ ОТВЕТОВ
              </div>
              {hasBranching ? (
                <span
                  className="text-[10px] font-bold px-2 py-1 rounded-full"
                  style={{ background: `${accent}22`, color: accent }}
                >
                  ⚡ Ветвление активно
                </span>
              ) : null}
            </div>
            <AnimatePresence>
              {screen.options?.map((opt, i) => (
                <motion.div
                  key={opt.id}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-2"
                >
                  <div className="flex items-center gap-2">
                    {/* Emoji picker — Radix Popover */}
                    <Popover.Root>
                      <Popover.Trigger asChild>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.92 }}
                          className="w-8 h-8 rounded-lg text-base flex items-center justify-center cursor-pointer flex-shrink-0 select-none"
                          style={{ background: "#f1f5f9" }}
                          title="Выбрать иконку"
                        >
                          {opt.emoji}
                        </motion.button>
                      </Popover.Trigger>

                      <Popover.Portal>
                        <Popover.Content
                          side="bottom"
                          align="start"
                          sideOffset={6}
                          style={{
                            zIndex: 9999,
                            background: "#ffffff",
                            border: "1px solid #e2e8f0",
                            borderRadius: 14,
                            padding: 10,
                            display: "grid",
                            gridTemplateColumns: "repeat(5, 1fr)",
                            gap: 4,
                            width: 172,
                            maxHeight: 240,
                            overflowY: "auto",
                            boxShadow: "0 16px 48px rgba(0,0,0,0.7)",
                            outline: "none",
                          }}
                          onOpenAutoFocus={e => e.preventDefault()}
                        >
                          {EMOJIS.map(e => (
                            <Popover.Close key={e} asChild>
                              <motion.button
                                whileHover={{ scale: 1.2, background: "#f1f5f9" }}
                                whileTap={{ scale: 0.9 }}
                                onClick={() => updateOption(opt.id, { emoji: e })}
                                className="w-7 h-7 rounded-lg text-sm flex items-center justify-center cursor-pointer"
                                style={{
                                  background: opt.emoji === e ? "#f1f5f9" : "transparent",
                                  outline: opt.emoji === e ? `1.5px solid ${accent}` : "none",
                                }}
                              >
                                {e}
                              </motion.button>
                            </Popover.Close>
                          ))}

                          <Popover.Arrow style={{ fill: "#ffffff" }} />
                        </Popover.Content>
                      </Popover.Portal>
                    </Popover.Root>

                    <input
                      value={opt.label}
                      onChange={e => updateOption(opt.id, { label: e.target.value })}
                      placeholder={`Вариант ${i + 1}`}
                      style={{ ...inputStyle, flex: 1 }}
                    />
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={() => removeOption(opt.id)}
                      className="w-7 h-7 rounded-lg flex items-center justify-center text-xs flex-shrink-0 cursor-pointer"
                      style={{ background: "#f1f5f9", color: "#ef4444" }}
                    >
                      ✕
                    </motion.button>
                  </div>
                  <NextScreenSelect
                    value={{ nextScreenId: opt.nextScreenId, nextSpecial: opt.nextSpecial }}
                    onChange={(target) => {
                      updateOption(opt.id, {
                        nextScreenId: target.nextScreenId,
                        nextSpecial: target.nextSpecial,
                      });
                    }}
                    screens={allScreens}
                    currentScreenId={screen.id}
                    accent={accent}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
            <motion.button
              whileHover={{ scale: 1.02, y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={addOption}
              className="mt-1 w-full rounded-xl py-2 text-xs font-bold border-2 border-dashed cursor-pointer transition-colors"
              style={{ borderColor: "#e2e8f0", color: "#475569" }}
            >
              + Добавить вариант
            </motion.button>
          </>
        )}

        {/* Rating settings */}
        {screen.kind === "question" && screen.questionType === "rating" && (
          <>
            {label("Максимум звёзд")}
            <div className="flex gap-2">
              {[3, 5, 7, 10].map(n => (
                <motion.button
                  key={n}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => onChange({ maxRating: n })}
                  className="flex-1 rounded-lg py-1.5 text-sm font-bold cursor-pointer transition-colors"
                  style={{
                    background: (screen.maxRating ?? 5) === n ? accent : "#ffffff",
                    border: `1px solid ${(screen.maxRating ?? 5) === n ? accent : "#e2e8f0"}`,
                    color: (screen.maxRating ?? 5) === n ? "#fff" : "#64748b",
                  }}
                >
                  {n}
                </motion.button>
              ))}
            </div>
          </>
        )}

        {/* Text placeholder */}
        {screen.kind === "question" && screen.questionType === "text" && (
          <>
            {label("Подсказка в поле")}
            <input
              value={screen.placeholder ?? ""}
              onChange={e => onChange({ placeholder: e.target.value })}
              placeholder="Введите ваш ответ..."
              style={inputStyle}
            />
          </>
        )}

        {/* Slider settings */}
        {screen.kind === "question" && screen.questionType === "slider" && (
          <>
            {label("Диапазон значений")}
            <div className="flex gap-2">
              <div className="flex-1">
                <div className="text-xs mb-1" style={{ color: "#64748b" }}>Мин</div>
                <input
                  type="number"
                  value={screen.minVal ?? 0}
                  onChange={e => onChange({ minVal: +e.target.value })}
                  style={inputStyle}
                />
              </div>
              <div className="flex-1">
                <div className="text-xs mb-1" style={{ color: "#64748b" }}>Макс</div>
                <input
                  type="number"
                  value={screen.maxVal ?? 100}
                  onChange={e => onChange({ maxVal: +e.target.value })}
                  style={inputStyle}
                />
              </div>
            </div>
          </>
        )}

        {/* Required toggle */}
        {screen.kind === "question" && (
          <>
            {label("Обязательный")}
            <div className="flex items-center gap-3">
              <motion.button
                onClick={() => onChange({ required: !screen.required })}
                className="relative w-10 h-5 rounded-full cursor-pointer flex-shrink-0"
                style={{ background: screen.required ? accent : "#cbd5e1" }}
              >
                <motion.div
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white"
                  animate={{ left: screen.required ? "calc(100% - 18px)" : 2 }}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              </motion.button>
              <span className="text-xs" style={{ color: "#64748b" }}>
                {screen.required ? "Нельзя пропустить" : "Можно пропустить"}
              </span>
            </div>
          </>
        )}

        {screen.kind === "result" && (
          <>
            {label("Результат по умолчанию")}
            <div className="flex items-center gap-3 mb-4">
              <motion.button
                onClick={() => onChange({ isDefaultResult: !screen.isDefaultResult })}
                className="relative w-10 h-5 rounded-full cursor-pointer flex-shrink-0"
                style={{ background: screen.isDefaultResult ? accent : "#cbd5e1" }}
              >
                <motion.div
                  className="absolute top-0.5 w-4 h-4 rounded-full bg-white"
                  animate={{ left: screen.isDefaultResult ? "calc(100% - 18px)" : 2 }}
                  transition={{ type: "spring", stiffness: 500, damping: 30 }}
                />
              </motion.button>
              <span className="text-xs" style={{ color: "#64748b" }}>
                {screen.isDefaultResult ? "Да, fallback" : "Нет"}
              </span>
            </div>

            {label("Правила показа")}
            <ResultRulesBuilder
              screen={screen}
              allScreens={allScreens}
              onChange={onChange}
              accent={accent}
            />
          </>
        )}
      </div>
    </div>
  );
}

// ─── Add Screen Modal ─────────────────────────────────────────────────────────

function AddScreenModal({
  onAdd,
  onClose,
}: {
  onAdd: (type: QuestionType) => void;
  onClose: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0, y: 16 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.9, opacity: 0, y: 16 }}
        transition={{ type: "spring", stiffness: 400, damping: 30 }}
        className="rounded-2xl p-6 w-full max-w-sm"
        style={{ background: "#ffffff", border: "1px solid #e2e8f0" }}
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-slate-900 font-bold mb-1">Добавить экран</h3>
        <p className="text-xs mb-5" style={{ color: "#64748b" }}>Выберите тип вопроса</p>
        <div className="grid grid-cols-2 gap-2">
          {QUESTION_TYPES.map(qt => (
            <motion.button
              key={qt.type}
              whileHover={{ scale: 1.03, y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => { onAdd(qt.type); onClose(); }}
              className="text-left rounded-xl p-3 border cursor-pointer"
              style={{ border: "1px solid #e2e8f0", background: "#ffffff" }}
            >
              <div className="text-xl mb-1">{qt.icon}</div>
              <div className="text-sm font-semibold text-slate-900">{qt.label}</div>
              <div className="text-xs mt-0.5" style={{ color: "#64748b" }}>{qt.desc}</div>
            </motion.button>
          ))}
        </div>
        <motion.button
          whileHover={{ scale: 1.01 }}
          onClick={onClose}
          className="mt-4 w-full text-center text-sm py-2 rounded-xl cursor-pointer"
          style={{ color: "#64748b", background: "#ffffff", border: "1px solid #e2e8f0" }}
        >
          Отмена
        </motion.button>
      </motion.div>
    </motion.div>
  );
}

// ─── Main Builder ─────────────────────────────────────────────────────────────

export function QuizBuilder() {
  const router = useRouter();
  const [quizId, setQuizId] = useState<number | null>(null);
  const [screens, setScreens] = useState<Screen[]>(defaultScreens);
  const [activeId, setActiveId] = useState<string>(screens[0].id);
  const [showAddModal, setShowAddModal] = useState(false);
  const [quizTitle, setQuizTitle] = useState("Мой первый квиз");
  const [accentColor, setAccentColor] = useState(ACCENT);
  const [isPublished, setIsPublished] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);

  const activeScreen = screens.find(s => s.id === activeId) ?? screens[0];
  const questionScreens = screens.filter(s => s.kind === "question");

  const updateScreen = useCallback((id: string, patch: Partial<Screen>) => {
    setScreens((prev) => {
      if (patch.isDefaultResult) {
        return prev.map((screen) => {
          if (screen.kind !== "result") return screen;
          if (screen.id === id) return { ...screen, ...patch, isDefaultResult: true };
          return { ...screen, isDefaultResult: false };
        });
      }
      return prev.map((screen) => (screen.id === id ? { ...screen, ...patch } : screen));
    });
  }, []);

  const addQuestion = (type: QuestionType) => {
    const newScreen: Screen = {
      id: uid(),
      kind: "question",
      title: "Новый вопрос",
      subtitle: "",
      questionType: type,
      options: (type === "single" || type === "multiple") ? [
        { id: uid(), label: "Вариант 1", emoji: "📈" },
        { id: uid(), label: "Вариант 2", emoji: "🎯" },
      ] : undefined,
      maxRating: type === "rating" ? 5 : undefined,
      minVal: type === "slider" ? 0 : undefined,
      maxVal: type === "slider" ? 100 : undefined,
      required: false,
    };
    // Insert before "lead" screen
    setScreens(prev => {
      const leadIdx = prev.findIndex(s => s.kind === "lead");
      const arr = [...prev];
      arr.splice(leadIdx === -1 ? arr.length - 1 : leadIdx, 0, newScreen);
      return arr;
    });
    setActiveId(newScreen.id);
  };

  const deleteScreen = (id: string) => {
    setScreens(prev => {
      const next = prev.filter(s => s.id !== id);
      if (activeId === id) setActiveId(next[0]?.id ?? "");
      return next;
    });
  };

  const loadQuiz = useCallback(async () => {
    setIsLoading(true);
    try {
      const payload = await quizBuilderApi.getCurrent();
      const loadedScreens: Screen[] = Array.isArray(payload.screens) && payload.screens.length > 0
        ? payload.screens.map((screen, index) => ({
            id: String(screen.id ?? `${index}-${uid()}`),
            kind: screen.kind,
            title: screen.title || "",
            subtitle: screen.subtitle || "",
            questionType: screen.questionType || undefined,
            options: Array.isArray(screen.options)
              ? screen.options.map((option, optionIndex) => ({
                  id: String(option.id ?? `${index}-${optionIndex}-${uid()}`),
                  label: option.label || "",
                  emoji: option.emoji || "",
                  nextScreenId: option.nextScreenId != null ? String(option.nextScreenId) : undefined,
                  nextSpecial: option.nextSpecial || undefined,
                }))
              : undefined,
            placeholder: screen.placeholder || undefined,
            minVal: typeof screen.minVal === "number" ? screen.minVal : undefined,
            maxVal: typeof screen.maxVal === "number" ? screen.maxVal : undefined,
            maxRating: typeof screen.maxRating === "number" ? screen.maxRating : undefined,
            required: Boolean(screen.required),
            isDefaultResult: Boolean(screen.isDefaultResult),
            rules: Array.isArray(screen.rules)
              ? screen.rules.map((rule, ruleIndex) => ({
                  id: String(rule.id ?? `${index}-rule-${ruleIndex}-${uid()}`),
                  conditions: Array.isArray(rule.conditions)
                    ? rule.conditions.map((condition, conditionIndex) => ({
                        id: String(condition.id ?? `${index}-rule-${ruleIndex}-cond-${conditionIndex}-${uid()}`),
                        screenId: String(condition.screenId ?? ""),
                        operator: condition.operator || "includes",
                        value: Array.isArray(condition.value) ? condition.value.map((item) => String(item)) : [],
                      }))
                    : [],
                }))
              : [],
          }))
        : defaultScreens();

      setQuizTitle(payload.title || "Мой квиз");
      setQuizId(Number(payload.id) || null);
      setAccentColor(payload.accentColor || ACCENT);
      setIsPublished(Boolean(payload.isPublished));
      setScreens(loadedScreens);
      setActiveId(loadedScreens[0]?.id || "");
    } catch (error) {
      toast.error("Не удалось загрузить квиз");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQuiz();
  }, [loadQuiz]);

  const buildSavePayload = useCallback((nextPublished: boolean = isPublished) => {
    const resultScreens = screens.filter((screen) => screen.kind === "result");
    const explicitDefaultResultId =
      resultScreens.find((screen) => Boolean(screen.isDefaultResult))?.id ??
      resultScreens[resultScreens.length - 1]?.id;

    return {
      title: quizTitle.trim() || "Мой квиз",
      accentColor,
      isPublished: nextPublished,
      screens: screens.map((screen) => ({
        id: screen.id,
        kind: screen.kind,
        title: screen.title || "",
        subtitle: screen.subtitle || "",
        questionType: screen.kind === "question" ? screen.questionType || null : null,
        options:
          screen.kind === "question" && (screen.questionType === "single" || screen.questionType === "multiple")
            ? (screen.options || []).map((option) => ({
                id: option.id,
                label: option.label || "",
                emoji: option.emoji || "",
                nextScreenId: option.nextSpecial ? null : option.nextScreenId || null,
                nextSpecial: option.nextSpecial || null,
              }))
            : [],
        placeholder: screen.placeholder || null,
        minVal: screen.minVal ?? null,
        maxVal: screen.maxVal ?? null,
        maxRating: screen.maxRating ?? null,
        required: Boolean(screen.required),
        isDefaultResult: screen.kind === "result" && screen.id === explicitDefaultResultId,
        rules:
          screen.kind === "result"
            ? (screen.rules || []).map((rule, ruleIndex) => ({
                id: rule.id,
                position: ruleIndex,
                conditions: (rule.conditions || []).map((condition, conditionIndex) => ({
                  id: condition.id,
                  screenId: condition.screenId,
                  operator: condition.operator,
                  value: Array.isArray(condition.value) ? condition.value : [],
                  position: conditionIndex,
                })),
              }))
            : [],
      })),
    };
  }, [accentColor, isPublished, quizTitle, screens]);

  const saveQuiz = useCallback(async () => {
    setIsSaving(true);
    try {
      const saved = await quizBuilderApi.saveCurrent(buildSavePayload());
      setQuizId(Number(saved.id) || null);
      setIsPublished(Boolean(saved.isPublished));
      toast.success("Квиз сохранен");
    } catch (error) {
      toast.error("Не удалось сохранить квиз");
    } finally {
      setIsSaving(false);
    }
  }, [buildSavePayload]);

  const handleTogglePublish = useCallback(async () => {
    const prevPublished = isPublished;
    const nextPublished = !prevPublished;
    setIsPublished(nextPublished);
    setIsSaving(true);
    try {
      const saved = await quizBuilderApi.saveCurrent(buildSavePayload(nextPublished));
      setQuizId(Number(saved.id) || null);
      setIsPublished(Boolean(saved.isPublished));
      toast.success(saved.isPublished ? "Квиз опубликован" : "Квиз снят с публикации");
    } catch (error) {
      setIsPublished(prevPublished);
      toast.error("Не удалось изменить статус публикации");
    } finally {
      setIsSaving(false);
    }
  }, [buildSavePayload, isPublished]);

  const COLORS = ["#5b5ef4","#ec4899","#10b981","#f59e0b","#3b82f6","#8b5cf6","#ef4444","#06b6d4"];
  const publicQuizPath = quizId ? `/quiz/${quizId}` : null;
  const publicQuizUrl = typeof window !== "undefined" && publicQuizPath ? `${window.location.origin}${publicQuizPath}` : publicQuizPath;

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-white text-slate-900">
        Загрузка конструктора...
      </div>
    );
  }

  return (
    <div
      className="flex flex-col"
      style={{
        height: "100vh",
        background: "#f8fafc",
        fontFamily: "'DM Sans', 'Inter', sans-serif",
        overflow: "hidden",
      }}
    >
      {/* ── TOP NAV ── */}
      <div
        className="flex items-center justify-between px-4 flex-shrink-0"
        style={{
          height: 52,
          borderBottom: "1px solid #e2e8f0",
          background: "#ffffff",
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/settings?tab=site")}
            className="px-2 py-1 rounded-lg text-xs font-semibold cursor-pointer border"
            style={{ borderColor: "#e2e8f0", background: "#ffffff", color: "#475569" }}
          >
            ← Назад
          </button>
          <input
            value={quizTitle}
            onChange={e => setQuizTitle(e.target.value)}
            className="text-sm font-semibold outline-none bg-transparent"
            style={{ color: "#0f172a", minWidth: 120 }}
          />
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "#f1f5f9", color: "#64748b" }}>
            {questionScreens.length} {questionScreens.length === 1 ? "вопрос" : questionScreens.length < 5 ? "вопроса" : "вопросов"}
          </span>
        </div>

        {/* Center: color swatches */}
        <div className="flex items-center gap-1.5">
          {COLORS.map(c => (
            <motion.button
              key={c}
              whileHover={{ scale: 1.2 }}
              whileTap={{ scale: 0.9 }}
              onClick={() => setAccentColor(c)}
              className="rounded-full cursor-pointer"
              style={{
                width: 18, height: 18,
                background: c,
                outline: accentColor === c ? `2px solid ${c}` : "none",
                outlineOffset: 2,
              }}
            />
          ))}
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => setPreviewMode(p => !p)}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border"
            style={{
              borderColor: previewMode ? accentColor : "#e2e8f0",
              background: previewMode ? `${accentColor}18` : "transparent",
              color: previewMode ? accentColor : "#64748b",
            }}
          >
            {previewMode ? "← Редактор" : "Просмотр →"}
          </motion.button>
	          <motion.button
	            whileHover={{ scale: 1.03, y: -1 }}
	            whileTap={{ scale: 0.97 }}
	            onClick={() => void handleTogglePublish()}
	            className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border"
	            style={{
	              borderColor: isPublished ? "#10b981" : "#64748b",
	              background: isPublished ? "#10b98122" : "transparent",
	              color: isPublished ? "#10b981" : "#64748b",
                opacity: isSaving ? 0.7 : 1,
	            }}
              disabled={isSaving}
	          >
	            {isPublished ? "Снять с публикации" : "Опубликовать черновик"}
	          </motion.button>
	          <motion.button
	            whileHover={{ scale: 1.03, y: -1 }}
	            whileTap={{ scale: 0.97 }}
	            onClick={() => void saveQuiz()}
	            className="px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer"
	            style={{ background: "#0ea5e9", color: "#fff", opacity: isSaving ? 0.7 : 1 }}
	            disabled={isSaving}
	          >
	            {isSaving ? "Сохраняем..." : "Сохранить"}
	          </motion.button>
            {publicQuizUrl ? (
              <>
                <motion.button
                  whileHover={{ scale: 1.03, y: -1 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => {
                    navigator.clipboard.writeText(publicQuizUrl).then(
                      () => toast.success("Ссылка на квиз скопирована"),
                      () => toast.error("Не удалось скопировать ссылку"),
                    );
                  }}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border"
                  style={{
                    borderColor: "#64748b",
                    background: "transparent",
                    color: "#334155",
                  }}
                >
                  Копировать ссылку
                </motion.button>
                {isPublished ? (
                  <motion.button
                    whileHover={{ scale: 1.06, y: -1 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => window.open(publicQuizUrl, "_blank", "noopener,noreferrer")}
                    className="w-8 h-8 rounded-lg text-sm font-bold cursor-pointer border flex items-center justify-center"
                    style={{
                      borderColor: "#64748b",
                      background: "transparent",
                      color: "#334155",
                    }}
                    title="Открыть опубликованный квиз"
                    aria-label="Открыть опубликованный квиз"
                  >
                    ↗
                  </motion.button>
                ) : null}
              </>
            ) : null}
	        </div>
	      </div>

      {/* ── EDITOR BODY ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT: Slide List ── */}
        <div
          className="flex-shrink-0 flex flex-col overflow-hidden"
          style={{
            width: 220,
            borderRight: "1px solid #e2e8f0",
            background: "#ffffff",
          }}
        >
          <div
            className="px-3 py-2 text-xs font-bold flex-shrink-0"
            style={{ color: "#64748b", borderBottom: "1px solid #e2e8f0" }}
          >
            ЭКРАНЫ
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-2 flex flex-col gap-1">
            <Reorder.Group
              axis="y"
              values={screens}
              onReorder={(reordered) => {
                // Keep intro first and result/lead last
                const intro = reordered.find(s => s.kind === "intro");
                const lead = reordered.find(s => s.kind === "lead");
                const result = reordered.find(s => s.kind === "result");
                const questions = reordered.filter(s => s.kind === "question");
                setScreens([
                  ...(intro ? [intro] : []),
                  ...questions,
                  ...(lead ? [lead] : []),
                  ...(result ? [result] : []),
                ]);
              }}
              style={{ display: "flex", flexDirection: "column", gap: 4, listStyle: "none", padding: 0, margin: 0 }}
            >
              {screens.map((screen, i) => (
                <Reorder.Item
                  key={screen.id}
                  value={screen}
                  dragListener={screen.kind === "question"}
                  style={{ cursor: screen.kind === "question" ? "grab" : "default" }}
                >
                  <SlideThumbnail
                    screen={screen}
                    index={i}
                    isActive={activeId === screen.id}
                    onClick={() => setActiveId(screen.id)}
                    onDelete={() => deleteScreen(screen.id)}
                  />
                </Reorder.Item>
              ))}
            </Reorder.Group>
          </div>

          {/* Add screen button */}
          <div className="p-2 flex-shrink-0" style={{ borderTop: "1px solid #e2e8f0" }}>
            <motion.button
              whileHover={{ scale: 1.02, y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setShowAddModal(true)}
              className="w-full rounded-xl py-2 text-xs font-bold border-2 border-dashed cursor-pointer flex items-center justify-center gap-1.5"
              style={{ borderColor: accentColor + "44", color: accentColor, background: `${accentColor}08` }}
            >
              <span className="text-base leading-none">+</span>
              Добавить экран
            </motion.button>
          </div>
        </div>

        {/* ── CENTER: Preview ── */}
        <div
          className="flex-1 flex items-center justify-center overflow-auto p-8"
          style={{ background: "#f8fafc" }}
        >
          {/* Dot grid bg */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: `radial-gradient(circle, #e2e8f0 1px, transparent 1px)`,
              backgroundSize: "28px 28px",
              opacity: 0.4,
            }}
          />

          <AnimatePresence mode="wait">
            <motion.div
              key={activeScreen.id + (previewMode ? "-preview" : "-edit")}
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.97 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className="relative z-10 w-full"
              style={{ maxWidth: 480 }}
            >
              {/* Device chrome */}
              <div
                className="rounded-3xl overflow-hidden"
                style={{
                  boxShadow: `0 0 0 1px #e2e8f0, 0 0 60px ${accentColor}18, 0 20px 40px rgba(15,23,42,0.12)`,
                }}
              >
                {/* Status bar mock */}
                <div
                  className="flex justify-between items-center px-5 py-2 text-xs"
                  style={{ background: "#ffffff", color: "#64748b" }}
                >
                  <span>9:41</span>
                  <div
                    className="h-4 w-24 rounded-full"
                    style={{ background: "#e2e8f0", margin: "0 auto" }}
                  />
                  <span>●●●</span>
                </div>

                <ScreenPreview screen={activeScreen} accent={accentColor} interactive={previewMode} />
              </div>

              {/* Step indicator below */}
              <div className="flex justify-center gap-1.5 mt-4">
                {screens.map(s => (
                  <motion.div
                    key={s.id}
                    onClick={() => setActiveId(s.id)}
                    className="rounded-full cursor-pointer transition-all"
                    style={{
                      width: s.id === activeId ? 20 : 6,
                      height: 6,
                      background: s.id === activeId ? accentColor : "#cbd5e1",
                    }}
                  />
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* ── RIGHT: Settings ── */}
        <AnimatePresence>
          {!previewMode && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="flex-shrink-0 overflow-hidden"
              style={{ borderLeft: "1px solid #e2e8f0", background: "#ffffff" }}
            >
              <div
                className="w-full h-full overflow-hidden"
                style={{ width: 260 }}
              >
                <SettingsPanel
                  screen={activeScreen}
                  allScreens={screens}
                  onChange={patch => updateScreen(activeScreen.id, patch)}
                  accent={accentColor}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── BOTTOM STATUS BAR ── */}
      <div
        className="flex items-center justify-between px-4 py-1.5 text-xs flex-shrink-0"
        style={{ borderTop: "1px solid #e2e8f0", background: "#ffffff", color: "#64748b" }}
      >
        <span>
          {screens.findIndex(s => s.id === activeId) + 1} / {screens.length} экранов
        </span>
        <span style={{ color: accentColor }}>
          ● Вопросов: {questionScreens.length}
        </span>
        <span>
          Перетащите вопросы для сортировки
        </span>
      </div>

      {/* ── ADD MODAL ── */}
      <AnimatePresence>
        {showAddModal && (
          <AddScreenModal
            onAdd={addQuestion}
            onClose={() => setShowAddModal(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default QuizBuilder;
