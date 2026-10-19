import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Incidents from './pages/Incidents';
import Analytics from './pages/Analytics';
import { useSafetyEvents } from './hooks/useSafetyEvents';

export default function App() {
  const {
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
    activeWorkers,
    activeAlerts,
    incidents,
    triggerScenario,
    dismissAlert,
    clearAlerts,
    refreshIncidents
  } = useSafetyEvents();

  return (
    <BrowserRouter>
      <div className="flex flex-col h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
        {/* Top Navbar */}
        <Navbar
          connectionStatus={connectionStatus}
          operatingMode={operatingMode}
          backendSource={backendSource}
          onTriggerScenario={triggerScenario}
          onSetLiveMode={setLiveMode}
          onReset={clearAlerts}
        />

        {/* Body Layout: Sidebar + Main Content */}
        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            incidentCount={incidents.length}
            alertCount={activeAlerts.length}
          />

          <main className="flex-1 overflow-y-auto bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950">
            <Routes>
              <Route
                path="/"
                element={
                  <Dashboard
                    latestEvent={latestEvent}
                    liveFrame={liveFrame}
                    liveMetrics={liveMetrics}
                    isCameraActive={isCameraActive}
                    backendCameraError={cameraError}
                    onClearBackendCameraError={() => setCameraError(null)}
                    onToggleCamera={toggleCamera}
                    activeWorkers={activeWorkers}
                    activeAlerts={activeAlerts}
                    incidents={incidents}
                    operatingMode={operatingMode}
                    backendSource={backendSource}
                    pipelineState={pipelineState}
                    privacyMode={privacyMode}
                    onSetPrivacyMode={setPrivacyMode}
                    onSetVideoSource={setVideoSource}
                    onUploadVideo={uploadVideo}
                    onTriggerScenario={triggerScenario}
                    onSetLiveMode={setLiveMode}
                    onDismissAlert={dismissAlert}
                    onClearAlerts={clearAlerts}
                    connectionStatus={connectionStatus}
                  />
                }
              />
              <Route
                path="/incidents"
                element={
                  <Incidents
                    incidents={incidents}
                    onRefresh={refreshIncidents}
                  />
                }
              />
              <Route
                path="/analytics"
                element={
                  <Analytics
                    incidents={incidents}
                  />
                }
              />
              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
