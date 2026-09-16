/* ==========================================================================
   Integrated Government Services System — interaction layer.
   Every feature here degrades safely: if JS fails to run, forms still
   submit normally and links still navigate normally.
   ========================================================================== */
(function () {
  "use strict";

  /* ------------------------------------------------------------ load bar */
  var bar = document.createElement("div");
  bar.className = "load-bar";
  document.documentElement.appendChild(bar);
  requestAnimationFrame(function () { bar.style.width = "70%"; });
  window.addEventListener("load", function () {
    bar.style.width = "100%";
    setTimeout(function () { bar.classList.add("done"); }, 150);
    setTimeout(function () { bar.remove(); }, 500);
  });
  document.querySelectorAll("a[href]").forEach(function (a) {
    if (a.target === "_blank" || a.getAttribute("href").indexOf("#") === 0 ||
        a.hasAttribute("data-no-fade") || a.getAttribute("href").indexOf("mailto:") === 0) return;
    a.addEventListener("click", function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey) return;
      var main = document.querySelector(".page-fade");
      if (main) { main.style.transition = "opacity .15s ease"; main.style.opacity = "0"; }
    });
  });

  /* -------------------------------------------------------------- theme */
  var THEME_KEY = "igss-theme";
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", t === "dark" ? "true" : "false");
    });
  }
  var saved = localStorage.getItem(THEME_KEY) ||
    (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(saved);
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  });

  /* -------------------------------------------------------- scroll reveal */
  var revealables = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window && revealables.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    revealables.forEach(function (el) { io.observe(el); });
    // Safety net: a very tall page, an odd viewport, or a visitor who never
    // scrolls should still see everything eventually rather than nothing.
    setTimeout(function () {
      revealables.forEach(function (el) { el.classList.add("in-view"); });
    }, 3000);
  } else {
    revealables.forEach(function (el) { el.classList.add("in-view"); });
  }

  /* -------------------------------------------------------- counters */
  var counters = document.querySelectorAll("[data-counter]");
  function runCounter(el) {
    var target = parseFloat(el.getAttribute("data-counter"));
    var suffix = el.getAttribute("data-counter-suffix") || "";
    var dur = 1100, start = null;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toLocaleString() + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  if ("IntersectionObserver" in window && counters.length) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { runCounter(entry.target); cio.unobserve(entry.target); }
      });
    }, { threshold: 0.4 });
    counters.forEach(function (el) { cio.observe(el); });
    setTimeout(function () {
      counters.forEach(function (el) {
        if (el.textContent === "0") runCounter(el);
      });
    }, 3000);
  } else {
    counters.forEach(runCounter);
  }

  /* ---------------------------------------------------------- ripple fx */
  document.querySelectorAll(".btn").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      var rect = btn.getBoundingClientRect();
      var span = document.createElement("span");
      var size = Math.max(rect.width, rect.height);
      span.className = "ripple";
      span.style.width = span.style.height = size + "px";
      span.style.left = (e.clientX - rect.left - size / 2) + "px";
      span.style.top = (e.clientY - rect.top - size / 2) + "px";
      btn.appendChild(span);
      setTimeout(function () { span.remove(); }, 650);
    });
  });

  /* ------------------------------------------------------------- toasts */
  var stack = document.createElement("div");
  stack.className = "toast-stack";
  stack.setAttribute("aria-live", "polite");
  document.body.appendChild(stack);
  window.toast = function (message, type) {
    type = type || "info";
    var el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = "<span>" + message + "</span><button aria-label=\"Dismiss\">&times;</button>";
    el.querySelector("button").addEventListener("click", function () { dismiss(el); });
    stack.appendChild(el);
    var timer = setTimeout(function () { dismiss(el); }, 5000);
    function dismiss(node) {
      clearTimeout(timer);
      node.classList.add("leaving");
      setTimeout(function () { node.remove(); }, 300);
    }
  };
  document.querySelectorAll(".alert[data-dismissable]").forEach(function (el) {
    var type = el.className.indexOf("alert-danger") > -1 ? "danger" :
               el.className.indexOf("alert-success") > -1 ? "success" : "info";
    window.toast(el.textContent.trim(), type);
  });

  /* ------------------------------------------------------------- modals */
  document.querySelectorAll("[data-modal-target]").forEach(function (trigger) {
    trigger.addEventListener("click", function (e) {
      var sel = trigger.getAttribute("data-modal-target");
      var modal = document.querySelector(sel);
      if (!modal) return;
      e.preventDefault();
      modal.classList.add("open");
      var first = modal.querySelector("input, button, textarea, select");
      if (first) first.focus();
    });
  });
  document.querySelectorAll(".modal-backdrop").forEach(function (modal) {
    modal.addEventListener("click", function (e) {
      if (e.target === modal || e.target.hasAttribute("data-modal-close")) {
        modal.classList.remove("open");
      }
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-backdrop.open").forEach(function (m) { m.classList.remove("open"); });
      document.querySelectorAll(".lightbox-backdrop.open").forEach(function (m) { m.classList.remove("open"); });
      document.querySelectorAll(".dropdown-panel.open").forEach(function (m) { m.classList.remove("open"); });
    }
  });

  /* -------------------------------------------------- confirm -> modal */
  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    var msg = form.getAttribute("data-confirm");
    var backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML =
      '<div class="modal-box pop-in"><h3>Please confirm</h3><p style="margin-bottom:0">' + msg + '</p>' +
      '<div class="modal-actions"><button type="button" class="btn btn-outline" data-modal-close>Cancel</button>' +
      '<button type="button" class="btn btn-primary" data-confirm-go>Continue</button></div></div>';
    document.body.appendChild(backdrop);
    form.addEventListener("submit", function (e) {
      if (form.dataset.confirmed === "yes") return;
      e.preventDefault();
      backdrop.classList.add("open");
    });
    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop || e.target.hasAttribute("data-modal-close")) backdrop.classList.remove("open");
    });
    backdrop.querySelector("[data-confirm-go]").addEventListener("click", function () {
      form.dataset.confirmed = "yes";
      backdrop.classList.remove("open");
      form.requestSubmit ? form.requestSubmit() : form.submit();
    });
  });

  /* ---------------------------------------------------------- dropdowns */
  document.querySelectorAll("[data-dropdown]").forEach(function (root) {
    var trigger = root.querySelector("[data-dropdown-trigger]");
    var panel = root.querySelector(".dropdown-panel");
    if (!trigger || !panel) return;
    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = !panel.classList.contains("open");
      document.querySelectorAll(".dropdown-panel.open").forEach(function (p) { p.classList.remove("open"); });
      if (willOpen) panel.classList.add("open");
      if (willOpen && root.hasAttribute("data-dropdown-fetch")) loadDropdown(root, panel);
    });
    document.addEventListener("click", function () { panel.classList.remove("open"); });
    panel.addEventListener("click", function (e) { e.stopPropagation(); });
  });

  function loadDropdown(root, panel) {
    var url = root.getAttribute("data-dropdown-fetch");
    panel.innerHTML = '<div class="dropdown-empty"><span class="spinner"></span></div>';
    fetch(url).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.items || !data.items.length) {
        panel.innerHTML = '<div class="dropdown-empty">Nothing new right now.</div>';
        return;
      }
      panel.innerHTML = data.items.map(function (n) {
        return '<a class="dropdown-item" href="' + (n.link || "#") + '">' +
          '<strong>' + n.title + '</strong><br><span style="color:var(--ink-faint)">' +
          n.message + '</span></a>';
      }).join("");
    }).catch(function () {
      panel.innerHTML = '<div class="dropdown-empty">Could not load right now.</div>';
    });
  }

  /* --------------------------------------------------------- lightbox */
  var lightbox = document.createElement("div");
  lightbox.className = "lightbox-backdrop";
  lightbox.innerHTML = '<button class="lightbox-close" aria-label="Close">&times;</button><img alt="">';
  document.body.appendChild(lightbox);
  var lbImg = lightbox.querySelector("img");
  document.querySelectorAll("[data-lightbox]").forEach(function (el) {
    el.style.cursor = "zoom-in";
    el.addEventListener("click", function () {
      var src = el.getAttribute("data-lightbox") || el.src;
      lbImg.src = src;
      lightbox.classList.add("open");
    });
  });
  lightbox.addEventListener("click", function (e) {
    if (e.target === lightbox || e.target.classList.contains("lightbox-close")) {
      lightbox.classList.remove("open");
    }
  });

  /* ---------------------------------------------------------- carousels */
  document.querySelectorAll("[data-carousel]").forEach(function (root) {
    var track = root.querySelector(".carousel-track");
    var prev = root.querySelector(".carousel-nav.prev");
    var next = root.querySelector(".carousel-nav.next");
    var dotsWrap = root.querySelector(".carousel-dots");
    if (!track) return;
    var items = track.children.length;
    if (dotsWrap) {
      for (var i = 0; i < items; i++) {
        var d = document.createElement("button");
        if (i === 0) d.className = "active";
        d.setAttribute("aria-label", "Go to slide " + (i + 1));
        (function (idx) {
          d.addEventListener("click", function () { scrollToIndex(idx); });
        })(i);
        dotsWrap.appendChild(d);
      }
    }
    function scrollToIndex(idx) {
      var child = track.children[idx];
      if (child) track.scrollTo({ left: child.offsetLeft - track.offsetLeft, behavior: "smooth" });
    }
    function step(dir) {
      track.scrollBy({ left: dir * (track.clientWidth * 0.86), behavior: "smooth" });
    }
    if (prev) prev.addEventListener("click", function () { step(-1); });
    if (next) next.addEventListener("click", function () { step(1); });
    if (dotsWrap) {
      track.addEventListener("scroll", function () {
        var idx = Math.round(track.scrollLeft / track.clientWidth * 1.16);
        Array.prototype.forEach.call(dotsWrap.children, function (dot, i) {
          dot.classList.toggle("active", i === Math.min(idx, dotsWrap.children.length - 1));
        });
      }, { passive: true });
    }
  });

  /* ------------------------------------------------------------- kanban */
  document.querySelectorAll("[data-kanban]").forEach(function (board) {
    var url = board.getAttribute("data-kanban-url");
    board.querySelectorAll(".kanban-card").forEach(function (card) {
      card.setAttribute("draggable", "true");
      card.addEventListener("dragstart", function () {
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", function () { card.classList.remove("dragging"); });
    });
    board.querySelectorAll(".kanban-col").forEach(function (col) {
      col.addEventListener("dragover", function (e) {
        e.preventDefault();
        col.classList.add("drag-over");
      });
      col.addEventListener("dragleave", function () { col.classList.remove("drag-over"); });
      col.addEventListener("drop", function (e) {
        e.preventDefault();
        col.classList.remove("drag-over");
        var dragging = board.querySelector(".dragging");
        if (!dragging) return;
        var sourceCol = dragging.closest(".kanban-col");
        var list = col.querySelector(".kanban-list") || col;
        list.appendChild(dragging);
        updateColumnCount(col);
        if (sourceCol && sourceCol !== col) updateColumnCount(sourceCol);
        var newStatus = col.getAttribute("data-status");
        var appId = dragging.getAttribute("data-app-id");
        if (!url || !newStatus || !appId) return;
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ application_id: appId, status: newStatus })
        }).then(function (r) { return r.json(); }).then(function (d) {
          window.toast(d && d.message ? d.message : "Status updated.", d && d.ok ? "success" : "danger");
        }).catch(function () { window.toast("Could not reach the server — change not saved.", "danger"); });
      });
    });
    function updateColumnCount(col) {
      var badge = col.querySelector("h4 .muted");
      var list = col.querySelector(".kanban-list") || col;
      var n = list.querySelectorAll(".kanban-card").length;
      if (badge) badge.textContent = n;
      var empty = list.querySelector(".kanban-empty-note");
      if (n > 0 && empty) empty.remove();
      if (n === 0 && !list.querySelector(".kanban-empty-note")) {
        var note = document.createElement("p");
        note.className = "small muted mt-2 mb-0 kanban-empty-note";
        note.textContent = "Nothing here.";
        list.appendChild(note);
      }
    }
  });

  /* --------------------------------------------------------- favourites */
  document.querySelectorAll("[data-fav-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var url = btn.getAttribute("data-fav-toggle");
      fetch(url, { method: "POST", headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          btn.classList.toggle("active", d.favourited);
          btn.classList.add("bump");
          setTimeout(function () { btn.classList.remove("bump"); }, 350);
          window.toast(d.favourited ? "Added to your favourites." : "Removed from favourites.", "success");
        }).catch(function () { window.toast("Could not update favourites.", "danger"); });
    });
  });

  /* -------------------------------------------------------- star rating */
  document.querySelectorAll("[data-star-input]").forEach(function (row) {
    var hidden = document.querySelector(row.getAttribute("data-star-input"));
    var buttons = row.querySelectorAll("button");
    function paint(val) {
      buttons.forEach(function (b, i) { b.classList.toggle("on", i < val); });
    }
    buttons.forEach(function (b, i) {
      b.addEventListener("click", function () { hidden.value = i + 1; paint(i + 1); });
      b.addEventListener("mouseenter", function () { paint(i + 1); });
    });
    row.addEventListener("mouseleave", function () { paint(parseInt(hidden.value || "0", 10)); });
    paint(parseInt(hidden.value || "0", 10));
  });

  /* --------------------------------------------------------- switch UI */
  document.querySelectorAll(".switch").forEach(function (sw) {
    var input = document.getElementById(sw.getAttribute("data-for"));
    sw.addEventListener("click", function () {
      sw.classList.toggle("on");
      if (input) input.value = sw.classList.contains("on") ? "1" : "0";
    });
  });

  /* -------------------------------------------------- inline validation */
  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var invalid = false;
      form.querySelectorAll("[required]").forEach(function (input) {
        var field = input.closest(".field") || input.parentElement;
        if (!input.value.trim()) {
          field.classList.add("invalid");
          invalid = true;
        } else {
          field.classList.remove("invalid");
        }
      });
      if (invalid) {
        e.preventDefault();
        form.classList.add("shake");
        setTimeout(function () { form.classList.remove("shake"); }, 400);
        window.toast("Please fill in the highlighted fields.", "danger");
      }
    });
  });

  /* ---------------------------------------------- mobile sidebar toggle */
  var toggle = document.querySelector("[data-menu-toggle]");
  var sidebar = document.querySelector(".sidebar");
  if (toggle && sidebar) {
    sidebar.classList.add("collapsed");
    toggle.addEventListener("click", function () {
      sidebar.classList.toggle("collapsed");
      toggle.setAttribute("aria-expanded",
        sidebar.classList.contains("collapsed") ? "false" : "true");
    });
  }

  /* ------------------------------------------------- table filter/sort */
  document.querySelectorAll("[data-filter-table]").forEach(function (input) {
    var table = document.querySelector(input.getAttribute("data-filter-table"));
    if (!table) return;
    input.addEventListener("input", function () {
      var term = input.value.toLowerCase();
      table.querySelectorAll("tbody tr").forEach(function (row) {
        row.style.display = row.textContent.toLowerCase().indexOf(term) > -1 ? "" : "none";
      });
    });
  });
  document.querySelectorAll("[data-sort-table] th[data-sort-key]").forEach(function (th) {
    th.style.cursor = "pointer";
    th.addEventListener("click", function () {
      var table = th.closest("table");
      var tbody = table.querySelector("tbody");
      var idx = Array.prototype.indexOf.call(th.parentElement.children, th);
      var asc = th.getAttribute("data-dir") !== "asc";
      table.querySelectorAll("th[data-sort-key]").forEach(function (h) { h.removeAttribute("data-dir"); });
      th.setAttribute("data-dir", asc ? "asc" : "desc");
      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
      rows.sort(function (a, b) {
        var av = a.children[idx] ? a.children[idx].textContent.trim() : "";
        var bv = b.children[idx] ? b.children[idx].textContent.trim() : "";
        var an = parseFloat(av.replace(/[^0-9.\-]/g, "")), bn = parseFloat(bv.replace(/[^0-9.\-]/g, ""));
        var cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
        return asc ? cmp : -cmp;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });

  /* ------------------------------------------------------------ select filters */
  document.querySelectorAll("[data-select-filter]").forEach(function (sel) {
    var table = document.querySelector(sel.getAttribute("data-select-filter"));
    var col = parseInt(sel.getAttribute("data-select-col") || "0", 10);
    if (!table) return;
    sel.addEventListener("change", function () {
      var val = sel.value.toLowerCase();
      table.querySelectorAll("tbody tr").forEach(function (row) {
        if (!val) { row.style.display = ""; return; }
        var cell = row.children[col];
        row.style.display = cell && cell.textContent.toLowerCase().indexOf(val) > -1 ? "" : "none";
      });
    });
  });

  /* ------------------------------------------------------- password match */
  var pw = document.getElementById("password");
  var confirmField = document.getElementById("confirm");
  if (pw && confirmField) {
    var report = function () {
      confirmField.setCustomValidity(
        confirmField.value && pw.value !== confirmField.value
          ? "The two passwords do not match." : "");
    };
    pw.addEventListener("input", report);
    confirmField.addEventListener("input", report);
  }

  /* ------------------------------------------- dismiss flash messages */
  document.querySelectorAll(".alert[data-dismissable]").forEach(function (el) {
    setTimeout(function () { el.style.display = "none"; }, 9000);
  });

  /* --------------------------------------------------- live unread count */
  var bell = document.querySelector("[data-bell]");
  if (bell) {
    var countUrl = bell.getAttribute("data-count-url");
    setInterval(function () {
      if (!countUrl) return;
      fetch(countUrl)
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          var dot = bell.querySelector(".dot");
          if (d.unread > 0) {
            if (!dot) { dot = document.createElement("span"); dot.className = "dot"; bell.appendChild(dot); }
            dot.textContent = d.unread;
          } else if (dot) { dot.remove(); }
        }).catch(function () {});
    }, 45000);
  }

  /* ----------------------------------------------- file input filename */
  document.querySelectorAll("input[type=file]").forEach(function (input) {
    input.addEventListener("change", function () {
      var hint = input.parentElement.querySelector(".hint");
      if (hint && input.files.length) {
        hint.textContent = input.files.length === 1 ? input.files[0].name : input.files.length + " files selected";
      }
    });
  });

  /* -------------------------------------------------------- drag upload */
  document.querySelectorAll("[data-dropzone]").forEach(function (zone) {
    var input = zone.querySelector("input[type=file]");
    if (!input) return;
    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.add("drag-over"); });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.remove("drag-over"); });
    });
    zone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) {
        input.files = e.dataTransfer.files;
        input.dispatchEvent(new Event("change"));
      }
    });
  });
})();
