import { Alert } from './Alert';
import { Card, CardContent, CardHeader, CardTitle } from './ui';

export function ValidationPanel({ errors, onClose }) {
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
            {errors.map((e, i) => (
              <Alert key={i} variant="error">
                <div className="flex gap-2">
                  <span>⚠</span>
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
