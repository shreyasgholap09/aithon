import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon, Flame } from 'lucide-react';

export default function RiskBadge({ level = 'SAFE', score, size = 'md' }) {
  const norm = (level || 'SAFE').toUpperCase();

  const configs = {
    SAFE: {
      label: 'SAFE',
      color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30 shadow-emerald-500/10',
      dot: 'bg-emerald-400',
      icon: ShieldCheck
    },
    LOW: {
      label: 'LOW RISK',
      color: 'text-blue-400 bg-blue-500/10 border-blue-500/30 shadow-blue-500/10',
      dot: 'bg-blue-400',
      icon: ShieldCheck
    },
    MEDIUM: {
      label: 'MEDIUM RISK',
      color: 'text-amber-400 bg-amber-500/10 border-amber-500/30 shadow-amber-500/10',
      dot: 'bg-amber-400 animate-pulse',
      icon: AlertTriangle
    },
    HIGH: {
      label: 'HIGH RISK',
      color: 'text-orange-400 bg-orange-500/10 border-orange-500/30 shadow-orange-500/10',
      dot: 'bg-orange-500 animate-ping',
      icon: AlertTriangle
    },
    CRITICAL: {
      label: 'CRITICAL',
      color: 'text-rose-400 bg-rose-500/15 border-rose-500/40 shadow-rose-500/20 ring-1 ring-rose-500/30',
      dot: 'bg-rose-500 animate-pulse',
      icon: AlertOctagon
    }
  };

  const cfg = configs[norm] || configs.SAFE;
  const Icon = cfg.icon;

  const sizeClasses = {
    sm: 'text-xs px-2.5 py-1 gap-1.5',
    md: 'text-xs px-3 py-1.5 gap-2 font-semibold',
    lg: 'text-sm px-4 py-2 gap-2.5 font-bold'
  };

  return (
    <span className={`inline-flex items-center rounded-full border backdrop-blur-md shadow-sm transition-all duration-300 ${cfg.color} ${sizeClasses[size] || sizeClasses.md}`}>
      <span className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      <Icon className={size === 'lg' ? 'w-4 h-4' : 'w-3.5 h-3.5'} />
      <span>{cfg.label}</span>
      {score !== undefined && (
        <span className="ml-1 pl-1.5 border-l border-current/25 font-mono text-[11px] opacity-90">
          {score}%
        </span>
      )}
    </span>
  );
}
