/* tema día/noche y navegación «En esta página» — copia idéntica en todos los sitios del portafolio.
   Sin elección guardada manda la preferencia del sistema (prefers-color-scheme). El botón #theme-toggle
   guarda una elección explícita ("light" | "dark") en localStorage con la clave "<sitio>:theme", donde
   <sitio> sale de data-sitio en la etiqueta <script>. Se carga en <head> sin defer para pintar el tema
   antes del primer render. Cada cambio emite "tema:cambio" y "<sitio>:themechange" en window.
   data-tema-efectivo en <html> dice qué tema se ve (para el ícono sol/luna). Si el botón trae íconos
   (svg), no se le cambia el texto; si no, dice «día» o «noche» como antes.
   Si existe nav.en-pagina, marca con aria-current="location" el enlace de la sección visible. */
(function () {
  var root = document.documentElement;
  var script = document.currentScript;
  var sitio = (script && script.dataset.sitio) || "portafolio";
  var clave = sitio + ":theme";
  var sistema = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  var guardado = function () {
    try {
      var v = JSON.parse(localStorage.getItem(clave) || "null");
      return v === "dark" || v === "light" ? v : null;
    } catch (e) { return null; }
  };
  var efectivo = function () {
    return guardado() || (sistema && sistema.matches ? "dark" : "light");
  };
  var estampar = function () {
    var g = guardado();
    if (g) root.dataset.theme = g; else root.removeAttribute("data-theme");
    root.dataset.temaEfectivo = efectivo();
  };
  var avisar = function () {
    var detalle = { detail: efectivo() };
    window.dispatchEvent(new CustomEvent("tema:cambio", detalle));
    window.dispatchEvent(new CustomEvent(sitio + ":themechange", detalle));
  };

  estampar();

  var marcarSeccion = function () {
    var nav = document.querySelector(".en-pagina");
    if (!nav || !("IntersectionObserver" in window)) return;
    var enlaces = {};
    nav.querySelectorAll('a[href^="#"]').forEach(function (a) { enlaces[a.getAttribute("href").slice(1)] = a; });
    var visibles = {};
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (e) { visibles[e.target.id] = e.isIntersecting; });
      var actual = Object.keys(enlaces).filter(function (id) { return visibles[id]; })[0];
      if (!actual) return;
      Object.keys(enlaces).forEach(function (id) {
        if (id === actual) enlaces[id].setAttribute("aria-current", "location");
        else enlaces[id].removeAttribute("aria-current");
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(enlaces).forEach(function (id) {
      var s = document.getElementById(id);
      if (s) observador.observe(s);
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    var conIconos = btn && btn.querySelector("svg");
    var pintar = function () {
      estampar();
      if (!btn) return;
      var oscuro = efectivo() === "dark";
      if (!conIconos) btn.textContent = oscuro ? "día" : "noche";
      btn.setAttribute("aria-label", oscuro ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
      btn.setAttribute("aria-pressed", String(oscuro));
    };
    pintar();
    if (btn) btn.addEventListener("click", function () {
      var siguiente = efectivo() === "dark" ? "light" : "dark";
      try { localStorage.setItem(clave, JSON.stringify(siguiente)); } catch (e) {}
      root.dataset.theme = siguiente;
      pintar();
      avisar();
    });
    if (sistema) {
      var alCambiar = function () { if (!guardado()) { pintar(); avisar(); } };
      if (sistema.addEventListener) sistema.addEventListener("change", alCambiar);
      else if (sistema.addListener) sistema.addListener(alCambiar);
    }
    marcarSeccion();
    // En pantallas angostas la lista de sitios se desplaza de lado: deja visible el sitio actual.
    var sitios = document.querySelector(".sitios");
    var actual = sitios && sitios.querySelector('[aria-current="page"]');
    if (actual && sitios.scrollWidth > sitios.clientWidth) {
      sitios.scrollLeft = actual.offsetLeft - sitios.offsetLeft - (sitios.clientWidth - actual.offsetWidth) / 2;
    }
  });
})();
