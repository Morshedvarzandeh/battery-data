/* Lemonergy Data — sortable tables on the battery pages. Progressive: the
 * tables are complete without it. Numbers sort by their data-v value. */
(function () {
  "use strict";
  document.querySelectorAll("table[data-sortable]").forEach(function (table) {
    var heads = table.querySelectorAll("thead th");
    heads.forEach(function (th, col) {
      th.setAttribute("aria-sort", "none");
      th.tabIndex = 0;
      function sort() {
        var dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
        heads.forEach(function (h) { h.setAttribute("aria-sort", "none"); });
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        var key = function (row) {
          var cell = row.cells[col];
          var v = cell.getAttribute("data-v");
          if (v !== null) return v === "" ? null : Number(v);
          return cell.textContent.trim().toLowerCase();
        };
        rows.sort(function (a, b) {
          var x = key(a), y = key(b);
          if (x === null && y === null) return 0;
          if (x === null) return 1;
          if (y === null) return -1;
          return (x < y ? -1 : x > y ? 1 : 0) * dir;
        });
        rows.forEach(function (row) { body.appendChild(row); });
      }
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
    });
  });
})();
