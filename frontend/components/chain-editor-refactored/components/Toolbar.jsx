import { useState } from 'react';
import { Button } from './ui';

const ADD_NODE_OPTIONS = [
  { type: 'message', label: 'Сообщение', icon: '💬' },
  { type: 'buttons', label: 'Кнопки', icon: '🔘' },
  { type: 'timer', label: 'Задержка', icon: '⏱️' },
  { type: 'router', label: 'Условие', icon: '🔀' },
];

export function Toolbar({ chain, dirty, onSave, onAddNode, onStatusChange, saving }) {
  const [statusOpen, setStatusOpen] = useState(false);
  const [addNodeOpen, setAddNodeOpen] = useState(false);

  return (
    <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-slate-200 flex-wrap">
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-semibold text-slate-900">{chain.name}</h1>

        <div className="relative">
          <button
            onClick={() => setStatusOpen(!statusOpen)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              chain.status === 'active'
                ? 'bg-emerald-100 text-emerald-700'
                : chain.status === 'paused'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-slate-100 text-slate-700'
            }`}
          >
            {chain.status} ▾
          </button>
          {statusOpen && (
            <>
              <div onClick={() => setStatusOpen(false)} className="fixed inset-0 z-10" />
              <div className="absolute top-full left-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 min-w-[120px]">
                {['draft', 'active', 'paused', 'archived'].map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      onStatusChange(s);
                      setStatusOpen(false);
                    }}
                    className="block w-full text-left px-4 py-2 text-sm hover:bg-slate-50 first:rounded-t-lg last:rounded-b-lg"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="flex-1" />

      <div className="relative">
        <Button variant="outline" onClick={() => setAddNodeOpen((v) => !v)}>+ Узел</Button>
        {addNodeOpen && (
          <>
            <div onClick={() => setAddNodeOpen(false)} className="fixed inset-0 z-10" />
            <div className="absolute top-full right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-20 min-w-[160px]">
              {ADD_NODE_OPTIONS.map((opt) => (
                <button
                  key={opt.type}
                  onClick={() => { onAddNode(opt.type); setAddNodeOpen(false); }}
                  className="block w-full text-left px-4 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
                >
                  <span>{opt.icon}</span>
                  <span>{opt.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      <Button variant="primary" onClick={onSave} disabled={!dirty || saving}>
        {saving ? 'Сохранение...' : dirty ? '💾 Сохранить' : 'Сохранено'}
      </Button>
    </div>
  );
}
