/* مقياس — shared utilities.
   escapeHtml: every page builds HTML by string-concatenating fields that
   come from data/*.json. Some of that data (results.json's leaderboard and
   contributors, in particular) is meant to accept community submissions —
   so any field that isn't a number MUST go through this before landing in
   innerHTML, or a submitted name/model/hardware string becomes stored XSS
   for every visitor. Plain global (window.MiqyasUtil), no bundler. */
"use strict";

function escapeHtml(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

window.MiqyasUtil = { escapeHtml };
