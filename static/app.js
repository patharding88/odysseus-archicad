const state = {
  view: "library",
  libraries: [],
  jobs: [],
  guides: [],
  guideFolder: "",
  part: null,
  file: "",
  original: "",
  dirty: false,
  showHidden: true,
};

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}

function setStatus(message, kind) {
  const node = $("save-state");
  node.textContent = message || "";
  node.className = "status" + (kind ? ` is-${kind}` : "");
}

async function boot() {
  const [libraries, jobs, guides] = await Promise.all([
    api("/api/libraries"),
    api("/api/jobs"),
    api("/api/guides"),
  ]);
  state.libraries = libraries.libraries;
  state.jobs = jobs.jobs;
  state.guides = guides.guides;
  state.guideFolder = guides.folder;
  renderSide();
  const first = state.libraries.find((lib) => lib.parts.length);
  if (first) await openPart(first.id, first.parts[0].id);
}

function renderSide() {
  const list = $("side-list");
  list.innerHTML = "";
  if (state.view === "library") {
    $("side-title").textContent = "Library";
    $("import-toggle").hidden = false;
    for (const lib of state.libraries) {
      const heading = document.createElement("div");
      heading.className = "lib-name";
      heading.textContent = lib.name;
      list.appendChild(heading);
      for (const part of lib.parts) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "part-btn" + (state.part && state.part.library === lib.id && state.part.id === part.id ? " is-active" : "");
        button.innerHTML = `${escapeHtml(part.name)}<small>${escapeHtml(part.author || part.guid)}</small>`;
        button.addEventListener("click", () => openPart(lib.id, part.id));
        list.appendChild(button);
      }
    }
    if (!state.libraries.length) {
      list.innerHTML = "<p class='status'>Nothing unpacked yet. Import a GSM or a library folder.</p>";
    }
    return;
  }
  $("import-toggle").hidden = true;
  $("import-form").hidden = true;
  if (state.view === "jobs") {
    $("side-title").textContent = "Jobs";
    for (const job of state.jobs) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "job-btn";
      button.innerHTML = `${escapeHtml(job.title)}<small>${escapeHtml(job.part)}</small>`;
      button.addEventListener("click", () => openPart(job.library, job.part, job.script));
      list.appendChild(button);
    }
    return;
  }
  $("side-title").textContent = "Guides";
  const note = document.createElement("p");
  note.className = "status";
  note.textContent = state.guides.length
    ? "The scripting notes stay in their own folder. This list is only the index."
    : "The guide folder was not found on this machine.";
  list.appendChild(note);
  for (const guide of state.guides) {
    const row = document.createElement("div");
    row.className = "guide-row";
    row.innerHTML = `${escapeHtml(guide.name.replace(".pdf", ""))}<small>${escapeHtml(guide.path)}</small>`;
    list.appendChild(row);
  }
}

async function openPart(libId, partId, scriptFile) {
  if (state.dirty && !confirm("This script has unsaved edits. Leave them?")) return;
  state.part = await api(`/api/libraries/${encodeURIComponent(libId)}/parts/${encodeURIComponent(partId)}`);
  state.view = "library";
  document.querySelectorAll(".rail-btn").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === "library");
  });
  renderSide();
  renderPart(scriptFile);
}

function renderPart(scriptFile) {
  const part = state.part;
  $("eyebrow").textContent = libraryName(part.library);
  $("object-title").textContent = part.name;
  $("export-btn").disabled = false;
  const job = state.jobs.find((item) => item.library === part.library && item.part === part.id);
  const banner = $("job-banner");
  if (job) {
    banner.hidden = false;
    banner.textContent = job.summary;
  } else {
    banner.hidden = true;
  }
  renderScripts(scriptFile);
  renderDetails();
  renderParameters();
  renderFiles();
  showPanel("details");
}

function renderScripts(preferred) {
  const tabs = $("script-tabs");
  tabs.innerHTML = "";
  const scripts = state.part.scripts;
  const chosen = scripts.find((script) => script.file.endsWith(preferred || "")) || scripts.find((script) => script.exists) || scripts[0];
  for (const script of scripts) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab" + (script === chosen ? " is-active" : "") + (script.exists ? "" : " is-empty");
    button.textContent = script.label;
    button.addEventListener("click", () => loadFile(script.file, button));
    tabs.appendChild(button);
  }
  if (chosen) loadFile(chosen.file, tabs.querySelector(".is-active"));
}

async function loadFile(file, tab) {
  if (state.dirty && file !== state.file && !confirm("This script has unsaved edits. Leave them?")) return;
  if (tab) {
    tab.parentElement.querySelectorAll(".tab").forEach((button) => button.classList.remove("is-active"));
    tab.classList.add("is-active");
  }
  try {
    const data = await api(`/api/libraries/${state.part.library}/parts/${state.part.id}/text?file=${encodeURIComponent(file)}`);
    setEditor(file, data.text);
  } catch (error) {
    setEditor(file, "");
    setStatus(error.message, "bad");
  }
}

function setEditor(file, text) {
  state.file = file;
  state.original = text;
  state.dirty = false;
  $("code").value = text;
  $("save-btn").disabled = true;
  setStatus(file);
  paintGutter();
}

function paintGutter() {
  const lines = $("code").value.split("\n").length || 1;
  $("gutter").textContent = Array.from({ length: lines }, (_, index) => index + 1).join("\n");
}

function renderDetails() {
  const part = state.part;
  const preview = part.preview
    ? `<img class="preview" alt="" src="/api/libraries/${part.library}/parts/${part.id}/preview">`
    : "";
  $("panel-details").innerHTML = `
    ${preview}
    <dl class="meta">
      <dt>Placeable</dt><dd>${part.placeable ? "Yes" : "No"}</dd>
      <dt>Author</dt><dd>${escapeHtml(part.author || "Not recorded")}</dd>
      <dt>Licence</dt><dd>${escapeHtml(part.license || "Not recorded")}</dd>
      <dt>GUID</dt><dd>${escapeHtml(part.guid)}</dd>
      <dt>Subtype chain</dt><dd>${part.ancestry.length} ancestor GUID${part.ancestry.length === 1 ? "" : "s"}</dd>
    </dl>
    <p class="comment">${escapeHtml(part.comment || "No comment in the library part.")}</p>
  `;
}

function renderParameters() {
  const rows = state.part.parameters.filter((row) => state.showHidden || !row.hidden);
  const body = rows.map((row) => {
    const metres = row.type === "Length" || row.type === "Angle" ? Number(row.value) : NaN;
    const extra = row.type === "Length" && Number.isFinite(metres) ? ` <small>(${Math.round(metres * 1000)} mm)</small>` : "";
    return `<tr class="${row.hidden ? "is-hidden" : ""} ${row.bold ? "is-bold" : ""}">
      <td>${escapeHtml(row.name)}</td>
      <td>${escapeHtml(row.type)}</td>
      <td>${escapeHtml(row.value)}${extra}</td>
      <td>${escapeHtml(row.description)}</td>
    </tr>`;
  }).join("");
  $("panel-parameters").innerHTML = `
    <label class="filter"><input id="show-hidden" type="checkbox" ${state.showHidden ? "checked" : ""}> Show hidden parameters</label>
    <p class="status">Lengths are stored in metres. The value lists that ArchiCAD shows live in the parameter script, not in this table.</p>
    <table>
      <thead><tr><th>Name</th><th>Type</th><th>Value</th><th>Description</th></tr></thead>
      <tbody>${body}</tbody>
    </table>
  `;
  $("show-hidden").addEventListener("change", (event) => {
    state.showHidden = event.target.checked;
    renderParameters();
  });
}

function renderFiles() {
  const files = state.part.files.filter((file) => file.file.toLowerCase().endsWith(".txt"));
  if (!files.length) {
    $("panel-files").innerHTML = "<p class='status'>This object has no library text files beside it. The downpipe is a single GSM. The tank capacity tables show up here.</p>";
    return;
  }
  $("panel-files").innerHTML = files.map((file) =>
    `<button class="file-btn" type="button" data-file="${escapeHtml(file.file)}">${escapeHtml(file.file.replace(/^files\//, ""))}</button>`
  ).join("");
  $("panel-files").querySelectorAll(".file-btn").forEach((button) => {
    button.addEventListener("click", () => {
      $("script-tabs").querySelectorAll(".tab").forEach((tab) => tab.classList.remove("is-active"));
      loadFile(button.dataset.file);
    });
  });
}

function libraryName(id) {
  return state.libraries.find((lib) => lib.id === id)?.name || id;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

$("code").addEventListener("input", () => {
  state.dirty = $("code").value !== state.original;
  $("save-btn").disabled = !state.dirty;
  setStatus(state.dirty ? "Unsaved" : state.file);
  paintGutter();
});
$("code").addEventListener("scroll", () => {
  $("gutter").scrollTop = $("code").scrollTop;
});
$("code").addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const el = event.target;
    const start = el.selectionStart;
    el.value = el.value.slice(0, start) + "\t" + el.value.slice(el.selectionEnd);
    el.selectionStart = el.selectionEnd = start + 1;
    el.dispatchEvent(new Event("input"));
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    $("save-btn").click();
  }
});

$("save-btn").addEventListener("click", async () => {
  if (!state.part || !state.file) return;
  try {
    await api(`/api/libraries/${state.part.library}/parts/${state.part.id}/text`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: state.file, text: $("code").value }),
    });
    state.original = $("code").value;
    state.dirty = false;
    $("save-btn").disabled = true;
    setStatus("Saved", "ok");
  } catch (error) {
    setStatus(error.message, "bad");
  }
});

$("export-btn").addEventListener("click", async () => {
  if (!state.part) return;
  if (state.dirty) {
    setStatus("Save the script before exporting.", "bad");
    return;
  }
  try {
    const result = await api(`/api/libraries/${state.part.library}/parts/${state.part.id}/export`, { method: "POST" });
    setStatus(`Wrote ${result.gsm}`, "ok");
  } catch (error) {
    setStatus(error.message, "bad");
  }
});

$("import-toggle").addEventListener("click", () => {
  $("import-form").hidden = !$("import-form").hidden;
});
$("import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = $("import-status");
  status.textContent = "Unpacking…";
  status.className = "status";
  try {
    const library = await api("/api/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path: $("import-path").value.trim(),
        name: $("import-name").value.trim() || null,
      }),
    });
    const listed = await api("/api/libraries");
    state.libraries = listed.libraries;
    status.textContent = `Imported ${library.name}.`;
    status.className = "status is-ok";
    if (library.parts[0]) await openPart(library.id, library.parts[0].id);
    else renderSide();
  } catch (error) {
    status.textContent = error.message;
    status.className = "status is-bad";
  }
});

document.querySelectorAll(".rail-btn").forEach((button) => {
  button.addEventListener("click", () => {
    state.view = button.dataset.view;
    document.querySelectorAll(".rail-btn").forEach((item) => item.classList.toggle("is-active", item === button));
    renderSide();
  });
});

function showPanel(name) {
  document.querySelectorAll(".inspect .tab").forEach((item) => item.classList.toggle("is-active", item.dataset.panel === name));
  for (const panel of ["details", "parameters", "files"]) {
    $(`panel-${panel}`).hidden = panel !== name;
  }
}

document.querySelectorAll(".inspect .tab").forEach((button) => {
  button.addEventListener("click", () => showPanel(button.dataset.panel));
});

async function refreshOpenPart() {
  if (!state.part || state.dirty || document.hidden) return;
  try {
    const part = await api(`/api/libraries/${encodeURIComponent(state.part.library)}/parts/${encodeURIComponent(state.part.id)}`);
    const nameChanged = part.name !== state.part.name;
    state.part = part;
    if (nameChanged) {
      $("object-title").textContent = part.name;
      const listed = await api("/api/libraries");
      state.libraries = listed.libraries;
      if (state.view === "library") renderSide();
    }
    if (!state.file) return;
    const data = await api(`/api/libraries/${state.part.library}/parts/${state.part.id}/text?file=${encodeURIComponent(state.file)}`);
    if (!state.dirty && data.text !== state.original) {
      const cursor = $("code").selectionStart;
      setEditor(state.file, data.text);
      $("code").selectionStart = $("code").selectionEnd = Math.min(cursor, data.text.length);
      setStatus("Updated from the library");
    }
  } catch (error) {
    // A missed refresh can wait for the next pass.
  }
}

setInterval(refreshOpenPart, 2000);

boot().catch((error) => setStatus(error.message, "bad"));
