/**
 * Custom React Hook: useSafetyEvents
 * Manages WebSocket connection to Python AI backend,
 * decouples high-bandwidth video frame updates from telemetry,
 * throttles IndexedDB incident writes and alert sounds,
 * and exposes live profiling metrics for the debug panel.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { saveOrUpdateIncident, resolveIncident, getAllIncidents, seedSampleIncidentsIfEmpty } from '../services/indexedDB';
import { DEMO_SCENARIOS, createSimulatedEvent } from '../services/detectionService';

const WS_URL = (typeof window !== 'undefined' && window.location.hostname && window.location.hostname !== 'localhost')
  ? `ws://${window.location.hostname}:8765`
  : 'ws://127.0.0.1:8765';


export function useSafetyEvents() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [operatingMode, setOperatingMode] = useState('LIVE'); // 'LIVE' | 'DEMO'
  const [backendSource, setBackendSource] = useState('LIVE_AI'); // 'LIVE_AI' | 'VIDEO_AI' | 'TEST_FIXTURE' | 'SIMULATED' | 'STANDBY'
  const [latestEvent, setLatestEvent] = useState(null);
  const [liveFrame, setLiveFrame] = useState(null);
  const [liveMetrics, setLiveMetrics] = useState({
    capture_fps: 30.0,
    inference_fps: 0.0,
    person_det_ms: 0.0,
    ppe_det_ms: 0.0,
    encode_ms: 0.0,
    tx_ms: 0.0,
    e2e_latency_ms: 0.0,
    ppe_reused: false
  });
  const [activeWorkers, setActiveWorkers] = useState({}); // worker_id -> event
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [privacyMode, setPrivacyModeState] = useState('OFF');
  const [pipelineState, setPipelineState] = useState('STANDBY');

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const processedEventIds = useRef(new Set());
  const lastAlertSoundTime = useRef(0);
  const activeViolationWorkers = useRef(new Set());
  const lastDbWriteTime = useRef({});
  const lastDbRefreshTime = useRef(0);

  // Refresh incident history from IndexedDB
  const refreshIncidents = useCallback(async () => {
    try {
      const list = await getAllIncidents();
      setIncidents(list || []);
    } catch (_) {}
  }, []);

  // Optimized alert sound: only plays on transition or after cooldown
  const playAlertSound = useCallback((riskLevel, workerId) => {
    if (riskLevel !== 'CRITICAL' && riskLevel !== 'HIGH') return;
    const now = Date.now();
    const isNew = !activeViolationWorkers.current.has(workerId);
    if (!isNew && (now - lastAlertSoundTime.current < 3500)) {
      return;
    }
    lastAlertSoundTime.current = now;
    activeViolationWorkers.current.add(workerId);

    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(riskLevel === 'CRITICAL' ? 880 : 540, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.35);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.35);
    } catch (_) {}
  }, []);

  // Process incoming telemetry event
  const processEvent = useCallback(async (event) => {
    if (!event || !event.worker_id) return;

    // Idempotency check on event_id
    if (event.event_id) {
      if (processedEventIds.current.has(event.event_id)) return;
      processedEventIds.current.add(event.event_id);
      if (processedEventIds.current.size > 200) {
        processedEventIds.current.clear();
      }
    }

    setLatestEvent(event);

    // Update active workers state
    if (event.worker_id !== 'NONE') {
      setActiveWorkers(prev => ({
        ...prev,
        [event.worker_id]: { ...event, last_seen: Date.now() }
      }));
    } else {
      setActiveWorkers({});
      activeViolationWorkers.current.clear();
    }

    // Process violations & incident lifecycle with DB write throttling
    const hasViolations = event.violations && event.violations.length > 0;

    if (hasViolations) {
      playAlertSound(event.risk_level, event.worker_id);

      setActiveAlerts(prev => [
        event,
        ...prev.filter(a => a.worker_id !== event.worker_id)
      ].slice(0, 15));

      const now = Date.now();

      // Priority 4: Stable Per-Violation Incident Storage
      if (event.active_incidents && event.active_incidents.length > 0) {
        for (const inc of event.active_incidents) {
          const incId = inc.incident_id;
          const lastWrite = lastDbWriteTime.current[incId] || 0;
          const isStateTransition = inc.lifecycle_state === 'DETECTED';

          if (isStateTransition || (now - lastWrite > 3000)) {
            lastDbWriteTime.current[incId] = now;
            try {
              await saveOrUpdateIncident({
                ...event,
                incident_id: incId,
                violation: inc.violation,
                violations: [inc.violation],
                severity: inc.severity || event.risk_level,
                risk_level: inc.severity || event.risk_level,
                lifecycle_state: inc.lifecycle_state || 'ACTIVE',
                first_detected_at: inc.first_detected_at ? new Date(inc.first_detected_at * 1000).toISOString() : (event.timestamp || new Date().toISOString()),
                last_seen_at: inc.last_seen_at ? new Date(inc.last_seen_at * 1000).toISOString() : (event.timestamp || new Date().toISOString()),
                source: event.source || 'LIVE_AI'
              });
            } catch (_) {}
          }
        }
      } else {
        // Fallback for single violation or legacy events
        for (const v of event.violations) {
          const incId = (event.incident_id && event.violations.length === 1)
            ? event.incident_id
            : `inc-${event.worker_id}-${v}`;
          const lastWrite = lastDbWriteTime.current[incId] || 0;
          const isStateTransition = event.lifecycle_state === 'DETECTED';

          if (isStateTransition || (now - lastWrite > 3000)) {
            lastDbWriteTime.current[incId] = now;
            try {
              await saveOrUpdateIncident({
                ...event,
                incident_id: incId,
                violation: v,
                violations: [v],
                lifecycle_state: event.lifecycle_state || 'ACTIVE',
                source: event.source || 'LIVE_AI'
              });
            } catch (_) {}
          }
        }
      }

      if (now - lastDbRefreshTime.current > 2500) {
        lastDbRefreshTime.current = now;
        await refreshIncidents();
      }
    } else if (event.lifecycle_state === 'RESOLVED') {
      activeViolationWorkers.current.delete(event.worker_id);
      setActiveAlerts(prev => prev.filter(a => a.worker_id !== event.worker_id));
      if (event.incident_id) {
        try {
          await resolveIncident(event.incident_id);
          await refreshIncidents();
        } catch (_) {}
      }
    }
  }, [playAlertSound, refreshIncidents]);

  // Connect to Python WebSocket
  const connectWebSocket = useCallback(() => {
    try {
      setConnectionStatus('connecting');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setConnectionStatus('connected');
        console.log('[ErgoGuard] WebSocket transport connected on', WS_URL);
      };

      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (!data) return;

          // Decoupled Video Stream message
          if (data.type === 'VIDEO_FRAME') {
            if (data.frame_image) setLiveFrame(data.frame_image);
            if (data.metrics) {
              setLiveMetrics(data.metrics);
              if (data.metrics.active_source) setBackendSource(data.metrics.active_source);
              if (data.metrics.privacy_mode) setPrivacyModeState(data.metrics.privacy_mode);
              if (data.metrics.pipeline_state) setPipelineState(data.metrics.pipeline_state);
            }
            return;
          }

          // Source status message
          if (data.type === 'SOURCE_STATUS') {
            if (data.source) setBackendSource(data.source);
            return;
          }

          // Camera status message from Python backend
          if (data.type === 'CAMERA_STATUS') {
            if (data.active !== undefined) {
              setIsCameraActive(data.active);
              if (!data.active) {
                setLiveFrame(null);
              }
            }
            if (data.source) setBackendSource(data.source);
            if (data.privacy_mode) setPrivacyModeState(data.privacy_mode);
            if (data.pipeline_state) setPipelineState(data.pipeline_state);
            if (data.error) {
              setCameraError({
                title: "Camera In Use or Unavailable",
                message: data.error,
                solution: "Close any other apps (Zoom, Teams, Skype, or other tabs) using the webcam, then click 'Turn Camera On'."
              });
            } else if (data.active) {
              setCameraError(null);
            }
            return;
          }

          // Incident lifecycle notifications
          if (data.type === 'INCIDENT_UPDATE' && data.incident) {
            const inc = data.incident;
            saveOrUpdateIncident({
              incident_id: inc.incident_id,
              worker_id: inc.worker_id,
              violation: inc.violation,
              violations: [inc.violation],
              location: inc.location,
              severity: inc.severity,
              risk_level: inc.severity,
              lifecycle_state: inc.lifecycle_state,
              first_detected_at: inc.first_detected_at ? new Date(inc.first_detected_at * 1000).toISOString() : new Date().toISOString(),
              last_seen_at: inc.last_seen_at ? new Date(inc.last_seen_at * 1000).toISOString() : new Date().toISOString(),
              source: data.source || 'LIVE_AI'
            }).then(() => refreshIncidents());
            return;
          }

          if (data.type === 'INCIDENT_RESOLVED' && data.incident) {
            resolveIncident(data.incident.incident_id).then(() => refreshIncidents());
            return;
          }

          if (data.type === 'INCIDENT_STALE' && data.incident) {
            const inc = data.incident;
            saveOrUpdateIncident({
              incident_id: inc.incident_id,
              worker_id: inc.worker_id,
              violation: inc.violation,
              violations: [inc.violation],
              location: inc.location,
              severity: inc.severity,
              risk_level: inc.severity,
              lifecycle_state: 'NOT_OBSERVED',
              first_detected_at: inc.first_detected_at ? new Date(inc.first_detected_at * 1000).toISOString() : new Date().toISOString(),
              last_seen_at: inc.last_seen_at ? new Date(inc.last_seen_at * 1000).toISOString() : new Date().toISOString(),
              source: data.source || 'LIVE_AI'
            }).then(() => refreshIncidents());
            return;
          }

          // Legacy compatibility: frame attached to event
          if (data.frame_image) {
            setLiveFrame(data.frame_image);
          }
          if (data.metrics) {
            setLiveMetrics(data.metrics);
          }

          // Telemetry event message
          if (data.worker_id) {
            processEvent(data);
          }
        } catch (e) {
          console.error('[ErgoGuard] WS JSON parse error:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        setIsCameraActive(false);
        setLiveFrame(null);
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = () => {
        setIsConnected(false);
        setConnectionStatus('disconnected');
        setIsCameraActive(false);
      };
    } catch (_) {
      setIsConnected(false);
      setConnectionStatus('disconnected');
      setIsCameraActive(false);
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 4000);
    }
  }, [processEvent]);

  // Initialize DB and connection
  useEffect(() => {
    seedSampleIncidentsIfEmpty(DEMO_SCENARIOS.map(s => s.event)).then(() => {
      refreshIncidents();
    });

    connectWebSocket();

    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connectWebSocket, refreshIncidents]);

  // Prune workers that have not been seen for > 8 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      setActiveWorkers(prev => {
        let changed = false;
        const next = { ...prev };
        for (const [id, worker] of Object.entries(next)) {
          if (now - (worker.last_seen || 0) > 8000) {
            delete next[id];
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  // Toggle Python Physical Webcam (Strictly on-demand)
  const toggleCamera = useCallback((enable) => {
    let sent = false;
    setCameraError(null);
    setIsCameraActive(prev => {
      const next = typeof enable === 'boolean' ? enable : !prev;
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ command: next ? 'START_CAMERA' : 'STOP_CAMERA' }));
        sent = true;
        if (!next) {
          setLiveFrame(null);
        }
        return next;
      }
      return false;
    });
    return sent;
  }, []);

  // Trigger demo scenario (immediately deactivates camera)
  const triggerScenario = useCallback((scenarioId) => {
    setOperatingMode('DEMO');
    setIsCameraActive(false);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: scenarioId }));
    }
    const localEvent = createSimulatedEvent(scenarioId);
    if (localEvent) {
      processEvent(localEvent);
    }
  }, [processEvent]);

  // Switch back to LIVE AI mode
  const setLiveMode = useCallback(() => {
    setOperatingMode('LIVE');
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'MODE_LIVE' }));
    }
  }, []);

  // Dismiss / resolve alert
  const dismissAlert = useCallback(async (index) => {
    const target = activeAlerts[index];
    setActiveAlerts(prev => prev.filter((_, i) => i !== index));
    if (target && target.incident_id) {
      await resolveIncident(target.incident_id);
      await refreshIncidents();
    }
  }, [activeAlerts, refreshIncidents]);

  // Set Privacy Filter mode (OFF, BLUR_FACES, SKELETON_ONLY)
  const setPrivacyMode = useCallback((mode) => {
    setPrivacyModeState(mode);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'SET_PRIVACY_MODE', mode }));
    }
  }, []);

  // Switch video input source (Webcam, CCTV URL, or video file)
  const setVideoSource = useCallback((source) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'SET_SOURCE', source }));
    }
  }, []);

  // Upload demo video from device's local storage for testing
  const uploadVideo = useCallback(async (file, onProgress) => {
    if (!file) return false;

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[ErgoGuard] WebSocket not connected; video file will play in local preview mode.');
      return false;
    }

    const CHUNK_SIZE = 1024 * 1024; // 1MB chunks
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(file.size, start + CHUNK_SIZE);
      const blobSlice = file.slice(start, end);

      const buffer = await blobSlice.arrayBuffer();
      let binary = '';
      const bytes = new Uint8Array(buffer);
      const len = bytes.byteLength;
      for (let b = 0; b < len; b++) {
        binary += String.fromCharCode(bytes[b]);
      }
      const chunkB64 = window.btoa(binary);

      wsRef.current.send(JSON.stringify({
        command: 'UPLOAD_VIDEO_CHUNK',
        upload_id: uploadId,
        filename: file.name,
        chunk_idx: i,
        total_chunks: totalChunks,
        chunk_data: chunkB64
      }));

      if (onProgress) {
        onProgress(Math.round(((i + 1) / totalChunks) * 100));
      }
    }
    return true;
  }, []);

  const clearAlerts = useCallback(() => {
    setActiveAlerts([]);
  }, []);

  return {
    isConnected,
    connectionStatus,
    operatingMode,
    backendSource,
    pipelineState,
    privacyMode,
    setPrivacyMode,
    setVideoSource,
    uploadVideo,
    setLiveMode,
    latestEvent,
    liveFrame,
    liveMetrics,
    isCameraActive,
    cameraError,
    setCameraError,
    toggleCamera,
    activeWorkers: Object.values(activeWorkers),
    activeAlerts,
    incidents,
    triggerScenario,
    dismissAlert,
    clearAlerts,
    refreshIncidents
  };
}
