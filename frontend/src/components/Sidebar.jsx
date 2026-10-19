import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, AlertOctagon, BarChart3, ShieldCheck, Database, HardHat } from 'lucide-react';

export default function Sidebar({ incidentCount = 0, alertCount = 0 }) {
  const navItems = [
    {
      to: '/',
      label: 'Safety Dashboard',
      icon: LayoutDashboard,
      badge: alertCount > 0 ? `${alertCount} live` : null,
      badgeColor: 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
    },
    {
      to: '/incidents',
      label: 'Incident Log',
      icon: AlertOctagon,
      badge: incidentCount > 0 ? incidentCount : null,
      badgeColor: 'bg-slate-800 text-slate-300 border border-slate-700'
    },
    {
      to: '/analytics',
      label: 'Safety Analytics',
      icon: BarChart3
    }
  ];

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-950/60 backdrop-blur-xl flex flex-col justify-between py-6 px-4 hidden md:flex shrink-0">
      <div className="space-y-6">
        <div>
          <p className="px-3 text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2 font-mono">
            Navigation
          </p>
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 group ${
                      isActive
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shadow-sm shadow-emerald-500/10'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                    }`
                  }
                >
                  <div className="flex items-center gap-3">
                    <Icon className="w-4 h-4 transition-transform group-hover:scale-110" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className={`text-[11px] font-mono px-2 py-0.5 rounded-full font-semibold ${item.badgeColor}`}>
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Industrial Safety Specs Checklist */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800/80">
          <p className="text-xs font-bold text-slate-300 flex items-center gap-2 mb-2">
            <HardHat className="w-4 h-4 text-emerald-400" /> Monitored Standards
          </p>
          <ul className="space-y-1.5 text-xs text-slate-400">
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              OSHA 1910.135 (Head Protection)
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              ANSI/ISEA 107 (High-Vis Vests)
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              ISO 11226 (Ergonomic Posture)
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Restricted Machine Geofence
            </li>
          </ul>
        </div>
      </div>

      {/* Storage & Architecture Footer */}
      <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400">
        <div className="flex items-center justify-between text-[11px] font-mono mb-1">
          <span className="flex items-center gap-1.5 text-slate-300">
            <Database className="w-3.5 h-3.5 text-cyan-400" /> Local Storage
          </span>
          <span className="text-emerald-400 font-semibold">IndexedDB</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-tight">
          All safety violations persist automatically across page reloads.
        </p>
      </div>
    </aside>
  );
}
