import { useEffect, useRef, useState } from 'react';

// ═══════════════════════════════════════════════════════════════════════════
// HOOKS - Shared hooks (can be used in ChainBuilder too!)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Определяет мобильное устройство
 * @returns {boolean} true если экран <= 768px
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handleChange(mql);
    mql.addEventListener('change', handleChange as EventListener);
    return () => mql.removeEventListener('change', handleChange as EventListener);
  }, []);

  return isMobile;
}

/**
 * Автосохранение с debounce
 * @param {T} value - значение для отслеживания
 * @param {Function} onSave - async функция сохранения
 * @param {number} delay - задержка в мс (по умолчанию 500)
 */
export function useAutoSave<T>(
  value: T, 
  onSave: (value: T) => Promise<void>, 
  delay = 500
) {
  const timerRef = useRef<number | null>(null);
  const lastSavedRef = useRef<T>(value);

  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(lastSavedRef.current)) return;
    
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      void onSave(value);
      lastSavedRef.current = value;
    }, delay);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [value, onSave, delay]);
}

/**
 * Управление Drag & Drop состоянием
 */
export function useDragAndDrop<T extends { key: string }>() {
  const [draggedKey, setDraggedKey] = useState<string | null>(null);

  const handleDragStart = (key: string) => {
    setDraggedKey(key);
  };

  const handleDragEnd = () => {
    setDraggedKey(null);
  };

  const handleDrop = (
    targetKey: string, 
    items: T[], 
    setItems: (items: T[]) => void
  ) => {
    if (!draggedKey || draggedKey === targetKey) return;

    const draggedIdx = items.findIndex((item) => item.key === draggedKey);
    const targetIdx = items.findIndex((item) => item.key === targetKey);
    
    if (draggedIdx === -1 || targetIdx === -1) return;

    const reordered = [...items];
    const [removed] = reordered.splice(draggedIdx, 1);
    reordered.splice(targetIdx, 0, removed);

    setItems(reordered.map((item, i) => ({ 
      ...item, 
      order_index: i 
    } as T)));
  };

  return {
    draggedKey,
    handleDragStart,
    handleDragEnd,
    handleDrop,
  };
}

/**
 * Управление временными сообщениями
 */
export function useTemporaryMessage(duration = 3000) {
  const [message, setMessage] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  const showMessage = (text: string) => {
    if (timerRef.current) window.clearTimeout(timerRef.current);
    setMessage(text);
    timerRef.current = window.setTimeout(() => setMessage(null), duration);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, []);

  return [message, showMessage] as const;
}
