import React from 'react';
import { ShieldAlert, Activity, Wifi, WifiOff, Sparkles, RefreshCw, Radio } from 'lucide-react';
import { DEMO_SCENARIOS } from '../services/detectionService';

export default function Navbar({ connectionStatus, operatingMode, backendSource = 'LIVE_AI', onTriggerScenario, onSetLiveMode, onReset }) {
  const isConnected = connectionStatus === 'connected';
  const isDemo = operatingMode === 'DEMO';

  const renderSourceBadge = () => {
    if (isDemo) {
      return (
        <span className="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-lg border border-amber-500/30">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          SIMULATED DEMO
        </span>
      );
    }
    if (backendSource === 'VIDEO_AI') {
      return (
        <span className="flex items-center gap-1.5 text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded-lg border border-cyan-500/30">
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          VIDEO AI (RECORDED)
        </span>
      );
    }
    if (backendSource === 'TEST_FIXTURE') {
      return (
        <span className="flex items-center gap-1.5 text-slate-300 bg-slate-800 px-2 py-0.5 rounded-lg border border-slate-700">
          <span className="w-2 h-2 rounded-full bg-slate-400" />
          TEST FIXTURE (SAMPLE)
        </span>
      );
    }
    if (backendSource === 'STANDBY') {
      return (
        <span className="flex items-center gap-1.5 text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded-lg border border-yellow-500/30">
          <span className="w-2 h-2 rounded-full bg-yellow-400" />
          CAMERA STANDBY
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-lg border border-emerald-500/30">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        LIVE CAMERA AI
      </span>
    );
  };

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl px-4 lg:px-6 flex items-center justify-between z-30 sticky top-0">
      {/* Brand Identity & Track Tag */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 p-0.5 shadow-lg shadow-emerald-500/20">
          <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-emerald-400" />
          </div>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              ErgoGuard AI
            </span>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              HACKATHON MVP
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
            Intelligent Workplace Safety & Compliance Platform
          </p>
        </div>
      </div>

      {/* Mode Indicator & 1-Click Judge Scenario Launcher */}
      <div className="flex items-center gap-3">
        {/* Active Mode Pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-xs font-mono font-bold backdrop-blur">
          {renderSourceBadge()}

          {isDemo && onSetLiveMode && (
            <button
              onClick={onSetLiveMode}
              className="ml-1 text-[11px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
              title="Return to real computer vision inference"
            >
              Back to Live
            </button>
          )}
        </div>

        {/* 1-Click Judge Demo Scenarios */}
        <div className="hidden md:flex items-center gap-1 bg-slate-900/90 border border-slate-800 p-1 rounded-xl">
          <span className="text-[11px] font-semibold text-slate-400 px-2 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Demo:
          </span>
          {DEMO_SCENARIOS.map((s, idx) => (
            <button
              key={s.id}
              onClick={() => onTriggerScenario(s.id)}
              className="text-xs px-2.5 py-1 rounded-lg font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition duration-150 border border-transparent hover:border-slate-700 active:scale-95"
              title={s.description}
            >
              #{idx + 1} {s.name.split('.')[1] || s.name}
            </button>
          ))}
          {onReset && (
            <button
              onClick={onReset}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
              title="Reset alerts & state"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* WebSocket Connection Status */}
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-mono font-medium backdrop-blur-md transition-all ${
            isConnected
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
          }`}
          title={
            isConnected
              ? 'Connected to Python WebSocket backend (ws://localhost:8765)'
              : 'Python backend offline. Running in local browser simulator mode'
          }
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isConnected ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isConnected ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
          </span>
          <span className="hidden lg:inline">
            {isConnected ? 'WS CONNECTED' : 'WS OFFLINE'}
          </span>
          {isConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
        </div>
      </div>
    </header>
  );
}
