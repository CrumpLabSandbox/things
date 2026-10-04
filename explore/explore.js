/* Explore page: loads data/public/artworks.json, vocabulary.json and
   similarity.json and renders tag facets, a search box, a thumbnail grid,
   a 2D map and a detail view with similar pieces. Plain JavaScript, no
   dependencies. Paths are relative to the site root, so this works both in
   the rendered Quarto site and when the repo root is served directly. */
(function () {
  "use strict";

  // Resolve data paths relative to the directory this script was loaded from.
  var scriptEl = document.currentScript;
  var base = scriptEl ? scriptEl.src.replace(/explore\/explore\.js(\?.*)?$/, "") : "";
  var PATHS = {
    artworks: base + "data/public/artworks.json",
    vocabulary: base + "data/public/vocabulary.json",
    similarity: base + "data/public/similarity.json",
    series: base + "data/public/series.json"
  };

  var FACETS = ["series", "characters", "subjects", "themes", "style", "mood", "setting", "composition", "line", "color_words", "medium", "year", "elements"];
  var FACET_LABEL = { color_words: "colour", series: "series", medium: "medium", year: "year" };
  var MAX_CHIPS = 18;

  var state = { records: [], byId: {}, sim: null, vocab: null, filters: {}, query: "", sort: "date-desc", view: "grid", expanded: {} };

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k.indexOf("on") === 0) e.addEventListener(k.slice(2), attrs[k]);
      else if (k === "hidden") { if (attrs[k]) e.hidden = true; }
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c == null) return;
      e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return e;
  }

  function facetValues(rec, facet) {
    if (facet === "series") return [rec.catalog.series];
    if (facet === "medium") return rec.catalog.medium ? [rec.catalog.medium] : [];
    if (facet === "year") return rec.catalog.year ? [String(rec.catalog.year)] : [];
    return (rec.described && rec.described[facet]) || [];
  }

  function searchText(rec) {
    if (rec._text) return rec._text;
    var d = rec.described || {};
    var parts = [rec.catalog.title, rec.catalog.series, rec.catalog.medium, rec.catalog.caption, d.alt_text];
    FACETS.forEach(function (f) { parts = parts.concat(facetValues(rec, f)); });
    rec._text = parts.filter(Boolean).join(" | ").toLowerCase();
    return rec._text;
  }

  function matches(rec) {
    var ok = Object.keys(state.filters).every(function (facet) {
      var want = state.filters[facet];
      if (!want.length) return true;
      var have = facetValues(rec, facet);
      return want.every(function (t) { return have.indexOf(t) >= 0; });
    });
    if (!ok) return false;
    if (state.query) {
      var words = state.query.toLowerCase().split(/\s+/).filter(Boolean);
      var text = searchText(rec);
      return words.every(function (w) { return text.indexOf(w) >= 0; });
    }
    return true;
  }

  function sorted(list) {
    var s = state.sort;
    var key = {
      "date-desc": function (r) { return -(Date.parse(r.catalog.date) || 0); },
      "date-asc": function (r) { return Date.parse(r.catalog.date) || 0; },
      "series": function (r) { return r.catalog.series + " " + r.catalog.title; },
      "saturation": function (r) { return -(r.measured.colorfulness || 0); },
      "edges": function (r) { return -(r.measured.edge_density || 0); },
      "busyness": function (r) { return -(r.measured.busyness || 0); },
      "lightness": function (r) { return -(r.measured.light_fraction || 0); }
    }[s];
    return list.slice().sort(function (a, b) { var ka = key(a), kb = key(b); return ka < kb ? -1 : ka > kb ? 1 : 0; });
  }

  function visible() { return sorted(state.records.filter(matches)); }

  function toggleFilter(facet, tag) {
    var list = state.filters[facet] || (state.filters[facet] = []);
    var i = list.indexOf(tag);
    if (i >= 0) list.splice(i, 1); else list.push(tag);
    render();
  }

  function thumb(rec) { return base + rec.measured.thumbnail; }
  function full(rec) { return base + rec.catalog.image.path; }

  function card(rec, small) {
    var c = el("div", { class: "x-card", title: rec.catalog.title, onclick: function () { openDetail(rec.id); } }, [
      el("img", { src: thumb(rec), alt: (rec.described && rec.described.alt_text) || rec.catalog.title, loading: "lazy" }),
      small ? null : el("div", { class: "x-cap" }, [rec.catalog.title])
    ]);
    return c;
  }

  // ------------------------------------------------------------ facets
  function renderFacets(list) {
    var box = document.getElementById("x-facets");
    box.innerHTML = "";
    FACETS.forEach(function (facet) {
      var counts = {};
      list.forEach(function (r) { facetValues(r, facet).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; }); });
      var active = state.filters[facet] || [];
      var tags = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a] || a.localeCompare(b); });
      if (facet === "year") tags.sort(function (a, b) { return b.localeCompare(a); });
      if (!tags.length && !active.length) return;
      var showAll = state.expanded[facet];
      var shown = showAll ? tags : tags.slice(0, MAX_CHIPS);
      active.forEach(function (t) { if (shown.indexOf(t) < 0) shown.unshift(t); });
      var chips = shown.map(function (t) {
        return el("span", { class: "x-chip" + (active.indexOf(t) >= 0 ? " is-on" : ""), onclick: function () { toggleFilter(facet, t); } },
          [t, el("small", {}, [String(counts[t] || 0)])]);
      });
      if (tags.length > MAX_CHIPS) {
        chips.push(el("span", { class: "x-chip", style: "background:none;text-decoration:underline", onclick: function () { state.expanded[facet] = !showAll; render(); } },
          [showAll ? "fewer" : "+" + (tags.length - MAX_CHIPS) + " more"]));
      }
      var narrow = window.matchMedia && window.matchMedia("(max-width: 800px)").matches;
      var open = active.length > 0 || (!narrow && ["series", "characters", "subjects", "themes"].indexOf(facet) >= 0);
      var det = el("details", { class: "x-facet" }, [
        el("summary", {}, [FACET_LABEL[facet] || facet.replace("_", " ")]),
        el("div", { class: "x-tags" }, chips)
      ]);
      det.open = open;
      box.appendChild(det);
    });
    var act = document.getElementById("x-active");
    act.innerHTML = "";
    Object.keys(state.filters).forEach(function (facet) {
      state.filters[facet].forEach(function (t) {
        act.appendChild(el("span", { class: "x-chip is-on", onclick: function () { toggleFilter(facet, t); } }, [t + " ×"]));
      });
    });
  }

  // ------------------------------------------------------------ grid and map
  function renderGrid(list) {
    var g = document.getElementById("x-grid");
    g.innerHTML = "";
    list.forEach(function (r) { g.appendChild(card(r)); });
  }

  function renderMap(list) {
    var m = document.getElementById("x-map");
    m.innerHTML = "";
    if (!state.sim) return;
    var shown = {};
    list.forEach(function (r) { shown[r.id] = true; });
    state.records.forEach(function (r) {
      var xy = state.sim.layout[r.id];
      if (!xy) return;
      var d = el("div", { class: "x-dot" + (shown[r.id] ? "" : " is-dim"), title: r.catalog.title, style: "left:" + (xy[0] * 92 + 4) + "%;top:" + (xy[1] * 92 + 4) + "%", onclick: function () { openDetail(r.id); } },
        [el("img", { src: thumb(r), alt: "", loading: "lazy" })]);
      m.appendChild(d);
    });
  }

  function render() {
    var list = visible();
    document.getElementById("x-count").textContent = list.length + " of " + state.records.length + " pieces";
    renderFacets(list);
    if (state.view === "grid") renderGrid(list); else renderMap(list);
    document.getElementById("x-grid").hidden = state.view !== "grid";
    document.getElementById("x-map").hidden = state.view !== "map";
    document.querySelectorAll(".x-views button").forEach(function (b) { b.classList.toggle("is-on", b.getAttribute("data-view") === state.view); });
  }

  // ------------------------------------------------------------ detail
  var detailOrder = [];
  function openDetail(id) {
    var rec = state.byId[id];
    if (!rec) return;
    detailOrder = visible().map(function (r) { return r.id; });
    if (detailOrder.indexOf(id) < 0) detailOrder = state.records.map(function (r) { return r.id; });
    var box = document.getElementById("x-detail");
    box.innerHTML = "";
    var d = rec.described || {};
    var c = rec.catalog;
    var meta = [c.series, c.medium, c.surface, c.year, c.image.width + "×" + c.image.height].filter(Boolean).join(" · ");
    var right = [
      el("h2", {}, [c.title]),
      el("div", { class: "x-meta" }, [meta, " · ", el("a", { href: base + c.page.html }, ["page"]), c.print_url ? " · " : null, c.print_url ? el("a", { href: c.print_url }, ["print"]) : null]),
      d.alt_text ? el("div", { class: "x-alt" }, [d.alt_text]) : null
    ];
    if (rec.measured.palette) {
      right.push(el("div", { class: "x-palette" }, rec.measured.palette.map(function (p) {
        return el("span", { style: "background:" + p.hex + ";flex:" + Math.max(p.fraction, 0.03), title: p.hex });
      })));
    }
    ["characters", "subjects", "themes", "style", "mood", "setting", "composition", "line", "color_words", "elements"].forEach(function (f) {
      var vals = facetValues(rec, f);
      if (!vals.length) return;
      right.push(el("div", { class: "x-facetline" }, [el("b", {}, [FACET_LABEL[f] || f.replace("_", " ")])].concat(vals.map(function (t) {
        return el("span", { class: "x-chip", onclick: function () { closeDetail(); state.filters = {}; state.filters[f] = [t]; render(); } }, [t, " "]);
      }))));
    });
    if (rec.relations && rec.relations.length) {
      right.push(el("h3", {}, ["relations"]));
      rec.relations.forEach(function (rel) {
        var t = state.byId[rel.target];
        right.push(el("div", { class: "x-rel" }, [rel.type.replace(/_/g, " "), " ",
          el("a", { onclick: function () { openDetail(rel.target); } }, [t ? t.catalog.title : rel.target]),
          rel.note ? " — " + rel.note : ""]));
      });
    }
    if (state.sim && state.sim.neighbours[id]) {
      var n = state.sim.neighbours[id];
      [["looks like", "visual"], ["tagged like", "tags"], ["reads like", "text"]].forEach(function (pair) {
        right.push(el("h3", {}, [pair[0]]));
        right.push(el("div", { class: "x-strip" }, n[pair[1]].map(function (x) { return state.byId[x[0]] ? card(state.byId[x[0]], true) : null; })));
      });
    }
    var idx = detailOrder.indexOf(id);
    box.appendChild(el("button", { class: "x-close", type: "button", onclick: closeDetail }, ["close ×"]));
    box.appendChild(el("button", { class: "x-nav x-prev", type: "button", onclick: function () { openDetail(detailOrder[(idx - 1 + detailOrder.length) % detailOrder.length]); } }, ["‹"]));
    box.appendChild(el("button", { class: "x-nav x-next", type: "button", onclick: function () { openDetail(detailOrder[(idx + 1) % detailOrder.length]); } }, ["›"]));
    box.appendChild(el("div", { class: "x-inner" }, [
      el("div", {}, [el("img", { class: "x-big", src: full(rec), alt: d.alt_text || c.title })]),
      el("div", {}, right)
    ]));
    box.hidden = false;
    box.scrollTop = 0;
    document.body.style.overflow = "hidden";
    if (history.replaceState) history.replaceState(null, "", "#" + encodeURIComponent(id));
  }

  function closeDetail() {
    document.getElementById("x-detail").hidden = true;
    document.body.style.overflow = "";
    if (history.replaceState) history.replaceState(null, "", location.pathname + location.search);
  }

  // ------------------------------------------------------------ boot
  function fetchJson(url) { return fetch(url).then(function (r) { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); }); }

  function boot() {
    Promise.all([fetchJson(PATHS.artworks), fetchJson(PATHS.vocabulary).catch(function () { return null; }), fetchJson(PATHS.similarity).catch(function () { return null; })])
      .then(function (res) {
        state.records = res[0];
        state.records.forEach(function (r) { state.byId[r.id] = r; });
        state.vocab = res[1];
        state.sim = res[2];
        document.getElementById("x-search").addEventListener("input", function (e) { state.query = e.target.value; render(); });
        document.getElementById("x-sort").addEventListener("change", function (e) { state.sort = e.target.value; render(); });
        document.getElementById("x-clear").addEventListener("click", function () { state.filters = {}; state.query = ""; document.getElementById("x-search").value = ""; render(); });
        document.querySelectorAll(".x-views button").forEach(function (b) { b.addEventListener("click", function () { state.view = b.getAttribute("data-view"); render(); }); });
        document.addEventListener("keydown", function (e) {
          var open = !document.getElementById("x-detail").hidden;
          if (!open) return;
          if (e.key === "Escape") closeDetail();
          if (e.key === "ArrowRight") document.querySelector(".x-next").click();
          if (e.key === "ArrowLeft") document.querySelector(".x-prev").click();
        });
        render();
        if (location.hash.length > 1) {
          var id = decodeURIComponent(location.hash.slice(1));
          if (state.byId[id]) openDetail(id);
        }
      })
      .catch(function (err) {
        document.getElementById("x-grid").textContent = "Could not load the collection data: " + err.message;
      });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
