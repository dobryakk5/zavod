/**
 * Alert component для отображения уведомлений
 * Использование:
 * 
 * <Alert variant="error">Ошибка сохранения</Alert>
 * <Alert variant="success">Успешно сохранено!</Alert>
 * <Alert variant="warning">Внимание!</Alert>
 * <Alert variant="info">Загрузка данных...</Alert>
 */
export function Alert({ children, variant = 'info' }) {
  const variantStyles = {
    info: {
      container: 'bg-blue-50 text-blue-900 border-blue-200',
      icon: '💡'
    },
    error: {
      container: 'bg-red-50 text-red-900 border-red-200',
      icon: '❌'
    },
    warning: {
      container: 'bg-amber-50 text-amber-900 border-amber-200',
      icon: '⚠️'
    },
    success: {
      container: 'bg-emerald-50 text-emerald-900 border-emerald-200',
      icon: '✓'
    },
  };

  const styles = variantStyles[variant] || variantStyles.info;

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm flex items-start gap-2 ${styles.container}`}>
      <span className="text-lg leading-none">{styles.icon}</span>
      <div className="flex-1">{children}</div>
    </div>
  );
}
