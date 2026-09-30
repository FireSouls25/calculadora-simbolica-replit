/**
 * Barra de símbolos siempre visible.
 *
 * Los símbolos llegan del servidor (`/api/palette`), así que la barra y el
 * evaluador nunca se desincronizan: aquí no hay ninguna lista de funciones.
 */

import { focusedField, insertInField } from "./cells.js";

const state = {
  groups: [],
  symbols: [],
  active: null,
  query: "",
};

export function buildSymbolShelf(palette) {
  state.groups = palette.groups || [];
  state.symbols = palette.symbols || [];
  state.active = state.groups[0]?.id || null;
  renderGroups();
  renderKeys();
  bindSearch();
}

/* ------------------------------------------------------------------ grupos */

function renderGroups() {
  const container = document.querySelector("#symbol-groups");
  container.replaceChildren();
  state.groups.forEach((group) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "group-chip";
    button.textContent = group.label;
    button.dataset.group = group.id;
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(group.id === state.active));
    button.addEventListener("click", () => {
      state.active = group.id;
      state.query = "";
      const search = document.querySelector("#symbol-search");
      if (search) search.value = "";
      renderGroups();
      renderKeys();
    });
    container.append(button);
  });
}

/* ------------------------------------------------------------------ búsqueda */

function bindSearch() {
  const search = document.querySelector("#symbol-search");
  search.addEventListener("input", () => {
    state.query = search.value.trim().toLowerCase();
    renderKeys();
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      search.value = "";
      state.query = "";
      renderKeys();
      search.blur();
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const first = document.querySelector("#symbol-keys button");
      if (first) first.click();
    }
  });
}

/* -------------------------------------------------------------------- teclas */

function normalize(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[\\{}()[\]^_]/g, " ")
    .trim();
}

function visibleSymbols() {
  if (state.query) {
    return state.symbols.filter((entry) => {
      const haystack = normalize(`${entry.label} ${entry.title || ""} ${entry.latex}`);
      return haystack.includes(state.query);
    });
  }
  return state.symbols.filter((entry) => entry.group === state.active);
}

function renderKeys() {
  const container = document.querySelector("#symbol-keys");
  const hint = document.querySelector("#shelf-hint");
  container.replaceChildren();
  const entries = visibleSymbols();
  entries.forEach((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "symbol-key";
    button.dataset.insert = entry.latex;
    button.textContent = entry.label;
    if (entry.title) button.title = entry.title;
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => insertInField(focusedField(), entry.latex));
    container.append(button);
  });
  if (!entries.length) {
    const empty = document.createElement("span");
    empty.className = "shelf-empty";
    empty.textContent = "Ningún símbolo coincide con la búsqueda.";
    container.append(empty);
  }
  hint.textContent = state.query
    ? `${entries.length} resultado(s) · Enter inserta el primero`
    : "Pulsa un símbolo para insertarlo en la celda activa; las flechas se mueven dentro de la estructura.";
}