import { useState, useEffect, useRef } from 'react';

// ═══════════════════════════════════════════════════════════════════════════
// HOOKS (из production MindMap)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Автосохранение с debounce
 * @param {*} value - значение для отслеживания
 * @param {Function} onSave - async функция сохранения
 * @param {number} delay - задержка в мс (по умолчанию 500)
 */
export function useAutoSave(value, onSave, delay = 500) {
  const timerRef = useRef(null);
  const lastSavedRef = useRef(value);

  useEffect(() => {
    // Не сохраняем если значение не изменилось
    if (JSON.stringify(value) === JSON.stringify(lastSavedRef.current)) return;
    
    // Очищаем предыдущий таймер
    if (timerRef.current) clearTimeout(timerRef.current);
    
    // Устанавливаем новый таймер
    timerRef.current = setTimeout(() => {
      onSave(value);
      lastSavedRef.current = value;
    }, delay);

    // Cleanup
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, onSave, delay]);
}

/**
 * Определяет мобильное устройство
 * @returns {boolean} true если экран <= 768px
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handleChange = (e) => setIsMobile(e.matches);
    
    // Проверяем сразу
    handleChange(mql);
    
    // Подписываемся на изменения
    mql.addEventListener('change', handleChange);
    
    return () => mql.removeEventListener('change', handleChange);
  }, []);

  return isMobile;
}

/**
 * Управление временными сообщениями (автоматически исчезают)
 * @param {number} duration - длительность показа в мс (по умолчанию 3000)
 * @returns {[string|null, Function]} [message, showMessage]
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
 * @returns {object} { status, setLoading, setError, setSuccess, reset }
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
