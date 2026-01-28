"use client";

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { CalendarIcon, PlusIcon, EditIcon, TrashIcon, UsersIcon, DollarSignIcon, ClockIcon, ChevronDownIcon, ChevronRightIcon } from 'lucide-react';

// Типы данных для новой CRM-схемы с иерархией
type ClientCategory = {
  id: number;
  name: string;
  description: string;
  color: string;
};

type Client = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  category_id: number;
  status: 'active' | 'inactive' | 'archived';
  photo_url: string;
  notes: string;
  parent_id: number | null; // Добавлено поле для связи с родительским клиентом
};

type EventType = {
  id: number;
  name: string;
  description: string;
  duration_minutes: number;
  color: string;
};

type Event = {
  id: number;
  client_id: number;
  event_type_id: number;
  title: string;
  description: string;
  start_time: string; // ISO string
  end_time: string; // ISO string
  location: string;
  status: 'scheduled' | 'completed' | 'cancelled' | 'no_show';
  notes: string;
};

type Payment = {
  id: number;
  client_id: number;
  amount: number;
  currency: string;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  payment_method: string;
  transaction_id: string;
  description: string;
  paid_at: string | null; // ISO string
};

type Note = {
  id: number;
  client_id: number;
  title: string;
  content: string;
  is_important: boolean;
};

export default function NewClientsEditor() {
  const [clients, setClients] = useState<Client[]>([]);
  const [categories, setCategories] = useState<ClientCategory[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [eventTypes, setEventTypes] = useState<EventType[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedClients, setExpandedClients] = useState<number[]>([]); // Для отслеживания развернутых родительских клиентов

  // Заглушка для API-вызовов - в реальном приложении здесь будет обращение к бэкенду
  useEffect(() => {
    // Здесь должны быть вызовы API для получения данных
    // Например: fetch('/api/crm/clients').then(r => r.json()).then(setClients);
    
    // Временные данные для демонстрации с иерархией
    const mockCategories: ClientCategory[] = [
      { id: 1, name: 'VIP', description: 'Премиум клиенты с индивидуальным подходом', color: '#FFD700' },
      { id: 2, name: 'Стандарт', description: 'Регулярные клиенты', color: '#4A90E2' },
      { id: 3, name: 'Новички', description: 'Клиенты на пробном периоде', color: '#50C878' },
      { id: 4, name: 'Потенциальные', description: 'Лиды в воронке продаж', color: '#FFA500' },
    ];

    const mockClients: Client[] = [
      { id: 1, first_name: 'ООО', last_name: 'Крупный Клиент', email: 'contact@bigcompany.ru', phone: '+74951234500', category_id: 1, status: 'active', photo_url: '', notes: 'Основной корпоративный клиент', parent_id: null },
      { id: 2, first_name: 'Иван', last_name: 'Петров', email: 'ivan.petrov@bigcompany.ru', phone: '+74951234501', category_id: 1, status: 'active', photo_url: '', notes: 'Главный специалист', parent_id: 1 },
      { id: 3, first_name: 'Мария', last_name: 'Сидорова', email: 'maria.sidorova@bigcompany.ru', phone: '+74951234502', category_id: 1, status: 'active', photo_url: '', notes: 'Менеджер проекта', parent_id: 1 },
      { id: 4, first_name: 'Алексей', last_name: 'Козлов', email: 'alexey.kozlov@bigcompany.ru', phone: '+74951234503', category_id: 2, status: 'active', photo_url: '', notes: 'Технический специалист', parent_id: 1 },
      { id: 5, first_name: 'ИП', last_name: 'Частный Предприниматель', email: 'contact@businessman.ru', phone: '+74951234600', category_id: 2, status: 'active', photo_url: '', notes: 'Частный клиент', parent_id: null },
    ];

    const mockEventTypes: EventType[] = [
      { id: 1, name: 'Индивидуальная сессия', description: 'Персональная коуч-сессия', duration_minutes: 60, color: '#4A90E2' },
      { id: 2, name: 'Групповая сессия', description: 'Групповой коучинг', duration_minutes: 90, color: '#9B59B6' },
      { id: 3, name: 'Первая консультация', description: 'Вводная встреча с новым клиентом', duration_minutes: 45, color: '#50C878' },
    ];

    const mockEvents: Event[] = [
      { id: 1, client_id: 1, event_type_id: 1, title: 'Консультация по стратегии', description: 'Обсуждение долгосрочной стратегии', start_time: '2026-02-01T10:00:00', end_time: '2026-02-01T11:00:00', location: 'Онлайн', status: 'scheduled', notes: '' },
      { id: 2, client_id: 2, event_type_id: 3, title: 'Первая встреча', description: 'Знакомство и обсуждение целей', start_time: '2026-01-30T14:00:00', end_time: '2026-01-30T14:45:00', location: 'Офис', status: 'completed', notes: 'Клиент заинтересован в индивидуальной программе' },
    ];

    const mockPayments: Payment[] = [
      { id: 1, client_id: 1, amount: 15000, currency: 'RUB', status: 'paid', payment_method: 'card', transaction_id: 'txn_12345', description: 'Оплата за 10 сессий', paid_at: '2026-01-25T12:00:00' },
      { id: 2, client_id: 2, amount: 5000, currency: 'RUB', status: 'pending', payment_method: 'transfer', transaction_id: 'txn_67890', description: 'Предоплата за первую сессию', paid_at: null },
    ];

    const mockNotes: Note[] = [
      { id: 1, client_id: 1, title: 'Предпочтения', content: 'Любит утренние встречи, предпочитает формальный стиль общения', is_important: true },
      { id: 2, client_id: 2, title: 'Прогресс', content: 'Хорошо реагирует на практику, быстро принимает изменения', is_important: false },
    ];

    setCategories(mockCategories);
    setClients(mockClients);
    setEventTypes(mockEventTypes);
    setEvents(mockEvents);
    setPayments(mockPayments);
    setNotes(mockNotes);
    setLoading(false);
  }, []);

  if (loading) {
    return <div className="p-6">Загрузка редактора клиентов...</div>;
  }

  const getClientCategory = (categoryId: number) => {
    return categories.find(cat => cat.id === categoryId) || null;
  };

  const getClientFullName = (client: Client) => {
    return `${client.first_name} ${client.last_name}`;
  };

  const toggleExpandClient = (clientId: number) => {
    if (expandedClients.includes(clientId)) {
      setExpandedClients(expandedClients.filter(id => id !== clientId));
    } else {
      setExpandedClients([...expandedClients, clientId]);
    }
  };

  // Функция для получения дочерних клиентов
  const getChildClients = (parentId: number) => {
    return clients.filter(client => client.parent_id === parentId);
  };

  // Функция для получения родительского клиента
  const getParentClient = (childId: number) => {
    const childClient = clients.find(client => client.id === childId);
    if (childClient && childClient.parent_id) {
      return clients.find(client => client.id === childClient.parent_id);
    }
    return null;
  };

  // Функция для проверки, является ли клиент родительским
  const isParentClient = (client: Client) => {
    return clients.some(c => c.parent_id === client.id);
  };

  return (
    <div className="container mx-auto py-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">CRM-система для управления клиентами</h1>
        <p className="text-muted-foreground mt-2">
          Управление клиентами, событиями, платежами и заметками
        </p>
      </div>

      <Tabs defaultValue="clients" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="clients">Клиенты</TabsTrigger>
          <TabsTrigger value="events">События</TabsTrigger>
          <TabsTrigger value="payments">Платежи</TabsTrigger>
          <TabsTrigger value="notes">Заметки</TabsTrigger>
          <TabsTrigger value="categories">Категории</TabsTrigger>
        </TabsList>

        {/* Вкладка "Клиенты" */}
        <TabsContent value="clients" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold">Список клиентов</h2>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Добавить клиента
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Добавить нового клиента</DialogTitle>
                  <DialogDescription>
                    Заполните информацию о новом клиенте
                  </DialogDescription>
                </DialogHeader>
                <NewClientForm 
                  categories={categories} 
                  clients={clients} 
                  onSave={(newClient) => setClients([...clients, newClient])} 
                />
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid gap-6">
            {clients
              .filter(client => client.parent_id === null) // Показываем только родительские клиенты
              .map((client) => {
                const category = getClientCategory(client.category_id);
                const childClients = getChildClients(client.id);
                const isExpanded = expandedClients.includes(client.id);
                
                return (
                  <div key={client.id}>
                    <Card className="overflow-hidden">
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center">
                            {isParentClient(client) && (
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                onClick={() => toggleExpandClient(client.id)}
                                className="mr-2 h-6 w-6 p-0"
                              >
                                {isExpanded ? (
                                  <ChevronDownIcon className="h-4 w-4" />
                                ) : (
                                  <ChevronRightIcon className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                            <CardTitle className="text-xl">{getClientFullName(client)}</CardTitle>
                          </div>
                          <Badge 
                            variant="outline" 
                            style={{ borderColor: category?.color, color: category?.color }}
                          >
                            {category?.name}
                          </Badge>
                        </div>
                        <CardDescription>
                          {client.email} • {client.phone}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            client.status === 'active' ? 'bg-green-100 text-green-800' :
                            client.status === 'inactive' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {client.status === 'active' ? 'Активный' : 
                             client.status === 'inactive' ? 'Неактивный' : 'В архиве'}
                          </span>
                          <div className="flex space-x-2">
                            <Button variant="outline" size="sm">
                              <EditIcon className="h-4 w-4" />
                            </Button>
                            <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                              <TrashIcon className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                        {client.notes && (
                          <p className="mt-3 text-sm text-muted-foreground line-clamp-2">{client.notes}</p>
                        )}
                      </CardContent>
                    </Card>
                    
                    {/* Отображение дочерних клиентов */}
                    {isExpanded && childClients.length > 0 && (
                      <div className="ml-8 mt-4 space-y-4">
                        <h3 className="text-lg font-medium">Дочерние клиенты</h3>
                        <div className="grid gap-4 md:grid-cols-2">
                          {childClients.map((childClient) => {
                            const childCategory = getClientCategory(childClient.category_id);
                            return (
                              <Card key={childClient.id} className="border-l-4 border-l-blue-500">
                                <CardHeader className="pb-2">
                                  <div className="flex items-center justify-between">
                                    <CardTitle className="text-lg">{getClientFullName(childClient)}</CardTitle>
                                    <Badge 
                                      variant="outline" 
                                      style={{ borderColor: childCategory?.color, color: childCategory?.color }}
                                    >
                                      {childCategory?.name}
                                    </Badge>
                                  </div>
                                  <CardDescription>
                                    {childClient.email} • {childClient.phone}
                                  </CardDescription>
                                </CardHeader>
                                <CardContent>
                                  <div className="flex items-center justify-between">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                      childClient.status === 'active' ? 'bg-green-100 text-green-800' :
                                      childClient.status === 'inactive' ? 'bg-yellow-100 text-yellow-800' :
                                      'bg-gray-100 text-gray-800'
                                    }`}>
                                      {childClient.status === 'active' ? 'Активный' : 
                                       childClient.status === 'inactive' ? 'Неактивный' : 'В архиве'}
                                    </span>
                                    <div className="flex space-x-2">
                                      <Button variant="outline" size="sm">
                                        <EditIcon className="h-4 w-4" />
                                      </Button>
                                      <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                                        <TrashIcon className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </div>
                                  {childClient.notes && (
                                    <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{childClient.notes}</p>
                                  )}
                                </CardContent>
                              </Card>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            
            {/* Отображение клиентов без родителя */}
            {clients.filter(client => client.parent_id === null).length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                Нет клиентов для отображения
              </div>
            )}
          </div>
        </TabsContent>

        {/* Вкладка "События" */}
        <TabsContent value="events" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold">События и встречи</h2>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Назначить встречу
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Назначить новое событие</DialogTitle>
                  <DialogDescription>
                    Запланируйте встречу или мероприятие для клиента
                  </DialogDescription>
                </DialogHeader>
                <NewEventForm 
                  clients={clients} 
                  eventTypes={eventTypes} 
                  onSave={(newEvent) => setEvents([...events, newEvent])} 
                />
              </DialogContent>
            </Dialog>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Клиент</TableHead>
                  <TableHead>Тип события</TableHead>
                  <TableHead>Дата и время</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Место</TableHead>
                  <TableHead>Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => {
                  const client = clients.find(c => c.id === event.client_id);
                  const eventType = eventTypes.find(et => et.id === event.event_type_id);
                  return (
                    <TableRow key={event.id}>
                      <TableCell className="font-medium">
                        {client ? (
                          client.parent_id ? (
                            <>
                              <span className="text-muted-foreground text-sm">{getParentClient(client.id)?.first_name} → </span>
                              {getClientFullName(client)}
                            </>
                          ) : (
                            getClientFullName(client)
                          )
                        ) : 'Неизвестный'}
                      </TableCell>
                      <TableCell>
                        <Badge style={{ backgroundColor: eventType?.color + '40', color: eventType?.color }}>
                          {eventType?.name}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {new Date(event.start_time).toLocaleString('ru-RU')}
                      </TableCell>
                      <TableCell>
                        <Badge 
                          variant={
                            event.status === 'scheduled' ? 'default' :
                            event.status === 'completed' ? 'secondary' :
                            event.status === 'cancelled' ? 'destructive' : 'outline'
                          }
                        >
                          {event.status === 'scheduled' ? 'Запланировано' : 
                           event.status === 'completed' ? 'Завершено' : 
                           event.status === 'cancelled' ? 'Отменено' : 'Не явился'}
                        </Badge>
                      </TableCell>
                      <TableCell>{event.location}</TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button variant="outline" size="sm">
                            <EditIcon className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Вкладка "Платежи" */}
        <TabsContent value="payments" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold">Платежи</h2>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Добавить платеж
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Добавить новый платеж</DialogTitle>
                  <DialogDescription>
                    Зарегистрируйте платеж от клиента
                  </DialogDescription>
                </DialogHeader>
                <NewPaymentForm 
                  clients={clients} 
                  onSave={(newPayment) => setPayments([...payments, newPayment])} 
                />
              </DialogContent>
            </Dialog>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Клиент</TableHead>
                  <TableHead>Сумма</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Метод</TableHead>
                  <TableHead>Дата оплаты</TableHead>
                  <TableHead>Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {payments.map((payment) => {
                  const client = clients.find(c => c.id === payment.client_id);
                  return (
                    <TableRow key={payment.id}>
                      <TableCell className="font-medium">
                        {client ? (
                          client.parent_id ? (
                            <>
                              <span className="text-muted-foreground text-sm">{getParentClient(client.id)?.first_name} → </span>
                              {getClientFullName(client)}
                            </>
                          ) : (
                            getClientFullName(client)
                          )
                        ) : 'Неизвестный'}
                      </TableCell>
                      <TableCell className="font-semibold">{payment.amount} {payment.currency}</TableCell>
                      <TableCell>
                        <Badge 
                          variant={
                            payment.status === 'paid' ? 'secondary' :
                            payment.status === 'pending' ? 'default' :
                            payment.status === 'refunded' ? 'outline' : 'destructive'
                          }
                        >
                          {payment.status === 'paid' ? 'Оплачено' : 
                           payment.status === 'pending' ? 'В ожидании' : 
                           payment.status === 'refunded' ? 'Возврат' : 'Ошибка'}
                        </Badge>
                      </TableCell>
                      <TableCell>{payment.payment_method}</TableCell>
                      <TableCell>
                        {payment.paid_at ? new Date(payment.paid_at).toLocaleDateString('ru-RU') : '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button variant="outline" size="sm">
                            <EditIcon className="h-4 w-4" />
                          </Button>
                          <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                            <TrashIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Вкладка "Заметки" */}
        <TabsContent value="notes" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold">Заметки</h2>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Добавить заметку
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Добавить новую заметку</DialogTitle>
                  <DialogDescription>
                    Добавьте важную информацию о клиенте
                  </DialogDescription>
                </DialogHeader>
                <NewNoteForm 
                  clients={clients} 
                  onSave={(newNote) => setNotes([...notes, newNote])} 
                />
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid gap-6">
            {notes.map((note) => {
              const client = clients.find(c => c.id === note.client_id);
              return (
                <Card key={note.id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{note.title || 'Без заголовка'}</CardTitle>
                        <CardDescription>
                          {client ? (
                            client.parent_id ? (
                              <>
                                <span className="text-muted-foreground text-sm">{getParentClient(client.id)?.first_name} → </span>
                                {getClientFullName(client)}
                              </>
                            ) : (
                              getClientFullName(client)
                            )
                          ) : 'Неизвестный клиент'} • {new Date(note.created_at || Date.now()).toLocaleDateString('ru-RU')}
                        </CardDescription>
                      </div>
                      {note.is_important && (
                        <Badge variant="destructive">Важно</Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground whitespace-pre-line">{note.content}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* Вкладка "Категории" */}
        <TabsContent value="categories" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-semibold">Категории клиентов</h2>
            <Dialog>
              <DialogTrigger asChild>
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Добавить категорию
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Добавить новую категорию</DialogTitle>
                  <DialogDescription>
                    Создайте новую категорию для сегментации клиентов
                  </DialogDescription>
                </DialogHeader>
                <NewCategoryForm onSave={(newCategory) => setCategories([...categories, newCategory])} />
              </DialogContent>
            </Dialog>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {categories.map((category) => (
              <Card key={category.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{category.name}</CardTitle>
                    <div 
                      className="w-4 h-4 rounded-full border" 
                      style={{ backgroundColor: category.color }}
                    ></div>
                  </div>
                  <CardDescription>
                      {category.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground">
                    Клиентов в категории: {clients.filter(c => c.category_id === category.id).length}
                  </div>
                  <div className="flex justify-end mt-4 space-x-2">
                    <Button variant="outline" size="sm">
                      <EditIcon className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                      <TrashIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Формы для добавления новых элементов
function NewClientForm({ categories, clients, onSave }: { 
  categories: ClientCategory[], 
  clients: Client[],
  onSave: (client: Client) => void 
}) {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [categoryId, setCategoryId] = useState(categories[0]?.id || 1);
  const [status, setStatus] = useState<'active' | 'inactive' | 'archived'>('active');
  const [notes, setNotes] = useState('');
  const [parentId, setParentId] = useState<number | null>(null); // Добавлено поле для выбора родительского клиента

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newClient: Client = {
      id: Date.now(), // В реальном приложении это будет ID из базы данных
      first_name: firstName,
      last_name: lastName,
      email,
      phone,
      category_id: categoryId,
      status,
      photo_url: '',
      notes,
      parent_id: parentId // Добавлено поле parent_id
    };
    onSave(newClient);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="firstName">Имя</Label>
        <Input 
          id="firstName" 
          value={firstName} 
          onChange={(e) => setFirstName(e.target.value)} 
          required 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="lastName">Фамилия</Label>
        <Input 
          id="lastName" 
          value={lastName} 
          onChange={(e) => setLastName(e.target.value)} 
          required 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input 
          id="email" 
          type="email" 
          value={email} 
          onChange={(e) => setEmail(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="phone">Телефон</Label>
        <Input 
          id="phone" 
          value={phone} 
          onChange={(e) => setPhone(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="category">Категория</Label>
        <Select value={categoryId.toString()} onValueChange={(val) => setCategoryId(Number(val))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {categories.map((category) => (
              <SelectItem key={category.id} value={category.id.toString()}>
                {category.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="parent">Родительский клиент (необязательно)</Label>
        <Select 
          value={parentId?.toString() || ""} 
          onValueChange={(val) => setParentId(val ? Number(val) : null)}
        >
          <SelectTrigger>
            <SelectValue placeholder="Выберите родительский клиент" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Без родителя</SelectItem>
            {clients
              .filter(client => client.parent_id === null) // Только родительские клиенты
              .map((client) => (
                <SelectItem key={client.id} value={client.id.toString()}>
                  {getClientFullName(client)}
                </SelectItem>
              ))
            }
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="status">Статус</Label>
        <Select value={status} onValueChange={(val: 'active' | 'inactive' | 'archived') => setStatus(val)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="active">Активный</SelectItem>
            <SelectItem value="inactive">Неактивный</SelectItem>
            <SelectItem value="archived">В архиве</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="notes">Заметки</Label>
        <Input 
          id="notes" 
          value={notes} 
          onChange={(e) => setNotes(e.target.value)} 
        />
      </div>
      
      <Button type="submit" className="w-full">Добавить клиента</Button>
    </form>
  );
}

function NewEventForm({ clients, eventTypes, onSave }: { 
  clients: Client[], 
  eventTypes: EventType[], 
  onSave: (event: Event) => void 
}) {
  const [clientId, setClientId] = useState(clients[0]?.id || 1);
  const [eventTypeId, setEventTypeId] = useState(eventTypes[0]?.id || 1);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [startTime, setStartTime] = useState(new Date().toISOString().slice(0, 16));
  const [location, setLocation] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Рассчитываем end_time на основе duration_minutes из типа события
    const eventType = eventTypes.find(et => et.id === eventTypeId);
    const duration = eventType?.duration_minutes || 60;
    const endTime = new Date(startTime);
    endTime.setMinutes(endTime.getMinutes() + duration);
    
    const newEvent: Event = {
      id: Date.now(),
      client_id: clientId,
      event_type_id: eventTypeId,
      title,
      description,
      start_time: startTime,
      end_time: endTime.toISOString(),
      location,
      status: 'scheduled',
      notes: ''
    };
    
    onSave(newEvent);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="client">Клиент</Label>
        <Select value={clientId.toString()} onValueChange={(val) => setClientId(Number(val))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {clients.map((client) => (
              <SelectItem key={client.id} value={client.id.toString()}>
                {client.parent_id ? (
                  <>
                    <span className="text-muted-foreground text-sm">{getParentClientName(client, clients)} → </span>
                    {getClientFullName(client)}
                  </>
                ) : (
                  getClientFullName(client)
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="eventType">Тип события</Label>
        <Select value={eventTypeId.toString()} onValueChange={(val) => setEventTypeId(Number(val))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {eventTypes.map((type) => (
              <SelectItem key={type.id} value={type.id.toString()}>
                {type.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="title">Название</Label>
        <Input 
          id="title" 
          value={title} 
          onChange={(e) => setTitle(e.target.value)} 
          required 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">Описание</Label>
        <Input 
          id="description" 
          value={description} 
          onChange={(e) => setDescription(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="startTime">Дата и время начала</Label>
        <Input 
          id="startTime" 
          type="datetime-local" 
          value={startTime} 
          onChange={(e) => setStartTime(e.target.value)} 
          required 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="location">Место проведения</Label>
        <Input 
          id="location" 
          value={location} 
          onChange={(e) => setLocation(e.target.value)} 
        />
      </div>
      
      <Button type="submit" className="w-full">Назначить встречу</Button>
    </form>
  );
}

function NewPaymentForm({ clients, onSave }: { 
  clients: Client[], 
  onSave: (payment: Payment) => void 
}) {
  const [clientId, setClientId] = useState(clients[0]?.id || 1);
  const [amount, setAmount] = useState('');
  const [currency, setCurrency] = useState('RUB');
  const [status, setStatus] = useState<'pending' | 'paid' | 'failed' | 'refunded'>('pending');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newPayment: Payment = {
      id: Date.now(),
      client_id: clientId,
      amount: parseFloat(amount),
      currency,
      status,
      payment_method: paymentMethod,
      transaction_id: 'txn_' + Date.now().toString(),
      description,
      paid_at: status === 'paid' ? new Date().toISOString() : null
    };
    onSave(newPayment);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="client">Клиент</Label>
        <Select value={clientId.toString()} onValueChange={(val) => setClientId(Number(val))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {clients.map((client) => (
              <SelectItem key={client.id} value={client.id.toString()}>
                {client.parent_id ? (
                  <>
                    <span className="text-muted-foreground text-sm">{getParentClientName(client, clients)} → </span>
                    {getClientFullName(client)}
                  </>
                ) : (
                  getClientFullName(client)
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="amount">Сумма</Label>
        <Input 
          id="amount" 
          type="number" 
          value={amount} 
          onChange={(e) => setAmount(e.target.value)} 
          required 
          step="0.01"
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="currency">Валюта</Label>
        <Select value={currency} onValueChange={setCurrency}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="RUB">RUB</SelectItem>
            <SelectItem value="USD">USD</SelectItem>
            <SelectItem value="EUR">EUR</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="status">Статус</Label>
        <Select 
          value={status} 
          onValueChange={(val: 'pending' | 'paid' | 'failed' | 'refunded') => setStatus(val)}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="pending">В ожидании</SelectItem>
            <SelectItem value="paid">Оплачено</SelectItem>
            <SelectItem value="failed">Ошибка</SelectItem>
            <SelectItem value="refunded">Возврат</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="method">Метод оплаты</Label>
        <Input 
          id="method" 
          value={paymentMethod} 
          onChange={(e) => setPaymentMethod(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">Описание</Label>
        <Input 
          id="description" 
          value={description} 
          onChange={(e) => setDescription(e.target.value)} 
        />
      </div>
      
      <Button type="submit" className="w-full">Добавить платеж</Button>
    </form>
  );
}

function NewNoteForm({ clients, onSave }: { 
  clients: Client[], 
  onSave: (note: Note) => void 
}) {
  const [clientId, setClientId] = useState(clients[0]?.id || 1);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [isImportant, setIsImportant] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newNote: Note = {
      id: Date.now(),
      client_id: clientId,
      title,
      content,
      is_important: isImportant
    };
    onSave(newNote);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="client">Клиент</Label>
        <Select value={clientId.toString()} onValueChange={(val) => setClientId(Number(val))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {clients.map((client) => (
              <SelectItem key={client.id} value={client.id.toString()}>
                {client.parent_id ? (
                  <>
                    <span className="text-muted-foreground text-sm">{getParentClientName(client, clients)} → </span>
                    {getClientFullName(client)}
                  </>
                ) : (
                  getClientFullName(client)
                )}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="title">Заголовок</Label>
        <Input 
          id="title" 
          value={title} 
          onChange={(e) => setTitle(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="content">Содержание</Label>
        <textarea 
          id="content" 
          value={content} 
          onChange={(e) => setContent(e.target.value)} 
          className="w-full p-2 border rounded-md min-h-[100px]"
          required
        />
      </div>
      
      <div className="flex items-center space-x-2">
        <input 
          type="checkbox" 
          id="isImportant" 
          checked={isImportant} 
          onChange={(e) => setIsImportant(e.target.checked)} 
          className="h-4 w-4"
        />
        <Label htmlFor="isImportant">Важная заметка</Label>
      </div>
      
      <Button type="submit" className="w-full">Добавить заметку</Button>
    </form>
  );
}

function NewCategoryForm({ onSave }: { onSave: (category: ClientCategory) => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#4A90E2');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newCategory: ClientCategory = {
      id: Date.now(),
      name,
      description,
      color
    };
    onSave(newCategory);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Название</Label>
        <Input 
          id="name" 
          value={name} 
          onChange={(e) => setName(e.target.value)} 
          required 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="description">Описание</Label>
        <Input 
          id="description" 
          value={description} 
          onChange={(e) => setDescription(e.target.value)} 
        />
      </div>
      
      <div className="space-y-2">
        <Label htmlFor="color">Цвет</Label>
        <div className="flex items-center space-x-2">
          <input 
            type="color" 
            id="color" 
            value={color} 
            onChange={(e) => setColor(e.target.value)} 
            className="w-12 h-10 border rounded cursor-pointer"
          />
          <Input 
            value={color} 
            onChange={(e) => setColor(e.target.value)} 
            className="w-24"
            maxLength={7}
          />
        </div>
      </div>
      
      <Button type="submit" className="w-full">Добавить категорию</Button>
    </form>
  );
}

// Вспомогательные функции
const getClientFullName = (client: Client) => {
  return `${client.first_name} ${client.last_name}`;
};

const getParentClientName = (client: Client, allClients: Client[]): string => {
  if (!client.parent_id) return '';
  const parent = allClients.find(c => c.id === client.parent_id);
  return parent ? `${parent.first_name} ${parent.last_name}` : '';
};