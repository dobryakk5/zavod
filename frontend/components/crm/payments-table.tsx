'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatInTenantTimezone } from '@/lib/timezone';
import { CopyIcon, EditIcon, TrashIcon } from 'lucide-react';

type PaymentStatus = 'pending' | 'paid' | 'failed' | 'refunded';

export type PaymentsTableContact = {
  id: number;
  name: string;
  parent_id?: number | null;
};

export type PaymentsTablePayment = {
  id: number;
  contact_id: number;
  event_id?: number | null;
  amount: number;
  currency: string;
  status: PaymentStatus;
  paid_at?: string | null;
};

type PaymentsTableProps<
  TPayment extends PaymentsTablePayment,
  TContact extends PaymentsTableContact,
> = {
  payments: TPayment[];
  contacts: TContact[];
  tenantTimezone: string;
  paymentLinkLoadingId?: number | null;
  paymentDeletingId?: number | null;
  eventDateById?: ReadonlyMap<number, string>;
  onCopyPaymentLink?: (payment: TPayment, contact?: TContact) => void;
  onEditPayment?: (payment: TPayment, contact?: TContact) => void;
  onDeletePayment?: (payment: TPayment, contact?: TContact) => void;
  emptyText?: string;
};

const getStatusLabel = (status: PaymentStatus): string => {
  if (status === 'paid') return 'Оплачено';
  if (status === 'pending') return 'В ожидании';
  if (status === 'refunded') return 'Возврат';
  return 'Ошибка';
};

const getStatusVariant = (status: PaymentStatus): 'default' | 'secondary' | 'destructive' | 'outline' => {
  if (status === 'paid') return 'secondary';
  if (status === 'pending') return 'default';
  if (status === 'refunded') return 'outline';
  return 'destructive';
};

const formatAmount = (amount: number): string => {
  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return '0';
  return new Intl.NumberFormat('ru-RU', {
    maximumFractionDigits: 0,
  }).format(Math.round(numeric));
};

const buildContactLabel = <TContact extends PaymentsTableContact>(
  contact: TContact | undefined,
  contactsById: Map<number, TContact>
): string => {
  if (!contact) return 'Неизвестный';
  if (!contact.parent_id) return contact.name;
  const parent = contactsById.get(contact.parent_id);
  if (!parent) return contact.name;
  return `${parent.name} → ${contact.name}`;
};

export function PaymentsTable<
  TPayment extends PaymentsTablePayment,
  TContact extends PaymentsTableContact,
>({
  payments,
  contacts,
  tenantTimezone,
  paymentLinkLoadingId = null,
  paymentDeletingId = null,
  eventDateById,
  onCopyPaymentLink,
  onEditPayment,
  onDeletePayment,
  emptyText = 'Нет платежей',
}: PaymentsTableProps<TPayment, TContact>) {
  const contactsById = new Map<number, TContact>(contacts.map((contact) => [contact.id, contact]));

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Клиент</TableHead>
            <TableHead>Сумма</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Дата оплаты</TableHead>
            <TableHead>Действия</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {payments.length > 0 ? (
            payments.map((payment) => {
              const contact = contactsById.get(payment.contact_id);
              const eventDate =
                payment.event_id != null ? eventDateById?.get(payment.event_id) : undefined;
              return (
                <TableRow key={payment.id}>
                  <TableCell className="font-medium">{buildContactLabel(contact, contactsById)}</TableCell>
                  <TableCell className="font-semibold">
                    {formatAmount(payment.amount)} {payment.currency}
                  </TableCell>
                  <TableCell>
                    <Badge variant={getStatusVariant(payment.status)}>{getStatusLabel(payment.status)}</Badge>
                  </TableCell>
                  <TableCell>
                    {eventDate
                      ? formatInTenantTimezone(eventDate, tenantTimezone, {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                        })
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {payment.paid_at
                      ? formatInTenantTimezone(payment.paid_at, tenantTimezone, {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                        })
                      : '-'}
                  </TableCell>
                  <TableCell>
                    <div className="flex space-x-2">
                      {onCopyPaymentLink && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onCopyPaymentLink(payment, contact)}
                          aria-label="Скопировать ссылку оплаты"
                          disabled={paymentLinkLoadingId === payment.id}
                        >
                          <CopyIcon className="h-4 w-4" />
                        </Button>
                      )}
                      {onEditPayment && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onEditPayment(payment, contact)}
                          aria-label="Редактировать платёж"
                        >
                          <EditIcon className="h-4 w-4" />
                        </Button>
                      )}
                      {onDeletePayment && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => onDeletePayment(payment, contact)}
                          aria-label="Удалить платёж"
                          disabled={paymentDeletingId === payment.id}
                        >
                          <TrashIcon className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })
          ) : (
            <TableRow>
              <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                {emptyText}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
