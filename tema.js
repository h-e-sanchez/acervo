/* tema día/noche — copia idéntica en centinela, consulta, cartilla y conciliador; editar las cuatro a la vez.
   Sin elección guardada manda la preferencia del sistema (prefers-color-scheme). El botón #theme-toggle
   guarda una elección explícita ("light" | "dark") en localStorage con la clave "<sitio>:theme", donde
   <sitio> sale de data-sitio en la etiqueta <script>. Se carga en <head> sin defer para pintar el tema
   antes del primer render. Cada cambio emite "tema:cambio" y "<sitio>:themechange" en window. */
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
  };
  var avisar = function () {
    var detalle = { detail: efectivo() };
    window.dispatchEvent(new CustomEvent("tema:cambio", detalle));
    window.dispatchEvent(new CustomEvent(sitio + ":themechange", detalle));
  };

  estampar();

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("theme-toggle");
    var pintar = function () {
      if (!btn) return;
      var oscuro = efectivo() === "dark";
      btn.textContent = oscuro ? "día" : "noche";
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
  });
})();
