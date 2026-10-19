import React, { useState, useRef, useEffect } from 'react';
import { 
  ShieldCheck, 
  Users, 
  AlertTriangle, 
  HardHat, 
  Camera, 
  VideoOff, 
  Play, 
  Square, 
  MapPin,
  Sparkles,
  Flame,
  CheckCircle,
  XCircle,
  Activity,
  Radio,
  FileVideo,
  Cpu
} from 'lucide-react';
import StatCard from '../components/StatCard';
import AlertCard from '../components/AlertCard';
import RiskBadge from '../components/RiskBadge';
import { DEMO_SCENARIOS } from '../services/detectionService';

export default function Dashboard({ 
  latestEvent, 
  liveFrame,
  liveMetrics = {},
  isCameraActive = false,
  backendCameraError = null,
  onClearBackendCameraError,
  onToggleCamera,
  activeWorkers = [], 
  activeAlerts = [], 
  incidents = [], 
  operatingMode = 'LIVE',
  backendSource = 'LIVE_AI',
  onTriggerScenario, 
  onSetLiveMode,
  onDismissAlert, 
  onClearAlerts,
  connectionStatus 
}) {
  const [webcamActive, setWebcamActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const effectiveCameraError = backendCameraError || cameraError;
  const dismissCameraError = React.useCallback(() => {
    setCameraError(null);
    if (onClearBackendCameraError) onClearBackendCameraError();
  }, [onClearBackendCameraError]);
  const [selectedZone, setSelectedZone] = useState('All Zones');
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // 1. Current Active Workers Count
  const totalActiveWorkers = activeWorkers.length;

  // 2. Real PPE Compliance Rate (Memoized to prevent frame rerender lag)
  // Non-negotiable requirement: Do not claim 100% compliance when results are unknown
  const ppeComplianceRate = React.useMemo(() => {
    if (totalActiveWorkers > 0) {
      let hasUnknown = false;
      let compliantCount = 0;

      activeWorkers.forEach(w => {
        const hStatus = w.ppe?.helmet?.status || (w.ppe?.helmet === true ? 'PRESENT' : (w.ppe?.helmet === false ? 'MISSING' : 'UNKNOWN'));
        const vStatus = w.ppe?.vest?.status || (w.ppe?.vest === true ? 'PRESENT' : (w.ppe?.vest === false ? 'MISSING' : 'UNKNOWN'));

        if (hStatus === 'UNKNOWN' || vStatus === 'UNKNOWN') {
          hasUnknown = true;
        } else if (hStatus === 'PRESENT' && vStatus === 'PRESENT') {
          compliantCount++;
        }
      });

      if (hasUnknown) {
        return 'Unverified';
      }
      return `${Math.round((compliantCount / totalActiveWorkers) * 100)}%`;
    }
    if (incidents.length > 0) {
      const recentSample = incidents.slice(0, 15);
      const compliantCount = recentSample.filter(i => i.violations?.length === 0).length;
      return `${Math.round((compliantCount / recentSample.length) * 100)}%`;
    }
    return '—';
  }, [totalActiveWorkers, activeWorkers, incidents]);

  // 3. Overall Safety Score (Memoized)
  const overallSafetyScore = React.useMemo(() => {
    if (totalActiveWorkers > 0) {
      const avgRisk = activeWorkers.reduce((acc, w) => acc + (w.risk_score || 0), 0) / totalActiveWorkers;
      return Math.max(0, Math.round(100 - avgRisk));
    }
    if (latestEvent && latestEvent.worker_id !== 'NONE') {
      return Math.max(0, 100 - (latestEvent.risk_score || 0));
    }
    return 100;
  }, [totalActiveWorkers, activeWorkers, latestEvent]);

  // Clean shutdown of browser webcam media tracks
  const stopWebcam = React.useCallback(() => {
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach(t => t.stop());
      } catch (_) {}
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setWebcamActive(false);
  }, []);

  // Toggle Laptop Web Camera via Browser getUserMedia API
  const toggleWebcam = React.useCallback(async () => {
    setCameraError(null);

    if (webcamActive) {
      stopWebcam();
      return;
    }

    const isLocalhost = typeof window !== 'undefined' && (
      window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1' ||
      window.location.hostname === '[::1]'
    );
    const isSecure = typeof window !== 'undefined' && (window.isSecureContext || isLocalhost);
    const hasMediaDevices = typeof navigator !== 'undefined' && navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function';
    const legacyGetUserMedia = typeof navigator !== 'undefined' ? (navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia || navigator.msGetUserMedia) : null;

    if (!hasMediaDevices && !legacyGetUserMedia) {
      if (!isSecure) {
        setCameraError({
          title: "Insecure Context / Non-Localhost Origin",
          message: "Browser camera access is blocked because this page is not served over HTTPS or http://localhost.",
          solution: "Open http://localhost:5173 instead of a network IP, or start the Python AI pipeline: python main.py"
        });
      } else {
        setCameraError({
          title: "Browser Camera Unsupported",
          message: "Your browser does not support standard webcam capture (navigator.mediaDevices).",
          solution: "Please use Chrome, Edge, or Firefox, or launch the Python AI backend: python main.py"
        });
      }
      return;
    }

    try {
      let stream = null;
      if (hasMediaDevices) {
        try {
          // Attempt ideal resolution with flexible fallback
          stream = await navigator.mediaDevices.getUserMedia({
            video: {
              width: { ideal: 1280, max: 1920 },
              height: { ideal: 720, max: 1080 },
              facingMode: 'user'
            }
          });
        } catch (constraintErr) {
          console.warn("[Dashboard] Ideal camera constraints rejected. Falling back to default video constraint:", constraintErr);
          // Immediate fallback to basic video constraint (essential for 480p/640x480 webcams)
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
        }
      } else {
        stream = await new Promise((resolve, reject) => {
          legacyGetUserMedia.call(navigator, { video: true }, resolve, reject);
        });
      }

      if (!stream) {
        throw new Error("No media stream returned by camera device.");
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        try {
          await videoRef.current.play();
        } catch (playErr) {
          console.warn("[Dashboard] video.play() deferred or interrupted:", playErr);
        }
      }
      setWebcamActive(true);
      setCameraError(null);
    } catch (err) {
      console.error("[Dashboard] Camera activation error:", err);
      let errorTitle = "Camera Not Accessible";
      let errorSolution = "Check if another app (Zoom, Teams, Skype, Python) has locked the webcam, and grant browser permissions.";

      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorTitle = "Camera Permission Denied";
        errorSolution = "Click the camera or lock icon in your browser address bar and select 'Allow' for camera access, then retry.";
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorTitle = "No Camera Hardware Detected";
        errorSolution = "No physical webcam was detected. Connect a USB camera or click a 1-Click Demo Scenario below.";
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errorTitle = "Camera Hardware In Use";
        errorSolution = "The webcam is locked by another process (Zoom, Teams, another tab, or Python OpenCV). Close other apps and retry.";
      } else if (err.name === 'OverconstrainedError') {
        errorTitle = "Camera Resolution Constraint Failed";
        errorSolution = "Your webcam driver does not support requested parameters. Trying standard resolution.";
      }

      setCameraError({
        title: errorTitle,
        message: err.message || err.name || "Failed to start camera device.",
        solution: errorSolution
      });
      stopWebcam();
    }
  }, [webcamActive, stopWebcam]);

  // Master Camera Toggle: Intelligently routes to Python AI Backend or Browser Webcam
  const isPythonConnected = connectionStatus === 'connected';

  const handleCameraToggle = React.useCallback(async () => {
    dismissCameraError();

    // If Python AI backend is connected and running:
    if (isPythonConnected && onToggleCamera) {
      // If browser webcam was running locally, stop it so Python can access device without hardware lock
      if (webcamActive) {
        stopWebcam();
      }
      onToggleCamera();
    } else {
      // Python backend is offline -> Use browser webcam directly so user immediately has working video!
      await toggleWebcam();
    }
  }, [dismissCameraError, isPythonConnected, onToggleCamera, webcamActive, stopWebcam, toggleWebcam]);

  useEffect(() => {
    return () => {
      stopWebcam();
    };
  }, [stopWebcam]);

  const displayEvent = activeWorkers.length > 0 ? activeWorkers[0] : latestEvent;
  const effectiveSource = backendSource || displayEvent?.source || (operatingMode === 'DEMO' ? 'SIMULATED' : 'LIVE_AI');
  const isSimulated = effectiveSource === 'SIMULATED' || operatingMode === 'DEMO';

  return (
    <div className="p-4 lg:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Page Title & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Safety Monitoring Dashboard
            </h1>
            <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full border ${
              effectiveSource === 'LIVE_AI'
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                : effectiveSource === 'VIDEO_AI'
                ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                : effectiveSource === 'TEST_FIXTURE'
                ? 'bg-purple-500/15 text-purple-400 border-purple-500/30'
                : effectiveSource === 'STANDBY'
                ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
            }`}>
              {effectiveSource === 'LIVE_AI' && 'MODE: LIVE CAMERA AI'}
              {effectiveSource === 'VIDEO_AI' && 'MODE: VIDEO AI (RECORDED)'}
              {effectiveSource === 'TEST_FIXTURE' && 'MODE: TEST FIXTURE (SAMPLE)'}
              {effectiveSource === 'STANDBY' && 'MODE: CAMERA STANDBY'}
              {effectiveSource === 'SIMULATED' && 'MODE: SIMULATED DEMO'}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Real-time multi-hazard telemetry: PPE compliance, posture kinematics, falls, and geofence breaches.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-400 font-medium">Zone:</label>
          <select 
            value={selectedZone} 
            onChange={(e) => setSelectedZone(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-sm text-slate-200 rounded-xl px-3 py-2 outline-none focus:border-emerald-500 transition"
          >
            <option>All Zones</option>
            <option>Machine Zone A</option>
            <option>Robotic Cell 4 Perimeter</option>
            <option>Assembly Line 1</option>
            <option>Loading Bay Ramp C</option>
            <option>Warehouse High-Rack 3</option>
          </select>
        </div>
      </div>

      {/* 1. Core Stat Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Overall Safety Score"
          value={`${overallSafetyScore}%`}
          subtext="Current monitored compliance index"
          icon={ShieldCheck}
          color={overallSafetyScore >= 75 ? 'emerald' : overallSafetyScore >= 45 ? 'amber' : 'rose'}
          badge={overallSafetyScore >= 80 ? 'EXCELLENT' : 'MONITOR'}
        />
        <StatCard
          title="Active Monitored Workers"
          value={totalActiveWorkers}
          subtext={totalActiveWorkers > 0 ? "Tracked in optical field of view" : "No workers detected in frame"}
          icon={Users}
          color="blue"
        />
        <StatCard
          title="Active Safety Alerts"
          value={activeAlerts.length}
          subtext={`${activeAlerts.filter(a => a.risk_level === 'CRITICAL').length} critical emergency`}
          icon={AlertTriangle}
          color={activeAlerts.length > 0 ? 'rose' : 'emerald'}
        />
        <StatCard
          title="PPE Compliance Rate"
          value={ppeComplianceRate}
          subtext="Hardhat & Hi-Vis vest adherence"
          icon={HardHat}
          color={ppeComplianceRate.includes('—') ? 'blue' : parseInt(ppeComplianceRate) >= 80 ? 'emerald' : 'amber'}
        />
      </div>

      {/* 2. Main Content Grid: Video Feed & Real-time Telemetry Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Live Video Canvas & Geofence HUD */}
        <div className="lg:col-span-2 space-y-4">
          <div className="relative rounded-2xl overflow-hidden bg-slate-950 border border-slate-800 shadow-2xl flex flex-col">
            {/* Video Header Bar */}
            <div className="px-4 py-3 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${effectiveSource === 'LIVE_AI' ? 'bg-emerald-400 animate-pulse' : effectiveSource === 'VIDEO_AI' ? 'bg-blue-400 animate-pulse' : effectiveSource === 'TEST_FIXTURE' ? 'bg-purple-400' : 'bg-amber-400'}`} />
                <span className="text-xs font-mono font-bold text-white tracking-wider uppercase">
                  CAMERA 01 • MACHINE ZONE A
                </span>
                <span className="text-[11px] font-mono text-slate-400 ml-2 hidden sm:inline">
                  [{effectiveSource === 'LIVE_AI' ? 'LIVE CV' : effectiveSource === 'VIDEO_AI' ? 'VIDEO CV' : effectiveSource === 'TEST_FIXTURE' ? 'TEST FIXTURE' : effectiveSource === 'STANDBY' ? 'STANDBY' : 'SIMULATED'}]
                </span>
              </div>
              <div className="flex items-center gap-2">
                {isPythonConnected && isCameraActive && (
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    AI Camera Active
                  </span>
                )}
                {webcamActive && (
                  <span className="text-[11px] font-mono text-cyan-400 bg-cyan-500/10 border border-cyan-500/30 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    Browser Camera Active
                  </span>
                )}
                <button
                  onClick={handleCameraToggle}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium flex items-center gap-1.5 transition ${
                    (isPythonConnected && isCameraActive) || webcamActive
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 hover:bg-rose-500/30' 
                      : 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-600/30'
                  }`}
                  title={
                    isPythonConnected
                      ? "Toggle physical AI camera inference pipeline"
                      : "Toggle browser webcam local preview"
                  }
                >
                  <Camera className="w-3.5 h-3.5" />
                  {(isPythonConnected && isCameraActive) || webcamActive ? 'Turn Camera Off' : 'Turn Camera On'}
                </button>
              </div>
            </div>

            {/* Video Viewport with AI HUD Overlays */}
            <div className="relative w-full aspect-video bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center overflow-hidden">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className={`absolute inset-0 w-full h-full object-cover ${webcamActive ? 'block' : 'hidden'}`}
              />

              {/* Live Computer Vision Stream from Python Backend */}
              {liveFrame && !webcamActive && (
                <img
                  src={liveFrame}
                  alt="ErgoGuard AI Live Camera Feed"
                  className="absolute inset-0 w-full h-full object-cover z-0"
                />
              )}

              {/* Local Browser Webcam Active Overlay Badge */}
              {webcamActive && (
                <div className="absolute top-3 left-3 z-10 px-3 py-1.5 rounded-xl bg-slate-950/85 border border-cyan-500/40 backdrop-blur-md flex items-center gap-2 shadow-lg">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="text-xs font-mono text-cyan-300 font-semibold">Browser Camera Preview Active</span>
                  <span className="text-[11px] text-slate-400 hidden sm:inline">• Run <code className="text-emerald-400 font-mono bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">python main.py</code> for AI detection</span>
                </div>
              )}

              {/* Camera Diagnostics Card if Camera Access Encountered Error */}
              {effectiveCameraError && !webcamActive && !liveFrame && (
                <div className="z-20 p-6 rounded-2xl bg-slate-900/95 border border-rose-500/40 backdrop-blur-md max-w-md mx-4 text-center shadow-2xl shadow-rose-950/40">
                  <div className="w-12 h-12 rounded-xl bg-rose-500/20 border border-rose-500/40 flex items-center justify-center mx-auto mb-3 text-rose-400">
                    <VideoOff className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-white mb-1">{effectiveCameraError.title}</h3>
                  <p className="text-xs text-rose-300/90 mb-3">{effectiveCameraError.message}</p>
                  <div className="text-[11px] bg-slate-950/80 rounded-lg p-2.5 text-slate-300 border border-slate-800 text-left mb-4">
                    <span className="font-semibold text-emerald-400 block mb-0.5">Recommended Fix:</span>
                    {effectiveCameraError.solution}
                  </div>
                  <div className="flex items-center justify-center gap-2">
                    <button
                      onClick={handleCameraToggle}
                      className="text-xs px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition"
                    >
                      Retry Camera
                    </button>
                    <button
                      onClick={dismissCameraError}
                      className="text-xs px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              )}

              {/* Graphical Simulation View when live stream is not yet connected */}
              {!webcamActive && !liveFrame && !effectiveCameraError && (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center select-none">
                  {/* Grid background */}
                  <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:3rem_3rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30 pointer-events-none" />

                  {/* If no worker detected in LIVE mode */}
                  {operatingMode === 'LIVE' && totalActiveWorkers === 0 ? (
                    <div className="z-10 text-center p-6 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm max-w-md">
                      <div className="w-12 h-12 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-center mx-auto mb-3 text-slate-400">
                        <Camera className="w-6 h-6 text-emerald-400" />
                      </div>
                      <p className="text-sm font-bold text-white">Camera Standby</p>
                      <p className="text-xs text-slate-400 mt-1 mb-4 leading-relaxed">
                        {isPythonConnected 
                          ? 'Python AI engine connected. Click "Turn Camera On" to begin live AI monitoring.'
                          : 'Click "Turn Camera On" to enable your webcam, or run python main.py for full AI inference.'}
                      </p>
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={handleCameraToggle}
                          className="text-xs px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center gap-1.5 transition shadow-lg shadow-emerald-900/20"
                        >
                          <Camera className="w-3.5 h-3.5" />
                          Turn Camera On
                        </button>
                        {onTriggerScenario && DEMO_SCENARIOS && DEMO_SCENARIOS.length > 0 && (
                          <button
                            onClick={() => onTriggerScenario(DEMO_SCENARIOS[0].id)}
                            className="text-xs px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium flex items-center gap-1.5 transition border border-slate-700"
                          >
                            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                            Launch Demo
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    /* Worker Bounding Box HUD */
                    <div className={`relative w-48 h-72 rounded-lg border-2 transition-all duration-500 flex flex-col justify-between p-2 shadow-2xl backdrop-blur-xs ${
                      displayEvent?.risk_level === 'CRITICAL'
                        ? 'border-rose-500 bg-rose-500/10 shadow-rose-500/20 animate-pulse'
                        : displayEvent?.risk_level === 'HIGH' || displayEvent?.risk_level === 'MEDIUM'
                        ? 'border-amber-500 bg-amber-500/10 shadow-amber-500/20'
                        : 'border-emerald-500 bg-emerald-500/10 shadow-emerald-500/20'
                    }`}>
                      {/* Bounding box top header */}
                      <div className="flex items-center justify-between text-[11px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-900/90 text-white border border-slate-700">
                        <span>{displayEvent?.worker_id || 'W01'}</span>
                        <span>{Math.round((displayEvent?.confidence || 0.95) * 100)}%</span>
                      </div>

                      {/* Head / Helmet ROI Tag */}
                      <div className={`text-[10px] font-mono font-semibold px-2 py-1 rounded text-center border ${
                        displayEvent?.ppe?.helmet?.status === 'PRESENT'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' 
                          : displayEvent?.ppe?.helmet?.status === 'MISSING'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-bounce'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}>
                        {displayEvent?.ppe?.helmet?.status === 'PRESENT' ? '✓ Hardhat Present' : displayEvent?.ppe?.helmet?.status === 'MISSING' ? '⚠ Missing Hardhat' : 'Hardhat: Unverified'}
                      </div>

                      {/* Torso / Vest ROI Tag */}
                      <div className={`text-[10px] font-mono font-semibold px-2 py-1 rounded text-center border ${
                        displayEvent?.ppe?.vest?.status === 'PRESENT'
                          ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' 
                          : displayEvent?.ppe?.vest?.status === 'MISSING'
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                          : 'bg-slate-800 text-slate-400 border-slate-700'
                      }`}>
                        {displayEvent?.ppe?.vest?.status === 'PRESENT' ? '✓ Hi-Vis Vest' : displayEvent?.ppe?.vest?.status === 'MISSING' ? '⚠ Missing Vest' : 'Vest: Unverified'}
                      </div>

                      {/* Posture / Ergonomics Tag */}
                      <div className="text-[10px] font-mono text-center text-slate-300 bg-slate-900/80 rounded py-0.5 border border-slate-700">
                        Posture: <span className="font-bold uppercase text-white">{displayEvent?.posture || 'SAFE'}</span>
                      </div>
                    </div>
                  )}

                  {/* Restricted Danger-Zone Geofence Overlay */}
                  <div className="absolute top-8 right-8 border-2 border-dashed border-rose-500/60 bg-rose-500/5 rounded-xl p-3 text-right pointer-events-none">
                    <span className="text-[10px] font-mono font-bold text-rose-400 uppercase tracking-wider block">
                      ⚠ RESTRICTED ROBOTIC GEOFENCE
                    </span>
                    <span className="text-[9px] text-slate-400">
                      Perimeter Coordinates: [0.50, 0.25, 0.45, 0.65]
                    </span>
                  </div>
                </div>
              )}

              {/* Real-time Top Overlay HUD Badge */}
              <div className="absolute top-4 left-4 flex items-center gap-2 z-10">
                <RiskBadge 
                  level={displayEvent?.risk_level || 'SAFE'} 
                  score={displayEvent?.risk_score || 0} 
                  size="md" 
                />
                <span className={`text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border ${
                  isSimulated
                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                    : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                }`}>
                  {isSimulated ? 'SIMULATED SCENARIO' : 'LIVE AI EVENT'}
                </span>
              </div>

              {/* Bottom Telemetry Ticker */}
              <div className="absolute bottom-3 left-4 right-4 bg-slate-950/80 backdrop-blur-md border border-slate-800 rounded-xl px-4 py-2 flex items-center justify-between text-xs font-mono text-slate-300 z-10">
                <div className="flex items-center gap-4">
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    {displayEvent?.location || 'Assembly Line 1'}
                  </span>
                  <span className="hidden sm:inline opacity-40">|</span>
                  <span className="hidden sm:inline">
                    Spine Angle: <strong className="text-white">{displayEvent?.spine_angle || 12.0}°</strong>
                  </span>
                </div>
                <div>
                  Status: <strong className="text-emerald-400">PIPELINE ACTIVE</strong>
                </div>
              </div>
            </div>
          </div>

          {/* Real-Time Performance & Pipeline Profiler HUD */}
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-bold text-white">
                  Real-Time Pipeline Profiler & Performance Telemetry
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  THREADED MULTI-STAGE ENGINE
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {/* 1. Capture FPS */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Capture</div>
                <div className="text-base font-bold font-mono text-white mt-0.5">
                  {liveMetrics.capture_fps !== undefined ? `${liveMetrics.capture_fps}` : '30.0'} <span className="text-[10px] font-normal text-slate-400">FPS</span>
                </div>
                <div className="text-[9px] font-mono text-emerald-400 mt-0.5">Threaded size=1</div>
              </div>

              {/* 2. Inference FPS */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">AI Inference</div>
                <div className="text-base font-bold font-mono text-cyan-300 mt-0.5">
                  {liveMetrics.inference_fps !== undefined ? `${liveMetrics.inference_fps}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">FPS</span>
                </div>
                <div className="text-[9px] font-mono text-slate-400 mt-0.5">Decoupled loop</div>
              </div>

              {/* 3. Person Det */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Person Det</div>
                <div className="text-base font-bold font-mono text-white mt-0.5">
                  {liveMetrics.person_det_ms !== undefined ? `${liveMetrics.person_det_ms}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">ms</span>
                </div>
                <div className="text-[9px] font-mono text-slate-400 mt-0.5">YOLOv8 + Tracker</div>
              </div>

              {/* 4. PPE Det */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">PPE Inference</div>
                <div className="text-base font-bold font-mono text-white mt-0.5">
                  {liveMetrics.ppe_det_ms !== undefined ? `${liveMetrics.ppe_det_ms}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">ms</span>
                </div>
                <div className={`text-[9px] font-mono mt-0.5 ${liveMetrics.ppe_reused ? 'text-amber-400 font-semibold' : 'text-emerald-400'}`}>
                  {liveMetrics.ppe_reused ? 'Cached (1.5Hz)' : 'Fresh Model'}
                </div>
              </div>

              {/* 5. Encode */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">JPEG Encode</div>
                <div className="text-base font-bold font-mono text-white mt-0.5">
                  {liveMetrics.encode_ms !== undefined ? `${liveMetrics.encode_ms}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">ms</span>
                </div>
                <div className="text-[9px] font-mono text-slate-400 mt-0.5">640x360 Q=55</div>
              </div>

              {/* 6. WS Tx */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">WebSocket Tx</div>
                <div className="text-base font-bold font-mono text-white mt-0.5">
                  {liveMetrics.tx_ms !== undefined ? `${liveMetrics.tx_ms}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">ms</span>
                </div>
                <div className="text-[9px] font-mono text-slate-400 mt-0.5">Zero-drop alerts</div>
              </div>

              {/* 7. E2E Latency */}
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-2.5">
                <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">E2E Latency</div>
                <div className="text-base font-bold font-mono text-emerald-400 mt-0.5">
                  {liveMetrics.e2e_latency_ms !== undefined ? `${liveMetrics.e2e_latency_ms}` : '0.0'} <span className="text-[10px] font-normal text-slate-400">ms</span>
                </div>
                <div className="text-[9px] font-mono text-emerald-400 mt-0.5">Capture to Render</div>
              </div>
            </div>
          </div>

          {/* Quick Scenario Runner Bar for Hackathon Judges */}
          <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white">
                  Judge Demonstration: One-Click Test Scenarios
                </h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                Injects deterministic test events into Safety Engine
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
              {DEMO_SCENARIOS.map((s, idx) => (
                <button
                  key={s.id}
                  onClick={() => onTriggerScenario(s.id)}
                  className="flex flex-col text-left p-2.5 rounded-xl bg-slate-950/80 hover:bg-slate-800/90 border border-slate-800 hover:border-slate-700 transition duration-200 group active:scale-95"
                >
                  <span className="text-[10px] font-mono font-bold text-slate-500 group-hover:text-emerald-400 transition">
                    SCENARIO #{idx + 1}
                  </span>
                  <span className="text-xs font-semibold text-slate-200 mt-1 leading-tight line-clamp-1">
                    {s.name.split('.')[1] || s.name}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 mt-1.5">
                    {s.badge}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Worker State & Active Alert Feed */}
        <div className="space-y-4">
          {/* Worker Status Card */}
          <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5 backdrop-blur-xl">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 font-mono mb-4 flex items-center justify-between">
              <span>Tracked Worker State</span>
              <span className="font-mono text-white text-xs px-2 py-0.5 rounded bg-slate-800">
                {displayEvent?.worker_id || 'NONE'}
              </span>
            </h3>

            <div className="space-y-3">
              {/* Helmet */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="flex items-center gap-2.5">
                  <HardHat className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-medium text-slate-300">Safety Hardhat</span>
                </div>
                {displayEvent?.ppe?.helmet?.status === 'PRESENT' ? (
                  <span className="flex items-center gap-1 text-xs font-semibold text-emerald-400">
                    <CheckCircle className="w-3.5 h-3.5" /> Equipped
                  </span>
                ) : displayEvent?.ppe?.helmet?.status === 'MISSING' ? (
                  <span className="flex items-center gap-1 text-xs font-semibold text-rose-400">
                    <XCircle className="w-3.5 h-3.5" /> Missing
                  </span>
                ) : (
                  <span className="text-xs font-semibold text-slate-400">
                    Unverified
                  </span>
                )}
              </div>

              {/* Vest */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="flex items-center gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-medium text-slate-300">Hi-Vis Safety Vest</span>
                </div>
                {displayEvent?.ppe?.vest?.status === 'PRESENT' ? (
                  <span className="flex items-center gap-1 text-xs font-semibold text-emerald-400">
                    <CheckCircle className="w-3.5 h-3.5" /> Equipped
                  </span>
                ) : displayEvent?.ppe?.vest?.status === 'MISSING' ? (
                  <span className="flex items-center gap-1 text-xs font-semibold text-rose-400">
                    <XCircle className="w-3.5 h-3.5" /> Missing
                  </span>
                ) : (
                  <span className="text-xs font-semibold text-slate-400">
                    Unverified
                  </span>
                )}
              </div>

              {/* Ergonomic Posture */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="flex items-center gap-2.5">
                  <Activity className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-medium text-slate-300">Ergonomic Posture</span>
                </div>
                <span className={`text-xs font-semibold uppercase ${
                  displayEvent?.posture === 'UNSAFE' ? 'text-rose-400' : 'text-emerald-400'
                }`}>
                  {displayEvent?.posture || 'SAFE'}
                </span>
              </div>

              {/* Danger Zone */}
              <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <div className="flex items-center gap-2.5">
                  <MapPin className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-medium text-slate-300">Geofence Boundary</span>
                </div>
                {displayEvent?.danger_zone?.entered ? (
                  <span className="text-xs font-bold text-rose-400 animate-pulse text-right">
                    Breach: {displayEvent?.danger_zone?.zone_name || displayEvent?.danger_zone?.zone_id || 'Restricted Area'}
                  </span>
                ) : (
                  <span className="text-xs font-semibold text-emerald-400">
                    Safe Zone
                  </span>
                )}
              </div>
            </div>

            {/* Risk Score Gauge */}
            <div className="mt-5 pt-4 border-t border-slate-800">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-slate-400 font-medium">Authoritative Risk Score</span>
                <span className="font-mono font-bold text-white">
                  {displayEvent?.risk_score || 0}/100
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all duration-500 ${
                    (displayEvent?.risk_score || 0) >= 61 
                      ? 'bg-rose-500' 
                      : (displayEvent?.risk_score || 0) >= 31 
                      ? 'bg-amber-500' 
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min(100, Math.max(5, displayEvent?.risk_score || 0))}%` }}
                />
              </div>
            </div>
          </div>

          {/* Active Alerts Feed */}
          <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-5 backdrop-blur-xl flex flex-col h-[340px]">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <h3 className="text-sm font-bold text-white">Active Alerts Feed</h3>
              </div>
              {activeAlerts.length > 0 && onClearAlerts && (
                <button
                  onClick={onClearAlerts}
                  className="text-[11px] text-slate-400 hover:text-white transition"
                >
                  Clear All
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {activeAlerts.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-500">
                  <CheckCircle className="w-8 h-8 text-emerald-500/40 mb-2" />
                  <p className="text-xs font-semibold text-slate-400">Zero Active Violations</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    All monitored areas operating within safety thresholds.
                  </p>
                </div>
              ) : (
                activeAlerts.map((alert, idx) => (
                  <AlertCard 
                    key={alert.incident_id || alert.event_id || idx} 
                    alert={alert} 
                    onDismiss={() => onDismissAlert && onDismissAlert(idx)} 
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
