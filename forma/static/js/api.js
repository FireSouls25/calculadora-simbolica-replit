/**
 * Cliente de la API.
 */

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    throw new Error("No hay conexión con el servidor.");
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    throw new Error("La respuesta del servidor no se pudo leer.");
  }
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || "No se pudo completar la operación.");
  }
  return payload;
}

export function calculate(expression) {
  return request("/api/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression }),
  });
}

export function convert(value, from, to) {
  return request("/api/convert", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value, from, to }),
  });
}

export function fetchPalette() {
  return request("/api/palette");
}