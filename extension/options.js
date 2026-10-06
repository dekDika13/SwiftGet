const api = globalThis.browser ?? globalThis.chrome;
const $ = id => document.getElementById(id);
const D = { port: 6277, token: "", intercept: true, minSizeMB: 0, excluded: "" };
(async () => {
  const c = { ...D, ...(await api.storage.local.get(D)) };
  $("token").value = c.token; $("port").value = c.port; $("intercept").checked = c.intercept;
  $("minSizeMB").value = c.minSizeMB; $("excluded").value = c.excluded;
})();
$("save").onclick = async () => {
  await api.storage.local.set({ token: $("token").value.trim(), port: +$("port").value || 6277, intercept: $("intercept").checked,
    minSizeMB: +$("minSizeMB").value || 0, excluded: $("excluded").value });
  $("msg").textContent = "Tersimpan ✓";
};
$("test").onclick = async () => {
  await $("save").onclick();
  const r = await api.runtime.sendMessage({ type: "ping" });
  $("msg").textContent = !r.ok ? "Aplikasi SwiftGet tidak terjangkau (apakah sedang berjalan?)"
    : r.data?.auth ? "Terhubung ✓" : "Aplikasi aktif, tetapi token salah.";
};
