// Private question snapshots and queued edits live in IndexedDB, never the service-worker cache.
let opening;

function database() {
  if (!opening) opening = new Promise((resolve, reject) => {
    const request = indexedDB.open('mindtrace-exams', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('attempts', { keyPath: ['scope', 'id'] }).createIndex('scope', 'scope');
    request.onsuccess = () => {
      const db = request.result;
      db.onversionchange = () => { db.close(); opening = undefined; };
      resolve(db);
    };
    request.onerror = request.onblocked = () => reject(new Error('Couldn’t open storage on this device.'));
  }).catch(error => { opening = undefined; throw error; });
  return opening;
}

async function useStore(mode, run) {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('attempts', mode);
    let result;
    tx.oncomplete = () => resolve(result);
    tx.onerror = tx.onabort = () => reject(tx.error || new Error('Couldn’t save to this device.'));
    run(tx.objectStore('attempts'), value => { result = value; });
  });
}

export const offlinePapers = scope => useStore('readonly', (store, done) => {
  const request = store.index('scope').getAll(scope);
  request.onsuccess = () => done(request.result);
});

// Compare revisions in the same transaction as the write. Another tab's edit cannot be overwritten silently.
export const writePaper = (scope, id, revision, next) => useStore('readwrite', (store, done) => {
  const request = store.get([scope, id]);
  request.onsuccess = () => {
    const current = request.result;
    if ((current?.revision || 0) !== revision) { done({ conflict: true, current }); return; }
    const record = next && { ...next, scope, id, revision: revision + 1 };
    if (record) store.put(record); else store.delete([scope, id]);
    done({ current: record });
  };
});

export const deviceDeadline = attempt => Date.now() + Date.parse(attempt.deadline_at) - Date.parse(attempt.server_time);
