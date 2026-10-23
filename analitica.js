/* analítica — copia idéntica en cada sitio del portafolio (centinela, consulta, cartilla, conciliador, acervo,
   cuadratura, fiabilidad); editar todas a la vez.
   Cuenta visitas con GoatCounter (sin cookies ni datos personales) en una sola cuenta para todos los
   sitios: cada ruta lleva el prefijo del sitio (data-sitio en la etiqueta <script>), así que
   /centinela/ficha.html?r=workforce se registra como "centinela/ficha/workforce".
   Eventos automáticos, sin tocar el HTML:
     - salida/github/<repo>    clic a github.com (botones de las tarjetas del portafolio)
     - salida/sitio/<sitio>    clic a otro sitio del portafolio (mismo dominio, otra carpeta)
     - salida/linkedin         clic al perfil de LinkedIn
     - pantalla-completa/<id>  clic a app.powerbi.com (abrir el reporte completo)
     - descarga/<archivo>      clic en un enlace con atributo download
     - contacto/email          clic en un enlace mailto:; contacto/copia si se copia un texto con @
   Lectura, una vez por visita a la página (<pagina> es index, ficha/workforce, etc.):
     - lectura/15s/<pagina>, lectura/60s/<pagina>  segundos con la pestaña visible
     - scroll/50/<pagina>, scroll/90/<pagina>      avance del scroll (solo si la persona desplaza)
   Visitantes, una vez por navegador y día en todo el portafolio (los sitios comparten dominio):
     - visitante/nuevo   primera visita de este navegador
     - visitante/vuelve  ya había venido otro día
   Para eso el navegador guarda solo la fecha de su última visita (localStorage "portafolio-ultima-visita"):
   sin identificador y sin enviarla a ningún lado.
   Eventos propios de cada página: window.analitica.evento("nombre"). Se encolan hasta que carga
   count.js. Elementos con data-evento="nombre" se cuentan al hacer clic.
   Para atribuir el canal, los enlaces al portafolio llevan ?ref=<canal> (cv, carta, linkedin-perfil,
   linkedin-post-AAAAMMDD, workana, github-readme): GoatCounter lo registra como fuente.
   GoatCounter no cuenta visitas desde localhost; para probar en local, abrir la página con
   ?analitica=local. */
(function () {
  var CODIGO = "h-e-sanchez";
  var PARAMETROS_ID = ["r", "m", "slug"]; // ficha.html?r=<reporte>, modulo.html?m=<módulo>
  var ID_VALIDO = /^[a-z0-9-]{2,60}$/; // los slugs reales; lo demás (bots, enlaces rotos) queda como "invalido"

  var script = document.currentScript;
  var sitio = (script && script.dataset.sitio) || "portafolio";
  var params = new URLSearchParams(location.search);
  var local = params.get("analitica") === "local";

  // Identificador de la página: archivo sin .html (index si es la raíz) + id del recurso si lo hay.
  var pagina = function () {
    var archivo = location.pathname.split("/").pop().replace(/\.html$/, "") || "index";
    for (var i = 0; i < PARAMETROS_ID.length; i++) {
      var v = params.get(PARAMETROS_ID[i]);
      if (v) return archivo + "/" + (ID_VALIDO.test(v) ? v : "invalido");
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
  // Un evento por visita a la página, aunque la acción se repita (p. ej. cada consulta SQL).
  var hechos = {};
  var unaVez = function (nombre) { if (!hechos[nombre]) { hechos[nombre] = true; enviar(nombre); } };

  // Visitante nuevo o que vuelve. Si el almacenamiento está bloqueado (modo privado, permisos), no se cuenta.
  try {
    var hoy = new Date().toLocaleDateString("sv"); // AAAA-MM-DD en hora local
    var ultima = localStorage.getItem("portafolio-ultima-visita");
    if (ultima !== hoy) {
      enviar(ultima ? "visitante/vuelve" : "visitante/nuevo");
      localStorage.setItem("portafolio-ultima-visita", hoy);
    }
  } catch (e) { /* sin almacenamiento: se omite */ }

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
    if (url.protocol === "mailto:") return unaVez("contacto/email");
    if (a.hasAttribute("download")) return enviar("descarga/" + url.pathname.split("/").pop());
    if (url.hostname === "github.com") {
      var repo = url.pathname.split("/").filter(Boolean)[1] || "perfil";
      return enviar("salida/github/" + repo);
    }
    if (/(^|\.)linkedin\.com$/.test(url.hostname)) return enviar("salida/linkedin");
    if (url.hostname === "app.powerbi.com") return enviar("pantalla-completa/" + id.split("/").pop());
    if (url.hostname === location.hostname) {
      // Cada sitio vive en su carpeta del mismo dominio (<usuario>.github.io/<sitio>/).
      var destino = url.pathname.split("/").filter(Boolean)[0];
      if (destino && destino !== sitio && !/\./.test(destino)) enviar("salida/sitio/" + destino);
    }
  };
  document.addEventListener("click", alClic, true);
  document.addEventListener("copy", function () {
    if (String(window.getSelection()).indexOf("@") >= 0) unaVez("contacto/copia");
  });

  // Tiempo de lectura: solo suma los segundos con la pestaña visible.
  var segundos = 0;
  var reloj = setInterval(function () {
    if (document.visibilityState !== "visible") return;
    segundos++;
    if (segundos === 15) unaVez("lectura/15s/" + id);
    if (segundos === 60) { unaVez("lectura/60s/" + id); clearInterval(reloj); }
  }, 1000);

  // Avance del scroll: cuenta solo cuando la persona desplaza la página, no al cargar una página corta.
  var alDesplazar = function () {
    var alto = document.documentElement.scrollHeight - window.innerHeight;
    if (alto <= 0) return;
    var avance = window.scrollY / alto;
    if (avance >= 0.5) unaVez("scroll/50/" + id);
    if (avance >= 0.9) { unaVez("scroll/90/" + id); window.removeEventListener("scroll", alDesplazar); }
  };
  window.addEventListener("scroll", alDesplazar, { passive: true });

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

  window.analitica = {
    sitio: sitio,
    pagina: id,
    evento: enviar,
    alVer: alVer,
    unaVez: unaVez,
  };
})();
