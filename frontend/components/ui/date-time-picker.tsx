'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { CalendarClock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

type DateTimePickerProps = {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

const splitDateTime = (value: string): { date: string; time: string } => {
  const trimmed = (value || '').trim();
  const [datePart = '', timePart = ''] = trimmed.split('T');
  return {
    date: /^\d{4}-\d{2}-\d{2}$/.test(datePart) ? datePart : '',
    time: /^\d{2}:\d{2}$/.test(timePart) ? timePart : '',
  };
};

const formatDateTimeLabel = (date: string, time: string, placeholder: string): string => {
  if (!date && !time) return placeholder;
  if (!date) return time;
  const [yyyy, mm, dd] = date.split('-');
  if (!yyyy || !mm || !dd) return placeholder;
  const dateLabel = `${dd}.${mm}.${yyyy}`;
  return time ? `${dateLabel} ${time}` : dateLabel;
};

export function DateTimePicker({
  value,
  onChange,
  disabled = false,
  placeholder = 'Выберите дату и время',
}: DateTimePickerProps) {
  const [open, setOpen] = useState(false);
  const dateInputRef = useRef<HTMLInputElement | null>(null);
  const dateFieldId = useId();
  const timeFieldId = useId();
  const parts = useMemo(() => splitDateTime(value), [value]);
  const label = useMemo(() => formatDateTimeLabel(parts.date, parts.time, placeholder), [parts.date, parts.time, placeholder]);

  useEffect(() => {
    if (!open || disabled || parts.date) return;
    const frameId = window.requestAnimationFrame(() => {
      const input = dateInputRef.current;
      if (!input) return;
      input.focus({ preventScroll: true });
      const pickerInput = input as HTMLInputElement & { showPicker?: () => void };
      if (typeof pickerInput.showPicker === 'function') {
        try {
          pickerInput.showPicker();
        } catch {}
      }
    });
    return () => window.cancelAnimationFrame(frameId);
  }, [disabled, open, parts.date]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className="w-full justify-between text-left font-normal"
          disabled={disabled}
        >
          <span className={parts.date ? '' : 'text-muted-foreground'}>{label}</span>
          <CalendarClock className="h-4 w-4 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 space-y-3 p-3" align="start">
        <div className="space-y-1">
          <Label htmlFor={dateFieldId}>Дата</Label>
          <Input
            id={dateFieldId}
            ref={dateInputRef}
            type="date"
            value={parts.date}
            onChange={(e) => {
              const nextDate = e.target.value;
              if (!nextDate) {
                onChange('');
                return;
              }
              onChange(`${nextDate}T${parts.time || '12:00'}`);
            }}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={timeFieldId}>Время</Label>
          <Input
            id={timeFieldId}
            type="time"
            step="60"
            value={parts.time}
            onChange={(e) => {
              const nextTime = e.target.value;
              if (!parts.date) return;
              onChange(nextTime ? `${parts.date}T${nextTime}` : `${parts.date}T12:00`);
            }}
            disabled={disabled || !parts.date}
          />
        </div>
        <div className="flex justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onChange('')}
            disabled={disabled || (!parts.date && !parts.time)}
          >
            Очистить
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
