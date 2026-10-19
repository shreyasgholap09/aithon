import React from 'react';
import { AlertCircle, Clock, MapPin, User, CheckCircle2, ShieldAlert } from 'lucide-react';
import RiskBadge from './RiskBadge';

export default function AlertCard({ alert, onDismiss }) {
  if (!alert) return null;

  const isCritical = alert.risk_level === 'CRITICAL';
  const timeStr = alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : 'Now';

  const formatViolation = (v) => {
    return v
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div
      className={`relative rounded-xl p-4 transition-all duration-300 border backdrop-blur-md ${
        isCritical
          ? 'bg-rose-950/30 border-rose-500/40 shadow-lg shadow-rose-950/50 ring-1 ring-rose-500/30'
          : 'bg-slate-900/70 border-slate-700/60 hover:border-slate-600'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div
            className={`p-2 rounded-lg ${
              isCritical
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30 animate-pulse'
                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-white flex items-center gap-1">
                <User className="w-3.5 h-3.5 text-slate-400" />
                {alert.worker_id}
              </span>
              <RiskBadge level={alert.risk_level} score={alert.risk_score} size="sm" />
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
              <MapPin className="w-3 h-3 text-slate-500" />
              {alert.location || 'Monitored Zone'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1">
            <Clock className="w-3 h-3 text-slate-500" />
            {timeStr}
          </span>
          {onDismiss && (
            <button
              onClick={() => onDismiss(alert)}
              className="text-xs px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition"
              title="Acknowledge alert"
            >
              Resolve
            </button>
          )}
        </div>
      </div>

      {/* Violations tags */}
      {alert.violations && alert.violations.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {alert.violations.map((v, i) => (
            <span
              key={i}
              className={`text-[11px] font-semibold px-2 py-0.5 rounded border ${
                v === 'fall_detected'
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  : v === 'danger_zone_entry'
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                  : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
              }`}
            >
              {formatViolation(v)}
            </span>
          ))}
        </div>
      )}

      {/* Description details */}
      {alert.details && (
        <p className="mt-2.5 text-xs text-slate-300/90 leading-relaxed bg-slate-950/40 p-2 rounded-lg border border-slate-800">
          {alert.details}
        </p>
      )}
    </div>
  );
}
