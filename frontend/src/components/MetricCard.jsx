import React from 'react';

const MetricCard = ({ title, value, subtitle, icon: Icon, color = 'blue' }) => {
  const colorMap = {
    blue: { text: 'text-accent', bg: 'bg-blue-50' },
    emerald: { text: 'text-emerald-600', bg: 'bg-emerald-50' },
    rose: { text: 'text-rose-600', bg: 'bg-rose-50' },
    slate: { text: 'text-slate-700', bg: 'bg-slate-100' },
    amber: { text: 'text-amber-600', bg: 'bg-amber-50' },
  };

  const c = colorMap[color] || colorMap.blue;

  return (
    <div className="bg-white rounded-xl p-5 border border-slate-200 card-shadow card-shadow-hover flex items-start justify-between">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">{title}</p>
        <p className="text-2xl font-bold text-slate-900 tracking-tight">{value}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-1 font-medium">{subtitle}</p>}
      </div>
      {Icon && (
        <div className={`p-2.5 rounded-lg ${c.bg}`}>
          <Icon className={`w-5 h-5 ${c.text}`} />
        </div>
      )}
    </div>
  );
};

export default MetricCard;

