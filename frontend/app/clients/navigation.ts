export type ClientsSectionKey =
  | 'list'
  | 'deals'
  | 'schedule'
  | 'inbox'
  | 'tags'
  | 'chatbot'
  | 'funnel';

export type ClientsSectionLink = {
  key: ClientsSectionKey;
  href: string;
  title: string;
  description: string;
};

export const CLIENTS_SECTION_LINKS: ClientsSectionLink[] = [
  {
    key: 'list',
    href: '/clients/list',
    title: 'Клиенты',
    description: 'Контакты, статусы, теги и быстрый переход в карточки клиентов.',
  },
  {
    key: 'deals',
    href: '/clients/deals',
    title: 'Сделки',
    description: 'Список и Kanban по сделкам с фильтрацией по этапам воронки.',
  },
  {
    key: 'schedule',
    href: '/clients/schedule',
    title: 'Расписание',
    description: 'Календарь встреч и переход к задачам операторов.',
  },
  {
    key: 'inbox',
    href: '/clients/inbox',
    title: 'Входящие',
    description: 'Единый inbox по обращениям, каналам и SLA.',
  },
  {
    key: 'tags',
    href: '/clients/tags',
    title: 'Теги',
    description: 'Справочник тегов CRM по целям, болям и опыту.',
  },
  {
    key: 'chatbot',
    href: '/clients/chatbot',
    title: 'ChatBot',
    description: 'Список цепочек и переход в отдельный редактор цепочки.',
  },
  {
    key: 'funnel',
    href: '/clients/funnel',
    title: 'Воронка',
    description: 'Статистика по этапам продаж, конверсиям и причинам потерь.',
  },
];
