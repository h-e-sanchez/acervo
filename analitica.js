/* analítica — copia idéntica en centinela, consulta, cartilla y conciliador; editar las cuatro a la vez.
   Cuenta visitas con GoatCounter (sin cookies ni datos personales) en una sola cuenta para los cuatro
   sitios: cada ruta lleva el prefijo del sitio (data-sitio en la etiqueta <script>), así que
   /centinela/ficha.html?r=workforce se registra como "centinela/ficha/workforce".
   Eventos automáticos, sin tocar el HTML:
     - salida/github/<repo>    clic a github.com (botones de las tarjetas del portafolio)
     - salida/sitio/<sitio>    clic a otro sitio del portafolio
     - salida/linkedin         clic al perfil de LinkedIn
     - pantalla-completa/<id>  clic a app.powerbi.com (abrir el reporte completo)
     - descarga/<archivo>      clic en un enlace con atributo download
   Eventos propios de cada página: window.analitica.evento("nombre"). Se encolan hasta que carga
   count.js. Elementos con data-evento="nombre" se cuentan al hacer clic.
   GoatCounter no cuenta visitas desde localhost; para probar en local, abrir la página con
   ?analitica=local. */
(function () {
  var CODIGO = "h-e-sanchez";
  var SITIOS = ["centinela", "consulta", "cartilla", "conciliador"];
  var PARAMETROS_ID = ["r", "m", "slug"]; // ficha.html?r=<reporte>, modulo.html?m=<módulo>

  var script = document.currentScript;
  var sitio = (script && script.dataset.sitio) || "portafolio";
  var params = new URLSearchParams(location.search);
  var local = params.get("analitica") === "local";

  // Identificador de la página: archivo sin .html (index si es la raíz) + id del recurso si lo hay.
  var pagina = function () {
    var archivo = location.pathname.split("/").pop().replace(/\.html$/, "") || "index";
    for (var i = 0; i < PARAMETROS_ID.length; i++) {
      var v = params.get(PARAMETROS_ID[i]);
      if (v) return archivo + "/" + v.replace(/[^\w-]/g, "");
    }
    return archivo;
  };
  var id = pagina();
  var limpiar = function (t) { return String(t).replace(/^\/+|\/+$/g, "").replace(/[^\w\-\/.]/g, ""); };

  var cola = [];
  var enviar = function (nombre) {
    var gc = window.goatcounter;
    var ruta = sitio + "/" + limpiar(nombre);
    if (gc && gc.count) gc.count({ path: ruta, title: ruta, event: true });
    else cola.push(nombre);
  };

  window.goatcounter = {
    path: function () { return sitio + "/" + id; },
    allow_local: local,
  };

  var gc = document.createElement("script");
  gc.async = true;
  gc.src = "https://gc.zgo.at/count.js";
  gc.dataset.goatcounter = "https://" + CODIGO + ".goatcounter.com/count";
  gc.onload = function () { cola.splice(0).forEach(enviar); };
  document.head.appendChild(gc);

  var alClic = function (ev) {
    var a = ev.target.closest && ev.target.closest("a, button, [data-evento]");
    if (!a) return;
    if (a.dataset.evento) return enviar(a.dataset.evento);
    if (!a.href) return;
    var url;
    try { url = new URL(a.href, location.href); } catch (e) { return; }
    if (a.hasAttribute("download")) return enviar("descarga/" + url.pathname.split("/").pop());
    if (url.hostname === "github.com") {
      var repo = url.pathname.split("/").filter(Boolean)[1] || "perfil";
      return enviar("salida/github/" + repo);
    }
    if (/(^|\.)linkedin\.com$/.test(url.hostname)) return enviar("salida/linkedin");
    if (url.hostname === "app.powerbi.com") return enviar("pantalla-completa/" + id.split("/").pop());
    if (url.hostname === location.hostname) {
      var destino = url.pathname.split("/").filter(Boolean)[0];
      if (destino && destino !== sitio && SITIOS.indexOf(destino) >= 0) enviar("salida/sitio/" + destino);
    }
  };
  document.addEventListener("click", alClic, true);

  // Cuenta una sola vez cuando el elemento queda visible en al menos la mitad (p. ej. un iframe de Power BI).
  var alVer = function (elemento, nombre) {
    if (!elemento || !("IntersectionObserver" in window)) return;
    var obs = new IntersectionObserver(function (entradas) {
      if (entradas.some(function (e) { return e.isIntersecting; })) {
        obs.disconnect();
        enviar(nombre);
      }
    }, { threshold: 0.5 });
    obs.observe(elemento);
  };

  var hechos = {};
  window.analitica = {
    sitio: sitio,
    pagina: id,
    evento: enviar,
    alVer: alVer,
    // Un evento por visita a la página, aunque la acción se repita (p. ej. cada consulta SQL).
    unaVez: function (nombre) { if (!hechos[nombre]) { hechos[nombre] = true; enviar(nombre); } },
  };
})();
