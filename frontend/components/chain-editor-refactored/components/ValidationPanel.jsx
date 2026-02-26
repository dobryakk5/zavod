import { Alert } from './Alert';
import { Card, CardContent, CardHeader, CardTitle } from './ui';

export function ValidationPanel({ errors, onClose }) {
  const errorCount = errors.filter((e) => (e?.severity || 'error') !== 'warning').length;
  const warningCount = errors.filter((e) => e?.severity === 'warning').length;

  return (
    <Card className="fixed top-20 right-6 w-80 z-30 shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Валидация</CardTitle>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">×</button>
        </div>
      </CardHeader>
      <CardContent>
        {errors.length === 0 ? (
          <Alert variant="success">✓ Всё в порядке!</Alert>
        ) : (
          <div className="space-y-2">
            <Alert variant={errorCount > 0 ? 'error' : 'warning'}>
              {errorCount > 0
                ? `Ошибок: ${errorCount}${warningCount ? `, предупреждений: ${warningCount}` : ''}`
                : `Предупреждений: ${warningCount}`}
            </Alert>
            {errors.map((e, i) => (
              <Alert key={i} variant={(e?.severity || 'error') === 'warning' ? 'warning' : 'error'}>
                <div className="flex gap-2">
                  <span>{(e?.severity || 'error') === 'warning' ? '!' : '⚠'}</span>
                  <span>{e.msg}</span>
                </div>
              </Alert>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
