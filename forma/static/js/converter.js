/**
 * Conversor de unidades.
 */

import { convert } from "./api.js";

export function buildConverter(categories) {
  const modal = document.querySelector("#converter-modal");
  const categorySelect = document.querySelector("#unit-category");
  const fromSelect = document.querySelector("#unit-from");
  const toSelect = document.querySelector("#unit-to");
  const valueInput = document.querySelector("#unit-value");
  const errorBox = document.querySelector("#conversion-error");

  categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.id;
    option.textContent = category.label;
    categorySelect.append(option);
  });

  function fillUnits() {
    const category = categories.find((item) => item.id === categorySelect.value) || categories[0];
    const options = category.units.map(([value, label]) => ({ value, label }));
    [fromSelect, toSelect].forEach((select) => {
      select.replaceChildren();
      options.forEach(({ value, label }) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        select.append(option);
      });
    });
    if (options.length > 1) toSelect.selectedIndex = 1;
    document.querySelector("#conversion-result strong").textContent = "—";
    document.querySelector("#conversion-result .result-unit").textContent = "";
    errorBox.textContent = "";
  }

  async function run() {
    errorBox.textContent = "";
    try {
      const result = await convert(valueInput.value, fromSelect.value, toSelect.value);
      document.querySelector("#conversion-result strong").textContent = result.formatted;
      const label = toSelect.options[toSelect.selectedIndex].text;
      document.querySelector("#conversion-result .result-unit").textContent = label;
    } catch (exception) {
      errorBox.textContent = exception.message;
    }
  }

  function open() {
    modal.hidden = false;
    valueInput.focus();
    valueInput.select();
  }
  function close() {
    modal.hidden = true;
  }

  document.querySelector("#open-converter").addEventListener("click", open);
  document.querySelector("#close-converter").addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  categorySelect.addEventListener("change", fillUnits);
  document.querySelector("#convert-button").addEventListener("click", run);
  valueInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") run();
  });
  document.querySelector("#swap-units").addEventListener("click", () => {
    const from = fromSelect.selectedIndex;
    fromSelect.selectedIndex = toSelect.selectedIndex;
    toSelect.selectedIndex = from;
    run();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) close();
  });

  fillUnits();
  return { open, close };
}