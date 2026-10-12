"use strict";

const URL_API = "/api/v1";
const POR_PAGINA = 25;

const filas = document.getElementById("filas");
const aviso = document.getElementById("aviso");
const filtroEspacio = document.getElementById("filtro-espacio");
const btnRecargar = document.getElementById("btn-recargar");
const btnAnterior = document.getElementById("btn-anterior");
const btnSiguiente = document.getElementById("btn-siguiente");
const rango = document.getElementById("rango");

let desplazamiento = 0;
let total = 0;

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
    return horas + " h " + minutos + " min";
  }
  return minutos + " min";
}

function mostrarAviso(texto, clase) {
  aviso.textContent = texto;
  aviso.className = "aviso aviso--" + clase;
}

function ocultarAviso() {
  aviso.className = "aviso aviso--oculto";
}

function celda(texto, clase) {
  const td = document.createElement("td");
  td.textContent = texto;
  if (clase) {
    td.className = clase;
  }
  return td;
}

function crearFila(transicion) {
  const entro = transicion.estado === "ocupado";
  const tr = document.createElement("tr");

  tr.append(
    celda(formatearHora(transicion.instante), "hora"),
    celda(transicion.espacio, "lugar"),
    celda(entro ? "Entró" : "Salió",
          entro ? "movimiento movimiento--entro" : "movimiento movimiento--salio"),
    celda(formatearDuracion(transicion.duracion_anterior_s), "antes")
  );

  return tr;
}

function filaVacia(texto) {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = 4;
  td.className = "vacio";
  td.textContent = texto;
  tr.append(td);
  return tr;
}

function actualizarPaginador() {
  if (total === 0) {
    rango.textContent = "sin movimientos";
  } else {
    const primera = desplazamiento + 1;
    const ultima = Math.min(desplazamiento + POR_PAGINA, total);
    rango.textContent = primera + "–" + ultima + " de " + total;
  }
  btnAnterior.disabled = desplazamiento === 0;
  btnSiguiente.disabled = desplazamiento + POR_PAGINA >= total;
}

async function cargar() {
  const parametros = new URLSearchParams();
  parametros.set("limite", POR_PAGINA);
  parametros.set("desplazamiento", desplazamiento);
  if (filtroEspacio.value) {
    parametros.set("espacio", filtroEspacio.value);
  }

  try {
    const respuesta = await fetch(URL_API + "/transiciones?" + parametros);

    if (respuesta.status === 503) {
      const cuerpo = await respuesta.json();
      filas.replaceChildren(filaVacia("—"));
      total = 0;
      actualizarPaginador();
      mostrarAviso(cuerpo.detalle || "El servidor todavía no recibió datos.", "espera");
      return;
    }

    if (!respuesta.ok) {
      throw new Error("El servidor respondió " + respuesta.status);
    }

    const datos = await respuesta.json();
    total = datos.total;

    if (datos.transiciones.length === 0) {
      filas.replaceChildren(filaVacia("No hay movimientos para este filtro."));
    } else {
      filas.replaceChildren(...datos.transiciones.map(crearFila));
    }

    actualizarPaginador();
    ocultarAviso();

  } catch (error) {
    mostrarAviso("Sin conexión con el servidor.", "alerta");
    console.error(error);
  }
}

btnRecargar.addEventListener("click", function () {
  desplazamiento = 0;
  cargar();
});

filtroEspacio.addEventListener("change", function () {
  desplazamiento = 0;
  cargar();
});

btnAnterior.addEventListener("click", function () {
  desplazamiento = Math.max(0, desplazamiento - POR_PAGINA);
  cargar();
});

btnSiguiente.addEventListener("click", function () {
  desplazamiento = desplazamiento + POR_PAGINA;
  cargar();
});

cargar();