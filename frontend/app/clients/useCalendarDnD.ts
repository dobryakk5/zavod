'use client';

import { useState, type DragEvent } from 'react';

type ClientYEvent = {
  clientY: number;
};

type Ghost = {
  dayKey?: string;
  top: number;
  height: number;
};

type Params = {
  startHour: number;
  pxPerMinute: number;
  slotMinutes: number;
};

export function useCalendarDnD({ startHour, pxPerMinute, slotMinutes }: Params) {
  const [draggingEventId, setDraggingEventId] = useState<number | null>(null);
  const [hoverMinutes, setHoverMinutes] = useState<number | null>(null);
  const [ghost, setGhost] = useState<Ghost | null>(null);

  function calcSlot(event: ClientYEvent, container: HTMLElement, maxMinutes?: number) {
    const rect = container.getBoundingClientRect();
    const slotHeight = pxPerMinute * slotMinutes;
    let offsetY = event.clientY - rect.top;
    if (maxMinutes !== undefined) {
      offsetY = Math.max(0, Math.min(offsetY, maxMinutes * pxPerMinute));
    }
    let slotIndex = Math.floor(offsetY / slotHeight);
    if (maxMinutes !== undefined) {
      const slotCount = Math.max(1, Math.floor(maxMinutes / slotMinutes));
      slotIndex = Math.min(slotCount - 1, slotIndex);
    }
    const minutes = Math.max(0, slotIndex * slotMinutes);
    return startHour * 60 + minutes;
  }

  function onDragStart(eventId: number, top: number, height: number, dayKey?: string) {
    setGhost({ top, height, dayKey });
    requestAnimationFrame(() => {
      setDraggingEventId(eventId);
    });
  }

  function onDragOver(event: DragEvent, container: HTMLElement, dayKey?: string) {
    event.preventDefault();
    const minutes = calcSlot(event, container);
    setHoverMinutes(minutes);
    setGhost({
      dayKey,
      top: (minutes - startHour * 60) * pxPerMinute,
      height: ghost?.height ?? pxPerMinute * slotMinutes,
    });
  }

  function onDragLeave() {
    setHoverMinutes(null);
    setGhost(null);
  }

  function onDragEnd() {
    setDraggingEventId(null);
    setGhost(null);
    setHoverMinutes(null);
  }

  return {
    draggingEventId,
    hoverMinutes,
    ghost,
    setGhost,
    calcSlot,
    onDragStart,
    onDragOver,
    onDragLeave,
    onDragEnd,
  };
}
