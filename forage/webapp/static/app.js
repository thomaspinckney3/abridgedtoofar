/* Forage galley — client for the editorial review app.
   No build step, no dependencies: this ships as-is to the host. */

const state = {
  session: { role: "public", can_write: false, can_admin: false, label: "",
             severities: [], kinds: [], statuses: [] },
  book: null,          // { book_id, title, author, chapters: [...] }
  media: null,
  selectionKey: null,
  chapter: null,       // rendered chapter view + comments
  filters: { unsupported: false, compressed: false, diagnostic: false, commented: false, query: "" },
  current: null,       // draft_para index the keyboard is on
  composerFor: null,   // draft_para the composer is open on
  scopeComposer: null, // "book" or "chapter"
  composerQuote: "",
};

const el = {
  main: document.getElementById("main"),
  rail: document.getElementById("rail"),
  layout: document.getElementById("layout"),
  topbarBook: document.getElementById("topbar-book"),
  bookTitle: document.getElementById("book-title"),
  bookAuthor: document.getElementById("book-author"),
  sessionBtn: document.getElementById("session-btn"),
  themeBtn: document.getElementById("theme-btn"),
  helpBtn: document.getElementById("help-btn"),
  toasts: document.getElementById("toasts"),
  tip: document.getElementById("selection-tip"),
  tipBtn: document.getElementById("selection-comment"),
  signin: document.getElementById("signin-dialog"),
  signinForm: document.getElementById("signin-form"),
  signinLabel: document.getElementById("signin-label"),
  signinToken: document.getElementById("signin-token"),
  signinError: document.getElementById("signin-error"),
  signinNote: document.getElementById("signin-note"),
  help: document.getElementById("help-dialog"),
};

/* ------------------------------------------------------------------ util */

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { detail = (await res.json()).detail || detail; } catch { /* keep status */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

function toast(message, kind = "") {
  const node = h("div", { class: `toast ${kind}` }, message);
  el.toasts.append(node);
  setTimeout(() => node.remove(), 4200);
}

function plural(n, one, many) { return `${n} ${n === 1 ? one : many}`; }

function labelize(value) { return String(value || "").replace(/[-_]/g, " "); }

function relTime(seconds) {
  const delta = Date.now() / 1000 - seconds;
  if (delta < 90) return "just now";
  if (delta < 3600) return `${Math.round(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  return `${Math.round(delta / 86400)}d ago`;
}

function displayTime(value) {
  if (value === null || value === undefined || value === "") return "";
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 0) return relTime(numeric);
  const parsed = Date.parse(value);
  if (Number.isFinite(parsed)) return relTime(parsed / 1000);
  return String(value);
}

/* --------------------------------------------------------------- routing */

function route() {
  const match = location.pathname.match(/^\/(?:b|release)\/([^/]+)/);
  const params = new URLSearchParams(location.search);
  const para = params.get("p");
  return {
    bookId: match ? decodeURIComponent(match[1]) : null,
    segmentId: params.get("c"),
    channel: location.pathname.startsWith("/release/") ? "release" : "review",
    revision: params.get("revision"),
    view: params.get("view"),
    // ?p=<n> deep-links a paragraph so a reviewer can send someone straight to it
    draftPara: para === null || para === "" ? null : Number(para),
  };
}

function selectionQuery() {
  const current = route();
  const query = new URLSearchParams();
  if (current.channel === "release") query.set("channel", "release");
  const revision = state.book?.publication_revision || current.revision;
  if (revision) query.set("revision", revision);
  return `?${query}`;
}

function bookRoute(extra = {}) {
  const current = route();
  const query = new URLSearchParams(extra);
  const revision = state.book?.publication_revision || current.revision;
  if (revision) query.set("revision", revision);
  return `/${current.channel === "release" ? "release" : "b"}/${encodeURIComponent(current.bookId)}?${query}`;
}

function publicationNav() {
  const book = state.book;
  const edition = book.publication_channel === "release" ? "Public release"
    : book.publication_channel === "revision" ? "Published revision" : "Review edition";
  return h("section", { class: "publication-nav" },
    h("p", { class: "revision-label" }, `${edition} · ${book.publication_revision ? book.publication_revision.slice(0, 12) : "local artifacts"}`),
    h("a", { class: "btn small", href: bookRoute(), "data-route": true }, "Read text"),
    h("a", { class: "btn small", href: bookRoute({ view: "media" }), "data-route": true }, "Audio & graphic novel"),
    h("a", { class: "btn small", href: `/release/${encodeURIComponent(book.book_id)}`, "data-route": true }, "Current public release"),
    h("a", { class: "btn small", href: `/b/${encodeURIComponent(book.book_id)}`, "data-route": true }, "Current review edition"),
    (book.downloads || []).map(item => h("a", { class: "download-link", href: item.url, download: true }, `Download ${item.path}`)));
}

function go(path, replace = false) {
  history[replace ? "replaceState" : "pushState"]({}, "", path);
  render();
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-route]");
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
  event.preventDefault();
  go(link.getAttribute("href"));
});
window.addEventListener("popstate", render);

/* --------------------------------------------------------------- session */

async function loadSession() {
  try {
    state.session = await api("/api/session");
  } catch { /* stay read-only */ }
  const who = state.session.label ? ` · ${state.session.label}` : "";
  el.sessionBtn.textContent = state.session.can_admin
    ? `Admin${who}`
    : state.session.can_write ? `Reviewer${who}` : "Sign in to comment";
}

el.sessionBtn.addEventListener("click", async () => {
  if (state.session.can_write) {
    await api("/api/session", { method: "DELETE" });
    await loadSession();
    toast("Signed out. Reading stays open.");
    render();
    return;
  }
  el.signinError.hidden = true;
  el.signinToken.value = "";
  el.signinNote.textContent = state.session.admin_enabled
    ? "Reading is open to anyone. The review token lets you leave notes; the admin token can also export feedback."
    : "Reading is open to anyone. The review token lets you leave notes.";
  if (state.session.generated_token) {
    el.signinNote.textContent += " This server generated its token at startup — it's in the server log.";
  }
  el.signin.showModal();
});

el.signinForm.addEventListener("submit", async (event) => {
  if (event.submitter && event.submitter.value === "cancel") return;
  event.preventDefault();
  try {
    await api("/api/session", {
      method: "POST",
      body: { token: el.signinToken.value, label: el.signinLabel.value },
    });
    el.signin.close();
    await loadSession();
    toast("Signed in. Comments are open.");
    render();
  } catch (err) {
    el.signinError.textContent = err.message;
    el.signinError.hidden = false;
  }
});

el.helpBtn.addEventListener("click", () => el.help.showModal());

/* ----------------------------------------------------------------- theme */

function applyTheme(theme) {
  if (theme) document.documentElement.setAttribute("data-theme", theme);
  else document.documentElement.removeAttribute("data-theme");
}
applyTheme(localStorage.getItem("forage-theme"));
el.themeBtn.addEventListener("click", () => {
  const now = document.documentElement.getAttribute("data-theme");
  const dark = now ? now === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  const next = dark ? "light" : "dark";
  localStorage.setItem("forage-theme", next);
  applyTheme(next);
});

/* ------------------------------------------------------------ book index */

async function renderIndex() {
  el.topbarBook.hidden = true;
  el.rail.innerHTML = "";
  el.rail.hidden = true;
  el.layout.classList.add("no-rail");
  el.main.replaceChildren(h("div", { class: "loading" }, "Loading books…"));

  const { books } = await api("/api/books");
  const head = h("div", { class: "index-head" },
    h("h1", {}, "Editorial review"),
    h("p", {}, "Every abridged paragraph next to the source it came from. Read anything; " +
      "sign in with the review token to leave notes for the fix pass."));

  if (!books.length) {
    el.main.replaceChildren(head, h("p", { class: "empty" },
      "No alignments yet. Run forage proofread <book> to produce them."));
    return;
  }

  const grid = h("div", { class: "book-grid" }, books.map((book) => {
    const total = Object.values(book.counts).reduce((a, b) => a + b, 0) || 1;
    const mix = h("div", { class: "mix", title: mixTitle(book.counts) },
      ["verbatim", "paraphrased", "compressed", "unsupported"].map((key) =>
        book.counts[key] ? h("span", {
          class: key, style: `width:${(book.counts[key] / total) * 100}%`,
        }) : null));
    return h("a", { class: "book-card", href: `/b/${encodeURIComponent(book.book_id)}`, "data-route": true },
      h("h2", {}, book.title),
      book.author ? h("div", { class: "byline" }, book.author) : null,
      mix,
      h("div", { class: "card-meta" },
        h("span", { class: "slug" }, book.book_id),
        h("span", {}, plural(book.chapters, "chapter", "chapters")),
        book.counts.unsupported ? h("span", {}, `${book.counts.unsupported} unsupported`) : null,
        book.diagnostics?.total ? h("span", {}, `${book.diagnostics.total} flags`) : null,
        h("span", {}, plural(book.comments.total || 0, "note", "notes"))));
  }));

  el.main.replaceChildren(head, grid);
  document.title = "Forage — editorial review";
}

function mixTitle(counts) {
  return Object.entries(counts).filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`).join(" · ");
}

/* ---------------------------------------------------------------- rail */

function renderRail(activeSegment) {
  const book = state.book;
  const list = h("div", { class: "chapter-list" }, book.chapters.map((ch) => {
    const unsupported = ch.counts.unsupported || 0;
    const diagnostics = (ch.diagnostics && ch.diagnostics.total) || 0;
    const notes = (ch.comments && ch.comments.total) || 0;
    return h("a", {
      class: "chapter-link",
      href: bookRoute({ c: ch.segment_id }),
      "data-route": true,
      "aria-current": ch.segment_id === activeSegment ? "true" : null,
      title: `${ch.title || ch.segment_id} — ${mixTitle(ch.counts)}`,
    },
      h("span", { class: "num" }, ch.segment_id),
      h("span", { class: "name" }, ch.title || "—"),
      h("span", { class: "flags" },
        unsupported ? h("span", { class: "flag-unsupported" }, `!${unsupported}`) : null,
        diagnostics ? h("span", { class: "flag-diagnostics" }, `?${diagnostics}`) : null,
        notes ? h("span", { class: "flag-comments" }, `¶${notes}`) : null));
  }));

  const chip = (key, label) => h("button", {
    class: "filter-chip", type: "button",
    "aria-pressed": state.filters[key] ? "true" : "false",
    onclick: () => { state.filters[key] = !state.filters[key]; renderChapterBody(); renderRail(activeSegment); },
  }, label);

  el.rail.hidden = false;
  el.layout.classList.remove("no-rail");
  el.rail.replaceChildren(
    h("a", { class: "rail-back", href: "/", "data-route": true }, "← All books"),
    publicationNav(),
    h("h2", {}, "Chapters"),
    list,
    h("div", { class: "rail-tools" },
      h("input", {
        type: "search", id: "chapter-search", placeholder: "Search this chapter",
        value: state.filters.query,
        oninput: (e) => { state.filters.query = e.target.value; renderChapterBody(); },
      }),
      h("div", { class: "filter-group" },
        chip("unsupported", "Unsupported"),
        chip("compressed", "Compressed"),
        chip("diagnostic", "Flags"),
        chip("commented", "Has notes")),
      state.session.can_admin
        ? h("button", { class: "btn small", type: "button", onclick: publish }, "Export feedback")
        : null,
      h("button", { class: "btn small", type: "button", onclick: () => openScopeComposer("book") },
        "Book note"),
      h("a", {
        class: "btn small", href: `/api/books/${encodeURIComponent(book.book_id)}/edits.json`,
        style: "text-align:center;text-decoration:none",
      }, "Download notes")));
}

async function publish() {
  try {
    const result = await api(`/api/books/${encodeURIComponent(state.book.book_id)}/publish`, { method: "POST" });
    toast(`Wrote ${result.comment_count} notes to ${result.path}` +
      (result.stale_count ? ` (${result.stale_count} stale)` : ""));
  } catch (err) {
    toast(err.message, "error");
  }
}

/* -------------------------------------------------------------- chapter */

async function renderChapter(bookId, segmentId, draftPara) {
  const currentRoute = route();
  const key = `${bookId}:${currentRoute.channel}:${currentRoute.revision || "current"}`;
  if (!state.book || state.selectionKey !== key) {
    el.main.replaceChildren(h("div", { class: "loading" }, "Loading…"));
    const query = new URLSearchParams();
    if (currentRoute.channel === "release") query.set("channel", "release");
    if (currentRoute.revision) query.set("revision", currentRoute.revision);
    state.book = await api(`/api/books/${encodeURIComponent(bookId)}/chapters?${query}`);
    state.selectionKey = key;
  }
  const book = state.book;
  if (currentRoute.view === "media") { await renderMedia(); return; }
  state.media = null;
  if (!book.chapters.length) {
    el.main.replaceChildren(h("p", { class: "empty" }, "This book has no aligned chapters."));
    return;
  }
  const target = book.chapters.some((c) => c.segment_id === segmentId)
    ? segmentId : book.chapters[0].segment_id;
  if (target !== segmentId) {
    go(bookRoute({ c: target }), true);
    return;
  }

  el.topbarBook.hidden = false;
  el.bookTitle.textContent = book.title;
  el.bookAuthor.textContent = book.author || "";
  document.title = `${book.title} — chapter ${target}`;

  state.chapter = await api(
    `/api/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(target)}${selectionQuery()}`);
  state.current = Number.isInteger(draftPara) ? draftPara : null;
  state.composerFor = null;
  state.scopeComposer = null;
  renderRail(target);
  renderChapterBody();
  if (state.current !== null) {
    document.getElementById(`p-${state.current}`)?.scrollIntoView({ block: "center" });
  }
}

function matchesFilters(block) {
  const f = state.filters;
  if (f.unsupported && block.note_key !== "unsupported") return false;
  if (f.compressed && block.note_key !== "compressed") return false;
  if (f.diagnostic && !(block.diagnostics || []).length) return false;
  if (f.commented && !commentsFor(block.draft_para).length) return false;
  if (f.query) {
    const needle = f.query.toLowerCase();
    const hay = [
      block.draft,
      ...block.sources.map((s) => s.text),
      ...(block.diagnostics || []).flatMap((d) =>
        [d.class, d.draft_passage, d.source_has, d.reason]),
    ].join(" ").toLowerCase();
    if (!hay.includes(needle)) return false;
  }
  return true;
}

function commentsFor(draftPara) {
  return (state.chapter.comments || []).filter((c) => c.scope === "paragraph" && c.current_draft_para === draftPara);
}

function renderChapterBody() {
  const chapter = state.chapter;
  const meta = state.book.chapters.find((c) => c.segment_id === chapter.segment_id) || {};
  const counts = chapter.counts;

  const head = h("div", { class: "chapter-head" },
    h("h1", {}, chapter.title ? `Chapter ${chapter.segment_id} — ${chapter.title}` : `Chapter ${chapter.segment_id}`),
    h("div", { class: "stats" },
      ["verbatim", "paraphrased", "compressed", "unsupported"].map((key) =>
        counts[key] ? h("span", {},
          h("span", { class: `stat-dot ${key}` }), `${counts[key]} ${key}`) : null),
      (chapter.diagnostic_counts?.total || 0) ? h("span", {},
        h("span", { class: "stat-dot diagnostic" }), `${chapter.diagnostic_counts.total} flags`) : null,
      h("span", {}, `${meta.draft_paragraphs || chapter.blocks.length} draft ¶ from ${meta.source_paragraphs || "?"} source ¶`)),
    h("div", { class: "chapter-actions" },
      h("button", { class: "btn small", type: "button", onclick: () => openScopeComposer("chapter") },
        "Chapter note")));

  const visible = chapter.blocks.filter(matchesFilters);
  const blocks = h("div", { class: "blocks" },
    visible.length
      ? visible.map(renderBlock)
      : h("p", { class: "empty" }, "No paragraphs match these filters."));

  const unplaced = (chapter.diagnostics_unmatched || []).length
    ? h("details", { class: "unplaced-diagnostics", open: true },
      h("summary", {}, `${chapter.diagnostics_unmatched.length} unplaced review flags`),
      h("p", { class: "unplaced-note" },
        "These came from current draft checks but could not be matched to a draft paragraph."),
      chapter.diagnostics_unmatched.map((d) => renderDiagnostic(d, null)))
    : null;

  const unused = chapter.unused.length
    ? h("details", { class: "unused" },
      h("summary", {}, `${chapter.unused.length} source paragraphs no draft paragraph uses — the cut material`),
      chapter.unused.map((p) => h("p", { class: "src-para" },
        h("span", { class: "para-id" }, `src ${p.index}`), p.text)))
    : null;

  const bookNotes = renderScopeNotes("Book notes", chapter.book_comments || [], "book");
  const chapterNotes = renderScopeNotes("Chapter notes",
    (chapter.comments || []).filter((c) => !c.pipeline_review && (c.scope === "chapter" || (!c.scope && c.draft_para === null))),
    "chapter");
  const review = renderPipelineReviews((chapter.comments || []).filter(c => c.pipeline_review),
    [renderChapterNotes(chapter.chapter_notes), unplaced].filter(Boolean));
  const jumpTo = (section) => {
    if (section.tagName === "DETAILS") section.open = true;
    section.focus({preventScroll: true});
    section.scrollIntoView({block: "start"});
  };
  head.querySelector(".chapter-actions").append(...[
    review.issues ? h("button", {class: "btn small", type: "button", onclick: () => jumpTo(review.issues)},
      `Suggested issues (${review.count})`) : null,
    review.history ? h("button", {class: "btn small", type: "button", onclick: () => jumpTo(review.history)},
      "Review history") : null,
  ].filter(Boolean));

  const unattached = (chapter.comments || []).filter(c =>
    c.scope === "paragraph" && c.current_draft_para === null);
  const earlierNotes = unattached.length ? h("section", { class: "scope-notes" },
    h("h2", {}, "Notes awaiting a matching passage"),
    h("p", {}, "These notes refer to earlier text. Their current location could not be established."),
    ...unattached.map(renderNote)) : null;
  el.main.replaceChildren(...[head, blocks, bookNotes, chapterNotes, earlierNotes,
    review.issues, review.history, unused].filter(Boolean));
}

function renderEvidence(evidence) {
  const names = {source: "Original source", initial: "Earlier draft", revision: "Reviewed draft"};
  return h("div", {class: "pipeline-evidence"}, evidence.map(e => {
    const match = e.document.match(/^([A-Za-z0-9_-]+)\.(source|initial|revision)$/);
    const label = match ? `${names[match[2]]} · chapter ${match[1]}` : e.document;
    return h("blockquote", {}, h("p", {}, e.quote),
      h("small", {}, `${label} · paragraph ${e.paragraph} in the recorded review`));
  }));
}

function renderPipelineReviews(notes, records) {
  const expanded = new Map([...document.querySelectorAll('.pipeline-card')]
    .map(card => [card.dataset.reviewId, card.open]));
  const order = {must_fix: 0, should_improve: 1, tradeoff: 2, review: 3};
  notes = [...notes].sort((a, b) => order[a.pipeline_review.priority] - order[b.pipeline_review.priority]);
  const outstanding = note => note.pipeline_review.kind === "finding"
    && note.revision_review?.state !== "accepted" && note.revision_review?.current !== false;
  const suggestions = notes.filter(outstanding);
  const previous = notes.filter(note => !outstanding(note));
  const issues = suggestions.length ? h("section", {
    id: "suggested-issues", class: "scope-notes suggested-issues", tabindex: "-1"},
    h("h2", {}, "Suggested issues"),
    h("p", {class: "sheet-note"},
      "Possible issues identified by automated review. Use your judgment; you can read and annotate the chapter without deciding every suggestion."),
    !state.session.can_write ? h("p", {class: "sheet-note"}, "Sign in to dismiss a suggestion or request a change.") : null,
    ...suggestions.map(note => renderPipelineCard(note, expanded))) : null;

  const context = `${state.book.book_id}/${state.chapter.segment_id}/${state.chapter.publication_revision || ""}`;
  const oldHistory = document.getElementById("review-history");
  const history = notes.length || records.length ? h("details", {
    id: "review-history", class: "scope-notes review-history", tabindex: "-1", "data-context": context,
    open: oldHistory?.dataset.context === context && oldHistory.open},
    h("summary", {}, "Review history"),
    h("p", {class: "sheet-note"},
      "Changes already made, reviewed suggestions, and detailed automated records. Earlier edits may have been revised again; the chapter above is the current text."),
    ...previous.map(note => renderPipelineCard(note, expanded)),
    notes.some(note => note.pipeline_review.kind === "finding") ? h("details", {class: "critic-records"},
      h("summary", {}, "Detailed critic records"),
      ...notes.filter(note => note.pipeline_review.kind === "finding").map(note => h("details", {class: "pipeline-record"},
        h("summary", {}, note.pipeline_review.title),
        h("p", {class: "sheet-note"}, `Recorded priority: ${labelize(note.pipeline_review.priority)} · ${labelize(note.pipeline_review.review_label)}`),
        h("p", {class: "note-body"}, note.body),
        note.pipeline_review.finding?.counterevidence ? h("p", {}, `Other context: ${note.pipeline_review.finding.counterevidence}`) : null,
        renderEvidence(note.pipeline_review.evidence),
        (note.llm_responses || []).filter(r => r.source === "pipeline_finding").map(renderLlmResponse)))) : null,
    ...records) : null;
  return {issues, history, count: suggestions.length};
}

function renderPipelineCard(note, expanded) {
  const item = note.pipeline_review;
  const review = note.revision_review;
  const labels = {must_fix: "Needs attention", should_improve: "Suggestion", tradeoff: "Optional", review: "Already edited"};
  const status = review?.current === false ? "Earlier text" : review?.state === "accepted"
    ? (note.llm_responses?.at(-1)?.source === "pipeline_finding" ? "Dismissed" : "Accepted")
    : review?.state === "rejected" ? "Changes requested" : "Awaiting review";
  return h("details", {class: "pipeline-card", "data-review-id": note.id, open: expanded.get(note.id) || false},
    h("summary", {}, h("span", {class: "tag"}, labels[item.priority]), " ",
      item.kind === "repair" ? "Changes already made to this chapter" : item.title,
      h("span", {class: "pipeline-status"}, status)),
    h("p", {class: "note-body"}, note.body),
    (note.llm_responses || []).filter(r => !["pipeline_finding", "pipeline_repair"].includes(r.source)).map(renderLlmResponse),
    review ? renderRevisionReview(note) : null,
    item.evidence.length ? h("details", {}, h("summary", {}, "Compare source and draft"), renderEvidence(item.evidence)) : null,
    ...item.history.map((pass, index) => h("details", {class: "pipeline-pass"},
      h("summary", {}, `Editing pass ${index + 1} · ${plural(pass.replacements.length, "change", "changes")}`),
      ...pass.replacements.map(patch => h("div", {class: "pipeline-patch"},
        h("strong", {}, "Before"), h("p", {}, patch.old),
        h("strong", {}, "After"), h("p", {}, patch.new || "[Removed]"))),
      h("details", {}, h("summary", {}, "Why these changes were made"),
        h("p", {class: "sheet-note"}, `Recorded pass: ${labelize(pass.pass)}`),
        ...pass.adjudications.map(a => {
          const finding = pass.findings.find(f => f.id === a.id);
          return h("div", {class: "pipeline-adjudication"},
            h("strong", {}, `${finding?.title || a.id} · ${a.decision}`),
            finding?.claim ? h("p", {}, finding.claim) : null,
            h("p", {}, a.reason), renderEvidence(a.evidence || []));
        })))));
}

function formatDelta(value) {
  if (value === null || value === undefined || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return `${number > 0 ? "+" : ""}${number}%`;
}

function renderChapterNotes(notes) {
  if (!notes || !Object.keys(notes).length) return null;
  const metrics = [
    notes.status ? ["status", notes.status] : null,
    notes.source_words !== undefined ? ["source", `${notes.source_words}w`] : null,
    notes.target_words !== undefined ? ["target", `${notes.target_words}w`] : null,
    notes.draft_words !== undefined ? ["draft", `${notes.draft_words}w`] : null,
    formatDelta(notes.word_count_delta_pct)
      ? ["delta", formatDelta(notes.word_count_delta_pct)] : null,
    notes.signatures_total !== undefined
      ? ["signatures", `${notes.signatures_matched || 0}/${notes.signatures_total}`] : null,
  ].filter(Boolean);

  const section = (title, items) => (items || []).length
    ? h("section", { class: "chapter-note-section" },
      h("h2", {}, title),
      h("ul", {}, items.map((item) => h("li", {}, item))))
    : null;

  const hasRich = !!notes.has_rich_notes;
  const hasRiskSignals = (notes.signature_misses || []).length || notes.parse_error;
  return h("details", {
    class: "chapter-notes",
    open: hasRich || hasRiskSignals ? true : null,
  },
    h("summary", {},
      h("span", {}, "Draft notes"),
      h("span", { class: "chapter-notes-state" },
        hasRich ? "LLM commentary" : "metrics only")),
    metrics.length
      ? h("div", { class: "chapter-note-metrics" },
        metrics.map(([label, value]) => h("span", {}, h("b", {}, label), value)))
      : null,
    notes.summary ? h("p", { class: "chapter-note-summary" }, notes.summary) : null,
    section("Why acceptable", notes.acceptable_changes),
    section("Risks", notes.risks),
    section("Review focus", notes.review_focus),
    section("Signature misses", notes.signature_misses),
    notes.parse_error
      ? h("p", { class: "chapter-note-error" },
        "The chapter note marker was present but could not be parsed.")
      : null,
    !hasRich
      ? h("p", { class: "chapter-note-empty" },
        "No detailed LLM commentary was captured for this chapter run.")
      : null);
}

function renderBlock(block) {
  const notes = commentsFor(block.draft_para);
  const diagnostics = block.diagnostics || [];
  const isCurrent = state.current === block.draft_para;

  const body = h("div", { class: "block-body" },
    h("div", { class: "block-meta" },
      h("span", { class: "verdict" }, block.note_key),
      h("span", { class: "para-id" }, `draft ${block.draft_para}`),
      diagnostics.length
        ? h("span", { class: "diag-count" }, `${diagnostics.length} flags`)
        : null,
      block.note.includes("—")
        ? h("span", { class: "rationale" }, block.note.split("—").slice(1).join("—").trim())
        : null,
      h("span", { class: "block-actions" },
        h("button", {
          class: "btn small", type: "button",
          onclick: () => openComposer(block.draft_para, ""),
        }, "Comment"))),
    block.diff_html
      ? h("p", { class: "draft diff-view selectable", html: block.diff_html, "data-para": block.draft_para })
      : h("p", { class: "draft selectable", "data-para": block.draft_para }, block.draft),
    block.sources.length
      ? h("div", { class: "source" }, block.sources.map((s) =>
        h("p", { class: "src-para" }, h("span", { class: "para-id" }, `src ${s.index}`), s.text)))
      : null,
    diagnostics.length
      ? h("div", { class: "diagnostics-inline" },
        diagnostics.map((d) => renderDiagnostic(d, block)))
      : null);

  const margin = h("div", { class: "margin" },
    notes.map(renderNote),
    state.composerFor === block.draft_para ? renderComposer(block) : null);

  return h("div", {
    class: `block ${block.note_key}${isCurrent ? " is-current" : ""}`,
    id: `p-${block.draft_para}`,
    "data-para": block.draft_para,
  }, body, margin);
}

function renderDiagnostic(diagnostic, block) {
  const sourceLabel = diagnostic.source === "name-lint"
    ? "name lint"
    : diagnostic.source === "dialogue-lint" ? "dialogue lint" : "review flag";
  const title = labelize(diagnostic.class);
  const commentBody = diagnostic.reason || diagnostic.draft_passage || title;
  return h("div", { class: `diagnostic ${diagnostic.severity || "major"}` },
    h("div", { class: "diagnostic-head" },
      h("span", { class: "tag diag-source" }, sourceLabel),
      h("span", { class: "tag" }, title),
    diagnostic.alias ? h("span", { class: "tag" }, diagnostic.alias) : null),
    diagnostic.draft_passage ? h("p", { class: "diagnostic-quote" }, diagnostic.draft_passage) : null,
    diagnostic.reason ? h("p", { class: "diagnostic-body" }, diagnostic.reason) : null,
    diagnostic.source_has ? h("div", { class: "diagnostic-source" },
      h("div", { class: "diagnostic-label" }, "Source context"),
      h("p", {}, diagnostic.source_has)) : null,
    block && state.session.can_write
      ? h("button", {
        class: "btn small", type: "button",
        onclick: () => {
          state.composerFor = block.draft_para;
          state.composerQuote = diagnostic.draft_passage || "";
          renderChapterBody();
          const kind = document.getElementById("composer-kind");
          const severity = document.getElementById("composer-severity");
          const body = document.getElementById("composer-body");
          if (kind) kind.value = "continuity";
          if (severity) severity.value = diagnostic.severity || "major";
          if (body) {
            body.value = commentBody;
            body.focus();
          }
        },
      }, "Turn into note")
      : null);
}

function renderNote(note) {
  const canWrite = state.session.can_write;
  const responses = note.llm_responses || [];
  return h("div", { class: `note ${note.severity} ${note.status}` },
    h("div", { class: "note-head" },
      h("span", { class: `tag sev-${note.severity}` }, note.severity),
      h("span", { class: "tag" }, note.kind),
      note.status !== "open" && !note.revision_review ? h("span", { class: "tag" }, note.status) : null,
      note.stale ? h("span", { class: "tag stale", title: "The reviewed content changed after this note was written" }, "stale") : null,
      note.orphaned ? h("span", { class: "tag stale", title: "The reviewed target is absent from this edition" }, "orphaned") : null,
      h("span", { class: "note-author" }, `${note.author || "anon"} · ${relTime(note.created_at)}`)),
    note.timestamp_seconds !== null && note.timestamp_seconds !== undefined ? h("p", { class: "note-time" }, `At ${note.timestamp_seconds.toFixed(2)} seconds in this chunk`) : null,
    note.quote ? h("p", { class: "note-quote" }, `“${note.quote}”`) : null,
    note.stale && note.original_text ? h("details", { class: "note-original" },
      h("summary", {}, "Originally reviewed passage"),
      h("p", { class: "note-quote" }, note.original_text)) : null,
    note.current_draft_paras?.length > 1 ? h("p", { class: "sheet-note" },
      `Revised passage: draft ${note.current_draft_paras.join(", ")}`) : null,
    h("p", { class: "note-body" }, note.body),
    responses.length
      ? h("div", { class: "note-responses" }, responses.map(renderLlmResponse))
      : null,
    note.revision_review ? renderRevisionReview(note) : null,
    canWrite && !note.revision_review
      ? h("div", { class: "note-foot" },
        note.status === "open"
          ? h("button", { type: "button", onclick: () => setStatus(note, "accepted") }, "Accept comment")
          : null,
        note.status !== "resolved"
          ? h("button", { type: "button", onclick: () => setStatus(note, "resolved") }, "Resolve")
          : h("button", { type: "button", onclick: () => setStatus(note, "open") }, "Reopen"),
        note.status !== "wontfix"
          ? h("button", { type: "button", onclick: () => setStatus(note, "wontfix") }, "Won't fix")
          : null,
        h("button", { type: "button", onclick: () => editNote(note) }, "Edit"),
        h("button", { type: "button", onclick: () => removeNote(note) }, "Delete"))
      : null);
}

function renderRevisionReview(note) {
  const review = note.revision_review;
  const finding = note.llm_responses?.at(-1)?.source === "pipeline_finding";
  const labels = {pending: finding ? "Suggestion awaiting review" : "Awaiting revision review", accepted: finding ? "Suggestion dismissed" : "Revision accepted",
    rejected: "Changes requested", reopened: finding ? "Suggestion reopened" : "Revision reopened"};
  const history = note.revision_reviews || [];
  return h("section", {class: "revision-review", "aria-label": "Revision review"},
    h("strong", {class: `revision-state ${review.state}`}, labels[review.state]),
    review.state === "rejected" ? h("p", {class: "revision-request"}, review.request.body) : null,
    review.state === "rejected" ? h("p", {class: "sheet-note"},
      "Your feedback is saved. The next pipeline run is started separately outside this website.") : null,
    !review.current ? h("p", {class: "sheet-note"},
      "This response refers to earlier text. Review the current edition before deciding.") : null,
    state.session.can_write && review.current ? h("div", {class: "revision-actions"},
      review.state === "accepted"
        ? h("button", {class: "btn small", type: "button", onclick: () => decideRevision(note, "reopened")}, finding ? "Reopen suggestion" : "Reopen revision")
        : [h("button", {class: "btn small", type: "button", onclick: () => decideRevision(note, "accepted")}, finding ? "Dismiss suggestion" : "Accept revision"),
           h("button", {class: "btn small", type: "button", onclick: () => rejectRevision(note)},
             review.state === "rejected" ? "Update revision request" : finding ? "Request change with comment" : "Reject with comment")]) : null,
    history.length ? h("details", {class: "revision-history"},
      h("summary", {}, `Review history (${history.length})`),
      ...history.map(event => h("div", {class: "revision-event"},
        h("p", {class: "sheet-note"}, `${labels[event.action]} · ${event.author || "Reviewer"} · ${displayTime(event.created_at)}`),
        event.body ? h("p", {class: "note-body"}, event.body) : null,
        h("details", {}, h("summary", {}, "Response reviewed"), h("p", {}, event.response.body))))) : null);
}

async function saveRevisionDecision(note, action, body = "") {
  const review = note.revision_review;
  const updated = await api(`/api/comments/${note.id}/revision-review`, {
    method: "POST", body: {action, body, response_id: review.response_id,
      version: review.version, chapter_anchor: review.chapter_anchor,
      publication_revision: review.publication_revision}
  });
  replaceComment(updated);
}

async function decideRevision(note, action) {
  try {
    await saveRevisionDecision(note, action);
    if (note.pipeline_review) {
      const card = document.querySelector(`.pipeline-card[data-review-id="${CSS.escape(note.id)}"]`);
      if (card) {
        const history = card.closest("#review-history");
        if (history) history.open = true;
        card.open = true;
        card.querySelector("summary").focus({preventScroll: true});
        card.scrollIntoView({block: "nearest"});
      }
    }
  }
  catch (err) { toast(err.message, "error"); }
}

function rejectRevision(note) {
  const finding = note.llm_responses?.at(-1)?.source === "pipeline_finding";
  const dialog = h("dialog", {class: "sheet"});
  const body = h("textarea", {rows: 6, "aria-label": "What should change?", required: true},
    note.revision_review.request?.body || "");
  const error = h("p", {class: "sheet-error", role: "alert"});
  const submit = h("button", {class: "btn primary", type: "button", onclick: async () => {
    if (!body.value.trim()) { error.textContent = "Describe what should change."; body.focus(); return; }
    submit.disabled = true;
    try { await saveRevisionDecision(note, "rejected", body.value.trim()); dialog.close(); }
    catch (err) { error.textContent = err.message; submit.disabled = false; }
  }}, "Save revision request");
  dialog.append(h("h2", {}, finding ? "Request a change" : "Reject revision with feedback"),
    h("p", {class: "sheet-note"}, "Explain what should change. Saving queues your feedback; the pipeline is run separately outside this website."),
    body, error, h("button", {class: "btn", type: "button", onclick: () => dialog.close()}, "Cancel"), submit);
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog); dialog.showModal(); body.focus();
}

function renderLlmResponse(response) {
  const action = labelize(response.action || "processed");
  const changed = Array.isArray(response.changed_paragraphs)
    ? response.changed_paragraphs : [];
  const meta = [
    response.segment_id ? `chapter ${response.segment_id}` : null,
    displayTime(response.processed_at),
    response.draft_changed ? "draft changed" : "no draft change",
  ].filter(Boolean).join(" · ");
  return h("div", { class: `llm-response ${response.action || "processed"}` },
    h("div", { class: "llm-response-head" },
      h("span", { class: `tag llm-${response.action || "processed"}` },
        response.source === "pipeline_finding" ? "Critic finding" : response.source === "pipeline_repair" ? "Pipeline repairs" : `LLM ${action}`),
      meta ? h("span", { class: "llm-response-meta" }, meta) : null),
    h("p", { class: "llm-response-body" }, response.body),
    changed.length
      ? h("p", { class: "llm-response-changes" },
        `Changed draft ${changed.join(", ")}`)
      : null);
}

async function setStatus(note, status) {
  try {
    const updated = await api(`/api/comments/${note.id}`, { method: "PATCH", body: { status } });
    replaceComment(updated);
  } catch (err) { toast(err.message, "error"); }
}

async function removeNote(note) {
  try {
    await api(`/api/comments/${note.id}`, { method: "DELETE" });
    removeLocalComment(note);
    if (state.media) renderMediaBody(); else renderChapterBody();
  } catch (err) { toast(err.message, "error"); }
}

function replaceComment(updated) {
  const list = localCommentList(updated);
  const at = list.findIndex((c) => c.id === updated.id);
  if (at >= 0) list[at] = updated; else list.push(updated);
  if (state.media) renderMediaBody(); else renderChapterBody();
}

function localCommentList(note) {
  if (state.media) return state.media.comments;
  if (note.scope === "book" || note.segment_id === "__book__") {
    state.chapter.book_comments = state.chapter.book_comments || [];
    return state.chapter.book_comments;
  }
  state.chapter.comments = state.chapter.comments || [];
  return state.chapter.comments;
}

function removeLocalComment(note) {
  if (state.media) { state.media.comments = state.media.comments.filter(c => c.id !== note.id); return; }
  if (note.scope === "book" || note.segment_id === "__book__") {
    state.chapter.book_comments = (state.chapter.book_comments || [])
      .filter((c) => c.id !== note.id);
    return;
  }
  state.chapter.comments = (state.chapter.comments || []).filter((c) => c.id !== note.id);
  bumpRailCount(-1);
}

function bumpRailCount(delta) {
  const ch = state.book.chapters.find((c) => c.segment_id === state.chapter.segment_id);
  if (!ch) return;
  ch.comments = ch.comments || { total: 0 };
  ch.comments.total = Math.max(0, (ch.comments.total || 0) + delta);
  renderRail(state.chapter.segment_id);
}

async function editNote(note) {
  const dialog = h("dialog", { class: "sheet" });
  const body = h("textarea", { rows: 6, "aria-label": "Edit note" }, note.body);
  const error = h("p", { class: "sheet-error" });
  dialog.append(h("h2", {}, "Edit note"), body, error,
    h("button", { class: "btn", onclick: () => dialog.close() }, "Cancel"),
    h("button", { class: "btn primary", onclick: async () => {
      try {
        const updated = await api(`/api/comments/${note.id}`, { method: "PATCH", body: { body: body.value } });
        dialog.close(); replaceComment(updated);
      } catch (err) { error.textContent = err.message; }
    } }, "Save"));
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog); dialog.showModal(); body.focus();
}

async function renderMedia() {
  state.chapter = null;
  state.media = await api(`/api/books/${encodeURIComponent(state.book.book_id)}/media${selectionQuery()}`);
  el.topbarBook.hidden = false;
  el.bookTitle.textContent = state.book.title;
  el.bookAuthor.textContent = state.book.author || "";
  el.rail.hidden = false; el.layout.classList.remove("no-rail");
  el.rail.replaceChildren(h("a", { href: "/", "data-route": true }, "← All books"), publicationNav(),
    h("a", { class: "btn small", href: `/api/books/${encodeURIComponent(state.book.book_id)}/edits.json${selectionQuery()}` }, "Download notes"));
  renderMediaBody();
}

function renderMediaBody() {
  const media = state.media;
  const cards = media.targets.map(target => {
    const player = target.kind === "audio"
      ? h("audio", { controls: true, preload: "metadata", src: target.url, "aria-label": target.title })
      : h("img", { src: target.url, alt: target.title, loading: "lazy", class: "graphic-frame" });
    const notes = media.comments.filter(c => c.target_id === target.id);
    const composer = h("div", { class: "media-composer" });
    const add = h("button", { class: "btn small", onclick: () => {
      if (!state.session.can_write) { el.signin.showModal(); return; }
      const time = h("input", { type: "number", min: "0", step: "0.01", value: target.kind === "audio" ? player.currentTime.toFixed(2) : "0", "aria-label": "Seconds in audio chunk" });
      if (target.duration_seconds !== null && target.duration_seconds !== undefined) time.max = String(target.duration_seconds);
      const body = h("textarea", { placeholder: "Describe the issue or suggested improvement", "aria-label": "Media note" });
      composer.replaceChildren(...[target.kind === "audio" ? h("label", {}, "Seconds in this chunk", time) : null,
        body, h("button", { class: "btn primary", onclick: async () => {
          try {
            const row = await api(`/api/books/${encodeURIComponent(state.book.book_id)}/comments`, {
              method: "POST", body: { scope: target.kind, target_id: target.id, target_revision: target.revision,
                publication_revision: media.publication_revision, timestamp_seconds: target.kind === "audio" ? Number(time.value) : null,
                body: body.value, severity: "minor", kind: "other" } });
            media.comments.push(row); renderMediaBody(); toast("Media note added.");
          } catch (err) { toast(err.message, "error"); }
        } }, "Add note")].filter(Boolean));
      body.focus();
    } }, target.kind === "audio" ? "Comment at playback time" : "Comment on this frame");
    return h("section", { class: "media-card", id: target.id }, h("h2", {}, target.title),
      h("p", { class: "revision-label" }, `${target.kind} · ${target.id}`), player, add, composer,
      h("div", { class: "scope-note-list" }, notes.map(renderNote)));
  });
  const orphaned = media.comments.filter(c => !media.targets.some(t => t.id === c.target_id));
  el.main.replaceChildren(...[h("h1", {}, "Audio & graphic novel"),
    h("p", { class: "revision-label" }, `Edition ${media.publication_revision ? media.publication_revision.slice(0, 12) : "local artifacts"}`),
    ...cards, !cards.length ? h("p", {}, "No media was published for this edition.") : null,
    orphaned.length ? h("section", { class: "scope-notes" }, h("h2", {}, "Notes on removed targets"), ...orphaned.map(renderNote)) : null].filter(Boolean));
}

/* ------------------------------------------------------------- composer */

function openComposer(draftPara, quote) {
  if (!state.session.can_write) {
    el.signin.showModal();
    return;
  }
  state.composerFor = draftPara;
  state.scopeComposer = null;
  state.composerQuote = quote || "";
  state.current = draftPara;
  renderChapterBody();
  const box = document.querySelector(".composer textarea");
  if (box) {
    box.focus();
    document.getElementById(`p-${draftPara}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

function closeComposer() {
  state.composerFor = null;
  state.scopeComposer = null;
  state.composerQuote = "";
  renderChapterBody();
}

function openScopeComposer(scope) {
  if (!state.session.can_write) {
    el.signin.showModal();
    return;
  }
  state.scopeComposer = scope;
  state.composerFor = null;
  state.composerQuote = "";
  renderChapterBody();
  document.querySelector(".scope-composer textarea")?.focus();
}

function renderScopeNotes(title, notes, scope) {
  const count = notes.length;
  if (!count && state.scopeComposer !== scope) return null;
  return h("section", { class: "scope-notes" },
    h("div", { class: "scope-notes-head" },
      h("h2", {}, title),
      count ? h("span", {}, plural(count, "note", "notes")) : null,
      h("button", { class: "btn small", type: "button", onclick: () => openScopeComposer(scope) },
        "Add")),
    state.scopeComposer === scope ? renderScopeComposer(scope) : null,
    count ? h("div", { class: "scope-note-list" }, notes.map(renderNote)) : null);
}

function renderScopeComposer(scope) {
  const severity = h("select", { id: `composer-severity-${scope}` },
    state.session.severities.map((s) =>
      h("option", { value: s, selected: s === "minor" }, s)));
  const kind = h("select", { id: `composer-kind-${scope}` },
    state.session.kinds.map((k) =>
      h("option", { value: k, selected: k === "continuity" }, k)));
  const body = h("textarea", {
    placeholder: scope === "book"
      ? "What should the fix pass understand about the whole book?"
      : "What should the fix pass understand about this chapter?",
    onkeydown: (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); }
      if (e.key === "Escape") { e.preventDefault(); closeComposer(); }
    },
  });

  async function submit() {
    const text = body.value.trim();
    if (!text) { body.focus(); return; }
    try {
      const payload = {
        publication_revision: state.chapter.publication_revision,
        scope,
        severity: severity.value,
        kind: kind.value,
        body: text,
      };
      if (scope === "chapter") payload.segment_id = state.chapter.segment_id;
      const created = await api(
        `/api/books/${encodeURIComponent(state.book.book_id)}/comments`, {
          method: "POST",
          body: payload,
        });
      localCommentList(created).push(created);
      if (scope === "chapter") bumpRailCount(1);
      state.scopeComposer = null;
      renderChapterBody();
      toast("Note added to the queue.");
    } catch (err) { toast(err.message, "error"); }
  }

  return h("div", { class: "composer scope-composer" },
    body,
    h("div", { class: "row" }, severity, kind),
    h("div", { class: "actions" },
      h("span", { class: "hint" }, "⌘↵ to save"),
      h("button", { class: "btn small", type: "button", onclick: closeComposer }, "Cancel"),
      h("button", { class: "btn small primary", type: "button", onclick: submit }, "Add note")));
}

function renderComposer(block) {
  const severity = h("select", { id: "composer-severity" },
    state.session.severities.map((s) =>
      h("option", { value: s, selected: s === "minor" }, s)));
  const kind = h("select", { id: "composer-kind" },
    state.session.kinds.map((k) =>
      h("option", { value: k, selected: k === "fidelity" }, k)));
  const body = h("textarea", {
    id: "composer-body",
    placeholder: "What needs fixing here, and what should it become?",
    onkeydown: (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); }
      if (e.key === "Escape") { e.preventDefault(); closeComposer(); }
    },
  });

  async function submit() {
    const text = body.value.trim();
    if (!text) { body.focus(); return; }
    try {
      const created = await api(
        `/api/books/${encodeURIComponent(state.book.book_id)}/comments`, {
          method: "POST",
          body: {
            publication_revision: state.chapter.publication_revision,
            segment_id: state.chapter.segment_id,
            draft_para: block.draft_para,
            quote: state.composerQuote,
            severity: severity.value,
            kind: kind.value,
            body: text,
          },
        });
      state.chapter.comments.push(created);
      state.composerFor = null;
      state.composerQuote = "";
      bumpRailCount(1);
      renderChapterBody();
      toast("Note added to the queue.");
    } catch (err) { toast(err.message, "error"); }
  }

  return h("div", { class: "composer" },
    state.composerQuote ? h("p", { class: "composer-quote" }, `“${state.composerQuote}”`) : null,
    body,
    h("div", { class: "row" }, severity, kind),
    h("div", { class: "actions" },
      h("span", { class: "hint" }, "⌘↵ to save"),
      h("button", { class: "btn small", type: "button", onclick: closeComposer }, "Cancel"),
      h("button", { class: "btn small primary", type: "button", onclick: submit }, "Add note")));
}

/* ------------------------------------------------------ text selection */

document.addEventListener("mouseup", () => {
  const selection = window.getSelection();
  const text = selection ? selection.toString().trim() : "";
  if (!text || !selection.rangeCount) { el.tip.hidden = true; return; }
  const paragraph = selection.anchorNode?.parentElement?.closest(".draft[data-para]");
  if (!paragraph) { el.tip.hidden = true; return; }
  const rect = selection.getRangeAt(0).getBoundingClientRect();
  el.tip.style.top = `${rect.bottom + window.scrollY + 6}px`;
  el.tip.style.left = `${rect.left + window.scrollX}px`;
  el.tip.hidden = false;
  el.tipBtn.onclick = () => {
    el.tip.hidden = true;
    openComposer(Number(paragraph.dataset.para), text.slice(0, 600));
  };
});

document.addEventListener("mousedown", (e) => {
  if (!el.tip.contains(e.target)) el.tip.hidden = true;
});

/* -------------------------------------------------------------- keyboard */

document.addEventListener("keydown", (event) => {
  const tag = event.target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || event.metaKey || event.ctrlKey) {
    if (event.key === "Escape" && (state.composerFor !== null || state.scopeComposer !== null)) closeComposer();
    return;
  }
  if (!state.chapter) return;

  const visible = state.chapter.blocks.filter(matchesFilters);
  if (!visible.length) return;
  const at = visible.findIndex((b) => b.draft_para === state.current);

  switch (event.key) {
    case "j": moveTo(visible[Math.min(visible.length - 1, at + 1)] || visible[0]); break;
    case "k": moveTo(at <= 0 ? visible[0] : visible[at - 1]); break;
    case "u": {
      const next = visible.slice(at + 1).find((b) => b.note_key === "unsupported")
        || visible.find((b) => b.note_key === "unsupported");
      if (next) moveTo(next); else toast("No unsupported paragraphs in this chapter.");
      break;
    }
    case "c": if (state.current !== null) { event.preventDefault(); openComposer(state.current, ""); } break;
    case "[": stepChapter(-1); break;
    case "]": stepChapter(1); break;
    case "/": event.preventDefault(); document.getElementById("chapter-search")?.focus(); break;
    case "Escape": if (state.composerFor !== null || state.scopeComposer !== null) closeComposer(); break;
    default: return;
  }
});

function moveTo(block) {
  if (!block) return;
  state.current = block.draft_para;
  renderChapterBody();
  // Keep the address bar on the paragraph being read, so the URL is always
  // shareable without adding a history entry per keystroke.
  const url = new URL(location.href);
  url.searchParams.set("p", String(block.draft_para));
  history.replaceState({}, "", url);
  document.getElementById(`p-${block.draft_para}`)
    ?.scrollIntoView({ block: "center", behavior: "smooth" });
}

function stepChapter(delta) {
  const chapters = state.book.chapters;
  const at = chapters.findIndex((c) => c.segment_id === state.chapter.segment_id);
  const next = chapters[at + delta];
  if (next) go(bookRoute({ c: next.segment_id }));
}

/* ----------------------------------------------------------------- boot */

async function render() {
  const { bookId, segmentId, draftPara } = route();
  try {
    if (!bookId) { state.book = null; await renderIndex(); }
    else await renderChapter(bookId, segmentId, draftPara);
  } catch (err) {
    el.main.replaceChildren(h("p", { class: "empty" }, err.message));
  }
}

(async function boot() {
  await loadSession();
  await render();
})();
