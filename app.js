/* acervo — pinta lo que publica `python -m src.construir` (sitio/*.json, sitio/erd.svg) y consulta la API
   de mindicador.cl desde el navegador, con la muestra guardada como respaldo. */
(function () {
  "use strict";

  var API = "https://mindicador.cl/api/";
  var $ = function (id) { return document.getElementById(id); };
  var pesos = function (n) { return "$" + Math.round(n).toLocaleString("es-CL"); };
  var num = function (n) { return Number(n).toLocaleString("es-CL"); };
  var pct = function (x) { return (x * 100).toLocaleString("es-CL", { maximumFractionDigits: 1 }) + "%"; };
  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function kpi(valor, rotulo, clase) {
    return '<div class="kpi ' + (clase || "") + '"><span class="valor">' + valor + '</span><span class="rotulo">' + rotulo + "</span></div>";
  }
  function tabla(id, cabeza, filas) {
    $(id).innerHTML = "<thead><tr>" + cabeza.map(function (c) {
      return "<th" + (c.num ? ' class="num"' : "") + ">" + esc(c.t) + "</th>";
    }).join("") + "</tr></thead><tbody>" + filas.join("") + "</tbody>";
  }
  var td = function (v, n) { return "<td" + (n ? ' class="num"' : "") + ">" + v + "</td>"; };
  var json = function (url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(url); return r.json(); }); };

  function pintarDatos(d) {
    $("corte").textContent = d.corte.split("-").reverse().join("-");
    var leidas = d.fuentes.reduce(function (s, f) { return s + f.leidas; }, 0);
    var cuarentena = d.fuentes.reduce(function (s, f) { return s + f.cuarentena; }, 0);
    $("kpis-flujo").innerHTML =
      kpi(d.fuentes.length, "fuentes integradas") +
      kpi(num(leidas), "filas leídas") +
      kpi(num(cuarentena), "filas en cuarentena", cuarentena ? "alerta" : "ok") +
      kpi(num(d.tablas.participante), "participantes cargados") +
      kpi(d.catalogo.problemas.length, "problemas de catálogo", d.catalogo.problemas.length ? "alerta" : "ok");

    tabla("tabla-costo", [{ t: "Programa" }, { t: "Mes" }, { t: "Gasto", num: 1 }, { t: "Participantes", num: 1 }, { t: "Costo por participante", num: 1 }],
      d.vistas.v_costo_por_participante.map(function (v) {
        return "<tr>" + td(esc(v.programa)) + td(v.mes) + td(pesos(v.gasto), 1) + td(v.participantes, 1) + td(pesos(v.costo_por_participante), 1) + "</tr>";
      }));
    tabla("tabla-fuentes", [{ t: "Fuente" }, { t: "Leídas", num: 1 }, { t: "Cuarentena", num: 1 }],
      d.fuentes.map(function (f) { return "<tr>" + td(esc(f.fuente)) + td(num(f.leidas), 1) + td(f.cuarentena, 1) + "</tr>"; }));
    tabla("tabla-cuarentena", [{ t: "Fuente" }, { t: "Motivo" }, { t: "Filas", num: 1 }],
      d.cuarentena.map(function (c) { return "<tr>" + td(esc(c.fuente)) + td(esc(c.motivo)) + td(c.filas, 1) + "</tr>"; }));
    tabla("tabla-calidad", [{ t: "Regla" }, { t: "Qué revisa" }, { t: "Casos", num: 1 }],
      d.calidad.map(function (r) { return "<tr>" + td("<code>" + r.id + "</code> " + esc(r.nombre)) + td(esc(r.descripcion)) + td(r.casos, 1) + "</tr>"; }));
    $("estudio").innerHTML = "La extracción para estadística e investigación entrega " + d.estudio.filas +
      " filas, solo de participantes activos con ese consentimiento vigente, con las columnas <code>" +
      d.estudio.columnas.join("</code>, <code>") + "</code>. El seudónimo es un HMAC-SHA256 con una clave que no está en el repositorio.";
    $("kpis-catalogo").innerHTML = kpi(d.catalogo.datasets, "datasets documentados") + kpi(d.catalogo.columnas, "columnas con descripción y nivel") +
      kpi(d.catalogo.problemas.length, "diferencias entre catálogo y esquema", d.catalogo.problemas.length ? "alerta" : "ok");
  }

  function pintarCatalogo(c) {
    var ds = c.acceso.datasets;
    tabla("tabla-acceso", [{ t: "Rol" }].concat(ds.map(function (d) { return { t: d.nombre }; })),
      c.acceso.roles.map(function (r) {
        return "<tr>" + td("<strong>" + esc(r.rol) + "</strong>") + ds.map(function (d) {
          return r.lee.indexOf(d.nombre) >= 0 ? '<td class="si" title="' + esc(d.nivel) + '">✓</td>' : '<td class="no">·</td>';
        }).join("") + "</tr>";
      }));
    Array.prototype.forEach.call(document.querySelectorAll("#tabla-acceso thead th"), function (th, i) {
      if (i) { th.className = "dataset"; th.title = ds[i - 1].capa + " · " + ds[i - 1].nivel; }
    });
    tabla("tabla-registro", [{ t: "Tratamiento" }, { t: "Finalidad" }, { t: "Base de licitud" }, { t: "Titulares" }, { t: "Categorías" }, { t: "Sistemas de origen" }],
      c.registro.map(function (r) {
        return "<tr>" + td("<code>" + r.id + "</code> " + esc(r.nombre)) + td(esc(r.finalidad)) + td(esc(r.base_licitud)) + td(esc(r.titulares)) +
          td(r.categorias.map(function (n) { return '<span class="nivel ' + n + '">' + n + "</span>"; }).join(" ")) + td(esc(r.sistemas.join(", "))) + "</tr>";
      }));
  }

  function indicador(codigo) {
    return fetch(API + codigo, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  var CODIGOS = ["uf", "utm", "dolar"];

  /* Primero la muestra guardada (aparece al instante); después, si la API responde, los valores en vivo. */
  async function pintarApi() {
    var muestra = await json("sitio/indicadores_muestra.json");
    pintarIndicadores(CODIGOS.map(function (c) { return muestra[c]; }), false);
    $("estado-api").textContent = "Mostrando la última muestra guardada mientras responde la API…";
    var limite = new Promise(function (_, no) { setTimeout(function () { no(new Error("tiempo agotado")); }, 45000); });
    try {
      pintarIndicadores(await Promise.race([Promise.all(CODIGOS.map(indicador)), limite]), true);
    } catch (e) {
      $("estado-api").textContent = "La API no respondió (" + e.message + "): se muestra la última muestra guardada (sitio/indicadores_muestra.json).";
    }
  }

  function pintarIndicadores(datos, vivo) {
    var codigos = CODIGOS;
    var v = {};
    datos.forEach(function (d) { v[d.codigo] = { valor: d.serie[0].valor, fecha: d.serie[0].fecha.slice(0, 10), nombre: d.nombre }; });
    $("kpis-api").innerHTML = codigos.map(function (c) {
      return kpi(pesos(v[c].valor), esc(v[c].nombre) + " · " + v[c].fecha.split("-").reverse().join("-") + " · <code>/api/" + c + "</code>");
    }).join("");
    $("estado-api").className = "estado-api " + (vivo ? "vivo" : "muestra");
    if (vivo) $("estado-api").textContent = "Valores en vivo desde la API.";
    var utm = v.utm.valor;
    $("multas").innerHTML = "Leves hasta 5.000 UTM (" + pesos(5000 * utm) + "), graves hasta 10.000 UTM (" + pesos(10000 * utm) +
      ") y gravísimas hasta 20.000 UTM (" + pesos(20000 * utm) + "), con la UTM de " + v.utm.fecha.slice(5, 7) + "-" + v.utm.fecha.slice(0, 4) +
      ". La reincidencia puede triplicar la multa y, en empresas que no son de menor tamaño, llegar a un porcentaje de sus ingresos.";
    var utmDatos = datos[1];
    $("json-api").textContent = JSON.stringify({ version: utmDatos.version, codigo: utmDatos.codigo, nombre: utmDatos.nombre,
      unidad_medida: utmDatos.unidad_medida, serie: utmDatos.serie.slice(0, 3) }, null, 2) + "\n…";
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch("sitio/erd.svg").then(function (r) { return r.text(); }).then(function (svg) {
      $("erd").innerHTML = svg;
      $("erd").removeAttribute("aria-busy");
    });
    json("sitio/datos.json").then(pintarDatos);
    json("sitio/catalogo.json").then(pintarCatalogo);
    pintarApi().catch(function (e) { $("estado-api").textContent = "No se pudo leer la API ni la muestra: " + e.message; });
  });
})();
