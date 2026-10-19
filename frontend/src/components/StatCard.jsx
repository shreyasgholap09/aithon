import React from 'react';

export default function StatCard({
  title,
  value,
  subtext,
  icon: Icon,
  trend,
  color = 'emerald',
  badge
}) {
  const colorSchemes = {
    emerald: {
      border: 'border-emerald-500/20 hover:border-emerald-500/40',
      bgGlow: 'from-emerald-500/10 to-transparent',
      iconBg: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
      textAccent: 'text-emerald-400'
    },
    amber: {
      border: 'border-amber-500/20 hover:border-amber-500/40',
      bgGlow: 'from-amber-500/10 to-transparent',
      iconBg: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
      textAccent: 'text-amber-400'
    },
    rose: {
      border: 'border-rose-500/20 hover:border-rose-500/40',
      bgGlow: 'from-rose-500/10 to-transparent',
      iconBg: 'bg-rose-500/15 text-rose-400 border border-rose-500/30',
      textAccent: 'text-rose-400'
    },
    blue: {
      border: 'border-cyan-500/20 hover:border-cyan-500/40',
      bgGlow: 'from-cyan-500/10 to-transparent',
      iconBg: 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30',
      textAccent: 'text-cyan-400'
    },
    indigo: {
      border: 'border-indigo-500/20 hover:border-indigo-500/40',
      bgGlow: 'from-indigo-500/10 to-transparent',
      iconBg: 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30',
      textAccent: 'text-indigo-400'
    }
  };

  const scheme = colorSchemes[color] || colorSchemes.emerald;

  return (
    <div className={`relative overflow-hidden rounded-2xl bg-slate-900/80 backdrop-blur-xl border ${scheme.border} p-5 transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 group`}>
      {/* Background radial gradient accent */}
      <div className={`absolute -right-8 -bottom-8 w-32 h-32 bg-gradient-to-br ${scheme.bgGlow} rounded-full blur-2xl pointer-events-none transition-all duration-500 group-hover:scale-125`} />

      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold tracking-wider uppercase text-slate-400 mb-1">
            {title}
          </p>
          <div className="flex items-baseline gap-2">
            <h3 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white font-mono">
              {value}
            </h3>
            {badge && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-medium">
                {badge}
              </span>
            )}
          </div>
        </div>

        {Icon && (
          <div className={`p-3 rounded-xl ${scheme.iconBg} shadow-inner`}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      {(subtext || trend) && (
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
          {trend && (
            <span className={`font-semibold ${trend.startsWith('+') ? 'text-rose-400' : 'text-emerald-400'}`}>
              {trend}
            </span>
          )}
          <span>{subtext}</span>
        </div>
      )}
    </div>
  );
}
