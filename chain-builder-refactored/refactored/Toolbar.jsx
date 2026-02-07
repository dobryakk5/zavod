import { useState } from "react";
import { NODE_TYPES } from './constants';

export function Toolbar({ chain, dirty, onSave, onAddNode, saving }) {
  const [statusOpen, setStatusOpen] = useState(false);
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  
  return (
    <div className="flex items-center gap-4 px-6 py-4 bg-white border-b border-slate-200">
      <h1 className="text-lg font-semibold text-slate-900">{chain.name}</h1>
      
      <div className="relative">
        <button 
          onClick={() => setStatusOpen(!statusOpen)} 
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            chain.status === "active" 
              ? "bg-emerald-100 text-emerald-700" 
              : "bg-slate-100 text-slate-600"
          }`}
        >
          {chain.status} ▾
        </button>
        {statusOpen && (
          <>
            <div onClick={() => setStatusOpen(false)} className="fixed inset-0 z-10" />
            <div className="absolute top-full left-0 mt-1 bg-white border rounded-lg shadow-lg z-20 min-w-[120px]">
              {["draft","active","paused"].map(s => (
                <button 
                  key={s} 
                  onClick={() => { onSave(s); setStatusOpen(false); }} 
                  className="block w-full text-left px-4 py-2 text-sm hover:bg-slate-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      
      <div className="flex-1" />
      
      {saving && <span className="text-sm text-slate-500 animate-pulse">💾 Сохранение...</span>}
      {dirty && !saving && <span className="text-sm text-amber-600">● Несохранённые изменения</span>}
      
      <div className="relative">
        <button 
          onClick={() => setAddNodeOpen(!addNodeOpen)} 
          className="px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-sm font-medium"
        >
          + Узел
        </button>
        {addNodeOpen && (
          <>
            <div onClick={() => setAddNodeOpen(false)} className="fixed inset-0 z-10" />
            <div className="absolute top-full right-0 mt-1 bg-white border rounded-lg shadow-lg z-20 min-w-[160px]">
              {NODE_TYPES.map(nt => (
                <button 
                  key={nt.type} 
                  onClick={() => { onAddNode(nt.type); setAddNodeOpen(false); }} 
                  className="block w-full text-left px-4 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
                >
                  <span>{nt.icon}</span>
                  <span>{nt.label}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
      
      <button 
        onClick={onSave} 
        disabled={!dirty || saving} 
        className={`px-4 py-2 rounded-lg text-sm font-medium ${
          dirty && !saving 
            ? 'bg-emerald-600 text-white hover:bg-emerald-700' 
            : 'bg-slate-200 text-slate-400 cursor-not-allowed'
        }`}
      >
        Сохранить
      </button>
    </div>
  );
}
