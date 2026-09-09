/** P1-05：本地报告 IndexedDB 存储（最多 10 份，无账号/同步）。 */

export const REPORT_SCHEMA_VERSION = 1
export const MAX_SAVED_REPORTS = 10
const DB_NAME = 'crusher_local_reports'
const DB_VERSION = 1
const STORE = 'reports'

/**
 * @typedef {Object} SavedReportRecord
 * @property {string} report_id
 * @property {number} schema_version
 * @property {string} title
 * @property {string} created_at
 * @property {'analysis'|'dual'} kind
 * @property {object} report
 * @property {string} [task_id]
 * @property {string} [source_text]
 */

function openDb() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('当前环境不支持 IndexedDB'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onerror = () => reject(req.error || new Error('打开本地库失败'))
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'report_id' })
        store.createIndex('created_at', 'created_at', { unique: false })
      }
    }
    req.onsuccess = () => resolve(req.result)
  })
}

function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error || new Error('事务失败'))
    tx.onabort = () => reject(tx.error || new Error('事务中止'))
  })
}

export function isSchemaCompatible(record) {
  return Boolean(record) && Number(record.schema_version) === REPORT_SCHEMA_VERSION
}

/**
 * @param {Omit<SavedReportRecord, 'report_id'|'schema_version'|'created_at'> & { report_id?: string }} input
 * @returns {Promise<SavedReportRecord>}
 */
export async function saveReport(input) {
  const db = await openDb()
  const record = {
    report_id: input.report_id || cryptoRandomId(),
    schema_version: REPORT_SCHEMA_VERSION,
    title: String(input.title || '未命名报告').slice(0, 80),
    created_at: new Date().toISOString(),
    kind: input.kind || 'analysis',
    report: input.report,
    task_id: input.task_id || undefined,
    source_text: input.source_text || undefined,
  }
  const tx = db.transaction(STORE, 'readwrite')
  const store = tx.objectStore(STORE)
  store.put(record)
  await txDone(tx)
  await trimToMax(db)
  db.close()
  return record
}

/** @returns {Promise<SavedReportRecord[]>} */
export async function listReports() {
  const db = await openDb()
  const tx = db.transaction(STORE, 'readonly')
  const store = tx.objectStore(STORE)
  const req = store.getAll()
  const rows = await reqToPromise(req)
  await txDone(tx)
  db.close()
  return (rows || []).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
}

/** @param {string} reportId */
export async function getReport(reportId) {
  const db = await openDb()
  const tx = db.transaction(STORE, 'readonly')
  const store = tx.objectStore(STORE)
  const row = await reqToPromise(store.get(reportId))
  await txDone(tx)
  db.close()
  return row || null
}

/** @param {string} reportId */
export async function deleteReport(reportId) {
  const db = await openDb()
  const tx = db.transaction(STORE, 'readwrite')
  tx.objectStore(STORE).delete(reportId)
  await txDone(tx)
  db.close()
}

async function trimToMax(db) {
  const tx = db.transaction(STORE, 'readwrite')
  const store = tx.objectStore(STORE)
  const all = await reqToPromise(store.getAll())
  const sorted = (all || []).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)))
  const overflow = sorted.length - MAX_SAVED_REPORTS
  if (overflow > 0) {
    for (let i = 0; i < overflow; i += 1) {
      store.delete(sorted[i].report_id)
    }
  }
  await txDone(tx)
}

function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('IndexedDB 请求失败'))
  })
}

function cryptoRandomId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `local_${Date.now()}_${Math.random().toString(16).slice(2)}`
}
