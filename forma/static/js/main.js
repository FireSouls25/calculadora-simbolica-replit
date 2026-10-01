/**
 * Arranque: espera a MathLive, monta el cuaderno y conecta la barra de símbolos.
 */

import { fetchPalette } from "./api.js";
import {
  configureNotebook,
  createField,
  deleteCell,
  focusCell,
  insertCellAfter,
  lastCell,
  restoreNotebook,
  runAll,
  runCell,
} from "./cells.js";
import { activeCell } from "./state.js";
import { buildConverter } from "./converter.js";
import { buildSymbolShelf } from "./symbols.js";

const MATHLIVE_TIMEOUT = 3500;

const HELP = [
  ["Multiplicación", "2x, x(y+1), 3π. El punto se multiplica solo."],
  ["Logaritmos", "log es decimal, ln es natural: log(100)=2. Con base: log_2(8)."],
  ["Porcentajes", "50% vale 1/2. Para el resto de una división, mod o \\bmod."],
  ["Grados y radianes", "En las trigonométricas los números van en GRADOS: sin(90)=1, sin(30)=1/2. Con π son radianes: sin(π/6)=1/2. Usa rad(90) o deg(π/2) para cambiar de unidad, y 30\\degree para multiplicar por grados."],
  ["Complejos", "i es la unidad imaginaria: (1+i)^8=16."],
  ["Sumas e integrales", "\\sum_{i=1}^{10} i^2, \\int_0^1 x^2 dx, \\lim_{x\\to 0}…"],
  ["Decimales exactos", "0.1+0.2 se calcula como 3/10, sin errores de coma flotante."],
  ["Resultados dobles", "x^2\\pm x muestra las dos ramas."],
  ["Matrices", "[1,2;3,4] o \\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}, con det, inv, rank…"],
  ["Conjuntos", "\\{1,2,3\\}, {n | n > 0}, x ∈ ℝ, ℝ se escribe \\mathbb{R}."],
  ["Ayudas", "solve(x^2-5x+6, x), series(e^x, x, 0, 4), diff(x^3, x), simplify(…)."],
];

async function mathLiveIsReady() {
  if (window.customElements && customElements.get("math-field")) return true;
  if (!window.customElements) return false;
  return Promise.race([
    customElements.whenDefined("math-field").then(() => true),
    new Promise((resolve) => setTimeout(() => resolve(false), MATHLIVE_TIMEOUT)),
  ]);
}

function buildHelp() {
  const body = document.querySelector("#help-body");
  HELP.forEach(([title, text]) => {
    const row = document.createElement("div");
    row.className = "help-row";
    row.innerHTML = `<strong></strong><span></span>`;
    row.querySelector("strong").textContent = title;
    row.querySelector("span").textContent = text;
    body.append(row);
  });
  const modal = document.querySelector("#help-modal");
  document.querySelector("#open-help").addEventListener("click", () => {
    modal.hidden = false;
  });
  document.querySelector("#close-help").addEventListener("click", () => {
    modal.hidden = true;
  });
  modal.addEventListener("click", (event) => {
    if (event.target === modal) modal.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) modal.hidden = true;
  });
}

function buildExamples(examples) {
  const grid = document.querySelector("#examples-grid");
  examples.forEach((example) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "example";
    button.title = example.expression;
    button.setAttribute("aria-label", `Ejemplo: ${example.note || example.expression}`);
    // La misma fábrica que usan las celdas: math-field si MathLive está,
    // texto plano si no (así los ejemplos nunca salen en crudo).
    button.append(createField(example.expression, true));
    const note = document.createElement("span");
    note.textContent = example.note || "";
    button.append(note);
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      const cell = activeCell() || lastCell();
      cell.field.value = example.expression;
      cell.dispatchEvent(new Event("input", { bubbles: true }));
      focusCell(cell);
    });
    grid.append(button);
  });
}

function wireToolbar() {
  document.querySelector("#new-cell").addEventListener("click", () => {
    insertCellAfter(activeCell() || lastCell());
  });
  document.querySelector("#empty-add-cell").addEventListener("click", () => {
    insertCellAfter(lastCell());
  });
  document.querySelector("#run-current").addEventListener("click", () => {
    runCell(activeCell() || lastCell(), { advance: true });
  });
  document.querySelector("#run-all").addEventListener("click", runAll);

  document.addEventListener("keydown", (event) => {
    const editing = event.target.closest("math-field, input");
    if (!editing) return;
    if (event.key === "Backspace" && !event.target.value) {
      event.preventDefault();
      deleteCell(event.target.closest(".cell"));
    }
    if (event.key === "Enter" && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.stopPropagation();
    }
  });
}

async function start() {
  const cellsRoot = document.querySelector("#cells");
  const mathLive = await mathLiveIsReady();
  configureNotebook({ root: cellsRoot, mathLive });
  restoreNotebook();
  buildHelp();
  wireToolbar();
  if (!mathLive) {
    document.querySelector("#shelf-hint").textContent =
      "MathLive no cargó (sin conexión): los campos son de texto plano.";
  }

  try {
    const palette = await fetchPalette();
    buildSymbolShelf(palette);
    buildConverter(palette.unitCategories || []);
    buildExamples(palette.examples || []);
  } catch (error) {
    document.querySelector("#symbol-keys").innerHTML =
      '<span class="shelf-empty">No se pudo cargar la lista de símbolos.</span>';
  }
}

document.addEventListener("DOMContentLoaded", start);