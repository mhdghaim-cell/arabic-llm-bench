/* مقياس — shared share-card generator.
   Draws the common chrome (paper background, mono label top-right, rule
   lines, footer URL burned in) onto a 1200x1200 canvas and hands off to a
   page-supplied draw() callback for the page-specific content. Every card
   this project produces — glossary term, tokenizer ratio, calculator
   result — goes through this one function so they stay visually one system.
   Plain global (window.MiqyasCard), no bundler, no imports. */
"use strict";

const CARD_COLORS = {
  ink: "#12161C", paper: "#FAF9F6", rule: "#D8D5CE",
  signal: "#B8342A", verify: "#1B5E4A", dim: "#6E7178",
};

function wrapText(ctx, text, font, maxWidth) {
  ctx.font = font;
  const words = text.split(" ");
  const lines = [];
  let line = "";
  words.forEach((w) => {
    const test = line ? line + " " + w : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = w;
    } else {
      line = test;
    }
  });
  if (line) lines.push(line);
  return lines;
}

// label: small mono string top-right (e.g. "مقياس · المسرد   v0.1")
// footerUrl: LTR string burned in bottom-left (e.g. "miqyas.ai/المسرد")
// draw(ctx, geometry): page-specific content; geometry.wrap(text, font, maxWidth) is bound to this ctx
async function renderCard({ canvas, label, footerUrl, draw, width = 1200, height = 1200 }) {
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (document.fonts && document.fonts.ready) await document.fonts.ready;

  const M = 100;
  const maxW = width - M * 2;
  const R = width - M;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = CARD_COLORS.paper;
  ctx.fillRect(0, 0, width, height);
  ctx.direction = "rtl";
  ctx.textAlign = "right";

  ctx.fillStyle = CARD_COLORS.rule;
  ctx.fillRect(M, 88, maxW, 1);
  ctx.font = "400 26px 'IBM Plex Mono'";
  ctx.fillStyle = CARD_COLORS.dim;
  ctx.fillText(label, R, 68);

  draw(ctx, {
    width,
    height,
    margin: M,
    maxW,
    right: R,
    colors: CARD_COLORS,
    wrap: (text, font, w) => wrapText(ctx, text, font, w),
  });

  ctx.fillStyle = CARD_COLORS.rule;
  ctx.fillRect(M, height - 130, maxW, 1);
  ctx.font = "500 30px 'IBM Plex Mono'";
  ctx.fillStyle = CARD_COLORS.dim;
  ctx.direction = "ltr";
  ctx.textAlign = "left";
  ctx.fillText(footerUrl, M, height - 78);

  return canvas;
}

function downloadCanvas(canvas, filename) {
  const a = document.createElement("a");
  a.download = filename;
  a.href = canvas.toDataURL("image/png");
  a.click();
}

window.MiqyasCard = { renderCard, downloadCanvas, wrapText, COLORS: CARD_COLORS };
