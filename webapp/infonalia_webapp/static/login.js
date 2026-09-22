const loginParams = new URLSearchParams(location.search);
const error = loginParams.get("error");
const requestedNext = loginParams.get("next");
const loginNext = document.getElementById("login-next");

if (loginNext && requestedNext) {
  loginNext.value = requestedNext;
}

if (error) {
  const el = document.getElementById("login-error");
  if (error === "maintenance") {
    el.textContent = "La app está en mantenimiento. Solo pueden entrar administradores.";
  }
  el.style.display = "block";
}
