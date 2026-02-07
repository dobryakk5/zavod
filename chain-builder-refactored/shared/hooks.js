import { useState, useEffect, useRef } from 'react';

// ═══════════════════════════════════════════════════════════════════════════
// SHARED HOOKS
// Используются в ChainBuilder и MindMap
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Автосохранение с debounce
 * Общий хук для ChainBuilder и MindMap
 */
export function useAutoSave(value, onSave, delay = 500) {
  const timerRef = useRef(null);
  const lastSavedRef = useRef(value);

  useEffect(() => {
    if (JSON.stringify(value) === JSON.stringify(lastSavedRef.current)) return;
    
    if (timerRef.current) clearTimeout(timerRef.current);
    
    timerRef.current = setTimeout(() => {
      onSave(value);
      lastSavedRef.current = value;
    }, delay);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, onSave, delay]);
}

/**
 * Определяет мобильное устройство
 * Общий хук для адаптивности
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handleChange = (e) => setIsMobile(e.matches);
    
    handleChange(mql);
    mql.addEventListener('change', handleChange);
    
    return () => mql.removeEventListener('change', handleChange);
  }, []);

  return isMobile;
}

/**
 * Управление временными сообщениями
 * Общий хук для уведомлений
 */
export function useTemporaryMessage(duration = 3000) {
  const [message, setMessage] = useState(null);
  const timerRef = useRef(null);

  const showMessage = (text) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setMessage(text);
    timerRef.current = setTimeout(() => setMessage(null), duration);
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return [message, showMessage];
}

/**
 * Управление состоянием загрузки/ошибок
 * Общий хук для async операций
 */
export function useAsyncStatus() {
  const [status, setStatus] = useState({
    loading: false,
    error: null,
    success: null,
  });

  return {
    status,
    setLoading: (loading) => setStatus(prev => ({ ...prev, loading, error: null })),
    setError: (error) => setStatus({ loading: false, error, success: null }),
    setSuccess: (success) => setStatus({ loading: false, error: null, success }),
    reset: () => setStatus({ loading: false, error: null, success: null }),
  };
}

/**
 * Drag & Drop для переупорядочивания
 * Общая логика для списков
 */
export function useDragAndDrop(items, setItems) {
  const [draggedItem, setDraggedItem] = useState(null);

  const handleDragStart = (itemId) => {
    setDraggedItem(itemId);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
  };

  const handleDrop = (targetId) => {
    if (!draggedItem || draggedItem === targetId) return;

    setItems((prev) => {
      const draggedIdx = prev.findIndex((item) => item.id === draggedItem || item.key === draggedItem);
      const targetIdx = prev.findIndex((item) => item.id === targetId || item.key === targetId);
      
      if (draggedIdx === -1 || targetIdx === -1) return prev;

      const reordered = [...prev];
      const [removed] = reordered.splice(draggedIdx, 1);
      reordered.splice(targetIdx, 0, removed);

      // Обновить order_index если есть
      return reordered.map((item, i) => ({ 
        ...item, 
        order_index: i 
      }));
    });
  };

  return {
    draggedItem,
    handleDragStart,
    handleDragEnd,
    handleDrop,
  };
}
