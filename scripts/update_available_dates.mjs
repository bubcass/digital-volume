import fs from "node:fs";
import path from "node:path";

const OUT = path.join("data", "available-dates.json");

const LOOKBACK_DAYS = 400; // catches late XML arrivals/updates
const WINDOW_DAYS = 14; // keep each API response small enough to process reliably
const MAX_ATTEMPTS = 3;
const REQUEST_TIMEOUT_MS = 60_000;

function iso(d) {
  return d.toISOString().slice(0, 10);
}

function parseExisting() {
  try {
    const raw = fs.readFileSync(OUT, "utf8");
    const data = JSON.parse(raw);
    if (Array.isArray(data))
      return new Set(data.filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)));
    if (Array.isArray(data?.dates))
      return new Set(data.dates.filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)));
    return new Set();
  } catch {
    return new Set();
  }
}

async function fetchDebates(date_start, date_end) {
  const url = `https://api.oireachtas.ie/v1/debates?date_start=${date_start}&date_end=${date_end}&limit=1000`;
  let lastError;

  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { accept: "application/json" },
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });

      if (!res.ok) {
        const error = new Error(
          `HTTP ${res.status} from debates API for ${date_start} to ${date_end}`,
        );
        error.retryable = res.status === 429 || res.status >= 500;
        error.shouldSplit = res.status === 413 || res.status >= 500;
        throw error;
      }

      const data = await res.json();
      if (!Array.isArray(data?.results)) {
        const error = new Error(
          `Unexpected debates API response for ${date_start} to ${date_end}`,
        );
        error.retryable = true;
        error.shouldSplit = true;
        throw error;
      }
      return data;
    } catch (error) {
      lastError = error;
      // Network errors, timeouts, and malformed/truncated JSON can be transient.
      if (error.retryable === undefined) error.retryable = true;
      if (error.shouldSplit === undefined) error.shouldSplit = true;
      if (!error.retryable || attempt === MAX_ATTEMPTS) break;

      const delayMs = 1000 * 2 ** (attempt - 1);
      console.warn(
        `Attempt ${attempt}/${MAX_ATTEMPTS} failed for ${date_start} to ${date_end}: ${error.message}. Retrying in ${delayMs} ms.`,
      );
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }

  lastError.retryable = lastError.retryable ?? true;
  throw lastError;
}

async function fetchDebatesWithSplitting(start, end) {
  try {
    const data = await fetchDebates(iso(start), iso(end));
    return data.results;
  } catch (error) {
    const dayCount = Math.floor((end.getTime() - start.getTime()) / 86_400_000) + 1;
    if (!error.shouldSplit || dayCount <= 1) throw error;

    const midpoint = new Date(start.getTime());
    midpoint.setUTCDate(midpoint.getUTCDate() + Math.floor(dayCount / 2) - 1);
    const nextDay = new Date(midpoint.getTime());
    nextDay.setUTCDate(nextDay.getUTCDate() + 1);

    console.warn(
      `Request failed for ${iso(start)} to ${iso(end)}; splitting into ${iso(start)} to ${iso(midpoint)} and ${iso(nextDay)} to ${iso(end)}.`,
    );
    const firstHalf = await fetchDebatesWithSplitting(start, midpoint);
    const secondHalf = await fetchDebatesWithSplitting(nextDay, end);
    return firstHalf.concat(secondHalf);
  }
}

async function fetchDebatesInWindows(start, end) {
  const results = [];
  let windowStart = new Date(start.getTime());

  while (windowStart <= end) {
    const windowEnd = new Date(windowStart.getTime());
    windowEnd.setUTCDate(windowEnd.getUTCDate() + WINDOW_DAYS - 1);
    if (windowEnd > end) windowEnd.setTime(end.getTime());

    const windowResults = await fetchDebatesWithSplitting(windowStart, windowEnd);
    results.push(...windowResults);
    console.log(
      `Fetched ${windowResults.length} debate records for ${iso(windowStart)} to ${iso(windowEnd)}.`,
    );

    windowStart = new Date(windowEnd.getTime());
    windowStart.setUTCDate(windowStart.getUTCDate() + 1);
  }

  return results;
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

  const results = await fetchDebatesInWindows(start, now);
  const newDates = extractDailDates(results);

  let added = 0;
  for (const d of newDates) {
    if (!existing.has(d)) {
      existing.add(d);
      added++;
    }
  }

  const sorted = Array.from(existing).sort();
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const temporaryOutput = `${OUT}.${process.pid}.tmp`;
  fs.writeFileSync(temporaryOutput, JSON.stringify(sorted, null, 2) + "\n", "utf8");
  fs.renameSync(temporaryOutput, OUT);

  console.log(
    `Fetched ${newDates.size} Dáil sitting dates in lookback window.`,
  );
  console.log(`Added ${added} new dates. Total now ${sorted.length}.`);
  console.log(`Wrote ${OUT}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
