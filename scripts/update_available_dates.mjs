import fs from "node:fs";
import path from "node:path";

const OUT = path.join("data", "available-dates.json");

// tweak these if you like:
const LOOKBACK_DAYS = 400; // catches late XML arrivals/updates

function iso(d) {
  return d.toISOString().slice(0, 10);
}

function parseExisting() {
  try {
    const raw = fs.readFileSync(OUT, "utf8");
    const data = JSON.parse(raw);
    if (Array.isArray(data)) return new Set(data.filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)));
    if (Array.isArray(data?.dates)) return new Set(data.dates.filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)));
    return new Set();
  } catch {
    return new Set();
  }
}

// Minimal “best guess” pagination: if the API ever enforces pagination,
// you can extend this (many Oireachtas endpoints include head.counts.skip/limit/total).
async function fetchDebates(date_start, date_end) {
  const url = `https://api.oireachtas.ie/v1/debates?date_start=${date_start}&date_end=${date_end}&limit=10000`;
  const res = await fetch(url, { headers: { "accept": "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status} from debates API`);
  return await res.json();
}

function extractDailDates(results) {
  const out = new Set();
  for (const d of results || []) {
    const chamber = d?.debateRecord?.chamber?.showAs || "";
    const date = d?.debateRecord?.date || "";
    // If you want to *only* include those that advertise an XML format:
    // const xmlUri = d?.debateRecord?.formats?.xml?.uri || "";
    // if (chamber === "Dáil Éireann" && xmlUri) out.add(date);

    if (chamber === "Dáil Éireann" && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
      out.add(date);
    }
  }
  return out;
}

async function main() {
  const existing = parseExisting();

  const now = new Date();
  const start = new Date(now.getTime() - LOOKBACK_DAYS * 24 * 60 * 60 * 1000);

  const date_start = iso(start);
  const date_end = iso(now);

  const data = await fetchDebates(date_start, date_end);
  const newDates = extractDailDates(data?.results);

  let added = 0;
  for (const d of newDates) {
    if (!existing.has(d)) {
      existing.add(d);
      added++;
    }
  }

  const sorted = Array.from(existing).sort();
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(sorted, null, 2) + "\n", "utf8");

  console.log(`Fetched ${newDates.size} Dáil sitting dates in lookback window.`);
  console.log(`Added ${added} new dates. Total now ${sorted.length}.`);
  console.log(`Wrote ${OUT}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
