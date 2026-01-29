// Types for the map CRM system

export type Contact = {
  id: number;
  name: string;
  email: string;
  phone: string;
  category_id: number | null;
  status: 'active' | 'inactive' | 'archived';
  photo_url: string;
  notes: string;
  parent_id: number | null;
  created_at: string;
  updated_at: string;
};

export type Tag = {
  id: number;
  type: 'goal' | 'pain' | 'experience';
  value: string;
  created_at: string;
};

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
  created_at: string;
  updated_at: string;
};

export type Payment = {
  id: number;
  contact_id: number;
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

export type Note = {
  id: number;
  contact_id: number;
  title: string;
  content: string;
  is_important: boolean;
  created_at: string;
  updated_at: string;
};
