/* acervo — catálogo navegable: fichas por dataset, búsqueda en nombres, descripciones y columnas, y el detalle
   de cada dataset en la URL (#dataset) para poder enlazarlo. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var cat = null;
  var capa = "";
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  var nivel = function (n) { return '<span class="nivel ' + esc(n) + '">' + esc(n) + "</span>"; };
  var normal = function (t) { return String(t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); };

  function coincide(d, q) {
    if (!q) return true;
    var texto = [d.nombre, d.descripcion, d.dominio, d.fuente.sistema].concat(d.columnas.map(function (c) { return c.nombre + " " + c.descripcion; })).join(" ");
    return normal(texto).indexOf(normal(q)) >= 0;
  }

  function fichas() {
    var q = $("buscar").value.trim();
    var actual = decodeURIComponent(location.hash.slice(1));
    var lista = cat.datasets.filter(function (d) { return (!capa || d.capa === capa) && coincide(d, q); });
    $("fichas").innerHTML = lista.length ? lista.map(function (d) {
      return '<button type="button" class="ficha" data-ds="' + esc(d.nombre) + '" aria-current="' + (d.nombre === actual) + '"><h3>' + esc(d.nombre) +
        "</h3><p>" + esc(d.descripcion) + "</p>" + nivel(d.nivel) + ' <span class="hint">' + esc(d.capa) + " · " + d.columnas.length + " columnas</span></button>";
    }).join("") : '<p class="hint">Nada coincide con la búsqueda.</p>';
  }

  function detalle(nombre) {
    var d = cat.datasets.filter(function (x) { return x.nombre === nombre; })[0];
    if (!d) { $("detalle").hidden = true; return; }
    var trat = cat.registro.filter(function (r) { return d.tratamientos.indexOf(r.id) >= 0; });
    var destino = d.capa === "Analítica" ? "Tableros" : d.tipo === "vista" ? "Procesos que la consultan" : "Vistas y procesos del modelo";
    $("detalle").hidden = false;
    $("detalle").innerHTML = "<h2><code>" + esc(d.nombre) + "</code> " + nivel(d.nivel) + "</h2><p>" + esc(d.descripcion) + "</p>" +
      '<div class="meta-dataset">' +
      [["Tipo y capa", d.tipo + " · " + d.capa], ["Dominio", d.dominio], ["Dueño", d.dueno], ["Custodio", d.custodio],
        ["Sistema de origen", d.fuente.sistema + (d.fuente.archivo !== "—" ? " (" + d.fuente.archivo + ")" : "")],
        ["Frecuencia", d.frecuencia], ["Retención", d.retencion],
        ["Tratamientos", trat.length ? trat.map(function (r) { return r.id + " " + r.nombre; }).join("; ") : "Ninguno (no tiene datos personales)"]]
        .map(function (m) { return "<div><span>" + m[0] + "</span>" + esc(m[1]) + "</div>"; }).join("") + "</div>" +
      '<h3>Linaje</h3><p class="linaje"><span>' + esc(d.fuente.sistema) + '</span><span class="flecha">→</span><span>validación y cuarentena</span>' +
      '<span class="flecha">→</span><span><code>' + esc(d.nombre) + '</code></span><span class="flecha">→</span><span>' + destino + "</span></p>" +
      '<h3>Columnas</h3><div class="table-scroll"><table><thead><tr><th>Columna</th><th>Tipo</th><th>Nulo</th><th>Clave</th><th>Nivel</th><th>Descripción</th></tr></thead><tbody>' +
      d.columnas.map(function (c) {
        return "<tr><td><code>" + esc(c.nombre) + "</code></td><td>" + esc(c.tipo) + "</td><td>" + (c.nulo ? "sí" : "no") + "</td><td>" +
          (c.pk ? "PK" : c.fk ? "FK → <code>" + esc(c.fk) + "</code>" : "") + "</td><td>" + nivel(c.nivel) + "</td><td>" + esc(c.descripcion) + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }

  function render() {
    fichas();
    detalle(decodeURIComponent(location.hash.slice(1)));
  }

  document.addEventListener("DOMContentLoaded", function () {
    fetch("sitio/catalogo.json").then(function (r) { return r.json(); }).then(function (c) {
      cat = c;
      var capas = [];
      c.datasets.forEach(function (d) { if (capas.indexOf(d.capa) < 0) capas.push(d.capa); });
      $("filtro-capa").innerHTML = ['<button type="button" class="chip" aria-pressed="true" data-capa="">Todas</button>'].concat(capas.map(function (k) {
        return '<button type="button" class="chip" aria-pressed="false" data-capa="' + esc(k) + '">' + esc(k) + "</button>";
      })).join("");
      $("tabla-niveles").innerHTML = "<thead><tr><th>Nivel</th><th>Qué incluye</th><th class=\"num\">Columnas</th></tr></thead><tbody>" +
        c.niveles.map(function (n) {
          var cuenta = c.datasets.reduce(function (s, d) { return s + d.columnas.filter(function (x) { return x.nivel === n.nivel; }).length; }, 0);
          return "<tr><td>" + nivel(n.nivel) + "</td><td>" + esc(n.descripcion) + '</td><td class="num">' + cuenta + "</td></tr>";
        }).join("") + "</tbody>";
      $("lista-glosario").innerHTML = c.glosario.map(function (g) { return "<dt>" + esc(g.termino) + "</dt><dd>" + esc(g.definicion) + "</dd>"; }).join("");
      render();
    });
    $("buscar").addEventListener("input", fichas);
    $("filtro-capa").addEventListener("click", function (ev) {
      var b = ev.target.closest(".chip");
      if (!b) return;
      Array.prototype.forEach.call(this.children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      capa = b.dataset.capa;
      fichas();
    });
    $("fichas").addEventListener("click", function (ev) {
      var b = ev.target.closest(".ficha");
      if (!b) return;
      location.hash = encodeURIComponent(b.dataset.ds);
      $("detalle").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    window.addEventListener("hashchange", render);
  });
})();
