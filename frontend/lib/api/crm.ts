// API service for CRM functionality (contacts, events, payments, notes)
import { apiFetch } from '../api';

// Types for the map CRM system
export type TagType = 'goal' | 'pain' | 'experience';
export type DealStage = '' | 'new_lead' | 'interest' | 'call' | 'payment_expected' | 'paid' | 'lost';
export type DealLossReasonCode =
  | ''
  | 'price'
  | 'timing'
  | 'no_response'
  | 'not_fit'
  | 'competitor'
  | 'priority_changed'
  | 'other';

export type Contact = {
  id: number;
  name: string;
  email: string;
  phone: string;
  source?: string;
  deal_stage?: DealStage;
  deal_amount?: number | string | null;
  deal_loss_reason_code?: DealLossReasonCode;
  deal_loss_reason_text?: string;
  deal_lost_at?: string | null;
  category_id: number | null;
  status: 'active' | 'inactive' | 'archived';
  photo_url: string;
  notes: string;
  parent_id: number | null;
  tags?: Partial<Record<TagType, number[]>>;
  created_at: string;
  updated_at: string;
};

export type Tag = {
  id: number;
  type: TagType;
  value: string;
  created_at: string;
};

export type Category = {
  id: number;
  name: string;
  description: string;
  color: string;
  created_at: string;
  updated_at: string;
};

export type ContactTag = {
  contact_id: number;
  tag_id: number;
  type: TagType;
  value: string;
  description: string;
};

type ContactTagApiRow = {
  contact_id: number;
  tag_id: number;
  type?: TagType;
  value?: string;
  tag_type?: TagType;
  tag_value?: string;
  description?: string | null;
};

export type ContactCreatePayload = Pick<Contact, 'name'> &
  Partial<Omit<Contact, 'id' | 'name' | 'created_at' | 'updated_at'>>;
export type ContactUpdatePayload = Partial<Omit<Contact, 'id' | 'created_at' | 'updated_at'>>;

export type EventType = {
  id: number;
  name: string;
  description: string;
  duration_minutes: number;
  color: string;
  created_at: string;
};

export type Event = {
  id: number;
  contact_id: number;
  event_type_id: number | null;
  title: string;
  description: string;
  start_time: string;
  end_time: string;
  location: string;
  status: 'scheduled' | 'completed' | 'cancelled' | 'no_show';
  notes: string;
  price?: number | null;
  created_at: string;
  updated_at: string;
};

export type AvailabilityEvent = {
  id: number;
  tenant_id: number;
  start_time: string;
  duration_minutes: number;
  repeat_type: 0 | 1 | 2 | 3;
  created_at: string;
  updated_at: string;
};

export type Payment = {
  id: number;
  contact_id: number;
  event_id?: number | null;
  product_id: number | null;
  amount: number;
  currency: string;
  status: 'pending' | 'paid' | 'failed' | 'refunded';
  payment_method: string;
  transaction_id: string;
  description: string;
  planned_at: string | null;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
};

export type YooKassaPaymentLinkResponse = {
  id?: string;
  status?: string;
  confirmation_url?: string;
  payment_url?: string;
};

export type Note = {
  id: number;
  contact_id: number;
  title: string;
  content: string;
  is_important: boolean;
  created_at: string;
  updated_at: string;
};

export type ContactTelegramInfo = {
  contact_id: number;
  tenant_id: number;
  telegram_chat_id: number | null;
  tg_name: string | null;
  is_connected: boolean;
  link: string;
};

export type ServicePackageBalance = {
  enabled: boolean;
  mode: 'count' | 'minutes';
  package_name?: string | null;
  total_units: number;
  used_units: number;
  remaining_units: number;
  is_exhausted: boolean;
  total_label: string;
  used_label: string;
  remaining_label: string;
  total_sessions?: number;
  used_sessions?: number;
  remaining_sessions?: number;
  total_minutes?: number;
  used_minutes?: number;
  remaining_minutes?: number;
};

export type ContactServicePackageItem = {
  purchase_id: number;
  product_id: number;
  product_name: string;
  paid_at: string | null;
  amount: string | null;
  currency: string;
  service_package: ServicePackageBalance;
};

export type ContactServicePackagesResponse = {
  contact_id: number;
  items: ContactServicePackageItem[];
};

// API functions for contacts
export const crmContactsApi = {
  list: async (): Promise<Contact[]> => {
    return apiFetch<Contact[]>('/crm/contacts/');
  },

  detail: async (id: number | string): Promise<Contact> => {
    return apiFetch<Contact>(`/crm/contacts/${id}/`);
  },

  create: async (data: ContactCreatePayload): Promise<Contact> => {
    return apiFetch<Contact>('/crm/contacts/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: ContactUpdatePayload): Promise<Contact> => {
    return apiFetch<Contact>(`/crm/contacts/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/contacts/${id}/`, {
      method: 'DELETE',
    });
  },

  telegramLink: async (id: number | string): Promise<ContactTelegramInfo> => {
    return apiFetch<ContactTelegramInfo>(`/crm/contacts/${id}/telegram-link/`);
  },

  servicePackages: async (id: number | string): Promise<ContactServicePackagesResponse> => {
    return apiFetch<ContactServicePackagesResponse>(`/crm/contacts/${id}/service-packages/`);
  },
};

// API functions for tags
export const crmTagsApi = {
  list: async (): Promise<Tag[]> => {
    return apiFetch<Tag[]>('/crm/tags/');
  },

  detail: async (id: number | string): Promise<Tag> => {
    return apiFetch<Tag>(`/crm/tags/${id}/`);
  },

  create: async (data: Omit<Tag, 'id' | 'created_at'>): Promise<Tag> => {
    return apiFetch<Tag>('/crm/tags/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<Tag, 'id' | 'created_at'>>): Promise<Tag> => {
    return apiFetch<Tag>(`/crm/tags/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/tags/${id}/`, {
      method: 'DELETE',
    });
  },
};

// API functions for contact-tags relationships
export const crmContactTagsApi = {
  list: async (contactId: number | string): Promise<ContactTag[]> => {
    const rows = await apiFetch<ContactTagApiRow[]>(`/crm/contact-tags/?contact_id=${contactId}`);
    return rows.map((row) => ({
      contact_id: row.contact_id,
      tag_id: row.tag_id,
      type: row.type || row.tag_type || 'goal',
      value: row.value || row.tag_value || '',
      description: row.description || '',
    }));
  },

  create: async (data: { contact_id: number; tag_id: number }): Promise<{ success: boolean }> => {
    return apiFetch<{ success: boolean }>('/crm/contact-tags/', {
      method: 'POST',
      body: data,
    });
  },

  upsert: async (data: { contact_id: number; tag_id: number; description?: string | null }): Promise<{ success: boolean }> => {
    return apiFetch<{ success: boolean }>('/crm/contact-tags/', {
      method: 'POST',
      body: data,
    });
  },

  delete: async (data: { contact_id: number; tag_id: number }): Promise<void> => {
    return apiFetch<void>('/crm/contact-tags/', {
      method: 'DELETE',
      body: data,
    });
  },
};

// API functions for categories
export const crmCategoriesApi = {
  list: async (): Promise<Category[]> => {
    return apiFetch<Category[]>('/crm/categories/');
  },

  detail: async (id: number | string): Promise<Category> => {
    return apiFetch<Category>(`/crm/categories/${id}/`);
  },

  create: async (data: Omit<Category, 'id' | 'created_at' | 'updated_at'>): Promise<Category> => {
    return apiFetch<Category>('/crm/categories/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<Category, 'id' | 'created_at' | 'updated_at'>>): Promise<Category> => {
    return apiFetch<Category>(`/crm/categories/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/categories/${id}/`, {
      method: 'DELETE',
    });
  },
};

// API functions for event types
export const crmEventTypesApi = {
  list: async (): Promise<EventType[]> => {
    return apiFetch<EventType[]>('/crm/event-types/');
  },

  detail: async (id: number | string): Promise<EventType> => {
    return apiFetch<EventType>(`/crm/event-types/${id}/`);
  },

  create: async (data: Omit<EventType, 'id' | 'created_at'>): Promise<EventType> => {
    return apiFetch<EventType>('/crm/event-types/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<EventType, 'id' | 'created_at'>>): Promise<EventType> => {
    return apiFetch<EventType>(`/crm/event-types/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/event-types/${id}/`, {
      method: 'DELETE',
    });
  },
};

// API functions for events
export const crmEventsApi = {
  list: async (): Promise<Event[]> => {
    return apiFetch<Event[]>('/crm/events/');
  },

  detail: async (id: number | string): Promise<Event> => {
    return apiFetch<Event>(`/crm/events/${id}/`);
  },

  create: async (data: Omit<Event, 'id' | 'created_at' | 'updated_at'>): Promise<Event> => {
    return apiFetch<Event>('/crm/events/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<Event, 'id' | 'created_at' | 'updated_at'>>): Promise<Event> => {
    return apiFetch<Event>(`/crm/events/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/events/${id}/`, {
      method: 'DELETE',
    });
  },
};

export const crmAvailabilityEventsApi = {
  list: async (): Promise<AvailabilityEvent[]> => {
    return apiFetch<AvailabilityEvent[]>('/crm/availability-events/');
  },

  detail: async (id: number | string): Promise<AvailabilityEvent> => {
    return apiFetch<AvailabilityEvent>(`/crm/availability-events/${id}/`);
  },

  create: async (data: { start_time: string; duration_minutes: number; repeat_type: AvailabilityEvent['repeat_type'] }): Promise<AvailabilityEvent> => {
    return apiFetch<AvailabilityEvent>('/crm/availability-events/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<{ start_time: string; duration_minutes: number; repeat_type: AvailabilityEvent['repeat_type'] }>): Promise<AvailabilityEvent> => {
    return apiFetch<AvailabilityEvent>(`/crm/availability-events/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/availability-events/${id}/`, {
      method: 'DELETE',
    });
  },
};

// API functions for payments
export const crmPaymentsApi = {
  list: async (): Promise<Payment[]> => {
    return apiFetch<Payment[]>('/crm/payments/');
  },

  detail: async (id: number | string): Promise<Payment> => {
    return apiFetch<Payment>(`/crm/payments/${id}/`);
  },

  create: async (data: Omit<Payment, 'id' | 'created_at' | 'updated_at'>): Promise<Payment> => {
    return apiFetch<Payment>('/crm/payments/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<Payment, 'id' | 'created_at' | 'updated_at'>>): Promise<Payment> => {
    return apiFetch<Payment>(`/crm/payments/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/payments/${id}/`, {
      method: 'DELETE',
    });
  },

  generateYooKassaLink: async (data: {
    amount: number;
    currency?: string;
    description?: string;
    metadata?: Record<string, string>;
    return_url?: string;
  }): Promise<YooKassaPaymentLinkResponse> => {
    return apiFetch<YooKassaPaymentLinkResponse>('/payments/link/', {
      method: 'POST',
      body: data,
    });
  },
};

// API functions for notes
export const crmNotesApi = {
  list: async (): Promise<Note[]> => {
    return apiFetch<Note[]>('/crm/notes/');
  },

  detail: async (id: number | string): Promise<Note> => {
    return apiFetch<Note>(`/crm/notes/${id}/`);
  },

  create: async (data: Omit<Note, 'id' | 'created_at' | 'updated_at'>): Promise<Note> => {
    return apiFetch<Note>('/crm/notes/', {
      method: 'POST',
      body: data,
    });
  },

  update: async (id: number | string, data: Partial<Omit<Note, 'id' | 'created_at' | 'updated_at'>>): Promise<Note> => {
    return apiFetch<Note>(`/crm/notes/${id}/`, {
      method: 'PATCH',
      body: data,
    });
  },

  delete: async (id: number | string): Promise<void> => {
    return apiFetch<void>(`/crm/notes/${id}/`, {
      method: 'DELETE',
    });
  },
};
