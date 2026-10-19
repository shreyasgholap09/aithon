/**
 * IndexedDB Service for ErgoGuard AI Incident Storage
 * Persists confirmed incident lifecycle records locally in the browser.
 * Ensures stable incident IDs prevent continuous video frames from creating duplicate rows.
 */

const DB_NAME = 'ErgoGuardDB';
const DB_VERSION = 2;
const STORE_NAME = 'incidents';

let dbPromise = null;

export function openDB() {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      let store;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        store = db.createObjectStore(STORE_NAME, { keyPath: 'incident_id' });
      } else {
        store = event.target.transaction.objectStore(STORE_NAME);
      }

      // Safe index creation
      const indexes = ['worker_id', 'timestamp', 'risk_level', 'location', 'source', 'lifecycle_state'];
      indexes.forEach(idx => {
        if (!store.indexNames.contains(idx)) {
          store.createIndex(idx, idx, { unique: false });
        }
      });
    };

    request.onsuccess = (event) => resolve(event.target.result);
    request.onerror = (event) => {
      console.error('[IndexedDB] DB connection error:', event.target.error);
      reject(event.target.error);
    };
  });

  return dbPromise;
}

/**
 * Upserts an incident record by its stable incident_id.
 * If the incident already exists (ongoing active violation), updates last_seen_at without duplicating!
 */
export async function saveOrUpdateIncident(incident) {
  if (!incident) return null;
  const incId = incident.incident_id || 
    (incident.worker_id && (incident.violation || (incident.violations && incident.violations[0]))
      ? `inc-${incident.worker_id}-${incident.violation || incident.violations[0]}`
      : incident.event_id) || 
    `inc-${incident.worker_id || 'unknown'}-${Date.now()}`;

  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);

      const getReq = store.get(incId);
      getReq.onsuccess = () => {
        const existing = getReq.result;
        const nowIso = new Date().toISOString();

        const record = {
          ...(existing || {}),
          ...incident,
          incident_id: incId,
          first_detected_at: existing?.first_detected_at || incident.first_detected_at || incident.timestamp || nowIso,
          last_seen_at: incident.last_seen_at || incident.timestamp || nowIso,
          updated_at: nowIso,
          lifecycle_state: incident.lifecycle_state || existing?.lifecycle_state || 'ACTIVE',
          source: incident.source || existing?.source || 'LIVE_AI'
        };

        const putReq = store.put(record);
        putReq.onsuccess = () => resolve(record);
        putReq.onerror = (e) => reject(e.target.error);
      };

      getReq.onerror = (e) => reject(e.target.error);
    });
  } catch (err) {
    console.error('[IndexedDB] Save error:', err);
    return null;
  }
}

/**
 * Marks an incident as RESOLVED
 */
export async function resolveIncident(incidentId) {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const getReq = store.get(incidentId);

      getReq.onsuccess = () => {
        const item = getReq.result;
        if (!item) return resolve(false);

        item.lifecycle_state = 'RESOLVED';
        item.resolved_at = new Date().toISOString();
        const putReq = store.put(item);
        putReq.onsuccess = () => resolve(true);
        putReq.onerror = (e) => reject(e.target.error);
      };
      getReq.onerror = (e) => reject(e.target.error);
    });
  } catch (err) {
    console.error('[IndexedDB] Resolve error:', err);
    return false;
  }
}

/**
 * Returns all stored incidents sorted by timestamp descending
 */
export async function getAllIncidents() {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();

      req.onsuccess = () => {
        const records = req.result || [];
        records.sort((a, b) => new Date(b.last_seen_at || b.timestamp).getTime() - new Date(a.last_seen_at || a.timestamp).getTime());
        resolve(records);
      };
      req.onerror = (e) => reject(e.target.error);
    });
  } catch (err) {
    console.error('[IndexedDB] Fetch error:', err);
    return [];
  }
}

/**
 * Clears the incident database
 */
export async function clearAllIncidents() {
  try {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.clear();
      req.onsuccess = () => resolve(true);
      req.onerror = (e) => reject(e.target.error);
    });
  } catch (err) {
    console.error('[IndexedDB] Clear error:', err);
    return false;
  }
}

/**
 * Seeds initial demo data if database is empty so judges immediately see historical audit metrics
 */
export async function seedSampleIncidentsIfEmpty(sampleEvents = []) {
  try {
    const existing = await getAllIncidents();
    if (existing.length === 0 && sampleEvents.length > 0) {
      for (const item of sampleEvents) {
        if (item.violations && item.violations.length > 0) {
          await saveOrUpdateIncident({
            ...item,
            incident_id: item.event_id || `seed-${item.worker_id}-${Date.now()}`,
            source: 'SIMULATED'
          });
        }
      }
      return true;
    }
    return false;
  } catch (err) {
    console.warn('[IndexedDB] Seed failed:', err);
    return false;
  }
}
