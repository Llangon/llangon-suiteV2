const error = new URLSearchParams(location.search).get("error");

if (error) {
  const el = document.getElementById("login-error");
  if (error === "maintenance") {
    el.textContent = "La app está en mantenimiento. Solo pueden entrar administradores.";
  }
  el.style.display = "block";
}
