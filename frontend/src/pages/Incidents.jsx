import React, { useState } from 'react';
import { 
  AlertOctagon, 
  Search, 
  Filter, 
  Trash2, 
  Download, 
  Clock, 
  MapPin, 
  User, 
  RefreshCw,
  Tag
} from 'lucide-react';
import RiskBadge from '../components/RiskBadge';
import { clearAllIncidents } from '../services/indexedDB';

export default function Incidents({ incidents = [], onRefresh }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedViolation, setSelectedViolation] = useState('ALL');
  const [selectedSource, setSelectedSource] = useState('ALL');

  // Filter incidents
  const filtered = incidents.filter((item) => {
    const matchesSearch = 
      (item.worker_id && item.worker_id.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (item.location && item.location.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (item.details && item.details.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesSeverity = 
      selectedSeverity === 'ALL' || item.risk_level === selectedSeverity;

    const matchesViolation = 
      selectedViolation === 'ALL' || 
      (item.violations && item.violations.includes(selectedViolation)) ||
      (item.violation && item.violation === selectedViolation);

    const matchesSource =
      selectedSource === 'ALL' || item.source === selectedSource;

    return matchesSearch && matchesSeverity && matchesViolation && matchesSource;
  });

  // Handle clearing DB
  const handleClear = async () => {
    if (window.confirm('Are you sure you want to clear all incidents from IndexedDB?')) {
      await clearAllIncidents();
      if (onRefresh) onRefresh();
    }
  };

  // Export incidents as JSON
  const handleExportJSON = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(incidents, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `ergoguard_incidents_${Date.now()}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="p-4 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Safety Incident Audit Log
            </h1>
            <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              {filtered.length} Records
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Persisted browser IndexedDB audit trail with lifecycle states.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="px-3 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1.5 transition"
              title="Refresh from IndexedDB"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          )}
          <button
            onClick={handleExportJSON}
            disabled={incidents.length === 0}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-white text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" />
            Export JSON
          </button>
          <button
            onClick={handleClear}
            disabled={incidents.length === 0}
            className="px-3 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-40"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear DB
          </button>
        </div>
      </div>

      {/* Search and Filters Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 p-4 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-xl">
        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search Worker ID, location, details..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 outline-none focus:border-emerald-500 transition"
          />
        </div>

        {/* Source Filter */}
        <div>
          <select
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 outline-none focus:border-emerald-500 transition"
          >
            <option value="ALL">All Event Sources</option>
            <option value="LIVE_AI">Live Camera AI</option>
            <option value="VIDEO_AI">Prerecorded Video AI</option>
            <option value="TEST_FIXTURE">Test Fixture Inferences</option>
            <option value="SIMULATED">Simulated Demo Events</option>
          </select>
        </div>

        {/* Severity Filter */}
        <div>
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 outline-none focus:border-emerald-500 transition"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical Emergencies</option>
            <option value="HIGH">High Risk</option>
            <option value="MEDIUM">Medium Risk</option>
            <option value="LOW">Low Risk</option>
            <option value="SAFE">Safe Baseline</option>
          </select>
        </div>

        {/* Violation Type Filter */}
        <div>
          <select
            value={selectedViolation}
            onChange={(e) => setSelectedViolation(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 outline-none focus:border-emerald-500 transition"
          >
            <option value="ALL">All Violation Types</option>
            <option value="helmet_missing">Missing Hardhat</option>
            <option value="vest_missing">Missing Safety Vest</option>
            <option value="danger_zone_entry">Danger Zone Breach</option>
            <option value="fall_detected">Fall Detection Alert</option>
            <option value="unsafe_posture">Unsafe Ergonomic Posture</option>
          </select>
        </div>
      </div>

      {/* Incidents Table */}
      <div className="rounded-2xl bg-slate-900/60 border border-slate-800 overflow-hidden backdrop-blur-xl shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/80 text-[11px] font-mono uppercase text-slate-400">
                <th className="py-3.5 px-4 font-semibold">Worker & Source</th>
                <th className="py-3.5 px-4 font-semibold">Location</th>
                <th className="py-3.5 px-4 font-semibold">Severity & State</th>
                <th className="py-3.5 px-4 font-semibold">Violations Detected</th>
                <th className="py-3.5 px-4 font-semibold">First / Last Seen</th>
                <th className="py-3.5 px-4 font-semibold">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-xs">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    <AlertOctagon className="w-8 h-8 text-slate-600 mx-auto mb-2 opacity-50" />
                    <p className="font-semibold text-slate-400">No incident records match current criteria</p>
                    <p className="text-[11px] text-slate-600 mt-1">
                      Trigger a demo scenario or wait for confirmed camera violations.
                    </p>
                  </td>
                </tr>
              ) : (
                filtered.map((item, idx) => (
                  <tr key={item.incident_id || item.event_id || idx} className="hover:bg-slate-800/40 transition">
                    {/* Worker & Source */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-white px-2 py-0.5 rounded bg-slate-800 border border-slate-700">
                          {item.worker_id}
                        </span>
                        <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                          item.source === 'SIMULATED'
                            ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                            : item.source === 'VIDEO_AI'
                            ? 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                            : item.source === 'TEST_FIXTURE'
                            ? 'bg-purple-500/10 text-purple-300 border-purple-500/30'
                            : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                        }`}>
                          {item.source === 'SIMULATED' ? 'SIM' : item.source === 'VIDEO_AI' ? 'VIDEO AI' : item.source === 'TEST_FIXTURE' ? 'FIXTURE' : 'LIVE'}
                        </span>
                      </div>
                    </td>

                    {/* Location */}
                    <td className="py-3.5 px-4 text-slate-300">
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-medium">{item.location || 'General Floor'}</span>
                      </div>
                    </td>

                    {/* Severity & State */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        <RiskBadge level={item.risk_level} score={item.risk_score} size="sm" />
                        <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          item.lifecycle_state === 'RESOLVED' 
                            ? 'bg-slate-800 text-slate-400' 
                            : (item.lifecycle_state === 'NOT_OBSERVED' || item.lifecycle_state === 'STALE')
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                            : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                        }`}>
                          {item.lifecycle_state || 'ACTIVE'}
                        </span>
                      </div>
                    </td>

                    {/* Violations Detected */}
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {item.violations && item.violations.length > 0 ? (
                          item.violations.map((v, i) => (
                            <span
                              key={i}
                              className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                                v === 'fall_detected'
                                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                                  : v === 'danger_zone_entry'
                                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                                  : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                              }`}
                            >
                              {v.replace(/_/g, ' ')}
                            </span>
                          ))
                        ) : (
                          <span className="text-[11px] text-emerald-400 font-medium">
                            None (Compliant)
                          </span>
                        )}
                      </div>
                    </td>

                    {/* First / Last Seen */}
                    <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px]">
                      <div>{item.last_seen_at ? new Date(item.last_seen_at).toLocaleTimeString() : 'N/A'}</div>
                      <div className="text-[10px] text-slate-500">
                        {item.first_detected_at ? `First: ${new Date(item.first_detected_at).toLocaleTimeString()}` : ''}
                      </div>
                    </td>

                    {/* Details */}
                    <td className="py-3.5 px-4 text-slate-400 max-w-xs">
                      <p className="truncate text-xs text-slate-300" title={item.details}>
                        {item.details || 'Standard telemetry verification'}
                      </p>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
