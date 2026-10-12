"use strict";

const URL_API = "/api/v1";
const REFRESCO_MS = 3000;
const UMBRAL_FRESCURA_S = 10;

const tablero = document.getElementById("tablero");
const aviso = document.getElementById("aviso");
const resumenLibres = document.getElementById("resumen-libres");
const resumenOcupados = document.getElementById("resumen-ocupados");
const resumenTotal = document.getElementById("resumen-total");
const horaSimulada = document.getElementById("hora-simulada");
const frescura = document.getElementById("frescura");

function formatearHora(iso) {
  if (!iso) {
    return "—";
  }
  return iso.slice(11, 16);
}

function formatearDuracion(segundos) {
  if (segundos === null || segundos === undefined) {
    return "—";
  }
  const horas = Math.floor(segundos / 3600);
  const minutos = Math.floor((segundos % 3600) / 60);
  if (horas > 0) {
    return horas + " h " + minutos + " min"; // 8 h 30 min
  }
  return minutos + " min"; // 30 min
}

function mostrarAviso(texto, clase) {
  aviso.textContent = texto;
  aviso.className = "aviso aviso--" + clase;
}

function ocultarAviso() {
  aviso.className = "aviso aviso--oculto";
}

function marcarDesactualizado(si) {
  document.body.classList.toggle("desactualizado", si);
}

function crearTarjeta(lugar) {
  const tarjeta = document.createElement("article");
  tarjeta.className = lugar.ocupado ? "lugar lugar--ocupado" : "lugar lugar--libre";

  const nombre = document.createElement("h2");
  nombre.className = "lugar__nombre";
  nombre.textContent = lugar.espacio;

  const estado = document.createElement("p");
  estado.className = "lugar__estado";
  estado.textContent = lugar.ocupado ? "Ocupado" : "Libre";

  const detalle = document.createElement("p");
  detalle.className = "lugar__detalle";
  detalle.textContent = "desde " + formatearHora(lugar.desde) +
                        " · hace " + formatearDuracion(lugar.duracion_s);

  tarjeta.append(nombre, estado, detalle);

  if (lugar.ocupado && lugar.confianza !== null && lugar.confianza !== undefined) {
    const confianza = document.createElement("p");
    confianza.className = "lugar__confianza";
    confianza.textContent = "confianza " + Math.round(lugar.confianza * 100) + " %";
    tarjeta.append(confianza);
  }

  return tarjeta;
}

function pintar(estado) {
  tablero.replaceChildren(...estado.lugares.map(crearTarjeta));

  resumenLibres.textContent = estado.resumen.libres;
  resumenOcupados.textContent = estado.resumen.ocupados;
  resumenTotal.textContent = estado.resumen.total;

  horaSimulada.textContent = "hora del predio " + formatearHora(estado.instante);
  frescura.textContent = "actualizado hace " + estado.actualizado_hace_s.toFixed(1) + " s";
}

async function consultar() {
  try {
    const respuesta = await fetch(URL_API + "/estado");

    if (respuesta.status === 503) {
      const cuerpo = await respuesta.json();
      marcarDesactualizado(true);
      mostrarAviso(cuerpo.detalle || "El servidor todavía no recibió datos.", "espera");
      return;
    }

    if (!respuesta.ok) {
      throw new Error("El servidor respondió " + respuesta.status);
    }

    const estado = await respuesta.json();
    pintar(estado);

    if (estado.actualizado_hace_s > UMBRAL_FRESCURA_S) {
      marcarDesactualizado(true);
      mostrarAviso("Datos viejos: la última publicación fue hace " +
                   Math.round(estado.actualizado_hace_s) + " s.", "alerta");
    } else {
      marcarDesactualizado(false);
      ocultarAviso();
    }

  } catch (error) {
    marcarDesactualizado(true);
    mostrarAviso("Sin conexión con el servidor. Reintentando…", "alerta");
    console.error(error);
  }
}

consultar();
setInterval(consultar, REFRESCO_MS);