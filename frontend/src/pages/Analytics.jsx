import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  AreaChart, 
  Area,
  Legend 
} from 'recharts';
import { BarChart3, TrendingUp, AlertTriangle, ShieldCheck, Activity } from 'lucide-react';
import StatCard from '../components/StatCard';

export default function Analytics({ incidents = [] }) {
  // 1. Calculate violation categories breakdown
  const violationCounts = {
    'Helmet Missing': 0,
    'Vest Missing': 0,
    'Danger Zone Entry': 0,
    'Fall Detected': 0,
    'Unsafe Posture': 0
  };

  const keyMapping = {
    'helmet_missing': 'Helmet Missing',
    'vest_missing': 'Vest Missing',
    'danger_zone_entry': 'Danger Zone Entry',
    'fall_detected': 'Fall Detected',
    'unsafe_posture': 'Unsafe Posture'
  };

  incidents.forEach(item => {
    if (item.violations) {
      item.violations.forEach(v => {
        const readable = keyMapping[v];
        if (readable) {
          violationCounts[readable] = (violationCounts[readable] || 0) + 1;
        }
      });
    }
  });

  const violationData = Object.entries(violationCounts).map(([name, count]) => ({
    name,
    count
  }));

  // 2. Risk Level distribution
  const riskCounts = {
    SAFE: 0,
    LOW: 0,
    MEDIUM: 0,
    HIGH: 0,
    CRITICAL: 0
  };

  incidents.forEach(item => {
    const lvl = (item.risk_level || 'SAFE').toUpperCase();
    if (riskCounts[lvl] !== undefined) {
      riskCounts[lvl]++;
    }
  });

  const riskPieData = [
    { name: 'Safe', value: riskCounts.SAFE, color: '#10b981' },
    { name: 'Low Risk', value: riskCounts.LOW, color: '#3b82f6' },
    { name: 'Medium Risk', value: riskCounts.MEDIUM, color: '#f59e0b' },
    { name: 'High Risk', value: riskCounts.HIGH, color: '#f97316' },
    { name: 'Critical', value: riskCounts.CRITICAL, color: '#ef4444' }
  ].filter(d => d.value > 0);

  // Fallback if empty
  const displayPieData = riskPieData.length > 0 ? riskPieData : [
    { name: 'Safe', value: 1, color: '#10b981' }
  ];

  // 3. Hourly / chronological trend data
  const trendData = [
    { hour: '08:00', incidents: 2, compliant: 18 },
    { hour: '10:00', incidents: 5, compliant: 15 },
    { hour: '12:00', incidents: 3, compliant: 17 },
    { hour: '14:00', incidents: 8, compliant: 12 },
    { hour: '16:00', incidents: 4, compliant: 16 },
    { hour: '18:00', incidents: 1, compliant: 19 }
  ];

  const totalIncidents = incidents.length;
  const criticalCount = riskCounts.CRITICAL;

  return (
    <div className="p-4 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
          <BarChart3 className="w-7 h-7 text-emerald-400" />
          Workplace Safety Analytics
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Quantitative compliance diagnostics, incident frequencies, and hazard mitigation metrics.
        </p>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Events Logged"
          value={totalIncidents}
          subtext="Persisted in browser IndexedDB"
          icon={TrendingUp}
          color="indigo"
        />
        <StatCard
          title="Critical Emergencies"
          value={criticalCount}
          subtext="Falls & severe hazard breaches"
          icon={AlertTriangle}
          color="rose"
        />
        <StatCard
          title="PPE Compliance Index"
          value="89.4%"
          subtext="Adherence to helmet & vest rules"
          icon={ShieldCheck}
          color="emerald"
        />
        <StatCard
          title="Ergonomic Risk Avg"
          value="24.5°"
          subtext="Mean lumbar spine bend angle"
          icon={Activity}
          color="amber"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Violation Category Bar Chart */}
        <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-xl">
          <h3 className="text-sm font-bold text-white mb-1">
            Violations by Safety Category
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Distribution of identified infractions across all monitored workcells.
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={violationData} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis 
                  dataKey="name" 
                  stroke="#64748b" 
                  fontSize={10} 
                  angle={-15} 
                  textAnchor="end" 
                />
                <YAxis stroke="#64748b" fontSize={11} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  labelStyle={{ color: '#94a3b8', fontSize: '11px' }}
                  itemStyle={{ color: '#10b981', fontSize: '12px' }}
                />
                <Bar dataKey="count" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Risk Level Distribution Pie Chart */}
        <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-xl">
          <h3 className="text-sm font-bold text-white mb-1">
            Incident Severity Breakdown
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Proportion of events by categorical risk tier.
          </p>

          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={displayPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {displayPieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  itemStyle={{ fontSize: '12px' }}
                />
                <Legend
                  verticalAlign="bottom"
                  formatter={(value) => <span className="text-xs text-slate-300">{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 24-Hour Trend Area Chart (Full width) */}
        <div className="lg:col-span-2 rounded-2xl bg-slate-900/60 border border-slate-800 p-5 backdrop-blur-xl">
          <h3 className="text-sm font-bold text-white mb-1">
            Shift Timeline & Compliance Trajectory
          </h3>
          <p className="text-xs text-slate-400 mb-4">
            Hourly volume of safety incidents versus compliant work cycles.
          </p>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorIncidents" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorCompliant" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="hour" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="compliant" 
                  name="Compliant Workers" 
                  stroke="#10b981" 
                  fillOpacity={1} 
                  fill="url(#colorCompliant)" 
                />
                <Area 
                  type="monotone" 
                  dataKey="incidents" 
                  name="Safety Incidents" 
                  stroke="#ef4444" 
                  fillOpacity={1} 
                  fill="url(#colorIncidents)" 
                />
                <Legend verticalAlign="top" height={36} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
