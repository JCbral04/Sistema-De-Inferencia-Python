// Casilla «Mostrar contraseña»: alterna el tipo de los campos de contraseña del mismo formulario.
document.querySelectorAll("input.ver-clave").forEach(function (casilla) {
  casilla.addEventListener("change", function () {
    casilla.form.querySelectorAll("input[data-clave]").forEach(function (campo) {
      campo.type = casilla.checked ? "text" : "password";
    });
  });
});
