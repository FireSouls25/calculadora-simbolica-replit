const NOTEBOOK_KEY = "forma-notebook-v2";
const LEGACY_NOTEBOOK_KEY = "forma-notebook";
const units = {
  length: [
    ["meter", "metros"], ["kilometer", "kilómetros"], ["centimeter", "centímetros"],
    ["millimeter", "milímetros"], ["mile", "millas"], ["foot", "pies"], ["inch", "pulgadas"],
  ],
  mass: [
    ["kilogram", "kilogramos"], ["gram", "gramos"], ["milligram", "miligramos"],
    ["pound", "libras"], ["ounce", "onzas"], ["tonne", "toneladas"],
  ],
  temperature: [
    ["degC", "°C · Celsius"], ["degF", "°F · Fahrenheit"], ["kelvin", "K · Kelvin"],
  ],
  volume: [
    ["liter", "litros"], ["milliliter", "mililitros"], ["gallon", "galones (US)"],
    ["cup", "tazas (US)"], ["meter ** 3", "metros cúbicos"], ["fluid_ounce", "onzas líquidas (US)"],
  ],
  time: [
    ["second", "segundos"], ["minute", "minutos"], ["hour", "horas"],
    ["day", "días"], ["week", "semanas"], ["year", "años"],
  ],
  speed: [
    ["meter / second", "m/s"], ["kilometer / hour", "km/h"], ["mile / hour", "mph"], ["knot", "nudos"],
  ],
  area: [
    ["meter ** 2", "m²"], ["kilometer ** 2", "km²"], ["hectare", "hectáreas"],
    ["acre", "acres"], ["foot ** 2", "pies²"],
  ],
  data: [
    ["byte", "bytes"], ["kilobyte", "kilobytes"], ["megabyte", "megabytes"],
    ["gigabyte", "gigabytes"], ["terabyte", "terabytes"],
  ],
};

const cellsRoot = document.querySelector("#cells");
let activeCell = null;
let activeField = null;
let cellNumber = 0;
let executionCount = 0;
let mathLiveReady = false;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function makeField(value = "", readOnly = false) {
  const field = document.createElement("math-field");
  field.className = readOnly ? "result-field" : "editor-field";
  field.setAttribute("math-virtual-keyboard-policy", "manual");
  field.setAttribute("aria-label", readOnly ? "Resultado exacto" : "Escribe una expresión matemática");
  if (readOnly) field.setAttribute("read-only", "");
  field.value = value;
  return field;
}

function makeCell({ expression = "", result = null, count = null, focus = false } = {}) {
  cellNumber += 1;
  const cell = document.createElement("article");
  cell.className = "cell";
  cell.dataset.number = String(cellNumber);
  cell._executionCount = count;
  cell._resultData = result;
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
  const field = makeField(expression);
  cell.querySelector(".math-shell").append(field);
  cell._field = field;
  field.addEventListener("focus", () => setActiveCell(cell));
  field.addEventListener("input", () => {
    cell._resultData = null;
    cell._executionCount = null;
    clearOutput(cell);
    refreshPrompts();
    saveNotebook();
  });
  field.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && event.shiftKey) {
      event.preventDefault();
      runCell(cell, { advance: true });
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      runCell(cell);
    } else if (event.key === "Enter" && event.altKey) {
      event.preventDefault();
      runCell(cell, { insertNext: true });
    }
  });
  cell.querySelector(".run-cell").addEventListener("click", () => runCell(cell, { advance: true }));
  cellsRoot.append(cell);
  if (result) renderResult(cell, result, count);
  refreshPrompts();
  if (focus) focusCell(cell);
  return cell;
}

function setActiveCell(cell) {
  activeCell = cell;
  activeField = cell?._field || null;
  document.querySelectorAll(".cell.is-active").forEach((node) => node.classList.remove("is-active"));
  if (cell) cell.classList.add("is-active");
}

function focusCell(cell) {
  if (!cell) return;
  setActiveCell(cell);
  requestAnimationFrame(() => cell._field?.focus());
}

function refreshPrompts() {
  [...cellsRoot.children].forEach((cell, index) => {
    cell.dataset.number = String(index + 1);
    const prompt = cell.querySelector(".input-prompt");
    prompt.textContent = cell._executionCount ? `In [${cell._executionCount}]:` : "In [ ]:";
    const outPrompt = cell.querySelector(".output-prompt");
    if (cell._executionCount) outPrompt.textContent = `Out[${cell._executionCount}]:`;
  });
  cellNumber = cellsRoot.children.length;
}

function clearOutput(cell) {
  const output = cell.querySelector(".output-row");
  output.hidden = true;
  output.querySelector(".output-content").replaceChildren();
  cell.querySelector(".cell-error").textContent = "";
}

function renderResult(cell, result, count = cell._executionCount) {
  cell._resultData = result;
  cell._executionCount = count;
  const output = cell.querySelector(".output-row");
  const content = output.querySelector(".output-content");
  content.replaceChildren();
  if (mathLiveReady) {
    content.append(makeField(result.latex, true));
  } else {
    const exact = document.createElement("div");
    exact.className = "output-text";
    exact.textContent = result.exact;
    content.append(exact);
  }
  if (result.approx !== null) {
    const approximate = document.createElement("div");
    approximate.className = "approx-row";
    approximate.innerHTML = `<span class="approx-tag">≈</span>${escapeHtml(result.approx)}`;
    content.append(approximate);
  } else if (result.branches) {
    const branches = document.createElement("div");
    branches.className = "approx-row";
    branches.textContent = "Dos resultados";
    content.append(branches);
  } else if (result.symbolic) {
    const symbolic = document.createElement("div");
    symbolic.className = "approx-row symbolic-tag";
    symbolic.textContent = "Resultado simbólico";
    content.append(symbolic);
  }
  output.querySelector(".output-prompt").textContent = `Out[${count}]:`;
  output.hidden = false;
  cell.querySelector(".cell-error").textContent = "";
  refreshPrompts();
}

function saveNotebook() {
  const snapshot = [...cellsRoot.children].map((cell) => ({
    expression: cell._field?.value || "",
    result: cell._resultData,
    count: cell._executionCount,
  }));
  try {
    localStorage.setItem(NOTEBOOK_KEY, JSON.stringify(snapshot));
    document.querySelector("#save-state").textContent = "guardado";
  } catch (_) {
    document.querySelector("#save-state").textContent = "sin guardar";
  }
}

function loadNotebook() {
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(NOTEBOOK_KEY) || "null");
    if (!Array.isArray(saved)) {
      const old = JSON.parse(localStorage.getItem(LEGACY_NOTEBOOK_KEY) || "null");
      const examples = ["\\sqrt{12+18}", "\\frac{1}{3}+\\frac{1}{6}"];
      if (Array.isArray(old) && !(old.length === examples.length && old.every((value, i) => value === examples[i]))) {
        saved = old.map((expression) => ({ expression }));
      }
    }
  } catch (_) {}
  if (Array.isArray(saved) && saved.length) {
    saved.forEach((entry) => {
      if (typeof entry === "string") makeCell({ expression: entry });
      else makeCell(entry || {});
      if (entry?.count) executionCount = Math.max(executionCount, entry.count);
    });
  } else {
    makeCell({ focus: true });
  }
  if (!cellsRoot.children.length) makeCell({ focus: true });
  const lastCell = cellsRoot.lastElementChild;
  if (lastCell._field.value.trim()) makeCell({ focus: true });
  else focusCell(lastCell);
  saveNotebook();
}

function insertCellAfter(cell, focus = true) {
  const next = makeCell();
  if (cell && cell.nextSibling) cellsRoot.insertBefore(next, cell.nextSibling);
  else if (cell) cellsRoot.append(next);
  else cellsRoot.prepend(next);
  refreshPrompts();
  saveNotebook();
  if (focus) focusCell(next);
  return next;
}

function nextCell(cell) {
  return cell.nextElementSibling;
}

async function runCell(cell, { advance = false, insertNext = false } = {}) {
  const field = cell?._field;
  const expression = field?.value?.trim() || "";
  const error = cell?.querySelector(".cell-error");
  const runButton = cell?.querySelector(".run-cell");
  if (!expression) {
    error.textContent = "Escribe una expresión para ejecutarla.";
    focusCell(cell);
    return;
  }
  error.textContent = "";
  runButton.disabled = true;
  runButton.textContent = "…";
  try {
    const response = await fetch("/api/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expression }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo calcular.");
    executionCount += 1;
    renderResult(cell, result, executionCount);
    saveNotebook();
    if (insertNext) {
      insertCellAfter(cell);
    } else if (advance) {
      const next = nextCell(cell);
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

function addNewCell() {
  if (!activeCell) return insertCellAfter(cellsRoot.lastElementChild);
  return insertCellAfter(activeCell);
}

document.querySelector("#new-cell").addEventListener("click", addNewCell);
document.querySelector("#empty-add-cell").addEventListener("click", addNewCell);
document.querySelector("#run-current").addEventListener("click", () => {
  if (activeCell) runCell(activeCell, { advance: true });
  else focusCell(cellsRoot.lastElementChild);
});

document.querySelectorAll(".symbol-key").forEach((button) => {
  button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", () => {
    if (!activeField) {
      const target = cellsRoot.lastElementChild;
      if (!target) return;
      focusCell(target);
      activeField = target._field;
    }
    activeField.focus();
    if (typeof activeField.insert === "function") activeField.insert(button.dataset.insert);
    saveNotebook();
  });
});

function makeFallbackEditors() {
  document.querySelectorAll("math-field.editor-field").forEach((field) => {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "fallback-field";
    input.value = field.value || "";
    input.setAttribute("aria-label", "Escribe una expresión matemática");
    field.replaceWith(input);
    const cell = input.closest(".cell");
    cell._field = input;
    input.addEventListener("focus", () => setActiveCell(cell));
    input.addEventListener("input", () => {
      cell._resultData = null;
      cell._executionCount = null;
      clearOutput(cell);
      saveNotebook();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.shiftKey) {
        event.preventDefault();
        runCell(cell, { advance: true });
      }
    });
  });
  document.querySelectorAll("math-field.result-field").forEach((field) => {
    const result = field.closest(".cell")?._resultData;
    if (!result) return;
    const output = field.closest(".output-content");
    const exact = document.createElement("div");
    exact.className = "output-text";
    exact.textContent = result.exact;
    field.replaceWith(exact);
  });
  if (!activeField) focusCell(cellsRoot.lastElementChild);
}

const modal = document.querySelector("#converter-modal");
const fromSelect = document.querySelector("#unit-from");
const toSelect = document.querySelector("#unit-to");
function setUnitOptions() {
  const selected = units[document.querySelector("#unit-category").value];
  const options = selected.map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`).join("");
  fromSelect.innerHTML = options;
  toSelect.innerHTML = options;
  if (selected.length > 1) toSelect.selectedIndex = 1;
  document.querySelector("#conversion-result strong").textContent = "—";
  document.querySelector("#conversion-result .result-unit").textContent = "";
  document.querySelector("#conversion-error").textContent = "";
}
function openConverter() {
  modal.hidden = false;
  document.querySelector("#unit-value").focus();
}
function closeConverter() { modal.hidden = true; }
document.querySelector("#open-converter").addEventListener("click", openConverter);
document.querySelector("#close-converter").addEventListener("click", closeConverter);
modal.addEventListener("click", (event) => { if (event.target === modal) closeConverter(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeConverter(); });
document.querySelector("#unit-category").addEventListener("change", setUnitOptions);
setUnitOptions();

async function convert() {
  const error = document.querySelector("#conversion-error");
  error.textContent = "";
  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        value: document.querySelector("#unit-value").value,
        from: fromSelect.value,
        to: toSelect.value,
      }),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.error || "No se pudo convertir.");
    document.querySelector("#conversion-result strong").textContent = result.formatted;
    document.querySelector("#conversion-result .result-unit").textContent = toSelect.options[toSelect.selectedIndex].text;
  } catch (exception) {
    error.textContent = exception.message;
  }
}
document.querySelector("#convert-button").addEventListener("click", convert);
document.querySelector("#unit-value").addEventListener("keydown", (event) => { if (event.key === "Enter") convert(); });
document.querySelector("#swap-units").addEventListener("click", () => {
  const from = fromSelect.selectedIndex;
  fromSelect.selectedIndex = toSelect.selectedIndex;
  toSelect.selectedIndex = from;
  convert();
});

if (window.customElements && customElements.get("math-field")) mathLiveReady = true;
loadNotebook();
if (!mathLiveReady && window.customElements) {
  Promise.race([
    customElements.whenDefined("math-field").then(() => { mathLiveReady = true; }),
    new Promise((resolve) => setTimeout(resolve, 3500)),
  ]).then(() => {
    if (!mathLiveReady) {
      makeFallbackEditors();
      return;
    }
    [...cellsRoot.children].forEach((cell) => {
      if (cell._resultData) renderResult(cell, cell._resultData, cell._executionCount);
    });
  });
}