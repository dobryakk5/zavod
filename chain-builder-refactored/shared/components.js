// ═══════════════════════════════════════════════════════════════════════════
// SHARED COMPONENTS
// Используются в ChainBuilder и MindMap
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Alert component для уведомлений
 * Общий для ChainBuilder и MindMap
 */
export function Alert({ children, variant = 'info' }) {
  const variantStyles = {
    info: 'bg-blue-50 text-blue-900 border-blue-200',
    error: 'bg-red-50 text-red-900 border-red-200',
    warning: 'bg-amber-50 text-amber-900 border-amber-200',
    success: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  };

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${variantStyles[variant]}`}>
      {children}
    </div>
  );
}

/**
 * Label component
 * Общий для всех форм
 */
export function Label({ children, className = '' }) {
  return (
    <label className={`block text-sm font-medium text-slate-700 mb-1.5 ${className}`}>
      {children}
    </label>
  );
}

/**
 * LoadingSpinner
 * Общий индикатор загрузки
 */
export function LoadingSpinner({ text = 'Загрузка...' }) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 mb-4"></div>
        <p className="text-slate-600">{text}</p>
      </div>
    </div>
  );
}

/**
 * EmptyState
 * Общий компонент для пустых состояний
 */
export function EmptyState({ 
  icon, 
  title, 
  description, 
  action 
}) {
  return (
    <div className="text-center py-12 px-4">
      {icon && <div className="text-4xl mb-4">{icon}</div>}
      <h3 className="text-lg font-semibold text-slate-900 mb-2">{title}</h3>
      {description && <p className="text-sm text-slate-600 mb-6">{description}</p>}
      {action}
    </div>
  );
}

/**
 * DraggableItem wrapper
 * Общая логика для drag & drop
 */
export function DraggableItem({ 
  children, 
  isDragging, 
  onDragStart, 
  onDragEnd,
  className = '' 
}) {
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`transition-all ${
        isDragging 
          ? 'opacity-50 cursor-grabbing' 
          : 'cursor-grab hover:shadow-sm'
      } ${className}`}
    >
      {children}
    </div>
  );
}

/**
 * SaveButton
 * Общая кнопка сохранения с состояниями
 */
export function SaveButton({ 
  onClick, 
  saving = false, 
  disabled = false,
  children = 'Сохранить'
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || saving}
      className={`px-4 py-2 rounded-lg text-sm font-medium inline-flex items-center gap-2 ${
        disabled || saving
          ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
          : 'bg-slate-900 text-white hover:bg-slate-800'
      }`}
    >
      {saving ? (
        <>
          <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
          Сохранение...
        </>
      ) : (
        children
      )}
    </button>
  );
}

/**
 * Card components
 * Общие компоненты карточек
 */
export function Card({ children, className = '' }) {
  return (
    <div className={`border-slate-200 bg-white shadow-sm rounded-xl ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`border-b border-slate-100 px-6 py-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = '' }) {
  return (
    <h3 className={`text-lg font-semibold text-slate-900 ${className}`}>
      {children}
    </h3>
  );
}

export function CardContent({ children, className = '' }) {
  return (
    <div className={`px-6 py-6 ${className}`}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`border-t border-slate-100 bg-slate-50/50 px-6 py-4 ${className}`}>
      {children}
    </div>
  );
}
