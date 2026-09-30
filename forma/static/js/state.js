/**
 * Estado del cuaderno y persistencia en localStorage.
 */

const STORAGE_KEY = "forma-notebook-v3";
const LEGACY_KEYS = ["forma-notebook-v2", "forma-notebook"];

export const notebook = {
  cells: [],
  executions: 0,
  active: null,
};

export function activeCell() {
  return notebook.active;
}

export function setActiveCell(cell) {
  notebook.active = cell;
}

export function nextExecution() {
  notebook.execution += 1;
  return notebook.execution;
}

function readStored(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch (error) {
    return null;
  }
}

/** Lectura tolerante: acepta el formato nuevo y el antiguo (solo expresiones). */
export function loadCells() {
  const stored = readStored(STORAGE_KEY);
  if (Array.isArray(stored)) return stored;
  for (const key of LEGACY_KEYS) {
    const legacy = readStored(key);
    if (Array.isArray(legacy) && legacy.length) {
      return legacy.map((entry) => (typeof entry === "string" ? { expression: entry } : entry || {}));
    }
  }
  return [];
}

export function saveCells(cells) {
  notebook.cells = cells;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cells));
    return true;
  } catch (error) {
    return false;
  }
}

export function clearStorage() {
  LEGACY_KEYS.concat(STORAGE_KEY).forEach((key) => localStorage.removeItem(key));
}