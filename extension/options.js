const api = globalThis.browser ?? globalThis.chrome;
const $ = id => document.getElementById(id);
const D = { port: 6277, token: "", intercept: true, interceptImages: false, minSizeMB: 0, excluded: "" };
(async () => {
  const c = { ...D, ...(await api.storage.local.get(D)) };
  $("token").value = c.token; $("port").value = c.port; $("intercept").checked = c.intercept; $("interceptImages").checked = c.interceptImages;
  $("minSizeMB").value = c.minSizeMB; $("excluded").value = c.excluded;
})();
$("save").onclick = async () => {
  await api.storage.local.set({ token: $("token").value.trim(), port: +$("port").value || 6277, intercept: $("intercept").checked, interceptImages: $("interceptImages").checked,
    minSizeMB: +$("minSizeMB").value || 0, excluded: $("excluded").value });
  $("msg").textContent = "Tersimpan ✓";
};
$("pair").onclick = async () => {
  $("pmsg").textContent = "Setujui permintaan di jendela SwiftGet…";
  const r = await api.runtime.sendMessage({ type: "pair" });
  $("pmsg").textContent = r?.ok ? "Terhubung ✓" : "Gagal: " + (r?.error || "ditolak");
  if (r?.ok) $("token").value = (await api.storage.local.get({ token: "" })).token;
};
$("test").onclick = async () => {
  await $("save").onclick();
  const r = await api.runtime.sendMessage({ type: "ping" });
  $("msg").textContent = !r.ok ? "Aplikasi SwiftGet tidak terjangkau (apakah sedang berjalan?)"
    : r.data?.auth ? "Terhubung ✓" : "Aplikasi aktif, tetapi token salah.";
};
