"use client";

import { useState } from "react";
import Link from "next/link";
import { Manrope, Merriweather } from "next/font/google";

const dmSans = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-dm-sans",
  weight: ["400", "500", "700"],
});

const playfair = Merriweather({
  subsets: ["latin", "cyrillic"],
  variable: "--font-playfair",
  weight: ["400", "700"],
});

const painPoints = [
  {
    title: "Сильная встреча быстро выветривается",
    body:
      "Через несколько дней клиент уже не держит в голове ключевые выводы. Если результат не зафиксирован, следующая сессия снова начинается с восстановления контекста.",
  },
  {
    title: "Вы становитесь администратором процесса",
    body:
      "Напоминания, догоняющие сообщения и ручной сбор статусов съедают время. Вместо работы по сути вы держите клиента в тонусе вручную.",
  },
  {
    title: "История клиента живет в разных местах",
    body:
      "Telegram, заметки, документы и память. Когда единая картина не собрана, глубина работы падает, а повторяющиеся паттерны остаются незаметными.",
  },
  {
    title: "Работу легко обесценить",
    body:
      "Если клиент не видит, что именно изменилось за месяц, ценность работы воспринимается как настроение после сессии. Видимый прогресс делает результат доказуемым.",
  },
];

const steps = [
  {
    title: "Добавляете клиента",
    body:
      "У клиента появляется свое пространство с задачами, заметками и историей движения. Уже с первой встречи процесс становится прозрачным.",
  },
  {
    title: "После сессии фиксируете суть",
    body:
      "Инсайты, договоренности и следующие шаги собираются в одном месте. Клиент видит, что делать дальше и зачем это важно.",
  },
  {
    title: "Перед следующей встречей открываете карточку",
    body:
      "За полминуты видно, что выполнено, где был сдвиг и что тормозит клиента. На сессию вы приходите уже в контексте.",
  },
];

const features = [
  {
    icon: "01",
    title: "Карточка клиента",
    body:
      "Сессии, договоренности, повторяющиеся темы и важные наблюдения хранятся в одном месте. Контекст не теряется между встречами.",
  },
  {
    icon: "02",
    title: "Кабинет клиента",
    body:
      "Клиент видит свои задачи, выводы и шаги. Он не выпадает из процесса и приходит на встречу не из пустоты, а из реального движения.",
  },
  {
    icon: "03",
    title: "Трекер прогресса",
    body:
      "Путь клиента становится видимым: что было сделано, какие инсайты закрепились, где произошел сдвиг. Вашу работу сложнее обесценить, когда результат виден.",
  },
  {
    icon: "04",
    title: "Ритуалы и программы",
    body:
      "Задачи, оплаты, этапы программы и подготовка к встречам живут в одной системе. Процесс не расползается по чатам и таблицам.",
  },
];

const coachStats = [
  { label: "Активных клиентов", value: "12", note: "+2 в этом месяце" },
  { label: "Выполнено заданий", value: "78%", note: "за последние 30 дней" },
  { label: "Средний прогресс", value: "+34%", note: "по всем клиентам" },
];

const coachClients = [
  { initials: "МК", name: "Михаил К.", focus: "Карьерный рост", status: "Завтра", tone: "blue" },
  { initials: "ОС", name: "Ольга С.", focus: "Уверенность в себе", status: "Прорыв", tone: "green" },
  { initials: "ДН", name: "Дмитрий Н.", focus: "Баланс жизни", status: "Новый", tone: "gold" },
  { initials: "АЛ", name: "Алина Л.", focus: "Отношения", status: "Сегодня", tone: "indigo" },
];

const progressTracks = [
  { label: "Уверенность", value: 82, tone: "green" },
  { label: "Коммуникация", value: 71, tone: "violet" },
  { label: "Границы", value: 58, tone: "orange" },
  { label: "Цели и фокус", value: 90, tone: "blue" },
];

const weeklyTasks = [
  { text: "Ольга · Утренний ритуал x5", done: true },
  { text: "Ольга · Разговор с руководителем", done: true },
  { text: "Михаил · Обновить резюме", done: false },
  { text: "Дмитрий · Колесо жизни", done: false },
];

const recentSessions = [
  { title: "Сессия 14 · 12 марта 2026", note: "Разговор с руководством — прорыв" },
  { title: "Сессия 13 · 26 февраля 2026", note: "Работа с внутренним критиком" },
  { title: "Сессия 12 · 12 февраля 2026", note: "Выстраивание границ в коллективе" },
];

const interfaceModules = [
  {
    title: "Для коуча",
    items: [
      "дашборд со всеми клиентами, ближайшими сессиями и статусами заданий",
      "заметки по каждой встрече и история сопровождения",
      "шаблоны вопросов, упражнений и следующих шагов",
      "аналитика эффективности и видимый сдвиг по клиентам",
    ],
  },
  {
    title: "Для клиента",
    items: [
      "личный кабинет с прогрессом и понятным следующим шагом",
      "журнал рефлексии и фиксация инсайтов между сессиями",
      "чеклист заданий и материалов",
      "оценка состояния перед встречей и по ходу работы",
    ],
  },
  {
    title: "Визуализация",
    items: [
      "линейные графики роста по компетенциям во времени",
      "радарный профиль клиента на текущем этапе",
      "карта активности по выполнению заданий и ритму работы",
      "milestone-метки вроде «первый прорыв» и «цель достигнута»",
    ],
  },
  {
    title: "Совместная работа",
    items: [
      "коуч и клиент смотрят на один процесс, но с разными правами доступа",
      "можно вести внутренние заметки коуча отдельно от того, что видит клиент",
      "клиенту открываются только задания, прогресс, материалы и понятные выводы",
      "ценность сопровождения становится общей, видимой реальностью, а не пересказом после сессии",
    ],
  },
];

const scaleItems = [
  { value: "10", label: "клиентов", sub: "Еще можно держать в голове. Недолго." },
  { value: "30", label: "клиентов", sub: "Контекст начинает теряться и рваться." },
  { value: "50+", label: "клиентов с системой", sub: "Каждый клиент остается в процессе спокойно.", accent: true },
];

const testimonials = [
  {
    quote:
      "Когда клиент стал видеть историю своей работы, ушли разговоры в духе «кажется, мы стоим на месте». Теперь у нас есть факты, а не ощущения.",
    name: "Мария К.",
    role: "Коуч по личной эффективности",
    initial: "М",
  },
  {
    quote:
      "Раньше часть ценности просто растворялась между встречами. Сейчас клиент открывает кабинет и видит, сколько уже сделано. Это сильно меняет удержание.",
    name: "Иван Р.",
    role: "Психолог, частная практика",
    initial: "И",
  },
];

const faqs = [
  {
    question: "У меня уже есть ChatGPT. Зачем еще одна система?",
    answer:
      "ChatGPT отвечает на запрос. Но он не ведет клиента между встречами, не хранит его историю и не показывает прогресс как целостный путь. Здесь фокус не на генерации текста, а на ведении процесса.",
  },
  {
    question: "Это сложная CRM, которую нужно долго настраивать?",
    answer:
      "Нет. Система сделана под работу специалиста с клиентом, а не под отдел продаж. Вы можете завести первого клиента и начать вести процесс без длинной настройки.",
  },
  {
    question: "У меня пока немного клиентов. Не рано?",
    answer:
      "Наоборот. Чем раньше вы строите процесс на системе, тем меньше хаоса потом. Гораздо проще выстроить прозрачную практику с несколькими клиентами, чем переносить в нее десятки историй позже.",
  },
  {
    question: "Почему акцент на прогрессе так важен?",
    answer:
      "Потому что без видимого трека клиент оценивает работу по последнему ощущению. Когда изменения, задачи и результаты собраны в одном месте, ценность вашей работы становится очевидной и для вас, и для клиента.",
  },
  {
    question: "Кому это подойдет?",
    answer:
      "Коучам, психологам, консультантам, менторам и всем, кто ведет клиентов в длительном процессе один на один. Если ваша работа строится на регулярных встречах, система снимает с вас административную часть и усиливает глубину работы.",
  },
];

export default function Landing() {
  const [openFaq, setOpenFaq] = useState<number>(0);

  return (
    <div className={`${dmSans.variable} ${playfair.variable} landing-shell`}>
      <nav className="landing-nav">
        <div className="nav-logo">
          Fibo<span>n</span>atty
        </div>
        <div className="nav-actions">
          <Link href="/features" className="nav-link">
            Возможности
          </Link>
          <a href="#how" className="nav-link">
            Как это работает
          </a>
          <Link href="/login" className="nav-cta">
            Вход в систему
          </Link>
        </div>
      </nav>

      <main>
        <section className="hero-section">
          <div className="hero-bg" />
          <div className="container hero-inner">
            <div className="fade-up hero-copy">
              <div className="hero-tag">Для специалистов с длительной клиентской работой</div>
              <h1>
                Работу сложно <em>обесценить</em>,
                <br />
                когда клиент
                <br />
                видит свой прогресс
              </h1>
              <p className="hero-sub">
                После каждой встречи клиент получает ясные шаги, фиксирует инсайты и видит, как движется вперед.
                <strong> Ваша ценность подтверждается не обещанием изменений, а видимой историей результатов.</strong>
              </p>
              <div className="cta-group">
                <Link href="/login" className="btn-primary">
                  Попробовать с первым клиентом
                </Link>
                <Link href="/features" className="btn-ghost">
                  <span>▶</span>
                  Смотреть возможности
                </Link>
              </div>
              <p className="hero-micro">Без карты. Без лишней настройки. Эффект заметен уже на следующей встрече.</p>
            </div>

            <div className="hero-visual">
              <div className="floating-badge">Прогресс клиента виден</div>
              <div className="client-card fade-up" style={{ animationDelay: "120ms" }}>
                <div className="card-header">
                  <div className="avatar">А</div>
                  <div>
                    <div className="card-name">Анна Соколова</div>
                    <div className="card-meta">Сессия 7 · 6 недель в работе</div>
                  </div>
                  <div className="card-badge">В процессе</div>
                </div>

                <div className="card-insight">
                  <div className="insight-label">Сдвиг недели</div>
                  <div className="insight-text">
                    Провела сложный разговор с руководителем и впервые не ушла в избегание после конфликта.
                  </div>
                </div>

                <div className="progress-box">
                  <div>
                    <div className="progress-label">Прогресс программы</div>
                    <div className="progress-value">8 из 10 шагов завершены</div>
                  </div>
                  <div className="progress-chip">3 видимых результата</div>
                </div>
                <div className="progress-bar">
                  <span />
                </div>

                <div className="card-tasks">
                  <div className="task-item">
                    <div className="task-check done">✓</div>
                    <span>Подготовила разговор о повышении</span>
                  </div>
                  <div className="task-item">
                    <div className="task-check done">✓</div>
                    <span>Пять дней вела дневник реакций</span>
                  </div>
                  <div className="task-item">
                    <div className="task-check pending" />
                    <span className="task-muted">Собрать обратную связь от команды</span>
                  </div>
                </div>

                <div className="card-next">
                  <div>
                    <div className="next-label">Следующая встреча</div>
                    <div className="next-date">Пятница, 14:00</div>
                  </div>
                  <Link href="/login" className="next-btn">
                    Открыть
                  </Link>
                </div>
              </div>
              <div className="floating-badge secondary">
                Ценность работы подтверждается фактами, а не ощущением
              </div>
            </div>
          </div>
        </section>

        <div className="tools-strip">
          <div className="container tools-strip-inner">
            <span className="tools-label">Без системы это обычно живет в:</span>
            <div className="tools-list">
              <div className="tool-item">Notion</div>
              <div className="tool-item">Telegram</div>
              <div className="tool-item">Google Docs</div>
              <div className="tool-item">Excel</div>
              <div className="tool-item">вашей памяти</div>
            </div>
          </div>
        </div>

        <section className="section-pad pain-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Знакомо?</div>
            <h2 className="fade-up">
              Вы проводите сильную сессию.
              <br />
              <em>А потом результат становится невидимым.</em>
            </h2>
            <div className="pain-grid">
              {painPoints.map((item, index) => (
                <div key={item.title} className="pain-card fade-up" style={{ animationDelay: `${index * 80}ms` }}>
                  <div className="pain-num">{`0${index + 1}`}</div>
                  <div className="pain-title">{item.title}</div>
                  <div className="pain-body">{item.body}</div>
                </div>
              ))}
            </div>
            <div className="insight-box fade-up" style={{ animationDelay: "220ms" }}>
              <p>
                Когда прогресс клиента не собран в систему,
                <br />
                <em>ценность вашей работы ощущается как эмоция, а не как факт.</em>
              </p>
            </div>
          </div>
        </section>

        <section className="section-pad solution-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Решение</div>
            <h2 className="fade-up">
              Система, в которой
              <br />
              <em>клиент видит путь</em>
            </h2>
            <p className="section-sub fade-up">
              Не очередной чат и не просто CRM. Это рабочее пространство, где между сессиями сохраняются контекст,
              действия и реальный сдвиг клиента.
            </p>

            <div className="transform-grid fade-up" style={{ animationDelay: "120ms" }}>
              <div className="transform-side">
                <div className="transform-label before">Без системы</div>
                <div className="transform-items">
                  <div className="t-item">
                    <span className="t-icon negative">✕</span>
                    Встреча закончилась, клиент выпал из процесса
                  </div>
                  <div className="t-item">
                    <span className="t-icon negative">✕</span>
                    Инсайты теряются между сессиями
                  </div>
                  <div className="t-item">
                    <span className="t-icon negative">✕</span>
                    Перед встречей вы вручную восстанавливаете контекст
                  </div>
                  <div className="t-item">
                    <span className="t-icon negative">✕</span>
                    Ценность работы обсуждается на уровне ощущений
                  </div>
                </div>
              </div>

              <div className="transform-arrow">→</div>

              <div className="transform-side success">
                <div className="transform-label after">С системой</div>
                <div className="transform-items">
                  <div className="t-item after-item">
                    <span className="t-icon positive">✓</span>
                    Сессия переходит в понятные шаги и действия между встречами
                  </div>
                  <div className="t-item after-item">
                    <span className="t-icon positive">✓</span>
                    Клиент видит свои задачи, инсайты и изменения
                  </div>
                  <div className="t-item after-item">
                    <span className="t-icon positive">✓</span>
                    Подготовка к встрече занимает секунды, а не десятки минут
                  </div>
                  <div className="t-item after-item">
                    <span className="t-icon positive">✓</span>
                    Вашу работу сложнее обесценить, потому что прогресс виден обеим сторонам
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="section-pad how-section" id="how">
          <div className="container">
            <div className="section-eyebrow fade-up">Как это работает</div>
            <h2 className="fade-up">
              Три шага,
              <br />
              <em>и процесс становится прозрачным</em>
            </h2>
            <div className="steps-grid">
              {steps.map((step, index) => (
                <div key={step.title} className="step-card fade-up" style={{ animationDelay: `${index * 80}ms` }}>
                  <div className="step-num">{index + 1}</div>
                  <div className="step-title">{step.title}</div>
                  <div className="step-body">{step.body}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-pad features-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Возможности</div>
            <h2 className="fade-up">
              Все, что помогает
              <br />
              <em>делать работу глубже и заметнее</em>
            </h2>
            <div className="features-grid">
              {features.map((feature, index) => (
                <div key={feature.title} className="feature-card fade-up" style={{ animationDelay: `${index * 80}ms` }}>
                  <div className="feature-icon">{feature.icon}</div>
                  <div>
                    <div className="feature-title">{feature.title}</div>
                    <div className="feature-body">{feature.body}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-pad interface-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Интерфейс</div>
            <h2 className="fade-up">
              Вот как это выглядит
              <br />
              <em>в Fibonatty</em>
            </h2>
            <p className="section-sub fade-up">
              Не чужой темный шаблон, а светлый интерфейс в логике Fibonatty. Ниже показано, как выглядят экран
              коуча и экран прогресса клиента, когда история работы, задачи и динамика собраны в одной системе.
            </p>

            <div className="interface-stack">
              <div className="screen-showcase fade-up" style={{ animationDelay: "80ms" }}>
                <div className="screen-label">Экран коуча</div>
                <div className="coach-screen">
                  <aside className="coach-sidebar">
                    <div className="coach-brand">
                      Fibo<span>n</span>atty
                    </div>
                    <div className="coach-menu">
                      {["Дашборд", "Клиенты", "Сессии", "Прогресс", "Задания", "Настройки"].map((item, index) => (
                        <div key={item} className={`coach-menu-item${index === 0 ? " active" : ""}`}>
                          <span className="coach-menu-dot" />
                          {item}
                        </div>
                      ))}
                    </div>
                  </aside>

                  <div className="coach-main">
                    <div className="coach-topbar">
                      <div>
                        <div className="coach-greeting">Добрый день, Анна</div>
                        <div className="coach-caption">Все клиенты, ближайшие сессии и прогресс между встречами видны сразу.</div>
                      </div>
                      <div className="coach-day-badge">3 сессии сегодня</div>
                    </div>

                    <div className="coach-stats">
                      {coachStats.map((item) => (
                        <div key={item.label} className="coach-stat-card">
                          <div className="coach-stat-label">{item.label}</div>
                          <div className="coach-stat-value">{item.value}</div>
                          <div className="coach-stat-note">{item.note}</div>
                        </div>
                      ))}
                    </div>

                    <div className="coach-panels">
                      <div className="coach-panel">
                        <div className="panel-title">Клиенты</div>
                        <div className="coach-client-list">
                          {coachClients.map((item) => (
                            <div key={item.name} className="coach-client-row">
                              <div className={`client-avatar ${item.tone}`}>{item.initials}</div>
                              <div className="coach-client-copy">
                                <div className="coach-client-name">{item.name}</div>
                                <div className="coach-client-focus">{item.focus}</div>
                              </div>
                              <div className={`status-pill ${item.tone}`}>{item.status}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="coach-panel">
                        <div className="panel-title">Прогресс Ольги С.</div>
                        <div className="coach-progress-list">
                          {progressTracks.map((item) => (
                            <div key={item.label} className="metric-row">
                              <div className="metric-head">
                                <span>{item.label}</span>
                                <span>{item.value}%</span>
                              </div>
                              <div className="metric-bar">
                                <span className={item.tone} style={{ width: `${item.value}%` }} />
                              </div>
                            </div>
                          ))}
                        </div>
                        <div className="progress-footnote">Начало: январь 2025 · Сессий: 14 · Этап: устойчивый рост</div>
                      </div>

                      <div className="coach-panel wide">
                        <div className="panel-title">Задания клиентов на эту неделю</div>
                        <div className="task-grid">
                          {weeklyTasks.map((item) => (
                            <div key={item.text} className="task-row">
                              <span className={`task-box${item.done ? " done" : ""}`}>{item.done ? "✓" : ""}</span>
                              <span>{item.text}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="screen-showcase fade-up" style={{ animationDelay: "160ms" }}>
                <div className="screen-label">Экран прогресса отдельного клиента</div>
                <div className="progress-screen">
                  <div className="progress-client-head">
                    <div className="progress-client-meta">
                      <div className="progress-avatar">ОС</div>
                      <div>
                        <div className="progress-client-name">Ольга Смирнова</div>
                        <div className="progress-client-sub">14 сессий · с января 2025 · направление: уверенность</div>
                      </div>
                    </div>
                    <div className="milestone-pill">Первый прорыв</div>
                  </div>

                  <div className="progress-tabs">
                    <div className="progress-tab active">Динамика</div>
                    <div className="progress-tab">Радар</div>
                    <div className="progress-tab">Журнал</div>
                    <div className="progress-tab">Задания</div>
                  </div>

                  <div className="progress-layout">
                    <div className="graph-card">
                      <div className="panel-title">Прогресс по компетенциям — 6 месяцев</div>
                      <svg viewBox="0 0 760 360" className="line-chart" aria-hidden="true">
                        <g stroke="rgba(0,0,0,0.09)" strokeWidth="1">
                          <line x1="68" y1="36" x2="710" y2="36" />
                          <line x1="68" y1="106" x2="710" y2="106" />
                          <line x1="68" y1="176" x2="710" y2="176" />
                          <line x1="68" y1="246" x2="710" y2="246" />
                          <line x1="68" y1="316" x2="710" y2="316" />
                        </g>
                        <g fill="#707585" fontSize="15">
                          <text x="18" y="321">0%</text>
                          <text x="10" y="251">25%</text>
                          <text x="10" y="181">50%</text>
                          <text x="10" y="111">75%</text>
                          <text x="0" y="41">100%</text>
                          <text x="68" y="348">Янв</text>
                          <text x="196" y="348">Фев</text>
                          <text x="324" y="348">Мар</text>
                          <text x="452" y="348">Апр</text>
                          <text x="580" y="348">Май</text>
                          <text x="688" y="348">Июн</text>
                        </g>
                        <path
                          d="M68 196 C132 182, 164 170, 196 162 S292 142, 324 128 S420 110, 452 98 S548 74, 580 60 S664 46, 708 40"
                          fill="none"
                          stroke="#4b8ef5"
                          strokeWidth="4"
                          strokeLinecap="round"
                        />
                        <path
                          d="M68 232 C132 220, 164 210, 196 202 S292 176, 324 166 S420 144, 452 130 S548 106, 580 92 S664 78, 708 70"
                          fill="none"
                          stroke="#2f8f7a"
                          strokeWidth="4"
                          strokeLinecap="round"
                        />
                        <path
                          d="M68 218 C132 208, 164 198, 196 190 S292 182, 324 172 S420 158, 452 150 S548 136, 580 122 S664 110, 708 100"
                          fill="none"
                          stroke="#7c70e8"
                          strokeWidth="4"
                          strokeLinecap="round"
                        />
                        {[
                          [68, 196, "#4b8ef5"],
                          [196, 162, "#4b8ef5"],
                          [324, 128, "#4b8ef5"],
                          [452, 98, "#4b8ef5"],
                          [580, 60, "#4b8ef5"],
                          [708, 40, "#4b8ef5"],
                          [68, 232, "#2f8f7a"],
                          [196, 202, "#2f8f7a"],
                          [324, 166, "#2f8f7a"],
                          [452, 130, "#2f8f7a"],
                          [580, 92, "#2f8f7a"],
                          [708, 70, "#2f8f7a"],
                          [68, 218, "#7c70e8"],
                          [196, 190, "#7c70e8"],
                          [324, 172, "#7c70e8"],
                          [452, 150, "#7c70e8"],
                          [580, 122, "#7c70e8"],
                          [708, 100, "#7c70e8"],
                        ].map(([cx, cy, fill], index) => (
                          <circle key={`${cx}-${cy}-${index}`} cx={cx} cy={cy} r="5.5" fill={fill as string} />
                        ))}
                      </svg>
                      <div className="chart-legend">
                        <span className="legend-item">
                          <span className="legend-dot green" />
                          Уверенность
                        </span>
                        <span className="legend-item">
                          <span className="legend-dot violet" />
                          Коммуникация
                        </span>
                        <span className="legend-item">
                          <span className="legend-dot blue" />
                          Цели и фокус
                        </span>
                      </div>
                    </div>

                    <div className="radar-card">
                      <div className="panel-title">Радар компетенций</div>
                      <svg viewBox="0 0 280 280" className="radar-chart" aria-hidden="true">
                        <g fill="none" stroke="rgba(0,0,0,0.1)" strokeWidth="1.2">
                          <polygon points="140,40 218,86 218,174 140,220 62,174 62,86" />
                          <polygon points="140,64 196,96 196,164 140,196 84,164 84,96" />
                          <polygon points="140,88 174,106 174,154 140,172 106,154 106,106" />
                          <line x1="140" y1="40" x2="140" y2="220" />
                          <line x1="62" y1="86" x2="218" y2="174" />
                          <line x1="62" y1="174" x2="218" y2="86" />
                        </g>
                        <polygon
                          points="140,72 190,104 176,156 140,186 102,158 92,116"
                          fill="rgba(92,82,224,0.16)"
                          stroke="#5c52e0"
                          strokeWidth="3"
                        />
                        <g fill="#707585" fontSize="14">
                          <text x="110" y="24">Уверенность</text>
                          <text x="220" y="102">Коммуникация</text>
                          <text x="212" y="188">Границы</text>
                          <text x="120" y="246">Цели</text>
                          <text x="8" y="190">Ценности</text>
                          <text x="20" y="102">Баланс</text>
                        </g>
                      </svg>
                      <div className="radar-note">Радар показывает профиль клиента на текущем этапе, а график слева дает динамику по времени.</div>
                    </div>
                  </div>

                  <div className="sessions-card">
                    <div className="panel-title">Последние сессии</div>
                    <div className="sessions-list">
                      {recentSessions.map((item) => (
                        <div key={item.title} className="session-row">
                          <span>{item.title}</span>
                          <span>{item.note}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="modules-grid">
              {interfaceModules.map((module, index) => (
                <div key={module.title} className="module-card fade-up" style={{ animationDelay: `${220 + index * 60}ms` }}>
                  <div className="module-title">{module.title}</div>
                  <div className="module-list">
                    {module.items.map((item) => (
                      <div key={item} className="module-item">
                        <span className="module-dot" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-pad scale-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Масштаб</div>
            <h2 className="fade-up">
              Когда процесс собран в систему,
              <br />
              <em>практика растет без хаоса</em>
            </h2>
            <div className="scale-grid fade-up" style={{ animationDelay: "120ms" }}>
              {scaleItems.map((item) => (
                <div key={`${item.value}-${item.label}`} className="scale-item">
                  <div className={`scale-num${item.accent ? " accent" : ""}`}>{item.value}</div>
                  <div className="scale-label">{item.label}</div>
                  <div className={`scale-sub${item.accent ? " good" : ""}`}>{item.sub}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-pad proof-section">
          <div className="container">
            <div className="section-eyebrow fade-up">Истории</div>
            <h2 className="fade-up">
              Специалисты, которые перестали
              <br />
              <em>доказывать ценность на словах</em>
            </h2>
            <div className="proof-grid">
              {testimonials.map((item, index) => (
                <div key={item.name} className="proof-card fade-up" style={{ animationDelay: `${index * 80}ms` }}>
                  <div className="proof-text">{item.quote}</div>
                  <div className="proof-meta">
                    <div className="proof-avatar">{item.initial}</div>
                    <div>
                      <div className="proof-name">{item.name}</div>
                      <div className="proof-role">{item.role}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="section-pad offer-section" id="offer">
          <div className="container">
            <div className="offer-box fade-up">
              <div className="section-eyebrow center">Начать сейчас</div>
              <h2>
                Создайте систему,
                <br />
                в которой клиент видит результат
              </h2>
              <p className="offer-sub">
                Добавьте первого клиента, зафиксируйте итоги встречи и покажите ему путь, который уже пройден.
                Именно это удерживает внимание, усиливает вовлеченность и защищает ценность вашей работы.
              </p>
              <div className="offer-bonus">Бонус: шаблон структуры сессии и трекер прогресса клиента</div>
              <div>
                <Link href="/login" className="btn-primary large">
                  Попробовать с первым клиентом
                </Link>
              </div>
              <div className="offer-micro">
                <span className="offer-micro-item">Бесплатный старт</span>
                <span className="offer-micro-item">Без карты</span>
                <span className="offer-micro-item">Первый сценарий за несколько минут</span>
              </div>
            </div>
          </div>
        </section>

        <section className="section-pad faq-section">
          <div className="container">
            <div className="section-eyebrow center fade-up">Вопросы</div>
            <h2 className="center fade-up">
              Возражения,
              <br />
              <em>которые здесь уже учтены</em>
            </h2>
            <div className="faq-list">
              {faqs.map((item, index) => {
                const isOpen = openFaq === index;
                return (
                  <div key={item.question} className={`faq-item fade-up${isOpen ? " open" : ""}`} style={{ animationDelay: `${index * 70}ms` }}>
                    <button
                      type="button"
                      className="faq-q"
                      onClick={() => setOpenFaq(isOpen ? -1 : index)}
                      aria-expanded={isOpen}
                    >
                      <span>{item.question}</span>
                    </button>
                    <div className="faq-a">{item.answer}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="final-section">
          <div className="container">
            <div className="final-tagline fade-up">
              Можно продолжать вести клиентов
              <br />
              в заметках, чатах и памяти.
              <br />
              А можно построить <em>систему</em>,
              <br />
              где прогресс видно и вам, и клиенту.
            </div>
            <Link href="/login" className="btn-primary large fade-up" style={{ animationDelay: "120ms" }}>
              Начать сейчас
            </Link>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="footer-brand">
          <div className="footer-logo">
            Fibo<span>n</span>atty
          </div>
          <div className="footer-meta">ИНН: 772305668632</div>
        </div>
        <div className="footer-links">
          <a href="/policy.html" target="_blank" rel="noreferrer">
            Конфиденциальность
          </a>
          <a href="mailto:hello@fibonatty.ru">hello@fibonatty.ru</a>
          <a href="https://t.me/Fibonatty_bot" target="_blank" rel="noreferrer">
            Поддержка
          </a>
        </div>
      </footer>

      <style jsx>{`
        .landing-shell {
          --bg: #f7f6f2;
          --bg2: #ffffff;
          --bg3: #f0ede8;
          --card: #ffffff;
          --border: rgba(0, 0, 0, 0.07);
          --border2: rgba(0, 0, 0, 0.1);
          --text: #1a1c24;
          --muted: #707585;
          --accent: #5c52e0;
          --accent2: #2f8f7a;
          --accent-soft: rgba(92, 82, 224, 0.07);
          --accent2-soft: rgba(47, 143, 122, 0.08);
          --glow: rgba(92, 82, 224, 0.2);
          --shadow: rgba(0, 0, 0, 0.06);
          --shadow-lg: rgba(0, 0, 0, 0.1);
          background: var(--bg);
          color: var(--text);
          font-family: var(--font-dm-sans), sans-serif;
          min-height: 100vh;
        }

        .landing-shell :global(*) {
          box-sizing: border-box;
        }

        .landing-shell :global(html) {
          scroll-behavior: smooth;
        }

        .landing-shell :global(body) {
          margin: 0;
        }

        .container {
          width: 100%;
          max-width: 1120px;
          margin: 0 auto;
          padding: 0 40px;
        }

        .landing-nav {
          position: sticky;
          top: 0;
          z-index: 100;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 18px 40px;
          background: rgba(247, 246, 242, 0.88);
          border-bottom: 1px solid var(--border);
          backdrop-filter: blur(18px);
        }

        .nav-logo,
        .footer-logo {
          font-family: var(--font-playfair), serif;
          font-size: 22px;
          line-height: 1;
          letter-spacing: 0.02em;
        }

        .nav-logo span,
        .footer-logo span {
          color: var(--accent);
        }

        .nav-actions {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .nav-link {
          color: var(--muted);
          text-decoration: none;
          font-size: 14px;
        }

        .nav-link:hover {
          color: var(--text);
        }

        .nav-cta,
        .btn-primary,
        .next-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          text-decoration: none;
          border: none;
          cursor: pointer;
          transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
        }

        .nav-cta,
        .btn-primary {
          background: var(--accent);
          color: #fff;
          border-radius: 999px;
          font-weight: 500;
        }

        .nav-cta {
          padding: 10px 22px;
          font-size: 14px;
        }

        .nav-cta:hover,
        .btn-primary:hover,
        .next-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 10px 28px var(--glow);
        }

        .hero-section {
          position: relative;
          overflow: hidden;
          padding: 92px 0 72px;
          background: var(--bg);
        }

        .hero-bg {
          position: absolute;
          inset: 0;
          background:
            radial-gradient(ellipse 52% 48% at 78% 36%, rgba(92, 82, 224, 0.08) 0%, transparent 72%),
            radial-gradient(ellipse 40% 40% at 15% 78%, rgba(47, 143, 122, 0.08) 0%, transparent 62%);
        }

        .hero-bg::after {
          content: "";
          position: absolute;
          inset: 0;
          background-image: radial-gradient(circle, rgba(0, 0, 0, 0.06) 1px, transparent 1px);
          background-size: 28px 28px;
          mask-image: radial-gradient(ellipse 72% 72% at 50% 50%, black 20%, transparent 100%);
        }

        .hero-inner {
          position: relative;
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(360px, 470px);
          gap: 72px;
          align-items: center;
        }

        .hero-copy {
          position: relative;
          z-index: 1;
        }

        .hero-tag,
        .offer-bonus {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 7px 15px;
          border-radius: 999px;
          font-size: 12px;
          font-weight: 500;
          letter-spacing: 0.05em;
        }

        .hero-tag {
          margin-bottom: 28px;
          color: var(--accent);
          text-transform: uppercase;
          background: var(--accent-soft);
          border: 1px solid rgba(92, 82, 224, 0.14);
        }

        .hero-tag::before {
          content: "";
          width: 6px;
          height: 6px;
          border-radius: 999px;
          background: var(--accent);
        }

        h1,
        h2,
        .final-tagline,
        .proof-text {
          font-family: var(--font-playfair), serif;
        }

        h1 {
          margin: 0 0 22px;
          font-size: clamp(38px, 5vw, 60px);
          line-height: 1.08;
          font-weight: 600;
        }

        h2 {
          margin: 0 0 18px;
          font-size: clamp(30px, 4vw, 46px);
          line-height: 1.18;
          font-weight: 600;
        }

        h1 em,
        h2 em,
        .final-tagline em {
          color: var(--accent);
          font-style: italic;
        }

        .hero-sub,
        .section-sub,
        .offer-sub {
          color: var(--muted);
          font-size: 17px;
          line-height: 1.8;
        }

        .hero-sub {
          max-width: 640px;
          margin: 0;
        }

        .hero-sub strong {
          color: var(--text);
          font-weight: 500;
        }

        .cta-group {
          display: flex;
          flex-wrap: wrap;
          gap: 14px;
          margin-top: 38px;
        }

        .btn-primary {
          padding: 16px 30px;
          font-size: 15px;
        }

        .btn-primary.large {
          padding: 18px 40px;
          font-size: 16px;
        }

        .btn-ghost {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          padding: 16px 28px;
          border-radius: 999px;
          border: 1px solid var(--border2);
          color: var(--text);
          text-decoration: none;
          font-size: 15px;
          transition: transform 0.25s ease, border-color 0.25s ease, background 0.25s ease;
        }

        .btn-ghost:hover {
          transform: translateY(-2px);
          border-color: rgba(0, 0, 0, 0.18);
          background: rgba(0, 0, 0, 0.02);
        }

        .hero-micro {
          margin-top: 18px;
          color: var(--muted);
          font-size: 13px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .hero-micro::before {
          content: "✓";
          color: var(--accent2);
          font-size: 12px;
        }

        .hero-visual {
          position: relative;
          padding: 18px 12px 28px 0;
        }

        .client-card {
          position: relative;
          z-index: 1;
          padding: 28px;
          border-radius: 24px;
          background: var(--card);
          border: 1px solid var(--border);
          box-shadow: 0 24px 60px var(--shadow-lg), 0 4px 16px var(--shadow);
        }

        .client-card::before,
        .offer-box::before {
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          top: 0;
          height: 3px;
          border-radius: 3px 3px 0 0;
          background: linear-gradient(90deg, var(--accent), var(--accent2));
        }

        .floating-badge {
          position: absolute;
          top: 0;
          right: 0;
          z-index: 2;
          max-width: 240px;
          padding: 12px 16px;
          border-radius: 14px;
          background: #fff;
          border: 1px solid var(--border);
          box-shadow: 0 8px 24px var(--shadow);
          color: var(--accent2);
          font-size: 12px;
          font-weight: 500;
          line-height: 1.5;
        }

        .floating-badge.secondary {
          top: auto;
          right: auto;
          left: -10px;
          bottom: 0;
          color: var(--muted);
        }

        .card-header,
        .proof-meta {
          display: flex;
          align-items: center;
          gap: 14px;
        }

        .avatar,
        .proof-avatar {
          width: 44px;
          height: 44px;
          border-radius: 999px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, var(--accent), var(--accent2));
          color: #fff;
          font-family: var(--font-playfair), serif;
          font-size: 18px;
        }

        .card-name,
        .proof-name {
          font-size: 15px;
          font-weight: 500;
        }

        .card-meta,
        .proof-role,
        .next-label,
        .progress-label {
          color: var(--muted);
          font-size: 12px;
        }

        .card-badge {
          margin-left: auto;
          padding: 4px 10px;
          border-radius: 999px;
          border: 1px solid rgba(47, 143, 122, 0.22);
          background: var(--accent2-soft);
          color: var(--accent2);
          font-size: 11px;
          font-weight: 500;
          white-space: nowrap;
        }

        .card-insight {
          margin-top: 22px;
          margin-bottom: 16px;
          padding: 14px 16px;
          border-radius: 14px;
          background: var(--accent-soft);
          border: 1px solid rgba(92, 82, 224, 0.12);
        }

        .insight-label {
          margin-bottom: 6px;
          color: var(--accent);
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .insight-text,
        .pain-body,
        .step-body,
        .feature-body,
        .faq-a {
          color: var(--text);
          font-size: 14px;
          line-height: 1.7;
        }

        .progress-box {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 10px;
        }

        .progress-value,
        .next-date {
          color: var(--text);
          font-size: 14px;
          font-weight: 500;
        }

        .progress-chip {
          padding: 6px 10px;
          border-radius: 999px;
          background: rgba(47, 143, 122, 0.1);
          color: var(--accent2);
          font-size: 11px;
          font-weight: 600;
          white-space: nowrap;
        }

        .progress-bar {
          width: 100%;
          height: 8px;
          margin-bottom: 18px;
          background: rgba(0, 0, 0, 0.06);
          border-radius: 999px;
          overflow: hidden;
        }

        .progress-bar span {
          display: block;
          width: 80%;
          height: 100%;
          border-radius: inherit;
          background: linear-gradient(90deg, var(--accent), var(--accent2));
        }

        .card-tasks,
        .transform-items {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .task-item,
        .t-item {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          color: var(--muted);
          font-size: 14px;
          line-height: 1.55;
        }

        .task-check {
          width: 18px;
          height: 18px;
          border-radius: 999px;
          flex-shrink: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid rgba(0, 0, 0, 0.15);
          font-size: 10px;
        }

        .task-check.done {
          color: var(--accent2);
          background: rgba(47, 143, 122, 0.1);
          border-color: rgba(47, 143, 122, 0.25);
        }

        .task-muted {
          color: rgba(0, 0, 0, 0.35);
        }

        .card-next {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-top: 18px;
          padding: 12px 14px;
          border-radius: 14px;
          background: var(--bg3);
        }

        .next-btn {
          padding: 7px 15px;
          border-radius: 999px;
          background: var(--accent);
          color: #fff;
          font-size: 12px;
          font-weight: 500;
        }

        .tools-strip {
          padding: 34px 0;
          border-top: 1px solid var(--border);
          border-bottom: 1px solid var(--border);
          background: var(--bg2);
        }

        .tools-strip-inner {
          display: flex;
          align-items: center;
          gap: 28px;
        }

        .tools-label,
        .tool-item {
          font-size: 14px;
          color: var(--muted);
        }

        .tools-list {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 28px;
        }

        .tool-item {
          position: relative;
          color: rgba(0, 0, 0, 0.34);
        }

        .tool-item::after {
          content: "×";
          position: absolute;
          right: -16px;
          color: rgba(0, 0, 0, 0.12);
          font-size: 12px;
        }

        .tool-item:last-child::after {
          display: none;
        }

        .section-pad {
          padding: 100px 0;
        }

        .section-eyebrow {
          margin-bottom: 16px;
          color: var(--accent);
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }

        .section-eyebrow.center,
        h2.center {
          text-align: center;
        }

        .pain-section,
        .how-section,
        .scale-section,
        .offer-section,
        .final-section {
          background: var(--bg2);
        }

        .features-section,
        .interface-section,
        .proof-section,
        .solution-section,
        .faq-section {
          background: var(--bg);
        }

        .pain-grid,
        .features-grid,
        .proof-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 20px;
          margin-top: 56px;
        }

        .pain-card,
        .feature-card,
        .proof-card,
        .step-card,
        .faq-item,
        .transform-side {
          border-radius: 20px;
          border: 1px solid var(--border);
          background: var(--card);
          box-shadow: 0 2px 12px var(--shadow);
        }

        .pain-card {
          position: relative;
          overflow: hidden;
          padding: 32px;
        }

        .pain-num {
          position: absolute;
          right: 22px;
          top: 16px;
          color: rgba(92, 82, 224, 0.08);
          font-family: var(--font-playfair), serif;
          font-size: 52px;
          font-style: italic;
          line-height: 1;
        }

        .pain-title,
        .feature-title,
        .step-title {
          margin-bottom: 10px;
          font-size: 16px;
          font-weight: 500;
          line-height: 1.4;
        }

        .pain-body,
        .step-body,
        .feature-body {
          color: var(--muted);
        }

        .insight-box {
          margin-top: 56px;
          padding: 40px;
          border-radius: 22px;
          border: 1px solid rgba(92, 82, 224, 0.12);
          background: linear-gradient(135deg, rgba(92, 82, 224, 0.06) 0%, rgba(47, 143, 122, 0.05) 100%);
          text-align: center;
        }

        .insight-box p {
          margin: 0;
          color: var(--text);
          font-family: var(--font-playfair), serif;
          font-size: clamp(19px, 2.5vw, 28px);
          line-height: 1.5;
        }

        .transform-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
          gap: 38px;
          align-items: center;
          margin-top: 56px;
        }

        .transform-side {
          padding: 34px;
        }

        .transform-side.success {
          border-color: rgba(47, 143, 122, 0.22);
        }

        .transform-label {
          margin-bottom: 18px;
          font-size: 11px;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }

        .transform-label.before {
          color: rgba(200, 60, 60, 0.65);
        }

        .transform-label.after {
          color: var(--accent2);
        }

        .transform-arrow {
          color: var(--accent);
          font-size: 28px;
          opacity: 0.35;
        }

        .t-icon {
          flex-shrink: 0;
          margin-top: 2px;
          font-size: 13px;
        }

        .t-icon.negative {
          color: rgba(200, 60, 60, 0.65);
        }

        .t-icon.positive {
          color: var(--accent2);
        }

        .after-item {
          color: var(--text);
        }

        .steps-grid {
          position: relative;
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 20px;
          margin-top: 56px;
        }

        .steps-grid::before {
          content: "";
          position: absolute;
          left: calc(16.66% + 22px);
          right: calc(16.66% + 22px);
          top: 34px;
          height: 1px;
          background: linear-gradient(90deg, var(--accent), transparent 50%, var(--accent));
          opacity: 0.15;
        }

        .step-card {
          position: relative;
          z-index: 1;
          padding: 32px;
        }

        .step-num,
        .feature-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          border-radius: 14px;
          background: var(--accent-soft);
          border: 1px solid rgba(92, 82, 224, 0.14);
          color: var(--accent);
          font-weight: 600;
        }

        .step-num {
          width: 40px;
          height: 40px;
          margin-bottom: 18px;
          border-radius: 999px;
        }

        .features-grid {
          margin-top: 56px;
        }

        .feature-card {
          display: flex;
          gap: 18px;
          padding: 34px;
        }

        .feature-icon {
          width: 48px;
          height: 48px;
          font-size: 13px;
          letter-spacing: 0.08em;
        }

        .interface-stack {
          display: flex;
          flex-direction: column;
          gap: 28px;
          margin-top: 56px;
        }

        .screen-showcase {
          padding: 20px;
          border-radius: 30px;
          border: 1px solid var(--border);
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(240, 237, 232, 0.94) 100%);
          box-shadow: 0 20px 60px var(--shadow);
        }

        .screen-label {
          margin-bottom: 16px;
          color: var(--accent);
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.1em;
          text-transform: uppercase;
        }

        .coach-screen {
          display: grid;
          grid-template-columns: 250px minmax(0, 1fr);
          overflow: hidden;
          border-radius: 24px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          background: #fff;
          min-height: 720px;
        }

        .coach-sidebar {
          padding: 26px 18px;
          background: linear-gradient(180deg, #f3f0ea 0%, #ebe7e0 100%);
          border-right: 1px solid rgba(0, 0, 0, 0.06);
        }

        .coach-brand {
          margin-bottom: 28px;
          font-family: var(--font-playfair), serif;
          font-size: 24px;
        }

        .coach-brand span {
          color: var(--accent);
        }

        .coach-menu {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .coach-menu-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 14px;
          border-radius: 16px;
          color: var(--muted);
          font-size: 16px;
        }

        .coach-menu-item.active {
          background: rgba(92, 82, 224, 0.12);
          color: var(--accent);
          font-weight: 500;
        }

        .coach-menu-dot,
        .module-dot {
          width: 9px;
          height: 9px;
          border-radius: 999px;
          background: currentColor;
          opacity: 0.5;
          flex-shrink: 0;
        }

        .coach-main {
          padding: 26px;
          background:
            radial-gradient(circle at top right, rgba(92, 82, 224, 0.08), transparent 30%),
            radial-gradient(circle at bottom left, rgba(47, 143, 122, 0.08), transparent 30%),
            #fcfbf8;
        }

        .coach-topbar,
        .progress-client-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 20px;
        }

        .coach-greeting,
        .progress-client-name {
          font-size: clamp(24px, 3vw, 38px);
          font-weight: 600;
          line-height: 1.15;
        }

        .coach-caption,
        .progress-client-sub,
        .progress-footnote,
        .radar-note {
          color: var(--muted);
          font-size: 14px;
          line-height: 1.6;
        }

        .coach-day-badge,
        .milestone-pill {
          padding: 10px 16px;
          border-radius: 999px;
          background: rgba(47, 143, 122, 0.12);
          border: 1px solid rgba(47, 143, 122, 0.18);
          color: var(--accent2);
          font-size: 13px;
          font-weight: 600;
          white-space: nowrap;
        }

        .coach-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 16px;
          margin-top: 22px;
        }

        .coach-stat-card,
        .coach-panel,
        .graph-card,
        .radar-card,
        .sessions-card,
        .module-card {
          border-radius: 22px;
          border: 1px solid rgba(0, 0, 0, 0.07);
          background: rgba(255, 255, 255, 0.92);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
        }

        .coach-stat-card {
          padding: 18px 20px;
        }

        .coach-stat-label,
        .panel-title,
        .module-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--text);
        }

        .coach-stat-value {
          margin-top: 10px;
          font-size: clamp(34px, 4vw, 50px);
          line-height: 1;
          font-weight: 600;
        }

        .coach-stat-note {
          margin-top: 8px;
          color: var(--muted);
          font-size: 14px;
        }

        .coach-panels {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 360px;
          gap: 16px;
          margin-top: 16px;
        }

        .coach-panel,
        .graph-card,
        .radar-card,
        .sessions-card {
          padding: 20px;
        }

        .coach-panel.wide,
        .sessions-card {
          grid-column: 1 / -1;
        }

        .coach-client-list,
        .coach-progress-list,
        .sessions-list,
        .module-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-top: 16px;
        }

        .coach-client-row,
        .session-row {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 12px 0;
          border-top: 1px solid rgba(0, 0, 0, 0.06);
        }

        .coach-client-row:first-child,
        .session-row:first-child {
          border-top: 0;
          padding-top: 0;
        }

        .client-avatar,
        .progress-avatar {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 48px;
          height: 48px;
          border-radius: 999px;
          font-weight: 600;
          color: #fff;
          flex-shrink: 0;
        }

        .client-avatar.blue,
        .status-pill.blue,
        .legend-dot.blue,
        .metric-bar span.blue {
          background: #4b8ef5;
        }

        .client-avatar.green,
        .status-pill.green,
        .legend-dot.green,
        .metric-bar span.green,
        .progress-avatar {
          background: #2f8f7a;
        }

        .client-avatar.gold,
        .status-pill.gold {
          background: #c2922d;
        }

        .client-avatar.indigo,
        .status-pill.indigo {
          background: #5c52e0;
        }

        .legend-dot.violet,
        .metric-bar span.violet {
          background: #7c70e8;
        }

        .metric-bar span.orange {
          background: #d67646;
        }

        .coach-client-copy {
          min-width: 0;
          flex: 1;
        }

        .coach-client-name {
          font-size: 17px;
          font-weight: 500;
        }

        .coach-client-focus {
          color: var(--muted);
          font-size: 14px;
          margin-top: 4px;
        }

        .status-pill {
          padding: 8px 12px;
          border-radius: 999px;
          color: #fff;
          font-size: 12px;
          font-weight: 600;
          white-space: nowrap;
        }

        .metric-row {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .metric-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
          font-size: 14px;
        }

        .metric-head span:last-child {
          color: var(--muted);
          font-weight: 600;
        }

        .metric-bar {
          height: 10px;
          border-radius: 999px;
          background: rgba(0, 0, 0, 0.08);
          overflow: hidden;
        }

        .metric-bar span {
          display: block;
          height: 100%;
          border-radius: inherit;
        }

        .task-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px 26px;
          margin-top: 18px;
        }

        .task-row,
        .module-item {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          color: var(--text);
          font-size: 15px;
          line-height: 1.6;
        }

        .task-box {
          width: 28px;
          height: 28px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 9px;
          border: 1px solid rgba(0, 0, 0, 0.12);
          color: transparent;
          flex-shrink: 0;
        }

        .task-box.done {
          background: rgba(47, 143, 122, 0.12);
          border-color: rgba(47, 143, 122, 0.2);
          color: var(--accent2);
        }

        .progress-screen {
          padding: 26px;
          border-radius: 24px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          background:
            radial-gradient(circle at top left, rgba(47, 143, 122, 0.07), transparent 24%),
            radial-gradient(circle at bottom right, rgba(92, 82, 224, 0.08), transparent 28%),
            #fff;
        }

        .progress-client-meta {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .progress-tabs {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 22px;
          margin-bottom: 18px;
        }

        .progress-tab {
          padding: 10px 16px;
          border-radius: 999px;
          border: 1px solid rgba(0, 0, 0, 0.1);
          color: var(--muted);
          font-size: 14px;
          font-weight: 500;
        }

        .progress-tab.active {
          color: var(--accent);
          border-color: rgba(92, 82, 224, 0.18);
          background: rgba(92, 82, 224, 0.09);
        }

        .progress-layout {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 320px;
          gap: 16px;
        }

        .line-chart,
        .radar-chart {
          width: 100%;
          height: auto;
          margin-top: 18px;
        }

        .chart-legend {
          display: flex;
          flex-wrap: wrap;
          gap: 18px;
          margin-top: 14px;
        }

        .legend-item {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          color: var(--muted);
          font-size: 14px;
        }

        .legend-dot {
          width: 10px;
          height: 10px;
          border-radius: 999px;
          display: inline-block;
        }

        .radar-note {
          margin-top: 12px;
        }

        .session-row {
          justify-content: space-between;
          color: var(--text);
          font-size: 15px;
        }

        .session-row span:last-child {
          color: var(--muted);
          text-align: right;
        }

        .modules-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 20px;
          margin-top: 28px;
        }

        .module-card {
          padding: 28px;
        }

        .scale-section {
          border-top: 1px solid var(--border);
          border-bottom: 1px solid var(--border);
        }

        .scale-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 2px;
          margin-top: 56px;
          border-radius: 20px;
          overflow: hidden;
          background: var(--border);
        }

        .scale-item {
          padding: 40px 32px;
          background: var(--card);
          text-align: center;
        }

        .scale-num {
          margin-bottom: 8px;
          color: var(--text);
          font-family: var(--font-playfair), serif;
          font-size: 52px;
          line-height: 1;
          font-weight: 600;
        }

        .scale-num.accent {
          color: var(--accent);
        }

        .scale-label {
          color: var(--muted);
          font-size: 14px;
        }

        .scale-sub {
          margin-top: 8px;
          color: rgba(200, 60, 60, 0.55);
          font-size: 12px;
        }

        .scale-sub.good {
          color: var(--accent2);
        }

        .proof-card {
          position: relative;
          padding: 36px;
        }

        .proof-card::before {
          content: '"';
          position: absolute;
          right: 28px;
          top: 18px;
          color: rgba(92, 82, 224, 0.08);
          font-family: var(--font-playfair), serif;
          font-size: 82px;
          line-height: 1;
        }

        .proof-text {
          margin: 0 0 24px;
          color: var(--text);
          font-size: 22px;
          line-height: 1.6;
          font-style: italic;
          max-width: 92%;
        }

        .offer-section {
          border-top: 1px solid var(--border);
        }

        .offer-box {
          position: relative;
          padding: 64px;
          border-radius: 28px;
          border: 1px solid rgba(92, 82, 224, 0.15);
          background: linear-gradient(135deg, rgba(92, 82, 224, 0.06) 0%, rgba(47, 143, 122, 0.05) 100%);
          box-shadow: 0 8px 40px var(--shadow);
          overflow: hidden;
          text-align: center;
        }

        .offer-sub {
          max-width: 720px;
          margin: 0 auto 34px;
        }

        .offer-bonus {
          margin-bottom: 30px;
          border: 1px solid rgba(47, 143, 122, 0.2);
          background: rgba(47, 143, 122, 0.08);
          color: var(--accent2);
          letter-spacing: 0;
        }

        .offer-micro {
          display: flex;
          justify-content: center;
          flex-wrap: wrap;
          gap: 18px;
          margin-top: 18px;
          color: var(--muted);
          font-size: 13px;
        }

        .offer-micro-item::before {
          content: "✓ ";
          color: var(--accent2);
        }

        .faq-list {
          max-width: 760px;
          margin: 56px auto 0;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .faq-item {
          overflow: hidden;
        }

        .faq-q {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 22px 28px;
          border: 0;
          background: transparent;
          color: var(--text);
          font: inherit;
          font-size: 15px;
          text-align: left;
          cursor: pointer;
        }

        .faq-q::after {
          content: "+";
          flex-shrink: 0;
          color: var(--accent);
          font-size: 20px;
          transition: transform 0.25s ease;
        }

        .faq-item.open .faq-q::after {
          transform: rotate(45deg);
        }

        .faq-a {
          max-height: 0;
          overflow: hidden;
          padding: 0 28px;
          color: var(--muted);
          transition: max-height 0.3s ease, padding 0.3s ease;
        }

        .faq-item.open .faq-a {
          max-height: 220px;
          padding: 0 28px 22px;
        }

        .final-section {
          padding: 84px 0;
          text-align: center;
          border-top: 1px solid var(--border);
        }

        .final-tagline {
          max-width: 720px;
          margin: 0 auto 36px;
          font-size: clamp(28px, 4vw, 44px);
          line-height: 1.35;
        }

        .landing-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          padding: 30px 40px;
          background: var(--bg3);
          border-top: 1px solid var(--border);
        }

        .footer-logo {
          color: var(--muted);
          font-size: 18px;
        }

        .footer-meta {
          margin-top: 6px;
          color: var(--muted);
          font-size: 13px;
        }

        .footer-links {
          display: flex;
          flex-wrap: wrap;
          gap: 22px;
        }

        .footer-links a {
          color: var(--muted);
          text-decoration: none;
          font-size: 13px;
        }

        .footer-links a:hover {
          color: var(--text);
        }

        .fade-up {
          opacity: 0;
          transform: translateY(24px);
          animation: fadeUp 0.7s ease forwards;
        }

        @keyframes fadeUp {
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @media (max-width: 1024px) {
          .hero-inner {
            grid-template-columns: 1fr;
            gap: 40px;
          }

          .hero-visual {
            max-width: 520px;
          }

          .transform-grid {
            grid-template-columns: 1fr;
          }

          .transform-arrow {
            transform: rotate(90deg);
            justify-self: center;
          }

          .steps-grid::before {
            display: none;
          }

          .coach-screen,
          .progress-layout,
          .coach-panels,
          .modules-grid {
            grid-template-columns: 1fr;
          }

          .coach-sidebar {
            border-right: 0;
            border-bottom: 1px solid rgba(0, 0, 0, 0.06);
          }
        }

        @media (max-width: 768px) {
          .container,
          .landing-nav,
          .landing-footer {
            padding-left: 20px;
            padding-right: 20px;
          }

          .landing-nav {
            gap: 16px;
          }

          .nav-actions {
            gap: 10px;
          }

          .nav-link {
            display: none;
          }

          .hero-section {
            padding-top: 72px;
            padding-bottom: 60px;
          }

          .hero-visual {
            padding: 0 0 30px;
          }

          .floating-badge {
            position: static;
            max-width: none;
            margin-bottom: 12px;
          }

          .floating-badge.secondary {
            margin-top: 12px;
            margin-bottom: 0;
          }

          .pain-grid,
          .features-grid,
          .modules-grid,
          .proof-grid,
          .steps-grid,
          .scale-grid {
            grid-template-columns: 1fr;
          }

          .tools-strip-inner {
            flex-direction: column;
            align-items: flex-start;
            gap: 14px;
          }

          .feature-card,
          .proof-card,
          .pain-card,
          .step-card,
          .transform-side,
          .offer-box {
            padding: 26px;
          }

          .proof-text {
            max-width: 100%;
            font-size: 20px;
          }

          .progress-box,
          .card-next,
          .coach-topbar,
          .progress-client-head,
          .landing-footer {
            flex-direction: column;
            align-items: flex-start;
          }

          .offer-box {
            padding-top: 48px;
            padding-bottom: 48px;
          }

          .final-tagline {
            font-size: 32px;
          }

          .screen-showcase,
          .progress-screen,
          .coach-main,
          .coach-panel,
          .graph-card,
          .radar-card,
          .sessions-card,
          .module-card {
            padding: 18px;
          }

          .task-grid {
            grid-template-columns: 1fr;
          }

          .coach-sidebar {
            padding: 20px 16px;
          }

          .coach-menu-item {
            padding: 12px;
            font-size: 14px;
          }

          .coach-greeting,
          .progress-client-name {
            font-size: 28px;
          }

          .session-row {
            flex-direction: column;
            align-items: flex-start;
          }

          .session-row span:last-child {
            text-align: left;
          }
        }
      `}</style>
    </div>
  );
}
