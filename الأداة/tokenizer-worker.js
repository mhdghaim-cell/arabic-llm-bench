/* مقياس — tokenizer playground worker.
   Runs off the main thread so typing never janks. Lazy-loads transformers.js
   from CDN only when the page first asks it to init (never on page load).
   Protocol (all messages are plain objects over postMessage):

   main -> worker  {type:"init", tokenizers:[{id,hf}]}
   worker -> main  {type:"progress", id, status:"loading"|"ready"|"error", pct?, message?}
   worker -> main  {type:"init-done"}
   main -> worker  {type:"tokenize", reqId, text, chipsFor}
   worker -> main  {type:"tokenize-result", reqId, counts:{id:n|null}, errors:{id:msg}, chips:string[]|null}
*/

const TRANSFORMERS_URL = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0/dist/transformers.web.min.js";

let AutoTokenizer = null;
const tokenizers = new Map(); // id -> loaded tokenizer instance

async function ensureLibrary() {
  if (!AutoTokenizer) {
    const mod = await import(TRANSFORMERS_URL);
    AutoTokenizer = mod.AutoTokenizer;
  }
}

async function initTokenizers(list) {
  await ensureLibrary();
  for (const t of list) {
    self.postMessage({ type: "progress", id: t.id, status: "loading" });
    try {
      const tok = await AutoTokenizer.from_pretrained(t.hf, {
        progress_callback: (p) => {
          if (p && p.status === "progress" && typeof p.progress === "number") {
            self.postMessage({ type: "progress", id: t.id, status: "loading", pct: Math.round(p.progress) });
          }
        },
      });
      tokenizers.set(t.id, tok);
      self.postMessage({ type: "progress", id: t.id, status: "ready" });
    } catch (err) {
      self.postMessage({ type: "progress", id: t.id, status: "error", message: String((err && err.message) || err) });
    }
  }
  self.postMessage({ type: "init-done" });
}

function tokenize(reqId, text, chipsFor) {
  const counts = {};
  const errors = {};
  let chips = null;
  for (const [id, tok] of tokenizers) {
    try {
      const { ids, tokens } = tok.encode(text, { add_special_tokens: false });
      counts[id] = ids.length;
      if (id === chipsFor) chips = tokens;
    } catch (err) {
      errors[id] = String((err && err.message) || err);
    }
  }
  self.postMessage({ type: "tokenize-result", reqId, counts, errors, chips });
}

self.onmessage = (e) => {
  const msg = e.data;
  if (msg.type === "init") initTokenizers(msg.tokenizers);
  else if (msg.type === "tokenize") tokenize(msg.reqId, msg.text, msg.chipsFor);
};
