/**
 * Celdas del cuaderno: crear, editar, ejecutar y mostrar el resultado.
 */

import { calculate } from "./api.js";
import { activeCell, loadCells, nextExecution, notebook, saveCells, setActiveCell } from "./state.js";

const KIND_LABELS = {
  number: "valor exacto",
  complex: "número complejo",
  symbolic: "resultado simbólico",
  relation: "relación",
  matrix: "matriz",
  set: "conjunto",
  formal: "expresión formal",
  infinity: "infinito",
  undefined: "indefinido",
  branches: "dos resultados",
};

let root = null;
let mathLiveReady = false;

export function configureNotebook(options) {
  root = options.root;
  mathLiveReady = options.mathLive;
}

/* ------------------------------------------------------------------ campos */

export function createField(value = "", readOnly = false) {
  if (!mathLiveReady) {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "fallback-field";
    input.value = value;
    input.spellcheck = false;
    input.setAttribute("aria-label", readOnly ? "Resultado" : "Escribe una expresión matemática");
    if (readOnly) {
      input.readOnly = true;
      input.tabIndex = -1; // los resultados no entran en el tabulador
    }
    return input;
  }
  const field = document.createElement("math-field");
  field.className = readOnly ? "result-field" : "editor-field";
  field.setAttribute("math-virtual-keyboard-policy", "manual");
  field.setAttribute("aria-label", readOnly ? "Resultado exacto" : "Escribe una expresión matemática");
  if (readOnly) {
    field.setAttribute("read-only", "");
    field.setAttribute("tabindex", "-1"); // resultados y ejemplos: no tabulables
  }
  field.value = value;
  return field;
}

function fieldValue(field) {
  return (field?.value || "").trim();
}

export function insertInField(field, latex) {
  if (!field) return;
  field.focus();
  if (typeof field.insert === "function") {
    field.insert(latex);
  } else if (typeof field.setSelectionRange === "function") {
    const start = field.selectionStart ?? field.value.length;
    const end = field.selectionEnd ?? start;
    field.value = field.value.slice(0, start) + latex + field.value.slice(end);
    const caret = start + latex.length;
    field.setSelectionRange(caret, caret);
    field.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

export function focusedField() {
  const cell = activeCell();
  if (cell && document.activeElement === cell.field) return cell.field;
  const field = root.querySelector("math-field.editor-field, input.fallback-field");
  return field || null;
}

/* ------------------------------------------------------------------ celdas */

export function makeCell({ expression = "", result = null, count = null } = {}) {
  const cell = document.createElement("article");
  cell.className = "cell";
  cell.result = result;
  cell.count = count;
  cell.innerHTML = `
    <div class="input-row">
      <div class="prompt input-prompt"></div>
      <div class="input-area">
        <div class="math-shell"></div>
        <button class="run-cell" type="button" title="Ejecutar (Shift + Enter)" aria-label="Ejecutar celda">▶</button>
      </div>
    </div>
    <div class="output-row" hidden>
      <div class="prompt output-prompt"></div>
      <div class="output-content"></div>
    </div>
    <span class="cell-error" role="alert" aria-live="polite"></span>`;

  const field = createField(expression);
  cell.field = field;
  cell.querySelector(".math-shell").append(field);

  field.addEventListener("focus", () => setActiveCell(cell));
  field.addEventListener("input", () => {
    cell.result = null;
    cell.count = null;
    clearOutput(cell);
    persist();
  });
  field.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    if (event.shiftKey) {
      event.preventDefault();
      runCell(cell, { advance: true });
    } else if (event.ctrlKey || event.metaKey) {
      event.preventDefault();
      runCell(cell);
    } else if (event.altKey) {
      event.preventDefault();
      runCell(cell, { insertNext: true });
    }
  });
  cell.querySelector(".run-cell").addEventListener("click", () => runCell(cell, { advance: true }));

  root.append(cell);
  if (result) renderResult(cell, result, count);
  return cell;
}

export function insertCellAfter(cell, { focus = true } = {}) {
  const created = makeCell();
  if (cell && cell.nextSibling) root.insertBefore(created, cell.nextSibling);
  else if (cell) root.append(created);
  else root.prepend(created);
  persist();
  if (focus) focusCell(created);
  return created;
}

export function focusCell(cell) {
  if (!cell) return;
  setActiveCell(cell);
  cell.classList.add("is-active");
  requestAnimationFrame(() => cell.field?.focus());
}

export function lastCell() {
  return root.lastElementChild;
}

/* ----------------------------------------------------------------- salidas */

function clearOutput(cell) {
  const output = cell.querySelector(".output-row");
  output.hidden = true;
  output.querySelector(".output-content").replaceChildren();
  cell.querySelector(".cell-error").textContent = "";
}

function renderExact(target, result) {
  const box = document.createElement("div");
  box.className = "output-item";
  const math = createField(result.latex, true);
  box.append(math);
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "copy-result";
  copy.title = "Copiar el resultado";
  copy.textContent = "⧉";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(result.exact);
      copy.textContent = "✓";
      setTimeout(() => (copy.textContent = "⧉"), 1200);
    } catch (error) {
      /* el portapapeles puede estar bloqueado: no es crítico */
    }
  });
  box.append(copy);
  box.title = result.exact;
  target.append(box);
}

export function renderResult(cell, result, count = cell.count) {
  cell.result = result;
  cell.count = count;
  const output = cell.querySelector(".output-row");
  const content = output.querySelector(".output-content");
  content.replaceChildren();

  if (result.branches && result.branches.length) {
    const list = document.createElement("div");
    list.className = "output-branches";
    result.branches.forEach((branch) => renderExact(list, branch));
    content.append(list);
  } else {
    renderExact(content, result);
  }

  const tag = KIND_LABELS[result.kind] || "resultado";
  const meta = document.createElement("div");
  meta.className = "approx-row";
  meta.append(Object.assign(document.createElement("span"), { className: "approx-tag", textContent: tag }));
  if (result.approx !== null && result.approx !== undefined) {
    meta.append(document.createTextNode(`≈ ${result.approx}`));
  }
  if (result.branches && result.branches.length > 1) {
    meta.append(document.createTextNode(` · ${result.branches.length} resultados`));
  }
  content.append(meta);

  output.querySelector(".output-prompt").textContent = `Out[${count}]:`;
  output.hidden = false;
  cell.querySelector(".cell-error").textContent = "";
  refreshPrompts();
}

/* ---------------------------------------------------------------- ejecución */

export async function runCell(cell, { advance = false, insertNext = false } = {}) {
  if (!cell) return;
  const error = cell.querySelector(".cell-error");
  const runButton = cell.querySelector(".run-cell");
  const expression = fieldValue(cell.field);
  if (!expression) {
    error.textContent = "Escribe una expresión para ejecutarla.";
    focusCell(cell);
    return;
  }
  error.textContent = "";
  runButton.disabled = true;
  runButton.textContent = "…";
  try {
    const result = await calculate(expression);
    renderResult(cell, result, nextExecution());
    persist();
    if (insertNext) {
      insertCellAfter(cell);
    } else if (advance) {
      const next = cell.nextElementSibling;
      if (next) focusCell(next);
      else insertCellAfter(cell);
    } else {
      focusCell(cell);
    }
  } catch (exception) {
    error.textContent = exception.message || "No se pudo completar el cálculo.";
  } finally {
    runButton.disabled = false;
    runButton.textContent = "▶";
  }
}

export async function runAll() {
  const cells = [...root.children];
  for (const cell of cells) {
    if (!fieldValue(cell.field)) continue;
    // eslint-disable-next-line no-await-in-loop
    await runCell(cell);
  }
  focusCell(lastCell());
}

export function deleteCell(cell) {
  if (root.children.length === 1) {
    cell.field.value = "";
    cell.result = null;
    cell.count = null;
    clearOutput(cell);
    persist();
    focusCell(cell);
    return;
  }
  const previous = cell.previousElementSibling || cell.nextElementSibling;
  cell.remove();
  refreshPrompts();
  persist();
  focusCell(previous);
}

/* ------------------------------------------------------------------ global */

export function refreshPrompts() {
  [...root.children].forEach((cell, index) => {
    cell.dataset.number = String(index + 1);
    cell.querySelector(".input-prompt").textContent = cell.count ? `In [${cell.count}]:` : "In [ ]:";
  });
}

export function persist() {
  const snapshot = [...root.children].map((cell) => ({
    expression: fieldValue(cell.field),
    result: cell.result,
    count: cell.count,
  }));
  const saved = saveCells(snapshot);
  const indicator = document.querySelector("#save-state");
  if (indicator) indicator.textContent = saved ? "guardado" : "sin guardar";
  refreshPrompts();
}

export function restoreNotebook() {
  const saved = loadCells();
  saved.forEach((entry) => {
    const cell = makeCell(entry || {});
    if (entry?.count) notebook.execution = Math.max(notebook.execution, entry.count);
  });
  if (!root.children.length) makeCell();
  const last = lastCell();
  if (fieldValue(last.field)) makeCell();
  focusCell(lastCell());
  refreshPrompts();
}