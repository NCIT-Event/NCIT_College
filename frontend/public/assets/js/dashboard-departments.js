// Department editor (dashboard view #departments).
// HODs see their own department; Super Admins pick any department and can add new ones.
// Talks to academics-service through /api/v1/academics/.

let ctx; // { api, toast, toastError, esc, icon, drawers, isSuperAdmin }
const $ = (sel, root = document) => root.querySelector(sel);
const initials = (name) => String(name || "?").replace(/^(Er|Dr|Mr|Ms|Mrs|Prof)\.?\s+/i, "").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const st = { list: [], slug: "", dept: null, sheet: null, courseProgramme: 0, courseSemester: 1, courseDirty: false };

/* ---------- field specs ---------- */

const FORMS = {
  overview: {
    title: "Department overview",
    fields: [
      { name: "name", label: "Department name", max: 120, superOnly: true, hint: "Only a Super Admin can rename a department." },
      { name: "tagline", label: "Short introduction", max: 300, hint: "One or two sentences under the department name." },
      { name: "overview", label: "Overview", type: "textarea", rows: 9, max: 6000, hint: "Leave a blank line between paragraphs." },
      { name: "hero_photo", label: "Department photo", type: "photo" },
      { name: "contact_email", label: "Contact email", type: "email", max: 254, half: true },
      { name: "contact_phone", label: "Contact phone", max: 60, half: true },
      { name: "office", label: "Office location", max: 200, hint: "e.g. Block A, first floor" },
    ],
  },
  hod: {
    title: "Message from the Head of Department",
    fields: [
      { name: "hod_name", label: "HOD name", max: 120, half: true },
      { name: "hod_title", label: "Title", max: 160, half: true, hint: "e.g. Head of Department, Computer Engineering" },
      { name: "hod_message", label: "Message", type: "textarea", rows: 8, max: 4000, hint: "Leave a blank line between paragraphs." },
      { name: "hod_photo", label: "HOD photo", type: "photo" },
    ],
  },
};

const ITEMS = {
  programmes: {
    singular: "programme",
    fields: [
      { name: "name", label: "Programme name", max: 160, required: true },
      { name: "level", label: "Level", type: "select", options: [["bachelor", "Bachelor's"], ["master", "Master's"]], half: true },
      { name: "duration_years", label: "Duration (years)", type: "number", min: 1, max: 6, half: true },
      { name: "affiliation", label: "Affiliation", max: 120 },
      { name: "eligibility", label: "Eligibility", type: "textarea", rows: 3, max: 2000 },
      { name: "description", label: "Description", type: "textarea", rows: 5, max: 4000 },
      { name: "syllabus_url", label: "Syllabus link (optional)", max: 300, hint: "A link starting with https://" },
    ],
    defaults: { level: "bachelor", duration_years: 4, affiliation: "Pokhara University" },
    title: (x) => x.name,
    meta: (x) => `${x.level === "master" ? "Master's" : "Bachelor's"} · ${x.duration_years} years · ${x.semesters.reduce((n, s) => n + s.courses.length, 0)} courses entered`,
  },
  faculty: {
    singular: "faculty member",
    fields: [
      { name: "name", label: "Name", max: 120, required: true },
      { name: "designation", label: "Designation", max: 120, half: true, hint: "e.g. Associate Professor" },
      { name: "specialization", label: "Subjects or research", max: 200, half: true },
      { name: "email", label: "Email (optional)", type: "email", max: 254 },
      { name: "photo", label: "Photo", type: "photo" },
    ],
    title: (x) => x.name,
    meta: (x) => [x.designation, x.specialization].filter(Boolean).join(" · "),
    photo: (x) => x.photo,
  },
  labs: {
    singular: "lab",
    fields: [
      { name: "name", label: "Lab name", max: 160, required: true },
      { name: "description", label: "Description", type: "textarea", rows: 4, max: 2000 },
      { name: "photo", label: "Photo", type: "photo" },
    ],
    title: (x) => x.name,
    meta: (x) => (x.description || "").slice(0, 90),
    photo: (x) => x.photo,
  },
  testimonials: {
    singular: "testimonial",
    fields: [
      { name: "student_name", label: "Student name", max: 120, required: true },
      { name: "programme_label", label: "Programme and year", max: 160, hint: "e.g. BE Computer, 7th semester" },
      { name: "quote", label: "Quote", type: "textarea", rows: 5, max: 1200, required: true },
      { name: "photo", label: "Photo (optional)", type: "photo" },
      { name: "approved", label: "Show on the department page", type: "checkbox" },
    ],
    defaults: { approved: true },
    title: (x) => x.student_name,
    meta: (x) => `“${(x.quote || "").slice(0, 80)}${(x.quote || "").length > 80 ? "…" : ""}”`,
    photo: (x) => x.photo,
    badge: (x) => (x.approved ? `<span class="tag tag-leaf">Shown</span>` : `<span class="tag tag-amber">Hidden</span>`),
  },
};

/* ---------- field rendering ---------- */

function fieldHtml(f, value, { disabled = false, prefix = "f" } = {}) {
  const { esc, icon } = ctx;
  const id = `${prefix}-${f.name}`;
  const hint = f.hint ? `<p class="mt-1.5 text-[0.875rem] text-ink-3" id="${id}-hint">${esc(f.hint)}</p>` : "";
  const counter = f.max && (f.type === "textarea" || f.name === "tagline") ? `<span class="text-[0.8125rem] font-normal text-ink-3" data-counter="${f.name}"></span>` : "";
  const label = `<label class="field-label flex items-baseline justify-between gap-3" for="${id}"><span>${esc(f.label)}${f.required ? "" : ""}</span>${counter}</label>`;
  const common = `id="${id}" name="${f.name}" ${f.hint ? `aria-describedby="${id}-hint"` : ""} ${disabled ? "disabled" : ""} ${f.required ? "required" : ""}`;
  const wrap = (inner) => `<div class="${f.half ? "sm:col-span-1" : "sm:col-span-2"}">${inner}</div>`;
  switch (f.type) {
    case "textarea":
      return wrap(`${label}<textarea ${common} rows="${f.rows || 4}" maxlength="${f.max}" class="field min-h-0 py-2.5 leading-relaxed">${esc(value)}</textarea>${hint}`);
    case "select":
      return wrap(`${label}<select ${common} class="field">${f.options.map(([v, l]) => `<option value="${v}" ${String(value) === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>${hint}`);
    case "number":
      return wrap(`${label}<input ${common} type="number" inputmode="numeric" min="${f.min}" max="${f.max}" value="${esc(value)}" class="field">${hint}`);
    case "checkbox":
      return wrap(`<label class="flex cursor-pointer items-center gap-3 font-semibold"><input type="checkbox" name="${f.name}" class="h-5 w-5 accent-brand-700" ${value ? "checked" : ""}>${esc(f.label)}</label>`);
    case "photo":
      return wrap(`<span class="field-label">${esc(f.label)}</span>
        <div class="flex items-center gap-4" data-photo-field="${f.name}">
          <div class="flex h-24 w-20 flex-none items-center justify-center overflow-hidden rounded-sm bg-brand-100 text-brand-700" data-photo-preview>${value ? `<img src="${esc(value)}" alt="" class="h-full w-full object-cover object-top">` : icon("camera", "icon")}</div>
          <div class="flex flex-col items-start gap-2">
            <label class="btn btn-outline btn-sm cursor-pointer focus-within:outline-2 focus-within:outline-brand-600">${icon("download")}<span data-photo-label>${value ? "Replace photo" : "Upload photo"}</span><input type="file" accept="image/jpeg,image/png,image/webp" class="sr-only" data-photo-input></label>
            <button type="button" class="text-[0.875rem] font-semibold text-om-700 hover:underline ${value ? "" : "hidden"}" data-photo-remove>Remove photo</button>
            <span class="text-[0.8125rem] text-ink-3">JPEG, PNG or WebP, up to 8 MB. Resized automatically.</span>
          </div>
          <input type="hidden" name="${f.name}" value="${esc(value)}">
        </div>`);
    default:
      return wrap(`${label}<input ${common} type="${f.type || "text"}" maxlength="${f.max || 200}" value="${esc(value)}" class="field">${hint}`);
  }
}

function readForm(form, fields) {
  const data = {};
  for (const f of fields) {
    const el = form.elements[f.name];
    if (!el || el.disabled) continue;
    data[f.name] = f.type === "checkbox" ? el.checked : f.type === "number" ? Number(el.value) : el.value;
  }
  return data;
}

function wireCounters(form, fields) {
  for (const f of fields) {
    const el = form.elements[f.name];
    const counter = form.querySelector(`[data-counter="${f.name}"]`);
    if (!el || !counter) continue;
    const update = () => {
      counter.textContent = `${el.value.length} / ${f.max}`;
      counter.classList.toggle("text-om-700", el.value.length > f.max * 0.95);
    };
    el.addEventListener("input", update);
    update();
  }
}

function wirePhotos(root) {
  $$("[data-photo-field]", root).forEach((box) => {
    const hidden = box.querySelector('input[type="hidden"]');
    const preview = box.querySelector("[data-photo-preview]");
    const remove = box.querySelector("[data-photo-remove]");
    const label = box.querySelector("[data-photo-label]");
    const set = (url) => {
      hidden.value = url;
      preview.innerHTML = url ? `<img src="${ctx.esc(url)}" alt="" class="h-full w-full object-cover object-top">` : ctx.icon("camera", "icon");
      remove.classList.toggle("hidden", !url);
      label.textContent = url ? "Replace photo" : "Upload photo";
      hidden.dispatchEvent(new Event("input", { bubbles: true }));
    };
    box.querySelector("[data-photo-input]").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      e.target.value = "";
      if (!file) return;
      if (file.size > 8 * 1024 * 1024) return ctx.toastError({ message: "That photo is larger than 8 MB. Use a smaller one." });
      label.textContent = "Uploading…";
      const body = new FormData();
      body.append("file", file);
      try {
        const { url } = await ctx.api(`/academics/departments/${st.slug}/media`, { method: "POST", body });
        set(url);
      } catch (err) {
        label.textContent = hidden.value ? "Replace photo" : "Upload photo";
        ctx.toastError(err);
      }
    });
    remove.addEventListener("click", () => set(""));
  });
}

/* ---------- load & render ---------- */

const deptValue = (d, name) => ({
  contact_email: d.contact.email, contact_phone: d.contact.phone, office: d.contact.office,
  hod_name: d.hod.name, hod_title: d.hod.title, hod_message: d.hod.message, hod_photo: d.hod.photo,
}[name] ?? d[name] ?? "");

function renderForm(key) {
  const spec = FORMS[key];
  const form = $(`[data-dept-form="${key}"]`);
  const superAdmin = ctx.isSuperAdmin();
  form.innerHTML = `
    <div class="grid gap-5 p-5 sm:grid-cols-2 sm:p-6">${spec.fields.map((f) => fieldHtml(f, deptValue(st.dept, f.name), { disabled: f.superOnly && !superAdmin, prefix: `d${key}` })).join("")}</div>
    <div class="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3 sm:px-6">
      <p class="text-[0.9375rem] font-semibold text-om-700" role="alert" data-form-error></p>
      <div class="flex items-center gap-3"><span class="text-[0.9375rem] text-ink-3" data-form-state></span><button type="submit" class="btn btn-primary" disabled data-form-save>Save changes</button></div>
    </div>`;
  const save = form.querySelector("[data-form-save]");
  const state = form.querySelector("[data-form-state]");
  const initial = JSON.stringify(readForm(form, spec.fields));
  form.oninput = () => {
    const dirty = JSON.stringify(readForm(form, spec.fields)) !== initial;
    form.dataset.dirty = String(dirty);
    save.disabled = !dirty;
    state.textContent = dirty ? "Unsaved changes" : "";
  };
  form.onsubmit = async (e) => {
    e.preventDefault();
    const before = JSON.parse(initial);
    const now = readForm(form, spec.fields);
    const changed = Object.fromEntries(Object.entries(now).filter(([k, v]) => before[k] !== v));
    save.disabled = true;
    save.textContent = "Saving…";
    form.querySelector("[data-form-error]").textContent = "";
    try {
      const { department } = await ctx.api(`/academics/departments/${st.slug}`, { method: "PATCH", json: changed });
      st.dept = department;
      renderStatus();
      renderForm(key);
      ctx.toast(`${ctx.icon("check")}<span>Saved. The website shows it within a minute.</span>`);
    } catch (err) {
      form.querySelector("[data-form-error]").textContent = err.message;
      save.disabled = false;
    } finally {
      save.textContent = "Save changes";
    }
  };
  wireCounters(form, spec.fields);
  wirePhotos(form);
}

function renderStatus() {
  const d = st.dept;
  $("[data-dept-heading]").textContent = ctx.isSuperAdmin() ? `Departments · ${d.name}` : `My department · ${d.name}`;
  $("[data-dept-published]").checked = d.published;
  $("[data-dept-published-label]").textContent = d.published ? "Published" : "Draft: not on the website";
  const when = new Date(d.updated_at).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  $("[data-dept-updated]").textContent = `Last updated ${when}${d.updated_by && d.updated_by !== "seed" ? ` by ${d.updated_by}` : ""}`;
  $("[data-dept-view]").href = `/departments/${d.slug}`;
}

function renderList(kind) {
  const spec = ITEMS[kind];
  const { esc, icon } = ctx;
  const items = st.dept[kind];
  const ul = $(`[data-list="${kind}"]`);
  ul.innerHTML = items.length ? items.map((x, i) => {
    const pic = spec.photo ? (spec.photo(x)
      ? `<img src="${esc(spec.photo(x))}" alt="" class="h-12 w-12 flex-none rounded-sm object-cover object-top">`
      : `<span class="flex h-12 w-12 flex-none items-center justify-center rounded-sm bg-brand-100 font-semibold text-brand-800" aria-hidden="true">${esc(initials(spec.title(x)))}</span>`) : "";
    return `<li class="flex flex-wrap items-center gap-4 px-5 py-3.5 sm:flex-nowrap">
      ${pic}
      <div class="min-w-0 flex-1 basis-[11rem]"><p class="font-semibold">${esc(spec.title(x))} ${spec.badge ? spec.badge(x) : ""}</p><p class="truncate text-[0.9375rem] text-ink-2">${esc(spec.meta(x))}</p></div>
      <div class="ml-auto flex flex-none items-center gap-1">
        ${kind !== "programmes" ? `
        <button type="button" class="btn btn-ghost h-9 w-9 px-0" data-move="${kind}:${i}:-1" ${i === 0 ? "disabled" : ""} aria-label="Move ${esc(spec.title(x))} up">${icon("chevron-down", "icon-sm rotate-180")}</button>
        <button type="button" class="btn btn-ghost h-9 w-9 px-0" data-move="${kind}:${i}:1" ${i === items.length - 1 ? "disabled" : ""} aria-label="Move ${esc(spec.title(x))} down">${icon("chevron-down")}</button>` : ""}
        <button type="button" class="btn btn-ghost btn-sm" data-edit-item="${kind}:${esc(x.id)}">${icon("pencil")}<span>Edit</span></button>
        <button type="button" class="btn btn-ghost btn-sm text-om-700 hover:bg-om-50 hover:text-om-700" data-delete-item="${kind}:${esc(x.id)}">Delete</button>
      </div>
    </li>`;
  }).join("") : `<li class="px-5 py-8 text-center text-ink-2">No ${spec.singular === "faculty member" ? "faculty" : spec.singular + "s"} yet. ${kind === "programmes" ? "" : "This section stays hidden on the website until you add one."}</li>`;
}

function renderAll() {
  renderStatus();
  renderForm("overview");
  renderForm("hod");
  ["programmes", "faculty", "labs", "testimonials"].forEach(renderList);
  renderCourseEditor();
}

async function loadDepartment(slug) {
  try {
    const { department } = await ctx.api(`/academics/departments/${slug}`);
    st.slug = slug;
    st.dept = department;
    st.courseProgramme = 0;
    st.courseSemester = 1;
    $("[data-dept-picker]").value = slug;
    if (location.hash !== `#departments/${slug}`) history.replaceState(null, "", `#departments/${slug}`);
    renderAll();
  } catch (err) { ctx.toastError(err); }
}

/* ---------- courses ---------- */

function courseRow(c = { code: "", title: "", credits: 3 }) {
  const { esc, icon } = ctx;
  return `<tr>
    <td><label class="sr-only">Code</label><input class="field min-h-10" maxlength="20" value="${esc(c.code)}" data-c="code" placeholder="CMP 114"></td>
    <td><label class="sr-only">Course title</label><input class="field min-h-10" maxlength="200" value="${esc(c.title)}" data-c="title" placeholder="Course title"></td>
    <td><label class="sr-only">Credits</label><input class="field min-h-10" type="number" step="0.5" min="0" max="12" value="${esc(c.credits)}" data-c="credits"></td>
    <td><button type="button" class="btn btn-ghost h-9 w-9 px-0 text-om-700 hover:bg-om-50" data-remove-course aria-label="Remove this course">${icon("x")}</button></td>
  </tr>`;
}

function renderCourseEditor() {
  const progs = st.dept.programmes;
  const box = $("[data-course-editor]");
  box.hidden = !progs.length;
  if (!progs.length) return;
  st.courseProgramme = Math.min(st.courseProgramme, progs.length - 1);
  const p = progs[st.courseProgramme];
  st.courseSemester = Math.min(st.courseSemester, p.semester_count);
  $("[data-course-programme]").innerHTML = progs.map((x, i) => `<option value="${i}" ${i === st.courseProgramme ? "selected" : ""}>${ctx.esc(x.name)}</option>`).join("");
  $("[data-course-semester]").innerHTML = Array.from({ length: p.semester_count }, (_, i) => {
    const n = i + 1, count = p.semesters.find((s) => s.semester === n)?.courses.length || 0;
    return `<option value="${n}" ${n === st.courseSemester ? "selected" : ""}>Semester ${n}${count ? ` (${count})` : ""}</option>`;
  }).join("");
  const sem = p.semesters.find((s) => s.semester === st.courseSemester);
  $("[data-course-rows]").innerHTML = (sem?.courses.length ? sem.courses : [undefined]).map((c) => courseRow(c)).join("");
  st.courseDirty = false;
  updateCourseTotal();
}

function updateCourseTotal() {
  const total = $$("[data-course-rows] [data-c='credits']").reduce((n, el) => n + (Number(el.value) || 0), 0);
  $("[data-course-total]").textContent = `${total} credits${st.courseDirty ? " · unsaved" : ""}`;
}

async function saveCourses() {
  const rows = $$("[data-course-rows] tr").map((tr) => ({
    code: tr.querySelector("[data-c='code']").value.trim(),
    title: tr.querySelector("[data-c='title']").value.trim(),
    credits: Number(tr.querySelector("[data-c='credits']").value || 0),
  })).filter((r) => r.code || r.title);
  const p = st.dept.programmes[st.courseProgramme];
  const btn = $("[data-save-courses]");
  btn.disabled = true;
  try {
    const { item } = await ctx.api(`/academics/departments/${st.slug}/programmes/${p.id}/semesters/${st.courseSemester}`, { method: "PUT", json: { courses: rows } });
    st.dept.programmes[st.courseProgramme] = item;
    renderCourseEditor();
    renderList("programmes");
    ctx.toast(`${ctx.icon("check")}<span>Semester ${st.courseSemester} saved: ${rows.length} course${rows.length === 1 ? "" : "s"}.</span>`);
  } catch (err) { ctx.toastError(err); } finally { btn.disabled = false; }
}

/* ---------- item sheet ---------- */

function openItemSheet(kind, item = null) {
  const spec = ITEMS[kind];
  st.sheet = { kind, id: item?.id || null };
  $("[data-item-title]").textContent = `${item ? "Edit" : "Add"} ${spec.singular}`;
  const values = item || spec.defaults || {};
  $("[data-item-fields]").innerHTML = `<div class="grid gap-5 sm:grid-cols-2">${spec.fields.map((f) => fieldHtml(f, values[f.name] ?? "", { prefix: "item" })).join("")}</div>`;
  $("[data-item-error]").classList.add("hidden");
  wireCounters($("[data-item-form]"), spec.fields);
  wirePhotos($("[data-item-fields]"));
  ctx.drawers.setOpen(document.getElementById("item-sheet"), true);
}

async function submitItem(e) {
  e.preventDefault();
  const { kind, id } = st.sheet;
  const spec = ITEMS[kind];
  const data = readForm($("[data-item-form]"), spec.fields);
  const missing = spec.fields.find((f) => f.required && !String(data[f.name] || "").trim());
  const error = $("[data-item-error]");
  if (missing) { error.textContent = `${missing.label} can't be empty.`; error.classList.remove("hidden"); return; }
  const btn = $("[data-item-submit]");
  btn.disabled = true;
  try {
    const path = `/academics/departments/${st.slug}/${kind}${id ? `/${id}` : ""}`;
    const { item } = await ctx.api(path, { method: id ? "PATCH" : "POST", json: data });
    const list = st.dept[kind];
    const at = list.findIndex((x) => x.id === item.id);
    if (at >= 0) list[at] = item; else list.push(item);
    renderList(kind);
    if (kind === "programmes") renderCourseEditor();
    ctx.drawers.setOpen(document.getElementById("item-sheet"), false);
    ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(spec.title(item))} ${id ? "updated" : "added"}.</span>`);
  } catch (err) {
    error.textContent = err.message;
    error.classList.remove("hidden");
  } finally { btn.disabled = false; }
}

async function deleteItem(kind, id, button) {
  // two-step delete: first click asks, second click (within 4 s) deletes
  if (button.dataset.confirming !== "true") {
    button.dataset.confirming = "true";
    button.textContent = "Really delete?";
    setTimeout(() => { button.dataset.confirming = ""; button.textContent = "Delete"; }, 4000);
    return;
  }
  const spec = ITEMS[kind];
  const item = st.dept[kind].find((x) => x.id === id);
  try {
    await ctx.api(`/academics/departments/${st.slug}/${kind}/${id}`, { method: "DELETE" });
    st.dept[kind] = st.dept[kind].filter((x) => x.id !== id);
    renderList(kind);
    if (kind === "programmes") renderCourseEditor();
    ctx.toast(`${ctx.icon("check")}<span>Deleted ${ctx.esc(spec.title(item))}.</span>`);
  } catch (err) { ctx.toastError(err); }
}

async function moveItem(kind, index, delta) {
  const list = st.dept[kind];
  const to = index + delta;
  if (to < 0 || to >= list.length) return;
  [list[index], list[to]] = [list[to], list[index]];
  renderList(kind);
  $(`[data-move="${kind}:${to}:${delta}"]`)?.focus();
  try {
    await ctx.api(`/academics/departments/${st.slug}/${kind}/order`, { method: "POST", json: { ids: list.map((x) => x.id) } });
  } catch (err) {
    ctx.toastError(err);
    loadDepartment(st.slug);
  }
}

/* ---------- departments list & new department ---------- */

async function loadList(preferred) {
  const { items } = await ctx.api("/academics/departments");
  st.list = items;
  $("[data-dept-picker]").innerHTML = items.map((d) => `<option value="${ctx.esc(d.slug)}">${ctx.esc(d.name)}${d.published ? "" : " (draft)"}</option>`).join("");
  $("[data-dept-picker]").hidden = items.length < 2;
  $("[data-new-dept]").hidden = !ctx.isSuperAdmin();
  return items.find((d) => d.slug === preferred)?.slug || items[0]?.slug;
}

function unsavedChanges() {
  return $$("[data-dept-form]").some((f) => f.dataset.dirty === "true") || st.courseDirty;
}

/* ---------- public API ---------- */

export function initDepartments(context) {
  ctx = context;

  $("[data-dept-picker]").addEventListener("change", (e) => {
    if (unsavedChanges() && !window.confirm("You have unsaved changes. Leave them and switch department?")) {
      e.target.value = st.slug;
      return;
    }
    loadDepartment(e.target.value);
  });

  $("[data-dept-published]").addEventListener("change", async (e) => {
    const published = e.target.checked;
    try {
      const { department } = await ctx.api(`/academics/departments/${st.slug}`, { method: "PATCH", json: { published } });
      st.dept = department;
      renderStatus();
      loadList(st.slug);
      ctx.toast(`${ctx.icon("check")}<span>${published ? "Published. The page is live on the website." : "Unpublished. The page is hidden from the website."}</span>`);
    } catch (err) {
      e.target.checked = !published;
      ctx.toastError(err);
    }
  });

  document.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add-item]");
    if (add) return openItemSheet(add.dataset.addItem);
    const edit = e.target.closest("[data-edit-item]");
    if (edit) {
      const [kind, id] = edit.dataset.editItem.split(":");
      return openItemSheet(kind, st.dept[kind].find((x) => x.id === id));
    }
    const del = e.target.closest("[data-delete-item]");
    if (del) {
      const [kind, id] = del.dataset.deleteItem.split(":");
      return deleteItem(kind, id, del);
    }
    const mv = e.target.closest("[data-move]");
    if (mv) {
      const [kind, i, d] = mv.dataset.move.split(":");
      return moveItem(kind, Number(i), Number(d));
    }
    if (e.target.closest("[data-remove-course]")) {
      e.target.closest("tr").remove();
      if (!$$("[data-course-rows] tr").length) $("[data-course-rows]").insertAdjacentHTML("beforeend", courseRow());
      st.courseDirty = true;
      updateCourseTotal();
    }
  });

  $("[data-item-form]").addEventListener("submit", submitItem);
  $("[data-add-course]").addEventListener("click", () => {
    $("[data-course-rows]").insertAdjacentHTML("beforeend", courseRow());
    $$("[data-course-rows] tr").at(-1).querySelector("input").focus();
    st.courseDirty = true;
    updateCourseTotal();
  });
  $("[data-course-rows]").addEventListener("input", () => { st.courseDirty = true; updateCourseTotal(); });
  $("[data-save-courses]").addEventListener("click", saveCourses);
  const switchCourses = (apply) => {
    if (st.courseDirty && !window.confirm("This semester has unsaved changes. Leave them?")) return renderCourseEditor();
    apply();
    renderCourseEditor();
  };
  $("[data-course-programme]").addEventListener("change", (e) => switchCourses(() => { st.courseProgramme = Number(e.target.value); st.courseSemester = 1; }));
  $("[data-course-semester]").addEventListener("change", (e) => switchCourses(() => { st.courseSemester = Number(e.target.value); }));

  // new department (Super Admin)
  const nameInput = $("#nd-name"), slugInput = $("#nd-slug");
  nameInput.addEventListener("input", () => {
    if (slugInput.dataset.touched) return;
    slugInput.value = nameInput.value.toLowerCase().replace(/&/g, "and").replace(/engineering/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 38);
  });
  slugInput.addEventListener("input", () => (slugInput.dataset.touched = "1"));
  $("[data-new-dept]").addEventListener("click", () => {
    $("[data-new-dept-form]").reset();
    delete slugInput.dataset.touched;
    $("[data-new-dept-error]").classList.add("hidden");
    ctx.drawers.setOpen(document.getElementById("dept-sheet"), true);
  });
  $("[data-new-dept-form]").addEventListener("submit", async (e) => {
    e.preventDefault();
    const error = $("[data-new-dept-error]");
    try {
      const { department } = await ctx.api("/academics/departments", { method: "POST", json: { name: nameInput.value, slug: slugInput.value } });
      ctx.drawers.setOpen(document.getElementById("dept-sheet"), false);
      await loadList(department.slug);
      await loadDepartment(department.slug);
      ctx.toast(`${ctx.icon("check")}<span>${ctx.esc(department.name)} created as a draft.</span>`);
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });

  window.addEventListener("beforeunload", (e) => { if (unsavedChanges()) e.preventDefault(); });
}

export async function showDepartments(slugFromHash) {
  try {
    const slug = await loadList(slugFromHash || st.slug);
    if (!slug) {
      $("[data-dept-heading]").textContent = "No department assigned";
      return;
    }
    if (slug !== st.slug || !st.dept) await loadDepartment(slug);
  } catch (err) { if (err.status !== 401) ctx.toastError(err); }
}
