
async function refreshConnectInfo() {
  const urlEl = document.getElementById('connect-url');
  const userEl = document.getElementById('connect-user');
  const badge = document.getElementById('connect-network-badge');
  const note = document.getElementById('connect-note');
  if (!urlEl && !userEl) return;
  try {
    const res = await fetch('/api/connect-info', { cache: 'no-store' });
    const info = await res.json();
    const browserHost = window.location.hostname || '';
    const ipv4 = info.ipv4 || (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(browserHost) ? browserHost : null);
    const port = Number(info.stratumPort || 6387);
    if (urlEl) urlEl.textContent = ipv4 ? `stratum+tcp://${ipv4}:${port}` : `stratum+tcp://YOUR-UMBREL-IP:${port}`;

    const payout = String(info.payoutAddress || '').trim();
    if (userEl) userEl.textContent = payout && payout !== 'CHANGEME_BCH_PAYOUT_ADDRESS'
      ? `${payout}.worker-name`
      : 'Set payout address in Settings';

    const network = String(info.network || '').toLowerCase();
    if (badge) badge.textContent = network === 'testnet4' ? 'TESTNET4' : 'MAINNET';
    if (note) note.textContent = ipv4
      ? `Detected Umbrel IPv4: ${ipv4}. Stratum listens on port ${port}.`
      : `Open Curtis BCH using your Umbrel IPv4 to auto-detect it. Stratum listens on port ${port}.`;
  } catch {
    if (urlEl) urlEl.textContent = 'Unable to detect pool address';
  }
}

function wireCopyButton(buttonId, valueId) {
  document.getElementById(buttonId)?.addEventListener('click', async () => {
    const text = document.getElementById(valueId)?.textContent || '';
    if (!text) return;
    try { await navigator.clipboard.writeText(text); } catch {}
  });
}


function bytesToMiB(bytes) {
  if (bytes == null) return '-';
  return `${Math.max(0, bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function bytesToGiB(bytes) {
  if (bytes == null) return '-';
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return '-';
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GiB`;
}

function formatDuration(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s <= 0) return '-';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} hr`;
  const d = Math.round(h / 24);
  return `${d} days`;
}

function computeSyncEtaSeconds(node, key) {
  try {
    const blocks = Number(node && node.blocks);
    const headers = Number(node && node.headers);
    if (!Number.isFinite(blocks) || !Number.isFinite(headers) || headers <= blocks) return null;
    const now = Date.now();
    const prevRaw = localStorage.getItem(key);
    localStorage.setItem(key, JSON.stringify({ t: now, blocks, headers }));
    if (!prevRaw) return null;
    const prev = JSON.parse(prevRaw);
    const dtS = (now - Number(prev.t || 0)) / 1000;
    const dBlocks = blocks - Number(prev.blocks || 0);
    if (!Number.isFinite(dtS) || dtS <= 5) return null;
    if (!Number.isFinite(dBlocks) || dBlocks <= 0) return null;
    const rate = dBlocks / dtS;
    if (!Number.isFinite(rate) || rate <= 0) return null;
    const remaining = headers - blocks;
    return remaining / rate;
  } catch {
    return null;
  }
}

function formatTHS(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  if (n === 0) return '0';
  if (Math.abs(n) < 0.01) return n.toFixed(4);
  if (Math.abs(n) < 1) return n.toFixed(3);
  if (Math.abs(n) < 10) return n.toFixed(2);
  return n.toFixed(1);
}

function formatHashrateFromTHS(v) {
  const ths = Number(v);
  if (!Number.isFinite(ths)) return '-';
  if (ths === 0) return '0 H/s';

  const abs = Math.abs(ths);
  // Convert from TH/s into a human unit.
  const units = [
    { unit: 'EH/s', scale: 1e6 },
    { unit: 'PH/s', scale: 1e3 },
    { unit: 'TH/s', scale: 1 },
    { unit: 'GH/s', scale: 1e-3 },
    { unit: 'MH/s', scale: 1e-6 },
    { unit: 'KH/s', scale: 1e-9 },
    { unit: 'H/s', scale: 1e-12 },
  ];

  for (const u of units) {
    const inUnit = abs / u.scale;
    if (inUnit >= 1 || u.unit === 'H/s') {
      const signed = ths / u.scale;
      const digits = Math.abs(signed) < 10 ? 2 : Math.abs(signed) < 100 ? 1 : 0;
      return `${signed.toFixed(digits)} ${u.unit}`;
    }
  }
  return `${formatTHS(ths)} TH/s`;
}

function formatBestShare(v) {
  if (v == null || v === '') return '-';
  const n = Number(v);
  if (!Number.isFinite(n)) return '-';
  if (n === 0) return '0';
  const abs = Math.abs(n);
  const units = [
    { s: 'T', v: 1e12 },
    { s: 'G', v: 1e9 },
    { s: 'M', v: 1e6 },
    { s: 'K', v: 1e3 },
  ];
  for (const u of units) {
    if (abs >= u.v) {
      const scaled = n / u.v;
      const digits = Math.abs(scaled) < 10 ? 2 : Math.abs(scaled) < 100 ? 1 : 0;
      return `${scaled.toFixed(digits)}${u.s}`;
    }
  }
  return String(Math.round(n));
}

function formatSmallPercent(pct) {
  const n = Number(pct);
  if (!Number.isFinite(n) || n <= 0) return '0%';
  if (n < 0.0001) return `${n.toExponential(2)}%`;
  if (n < 0.01) return `${n.toFixed(4)}%`;
  if (n < 1) return `${n.toFixed(2)}%`;
  if (n < 10) return `${n.toFixed(1)}%`;
  return `${Math.round(n)}%`;
}

function clamp(value, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}

function formatLuckPercent(pct) {
  if (pct == null || pct === '') return '-';
  const n = Number(pct);
  if (!Number.isFinite(n) || n < 0) return '-';
  return formatSmallPercent(n);
}

function shortenMiner(s) {
  if (!s) return '-';
  const str = String(s);
  if (str.length <= 20) return str;
  return `${str.slice(0, 10)}...${str.slice(-8)}`;
}

function splitWorkerIdent(raw) {
  const full = (raw == null ? '' : String(raw)).trim();
  if (!full) return { worker: '', base: '' };
  const dot = full.lastIndexOf('.');
  if (dot > 0 && dot < full.length - 1) {
    const base = full.slice(0, dot).trim();
    const worker = full.slice(dot + 1).trim();
    if (base && worker) return { worker, base };
  }
  return { worker: '', base: full };
}

function formatAge(v) {
  if (v == null) return '-';
  const n = Number(v);
  let ms = 0;
  if (Number.isFinite(n) && n > 0) {
    ms = n > 1e12 ? n : n * 1000;
  } else {
    const parsed = Date.parse(String(v));
    if (!Number.isFinite(parsed)) return '-';
    ms = parsed;
  }

  const ageS = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (ageS < 60) return `${ageS}s`;
  const ageM = Math.floor(ageS / 60);
  if (ageM < 60) return `${ageM}m`;
  const ageH = Math.floor(ageM / 60);
  return `${ageH}h`;
}

function renderWorkerDetails(miners) {
  const status = document.getElementById('worker-details-status');
  const rows = document.getElementById('worker-details-rows');
  const lastShareEl = document.getElementById('last-share');
  if (!rows) return;

  rows.innerHTML = '';
  const list = Array.isArray(miners) ? miners : [];
  const totalWorkers = Number.isFinite(Number(miners && miners._totalWorkers)) ? Number(miners._totalWorkers) : null;
  const showInactive = Boolean(document.getElementById('workers-show-inactive')?.checked);
  if (!list.length) {
    if (status) status.textContent = 'No workers connected yet.';
    if (lastShareEl) lastShareEl.textContent = '-';
    rows.innerHTML = '<div class="px-3 py-2 text-xs text-slate-400">Connect a miner to see per-worker stats.</div>';
    return;
  }

  const statusCount = totalWorkers != null && totalWorkers > 0 ? totalWorkers : list.length;
  const ACTIVE_WINDOW_S = 300;
  const STALE_WINDOW_S = 86400;
  const nowMs = Date.now();

  const toMs = (v) => {
    if (v == null) return null;
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) return null;
      return v > 1e12 ? v : v * 1000;
    }
    const parsed = Date.parse(String(v));
    if (!Number.isFinite(parsed)) return null;
    return parsed;
  };

  const splitWorker = (usernameRaw, fallbackBase) => {
    const raw = (usernameRaw || '').trim();
    const base = (fallbackBase || '').trim();
    if (!raw) return { name: '(default)', base: base || '' };

    if (base && raw.startsWith(`${base}.`)) {
      const suffix = raw.slice(base.length + 1).trim();
      return { name: suffix || '(default)', base };
    }

    const idx = raw.lastIndexOf('.');
    if (idx > 0 && idx < raw.length - 1) {
      const possibleBase = raw.slice(0, idx);
      const suffix = raw.slice(idx + 1).trim();
      return { name: suffix || '(default)', base: base || possibleBase };
    }

    return { name: '(default)', base: base || raw };
  };

  const ageSFor = (m) => {
    const ms = toMs(m.lastshare != null ? m.lastshare : m.lastShare);
    if (ms == null) return Infinity;
    return Math.max(0, Math.floor((nowMs - ms) / 1000));
  };

  const seen = list.filter((m) => ageSFor(m) <= STALE_WINDOW_S);
  const active = seen.filter((m) => ageSFor(m) <= ACTIVE_WINDOW_S);
  const inactive = seen.filter((m) => {
    const ageS = ageSFor(m);
    return ageS > ACTIVE_WINDOW_S && ageS <= STALE_WINDOW_S;
  });
  const visible = showInactive ? active.concat(inactive) : active;

  window.__lastWorkers = miners;

  if (status) {
    const inactiveSuffix = showInactive && inactive.length ? ` + ${inactive.length} inactive` : '';
    const seenSuffix = statusCount !== active.length ? ` (${Math.min(statusCount, seen.length)} seen)` : '';
    status.textContent = `${active.length} worker${active.length === 1 ? '' : 's'} active${inactiveSuffix}${seenSuffix}`;
  }

  const baseFor = (m) => {
    const explicit = (window.__payoutAddress || '').trim();
    if (explicit) return explicit;
    const miner = m && m.miner != null ? String(m.miner).trim() : '';
    return miner;
  };
  const sortKeyFor = (m) => {
    const raw = m && (m.workername || m.workerName || m.worker) ? String(m.workername || m.workerName || m.worker) : '';
    const split = splitWorker(raw, baseFor(m));
    return (split.name || '').toLowerCase();
  };
  const sortByName = (a, b) => sortKeyFor(a).localeCompare(sortKeyFor(b));
  const sortedVisible = visible.slice().sort(sortByName);
  if (!sortedVisible.length) {
    if (lastShareEl) lastShareEl.textContent = '-';
    rows.innerHTML = showInactive
      ? '<div class="px-3 py-2 text-xs text-slate-400">No worker stats yet.</div>'
      : '<div class="px-3 py-2 text-xs text-slate-400">No active workers. Turn on \"Show inactive (24h)\" to view recent workers.</div>';
    return;
  }
  const netDiff = Number(window.__networkDifficulty);
  const maxBestSince = sortedVisible.reduce((acc, mm) => {
    const raw = mm && (mm.bestshare_since_block ?? mm.bestShareSinceBlock);
    const n = Number(raw);
    return Number.isFinite(n) && n > acc ? n : acc;
  }, 0);

  const oddsWindow = (() => {
    const raw = (window.__bchOddsWindow || localStorage.getItem('bchOddsWindow') || '7d').toLowerCase();
    if (raw === '1m') return { key: '1m', s: 30 * 86400, label: '1 month', short: '1m' };
    if (raw === '1y') return { key: '1y', s: 365 * 86400, label: '1 year', short: '1y' };
    return { key: '7d', s: 7 * 86400, label: '7 days', short: '7d' };
  })();
  const LOG_GAMMA = 6.5;
  const pctVsTarget = (shareDiff) => {
    const v = Number(shareDiff);
    if (!Number.isFinite(v) || v <= 0) return 0;
    const target = Number.isFinite(netDiff) && netDiff > 0 ? netDiff : maxBestSince;
    if (!Number.isFinite(target) || target <= 0) return 0;
    const capped = Math.min(v, target);
    const denom = Math.log10(1 + target);
    if (!Number.isFinite(denom) || denom <= 0) return 0;
    const ratioLog = Math.log10(1 + capped) / denom;
    const pct = Math.pow(Math.max(0, Math.min(1, ratioLog)), LOG_GAMMA) * 100;
    return Math.max(0, Math.min(100, pct));
  };

  const lerp = (a, b, t) => a + (b - a) * Math.max(0, Math.min(1, t));
  const colorForLuckPct = (pct) => {
    const p = Math.max(0, Math.min(100, Number(pct) || 0));
    // 0..50: cyan -> magenta, 50..100: magenta -> orange
    const c0 = { r: 0, g: 229, b: 255 };
    const c1 = { r: 255, g: 43, b: 214 };
    const c2 = { r: 255, g: 154, b: 0 };
    const t = p / 100;
    let r = 0, g = 0, b = 0;
    if (t <= 0.5) {
      const u = t / 0.5;
      r = lerp(c0.r, c1.r, u);
      g = lerp(c0.g, c1.g, u);
      b = lerp(c0.b, c1.b, u);
    } else {
      const u = (t - 0.5) / 0.5;
      r = lerp(c1.r, c2.r, u);
      g = lerp(c1.g, c2.g, u);
      b = lerp(c1.b, c2.b, u);
    }
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  };
  const scaleLuckForRing = (luckFrac) => {
    const f = Number(luckFrac);
    if (!Number.isFinite(f) || f <= 0) return 0;
    // Log scaling for visibility (ring only). Text shows the true probability.
    // ~0.001% -> ~1%, 0.01% -> ~7.5%, 0.1% -> ~26%, 1% -> ~50%.
    const s = Math.log10(1 + f * 1e4) / 4;
    return Math.max(0, Math.min(1, s));
  };

  const bestByWorker = window.__bestByWorker || (window.__bestByWorker = {});
  const glazeHypeByWorker = window.__glazeHypeByWorker || (window.__glazeHypeByWorker = {});
  const glazeGlowByWorker = window.__glazeGlowByWorker || (window.__glazeGlowByWorker = {});
  const prevLastByWorker = window.__prevLastByWorker || (window.__prevLastByWorker = {});
  const prevHrByWorker = window.__prevHrByWorker || (window.__prevHrByWorker = {});
  const glazeEmaByWorker = window.__glazeEmaByWorker || (window.__glazeEmaByWorker = {});
  const glazeShareStateByWorker = window.__glazeShareStateByWorker || (window.__glazeShareStateByWorker = {});
  const glazeMetaByWorker = window.__glazeMetaByWorker || (window.__glazeMetaByWorker = {});

  const clearGlazeForWorker = (key) => {
    if (!key) return;
    try {
      delete glazeHypeByWorker[key];
    } catch {}
    try {
      delete glazeGlowByWorker[key];
    } catch {}
    try {
      delete glazeEmaByWorker[key];
    } catch {}
    try {
      delete glazeShareStateByWorker[key];
    } catch {}
    try {
      const levels = window.__glazeLevelByWorker;
      if (levels) delete levels[key];
    } catch {}
  };

  const updateGlow = (key, intensity01) => {
    const nowS = Date.now() / 1000;
    const prev = glazeGlowByWorker[key];
    const prevPeak = prev && Number.isFinite(prev.peak) ? Number(prev.peak) : 0;
    const prevTs = prev && Number.isFinite(prev.ts) ? Number(prev.ts) : nowS;
    // Slow decay so the donut "remembers" a record for a while.
    const TAU_S = 6 * 3600;
    const decayed = prevPeak > 0 ? prevPeak * Math.exp(-(nowS - prevTs) / TAU_S) : 0;
    const nextPeak = Math.max(decayed, Math.max(0, Math.min(1, Number(intensity01) || 0)));
    glazeGlowByWorker[key] = { peak: nextPeak, ts: nowS };
    return nextPeak;
  };

  const phraseStateByWorker = window.__phraseStateByWorker || (window.__phraseStateByWorker = {});
  const __hashStr = (s) => {
    const str = String(s || '');
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  };
  const __pick = (key, bucket, arr) => {
    const a = Array.isArray(arr) ? arr : [];
    if (!a.length) return '';
    const idx = (__hashStr(`${key}::${bucket}`) % a.length) >>> 0;
    return a[idx];
  };
  const pickGlazePhrase = ({ workerKey, workerName, workerThs, luckPct, hype01, glow01, lastAgeS }) => {
    const wk = String(workerKey || '');
    const wn = String(workerName || '');
    const now = Date.now();
    // 3m cadence with per-worker jitter so all workers don't update at once.
    const jitterMs = __hashStr(`${wk}::phrase`) % (2 * 60000);
    const bucket = Math.floor((now + jitterMs) / (3 * 60000));

    const stale = Number.isFinite(lastAgeS) ? Number(lastAgeS) : null;
    const isStale = stale != null && stale > 90;
    const isVeryStale = stale != null && stale > 600;
    const isSpike = Number(hype01 || 0) > 0.35;
    const isRecordGlow = Number(glow01 || 0) > 0.18;

    let tag = 'chill';
    if (isVeryStale) tag = 'sleep';
    else if (isStale) tag = 'idle';
    else if (isSpike && isRecordGlow) tag = 'party';
    else if (isSpike) tag = 'spike';
    else if (isRecordGlow) tag = 'glow';

    const prev = phraseStateByWorker[wk];
    const prevTag = prev && prev.tag ? String(prev.tag) : '';
    const prevBucket = prev && Number.isFinite(prev.bucket) ? Number(prev.bucket) : null;
    // Keep vibes stable: only change every ~6m unless the state changes (tag flip).
    if (prev && prevTag === tag && prevBucket != null && bucket - prevBucket < 2 && prev.phrase) return prev.phrase;
    if (prev && prevTag === tag && prevBucket === bucket && prev.phrase) return prev.phrase;

    const ths = Number(workerThs || 0);
    const lucky = Number(luckPct || 0);
    const baseVars = {
      wn,
      ths: Number.isFinite(ths) && ths > 0 ? `${ths.toFixed(ths < 10 ? 2 : 1)} TH/s` : '',
      odds: Number.isFinite(lucky) ? `${formatSmallPercent(lucky)} in ${oddsWindow.label}` : '',
    };
    const fmt = (s) =>
      String(s || '')
        .replace(/\{wn\}/g, baseVars.wn || 'worker')
        .replace(/\{ths\}/g, baseVars.ths || 'hashrate')
        .replace(/\{odds\}/g, baseVars.odds || 'odds');

    const phrases = {
      chill: [
        'Glaze is vibing',
        'Sprinkles standing by',
        'Oven is warm',
        'Just donut things',
        'Glaze level: acceptable',
        'Waiting for lightning',
        'Keep stirring the batter',
        'Do not anger the RNG',
        'Glaze is optimistic today',
        'No prophecy, just vibes',
      ],
      idle: [
        'Glaze cooling down',
        'Quiet kitchen...',
        'Sprinkles taking a break',
        'Waiting on fresh shares',
        'Still breathing, promise',
        'Glaze: low activity mode',
        'RNG is browsing memes',
      ],
      sleep: [
        'Glaze is asleep',
        'No shares? No glaze.',
        'Wake me when it hits',
        'Donut went AFK',
        'Sprinkles fell off',
      ],
      spike: [
        'Glaze spike detected',
        'Sprinkles deployed',
        'That share had spice',
        'Ooh, that was crunchy',
        'Glaze just twitched',
        'Fresh crumbs on the floor',
        'RNG blinked',
      ],
      glow: [
        'Record glow lingering',
        'Donut remembers that one',
        'Glaze is feeling brave',
        'That record still slaps',
        'Confidence rising',
      ],
      party: [
        'RNG is dancing',
        'Sprinkle party!',
        'Glaze is unhinged',
        'Kitchen is on fire (in a good way)',
        'Double sprinkle event',
        'Donut screaming internally',
      ],
    };

    const phrase = fmt(__pick(`${wk}::${tag}::${wn}`, bucket, phrases[tag] || phrases.chill));
    phraseStateByWorker[wk] = { phrase, tag, bucket };
    return phrase;
  };

  const updateDecayedPeak = (key, current) => {
    const nowS = Date.now() / 1000;
    const cur = Number(current);
    const prev = glazeHypeByWorker[key];
    const prevPeak = prev && Number.isFinite(prev.peak) ? Number(prev.peak) : 0;
    const prevTs = prev && Number.isFinite(prev.ts) ? Number(prev.ts) : nowS;
    // Fast decay so it feels "alive" while still being honest.
    // This is purely for the Glaze ring animation; it does not affect the Record metrics.
    const TAU_S = 90;
    const decayed = prevPeak > 0 ? prevPeak * Math.exp(-(nowS - prevTs) / TAU_S) : 0;
    const nextPeak = Number.isFinite(cur) && cur > 0 ? Math.max(cur, decayed) : decayed;
    glazeHypeByWorker[key] = { peak: nextPeak, ts: nowS };
    return nextPeak;
  };

  const glazeLevelByWorker = window.__glazeLevelByWorker || (window.__glazeLevelByWorker = {});
  const updateGlazeLevel = ({
    workerKey,
    target,
    workerThs,
    bestSinceNum,
    lastDiffNum,
    lastAgeS,
    hype01,
    glow01,
    recordBroke,
    hashSharePct,
    sharesCount,
  }) => {
    const nowS = Date.now() / 1000;
    const prev = glazeLevelByWorker[workerKey];
    const prevLevel = prev && Number.isFinite(prev.level) ? Number(prev.level) : 0.52;
    const prevTs = prev && Number.isFinite(prev.ts) ? Number(prev.ts) : nowS;
    const dt = Math.max(0, Math.min(5, nowS - prevTs));

    const t = Number(target);
    const record = Number(bestSinceNum);
    const last = Number(lastDiffNum);
    const ths = Number(workerThs);
    const age = Number(lastAgeS);
    const shares = Number(sharesCount);

    const recordRatio = Number.isFinite(t) && t > 0 && Number.isFinite(record) && record > 0 ? Math.min(1, record / t) : 0;
    const lastRatio = Number.isFinite(t) && t > 0 && Number.isFinite(last) && last > 0 ? Math.min(1, last / t) : 0;

    // Keep the donut lively and different per worker (fun only):
    // - Baseline differs per worker (seeded)
    // - Spikes hard on record breaks and big share events
    // - Drops fast on staleness / inactivity
    // - Adds subtle oscillation so workers don't "move in sync"
    const seed01 = __hashStr(workerKey) / 0xffffffff;
    const workerBias = (seed01 - 0.5) * 0.22;

    const stale = Number.isFinite(age) && age > 0 ? Math.max(0, Math.min(1, (age - 10) / 140)) : 0;
    const cool = 1 - stale * 0.60;

    const energy = Number.isFinite(ths) && ths > 0 ? Math.max(0, Math.min(1, Math.log10(1 + ths) / 3)) : 0;
    const shareOfPool = Number.isFinite(hashSharePct) ? Math.max(0, Math.min(1, Number(hashSharePct) / 100)) : 0;
    const hype = Math.max(0, Math.min(1, Number(hype01) || 0));
    const glow = Math.max(0, Math.min(1, Number(glow01) || 0));
    const broke = recordBroke ? 0.38 : 0;

    // Baseline around 50%: glaze should feel "alive" (go up and down), not sit near 0.
    const base =
      0.52 +
      (0.12 * energy) +
      (0.10 * Math.sqrt(Math.max(0, shareOfPool))) +
      workerBias;

    // Worker-specific oscillation (keeps workers from looking identical).
    const oscA = Math.sin((nowS / 7.5) + (seed01 * 6.28318));
    const oscB = Math.sin((nowS / 2.6) + (seed01 * 11.9));
    const osc = (oscA * (0.045 + 0.06 * energy)) + (oscB * (0.02 + 0.03 * shareOfPool));

    // Small wobble scaled by activity (random-ish, but deterministic).
    const wobbleSeed = __hashStr(`${workerKey}::${Math.floor(nowS * 1.6)}`) / 0xffffffff;
    const wobble = (wobbleSeed - 0.5) * (0.10 + 0.20 * Math.max(hype, shareOfPool, energy));

    // "Lots of tiny shares" can cool the glaze a bit: frequent updates with very low ratio.
    const tinySpam = Number.isFinite(age) && age > 0 && age < 25 && lastRatio > 0 && lastRatio < 1e-7 ? 0.14 : 0;

    // "Two good shares in a row" boost: consecutive last-diff improvements in a short window.
    // This is intentionally playful; it only drives the donut ring.
    const prevLast = Number(prevLastByWorker[workerKey] || 0);
    const upTick = Number.isFinite(last) && last > 0 && Number.isFinite(prevLast) && prevLast > 0 ? last / prevLast : 0;
    const consecutiveBoost = upTick > 1.35 && Number.isFinite(age) && age >= 0 && age < 75 ? Math.min(0.34, 0.12 + (Math.log10(upTick) * 0.26)) : 0;

    const prevHr = Number(prevHrByWorker[workerKey] || 0);
    const hrTick = Number.isFinite(ths) && ths > 0 && Number.isFinite(prevHr) && prevHr > 0 ? ths / prevHr : 1;
    const hrBoost = hrTick > 1.25 ? 0.16 : hrTick > 1.15 ? 0.10 : hrTick > 1.08 ? 0.06 : 0;
    const hrCool = hrTick < 0.75 ? 0.14 : hrTick < 0.88 ? 0.08 : 0;

    // Compare last share to its own recent baseline (EMA in log-space).
    const logLast = Number.isFinite(last) && last > 0 ? Math.log10(last) : null;
    const emaPrev = glazeEmaByWorker[workerKey];
    const emaPrevVal = emaPrev && Number.isFinite(emaPrev.v) ? Number(emaPrev.v) : (logLast != null ? logLast : 0);
    const emaAlpha = Math.max(0.04, Math.min(0.35, (dt / 2.2)));
    const emaNextVal = logLast != null ? (emaPrevVal + (logLast - emaPrevVal) * emaAlpha) : emaPrevVal;
    glazeEmaByWorker[workerKey] = { v: emaNextVal, ts: nowS };
    const dev = logLast != null ? Math.max(-1, Math.min(1, (logLast - emaNextVal) / 1.45)) : 0;

    // Share counter rate (rough activity proxy).
    const sharePrev = glazeShareStateByWorker[workerKey];
    const prevShares = sharePrev && Number.isFinite(sharePrev.s) ? Number(sharePrev.s) : (Number.isFinite(shares) ? shares : 0);
    const prevShareTs = sharePrev && Number.isFinite(sharePrev.ts) ? Number(sharePrev.ts) : nowS;
    const dShares = Number.isFinite(shares) && shares >= 0 ? Math.max(0, shares - prevShares) : 0;
    const dtShares = Math.max(1e-3, Math.min(30, nowS - prevShareTs));
    const shareRate = dShares / dtShares;
    const rateEmaPrev = sharePrev && Number.isFinite(sharePrev.r) ? Number(sharePrev.r) : shareRate;
    const rateEma = rateEmaPrev + (shareRate - rateEmaPrev) * Math.max(0.04, Math.min(0.5, dtShares / 8));
    glazeShareStateByWorker[workerKey] = { s: Number.isFinite(shares) ? shares : prevShares, ts: nowS, r: rateEma };
    const rate01 = Math.max(0, Math.min(1, Math.log10(1 + rateEma) / 4));

    // If we are hammering shares but they're all tiny, nudge glaze down a bit.
    const spamPenalty = rate01 > 0.55 && lastRatio > 0 && lastRatio < 1e-7 ? 0.12 : 0;

    // If the miner is totally quiet, glaze should drop quickly.
    const quietPenalty = (Number.isFinite(age) && age > 0 && age > 140) ? 0.28 : (Number.isFinite(age) && age > 0 && age > 70) ? 0.14 : 0;
    const activityBoost = rate01 > 0.5 ? 0.10 : rate01 > 0.25 ? 0.06 : rate01 > 0.08 ? 0.03 : 0;

    const targetLevel = Math.max(
      0.05,
      Math.min(
        0.98,
        (base +
          (dev * 0.28) +
          (recordRatio > 0 ? Math.pow(recordRatio, 0.22) * 0.22 : 0) +
          (hype * 0.26) +
          (glow * 0.16) +
          activityBoost +
          hrBoost -
          hrCool +
          consecutiveBoost +
          broke +
          osc +
          wobble -
          tinySpam -
          spamPenalty -
          quietPenalty) *
          (0.82 + 0.18 * energy) *
          cool
      )
    );
    // Make spikes feel responsive, and staleness drop quickly.
    const alphaFloor = 0.20;
    const spikeFast = recordBroke ? 0.75 : hype > 0.55 ? 0.62 : hype > 0.38 ? 0.42 : 0;
    const staleFast = (Number.isFinite(age) && age > 180) ? 0.70 : (Number.isFinite(age) && age > 90) ? 0.45 : 0;
    const baseAlpha = (0.20 + 0.44 * Math.max(hype, rate01) + glow * 0.22) * (dt / 0.95);
    const alphaUp = Math.max(alphaFloor, Math.min(0.92, baseAlpha + spikeFast));
    const alphaDown = Math.max(alphaFloor, Math.min(0.92, baseAlpha + staleFast));
    const alpha = targetLevel >= prevLevel ? alphaUp : alphaDown;
    const next = prevLevel + (targetLevel - prevLevel) * alpha;
    glazeLevelByWorker[workerKey] = { level: next, ts: nowS };

    // Export lightweight explanation for the vibe card (throttled).
    try {
      const nextTag = (() => {
        const st = Number.isFinite(age) ? Number(age) : null;
        const isStale2 = st != null && st > 90;
        const isVeryStale2 = st != null && st > 600;
        const isSpike2 = hype > 0.35;
        const isGlow2 = glow > 0.18;
        if (isVeryStale2) return 'sleep';
        if (isStale2) return 'idle';
        if (isSpike2 && isGlow2) return 'party';
        if (isSpike2) return 'spike';
        if (isGlow2) return 'glow';
        return 'chill';
      })();

      const signals = [];
      if (recordBroke) signals.push('record+');
      if (hype > 0.35) signals.push('spike');
      if (glow > 0.18) signals.push('glow');
      if (Number.isFinite(age) && age > 120) signals.push('stale');
      if (hrTick > 1.2) signals.push('hr+');
      else if (hrTick < 0.8) signals.push('hr-');
      if (spamPenalty > 0.05 || tinySpam > 0.05) signals.push('spam');
      if (!signals.length && rate01 > 0.25) signals.push('steady');
      if (!signals.length && Number.isFinite(age) && age > 0 && age > 60) signals.push('quiet');

      const explain = [];
      if (recordBroke) explain.push('new record');
      if (hype > 0.35) explain.push('big shares');
      if (Number.isFinite(age) && age > 120) explain.push('no recent shares');
      else if (Number.isFinite(age) && age > 60) explain.push('slowing down');
      if (hrTick > 1.2) explain.push('hashrate up');
      else if (hrTick < 0.8) explain.push('hashrate down');
      if (spamPenalty > 0.05 || tinySpam > 0.05) explain.push('tiny share spam');

      const prevMeta = glazeMetaByWorker[workerKey];
      const prevMetaTs = prevMeta && Number.isFinite(prevMeta.ts) ? Number(prevMeta.ts) : 0;
      const prevMetaTag = prevMeta && prevMeta.tag ? String(prevMeta.tag) : '';
      const holdJitterS = (seed01 * 60);
      const holdS = 120 + holdJitterS; // 2–3 minutes per worker (keeps it readable, not spammy)
      const shouldUpdate =
        recordBroke ||
        prevMetaTag !== nextTag ||
        !prevMetaTs ||
        (nowS - prevMetaTs) >= holdS;

      if (shouldUpdate) {
        glazeMetaByWorker[workerKey] = {
          tag: nextTag,
          ts: nowS,
          signals: signals.slice(0, 3),
          explain: explain.slice(0, 2),
          activity01: rate01,
          staleS: Number.isFinite(age) ? age : null,
        };
      }
    } catch {}

    return Math.max(0, Math.min(1, next));
  };

  const showWorkerResetModal = async ({ workerKey, workerName }) => {
    const wk = String(workerKey || '').trim();
    const wn = String(workerName || '').trim();
    if (!wk || !wn) return;

    const choice = await showActionModal({
      kicker: 'Worker',
      title: `Reset ${wn}?`,
      bodyHtml: `Choose what to reset:<br><br>
        <span class="text-slate-100 font-semibold">Reset glaze</span> resets the donut animations only.<br>
        <span class="text-slate-100 font-semibold">Reset record</span> clears this worker's <span class="text-slate-100 font-semibold">record since block</span> so it starts fresh.`,
      primaryText: 'Reset record',
      secondaryText: 'Reset glaze',
    });

    if (choice === 'secondary') {
      clearGlazeForWorker(wk);
      renderWorkerDetails(window.__lastWorkers || []);
      return;
    }

    if (choice !== 'primary') return;

    const confirm = await showActionModal({
      kicker: 'Confirm',
      title: `Reset record for ${wn}?`,
      bodyHtml: `This resets <span class="text-slate-100 font-semibold">record since block</span> for this worker only.<br><br>
        It does <span class="text-slate-100 font-semibold">not</span> affect mining, payouts, or your node.`,
      primaryText: 'Reset record',
      secondaryText: 'Cancel',
    });
    if (confirm !== 'primary') return;

    try {
      await postJson('/api/pool/workers/bestshare/reset', { worker: wn });
      clearGlazeForWorker(wk);
      try {
        delete bestByWorker[wk];
      } catch {}
      const w = await fetchJson('/api/pool/workers');
      const miners = w && Array.isArray(w.workers_details) ? w.workers_details : [];
      renderWorkerDetails(miners);
    } catch (e) {
      console.error(e);
      await showActionModal({
        kicker: 'Error',
        title: 'Reset failed',
        bodyHtml: escapeHtml(String(e && e.message ? e.message : e)),
        primaryText: 'OK',
      });
    }
  };

  for (const m of sortedVisible.slice(0, 50)) {
    const workerNameRaw = (m && (m.workername || m.workerName || m.worker)) ? String(m.workername || m.workerName || m.worker) : '';
    const base = (window.__payoutAddress || '').trim() || (m && m.miner ? String(m.miner).trim() : '');
    const split = splitWorker(workerNameRaw, base);
    const workerName = split.name;
    const workerBase = split.base;
	    const sub = workerBase ? shortenMiner(workerBase) : '';
	    const hrThs = m.hashrate_1m_ths != null ? m.hashrate_1m_ths : m.hashrate_ths;
	    const hr = formatHashrateFromTHS(hrThs);
	    const last = formatAge(m.lastshare != null ? m.lastshare : m.lastShare);
	    const bestSinceNum = m && (m.bestshare_since_block ?? m.bestShareSinceBlock) != null ? Number(m.bestshare_since_block ?? m.bestShareSinceBlock) : null;
      const lastDiffNum = m && (m.current_diff ?? m.currentDiff) != null ? Number(m.current_diff ?? m.currentDiff) : null;
	    const bestSinceText = Number.isFinite(bestSinceNum) && bestSinceNum > 0 ? formatBestShare(bestSinceNum) : '-';
	    const bestPct = pctVsTarget(bestSinceNum);
	    const bestOver = Number.isFinite(netDiff) && netDiff > 0 && Number.isFinite(bestSinceNum) && bestSinceNum > netDiff;
	    const bestLinearPct = Number.isFinite(netDiff) && netDiff > 0 && Number.isFinite(bestSinceNum) && bestSinceNum > 0 ? (bestSinceNum / netDiff) * 100 : null;
	    const bestLinearText = bestLinearPct != null ? `${formatSmallPercent(bestLinearPct)} of target` : 'Log scale';
	    const targetText = Number.isFinite(netDiff) && netDiff > 0 ? formatBestShare(netDiff) : '-';
      const workerThs = Number(hrThs);
      const poolThs = sortedVisible.reduce((acc, mm) => {
        const v = Number(mm.hashrate_1m_ths != null ? mm.hashrate_1m_ths : mm.hashrate_ths);
        return Number.isFinite(v) && v > 0 ? acc + v : acc;
      }, 0);
      const hashSharePct = Number.isFinite(workerThs) && workerThs > 0 && Number.isFinite(poolThs) && poolThs > 0 ? (workerThs / poolThs) * 100 : null;

      const formatEtaS = (s) => {
        const n = Number(s);
        if (!Number.isFinite(n) || n <= 0) return '-';
        const sec = Math.round(n);
        const m = Math.floor(sec / 60);
        const h = Math.floor(m / 60);
        const d = Math.floor(h / 24);
        if (d > 0) return `${d}d ${h % 24}h`;
        if (h > 0) return `${h}h ${m % 60}m`;
        if (m > 0) return `${m}m`;
        return `${sec}s`;
      };
      const etaS = Number.isFinite(workerThs) && workerThs > 0 && Number.isFinite(netDiff) && netDiff > 0 ? (netDiff * Math.pow(2, 32)) / (workerThs * 1e12) : null;
      const etaText = etaS != null ? formatEtaS(etaS) : '-';

      const luckFrac = etaS != null && etaS > 0 ? 1 - Math.exp(-oddsWindow.s / etaS) : 0;
      const luckPct = luckFrac * 100;
      const luckText = etaS != null && etaS > 0 ? formatSmallPercent(luckPct) : '-';

      const workerKey = `${workerBase || ''}::${workerName || ''}`.trim();
      const target = Number.isFinite(netDiff) && netDiff > 0 ? netDiff : maxBestSince;
      const decayedPeak = updateDecayedPeak(workerKey, lastDiffNum);
      const targetForHype = Number.isFinite(target) && target > 0 ? target : null;
      const hypeRatio = targetForHype && Number.isFinite(decayedPeak) && decayedPeak > 0 ? Math.min(1, decayedPeak / targetForHype) : 0;
      const hype01 = Math.max(0, Math.min(1, Math.log10(1 + hypeRatio * 1e6) / 6));

      const recordRatioRaw = Number.isFinite(bestSinceNum) && bestSinceNum > 0 && Number.isFinite(target) && target > 0 ? bestSinceNum / target : 0;
      const recordRatio = Math.max(0, Math.min(1, Number(recordRatioRaw) || 0));
      const baseRingPct = scaleLuckForRing(luckFrac) * 100;
      // Glow intensity rises with the record ratio, but only updates (spikes) when a new record is set.
      const prevBest = Number(bestByWorker[workerKey] || 0);
      const bestNow = Number.isFinite(bestSinceNum) && bestSinceNum > 0 ? bestSinceNum : 0;
      const recordBroke = bestNow > 0 && bestNow > prevBest * 1.000001;
      const glowAmp = recordBroke ? Math.max(0.15, Math.min(1, Math.pow(recordRatio || 0, 0.25))) : 0;
      const glow01 = updateGlow(workerKey, glowAmp);
      const lastAgeS = m && (m.lastshare_ago_s != null ? Number(m.lastshare_ago_s) : null);

      // Donut Glaze-o-meter: intentionally "fun" and responsive (not the true 7d odds).
      const glaze01 = updateGlazeLevel({
        workerKey,
        target,
        workerThs,
        bestSinceNum,
        lastDiffNum,
        lastAgeS,
        hype01,
        glow01,
        recordBroke,
        hashSharePct,
        sharesCount: m && m.shares != null ? Number(m.shares) : null,
      });
      const glazePct = Math.max(0, Math.min(100, glaze01 * 100));
      const glazeText = `${Math.round(glazePct)}%`;
      const isStale = Number.isFinite(lastAgeS) && Number(lastAgeS) > 90;
      const isVeryStale = Number.isFinite(lastAgeS) && Number(lastAgeS) > 600;
      const isSpike = Number(hype01 || 0) > 0.35;
      const isGlow = Number(glow01 || 0) > 0.18;
      let tag = 'chill';
      if (isVeryStale) tag = 'sleep';
      else if (isStale) tag = 'idle';
      else if (isSpike && isGlow) tag = 'party';
      else if (isSpike) tag = 'spike';
      else if (isGlow) tag = 'glow';

      const accentByTag = {
        chill: 'rgba(255,43,214,.96)',
        spike: 'rgba(255,154,0,.98)',
        glow: 'rgba(168,85,247,.96)',
        party: 'rgba(255,43,214,.98)',
        idle: 'rgba(0,229,255,.92)',
        sleep: 'rgba(148,163,184,.70)',
      };
      const accent = accentByTag[tag] || 'rgba(255,43,214,.96)';
      const spr = Math.max(
        0.15,
        Math.min(1, 0.35 + 0.55 * Math.max(Number(hype01) || 0, Number(glow01) || 0) + (recordBroke ? 0.25 : 0))
      );

      const pulse = bestNow > 0 && bestNow > prevBest * 1.000001;
      if (bestNow > 0) bestByWorker[workerKey] = bestNow;

      const phrase = pickGlazePhrase({
        workerKey,
        workerName,
        workerThs,
        luckPct,
        hype01,
        glow01,
        lastAgeS,
      });
      const meta = (window.__glazeMetaByWorker && window.__glazeMetaByWorker[workerKey]) ? window.__glazeMetaByWorker[workerKey] : null;
      const signalsText = meta && Array.isArray(meta.signals) && meta.signals.length ? `Signals: ${meta.signals.join(' ')}` : '';
      const explainText = meta && Array.isArray(meta.explain) && meta.explain.length ? `Why: ${meta.explain.join(', ')}` : '';

      const mid = `
        <div class="axe-worker-mid">
          <div class="axe-worker-mid__k">ODDS</div>
          <div class="axe-worker-mid__v">${escapeHtml(etaS != null && etaS > 0 ? `${luckText} in ${oddsWindow.label}` : '-')}</div>
        </div>
      `;

      prevLastByWorker[workerKey] = Number.isFinite(lastDiffNum) && lastDiffNum > 0 ? lastDiffNum : prevLastByWorker[workerKey];
      prevHrByWorker[workerKey] = Number.isFinite(workerThs) && workerThs > 0 ? workerThs : prevHrByWorker[workerKey];

    const left = `
      <div class="min-w-0">
        <div class="truncate font-mono text-white axe-shadow-heavy axe-worker-name">${escapeHtml(workerName)}</div>
        ${sub ? `<div class="truncate font-mono text-[11px] text-slate-400">${escapeHtml(sub)}</div>` : ''}
      </div>
    `;

	    const right = `
	      <div class="text-right">
	        <div class="font-mono text-sm text-white axe-shadow-heavy">${escapeHtml(hr)}</div>
	        <div class="font-mono text-[11px] text-slate-400">${escapeHtml(last)}</div>
	      </div>
	    `;

    const metrics = `
      <div class="axe-worker-metrics">
        <div class="axe-worker-donuts">
           <div class="axe-worker-donut" title="Glaze-o-meter: fun only. Jumps with share spikes, record glow, and activity. Not a prediction.">
             <div class="axe-donut axe-donut--luck${pulse ? ' axe-donut--pulse' : ''}" style="--p:${escapeHtml((Math.max(0, Math.min(100, glazePct)) * 3.6).toFixed(2))};--axe-glaze:${escapeHtml(accent)};--spr:${escapeHtml(spr.toFixed(2))}">
                <div class="axe-donut__meter"></div>
              </div>
            </div>
            <div class="axe-vibe-card">
              <div class="axe-vibe-card__k">Donut-O-Meter</div>
              <div class="axe-vibe-card__v">Glaze ${escapeHtml(glazeText)}</div>
              ${signalsText ? `<div class=\"axe-vibe-card__s\">${escapeHtml(signalsText)}</div>` : ''}
              ${explainText ? `<div class=\"axe-vibe-card__s\">${escapeHtml(explainText)}</div>` : ''}
              <div class="axe-vibe-card__m">${escapeHtml(phrase)}</div>
            </div>
          </div>
        <div class="axe-worker-tracks">
          <div class="axe-worker-tracks__meta">
            <div class="axe-worker-tracks__hint">Log scale</div>
            <div class="axe-worker-tracks__hint">Target ${escapeHtml(targetText)}</div>
          </div>
          <div class="axe-worker-track-row">
            <div class="axe-worker-track-row__label">Record</div>
            <div class="axe-worker-track axe-worker-track--best${bestOver ? ' axe-worker-track--over' : ''}" title="Record share since block vs current network difficulty (log scale)">
              <div class="axe-worker-track__mask" style="left:${bestPct.toFixed(2)}%"></div>
              <div class="axe-worker-track__marker" style="left:${bestPct.toFixed(2)}%" aria-hidden="true"></div>
              <div class="axe-worker-track__coin" aria-hidden="true"></div>
            </div>
          </div>
        </div>
        <div class="axe-worker-metric axe-worker-metric--best" title="Record share since block">
          <div class="axe-worker-metric__label">Record</div>
          <div class="axe-worker-metric__value">${escapeHtml(bestSinceText)}</div>
          <div class="axe-worker-metric__sub">${escapeHtml(bestLinearText)}</div>
          <button type="button" class="axe-worker-metric__pill axe-worker-metric__pill--reset js-worker-reset" data-worker-key="${escapeHtml(workerKey)}" data-worker-name="${escapeHtml(workerName)}">Reset...</button>
        </div>
      </div>
    `;

    const el = document.createElement('div');
    el.className = 'axe-worker-item px-3 py-2';
    el.innerHTML = `<div class="axe-worker-head flex items-center justify-between gap-3">${left}${mid}${right}</div>${metrics}`;
    if (Number(hype01 || 0) > 0.25 || recordBroke) el.querySelector('.axe-donut--luck')?.classList.add('axe-donut--sprinkle');
    rows.appendChild(el);
  }

  rows.onclick = (ev) => {
    const t = ev && ev.target;
    if (!t) return;
    const btn = t.closest ? t.closest('.js-worker-reset') : null;
    if (!btn) return;
    ev.preventDefault();
    ev.stopPropagation();
    const wk = btn.getAttribute('data-worker-key') || '';
    const wn = btn.getAttribute('data-worker-name') || '';
    showWorkerResetModal({ workerKey: wk, workerName: wn });
  };

  if (sortedVisible.length > 50) {
    const more = document.createElement('div');
    more.className = 'px-3 py-2 text-xs text-slate-400';
    more.textContent = `Showing first 50 of ${sortedVisible.length}.`;
    rows.appendChild(more);
  }
}

function formatAgo(seconds) {
  const s = Number(seconds);
  if (!Number.isFinite(s) || s < 0) return '-';
  if (s < 60) return `${Math.round(s)}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

function isEpochSeconds(v) {
  const n = Number(v);
  return Number.isFinite(n) && n > 1_000_000_000 && n < 100_000_000_000;
}

function formatBlockWinSubtitle(e) {
  const nowS = Date.now() / 1000;
  const detectedS = e && (e.detected_at ?? e.detectedAt ?? e.detected) != null ? Number(e.detected_at ?? e.detectedAt ?? e.detected) : null;
  const blockTimeS = e && (e.block_time ?? e.blockTime) != null ? Number(e.block_time ?? e.blockTime) : null;
  const tS = e && e.t != null ? Number(e.t) : null;
  const source = e && e.source ? String(e.source) : '';

  if (isEpochSeconds(detectedS)) return `Detected ${formatAgo(Math.max(0, nowS - detectedS))}`;

  const minedCandidate = isEpochSeconds(blockTimeS) ? blockTimeS : isEpochSeconds(tS) ? tS : null;
  if (source === 'backscan' && minedCandidate != null) return `Mined ${formatAgo(Math.max(0, nowS - minedCandidate))}`;

  const detectedCandidate = isEpochSeconds(tS) ? tS : minedCandidate;
  if (detectedCandidate != null) return `Detected ${formatAgo(Math.max(0, nowS - detectedCandidate))}`;

  return '';
}

function formatEtaText(etaText, etaSeconds) {
  const t = typeof etaText === 'string' ? etaText.trim() : '';
  if (t) return t;
  const s = Number(etaSeconds);
  if (!Number.isFinite(s) || s <= 0) return '-';
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function setRing(progress) {
  const ring = document.getElementById('ring');
  const label = document.getElementById('ring-label');
  const circumference = 301.6;
  const p = Math.max(0, Math.min(1, progress || 0));
  const offset = circumference * (1 - p);
  ring.style.strokeDashoffset = `${offset}`;
  label.textContent = `${Math.round(p * 100)}%`;
}

function drawSparklineMulti(canvas, series, opts = {}) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth;
  if (canvas.width !== width) canvas.width = width;
  const height = canvas.height;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const allValues = [];
  for (const s of series || []) {
    for (const p of (s && s.points) || []) {
      const v = p && typeof p.v === 'number' ? p.v : NaN;
      if (Number.isFinite(v)) allValues.push(v);
    }
  }

  if (!allValues.length) {
    ctx.fillStyle = 'rgba(148,163,184,0.6)';
    ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", monospace';
    ctx.fillText('-', 8, 22);
    return;
  }

  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const pad = 10;
  const span = max - min || 1;

  function x(i, n) {
    return pad + (i * (canvas.width - pad * 2)) / Math.max(1, n - 1);
  }
  function y(v) {
    return pad + ((max - v) * (canvas.height - pad * 2)) / span;
  }

  // grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, canvas.height - pad);
  ctx.lineTo(canvas.width - pad, canvas.height - pad);
  ctx.stroke();

  // lines
  ctx.lineWidth = 2;
  for (const s of series || []) {
    const points = (s && s.points) || [];
    if (!points.length) continue;
    ctx.strokeStyle = s.color || 'rgba(255,255,255,0.9)';
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < points.length; i++) {
      const v = points[i] && points[i].v;
      if (!Number.isFinite(v)) {
        started = false;
        continue;
      }
      const px = x(i, points.length);
      const py = y(v);
      if (!started) {
        ctx.moveTo(px, py);
        started = true;
      } else {
        ctx.lineTo(px, py);
      }
    }
    ctx.stroke();

    // last dot (last finite point)
    for (let i = points.length - 1; i >= 0; i--) {
      const v = points[i] && points[i].v;
      if (!Number.isFinite(v)) continue;
      ctx.fillStyle = s.color || 'rgba(255,255,255,0.9)';
      ctx.beginPath();
      ctx.arc(x(i, points.length), y(v), 2.2, 0, Math.PI * 2);
      ctx.fill();
      break;
    }
  }

  // min/max labels
  ctx.fillStyle = 'rgba(148,163,184,0.65)';
  ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", monospace';
  const fmt = opts.format || ((v) => String(v));
  ctx.fillText(fmt(max), pad, 14);
  ctx.fillText(fmt(min), pad, canvas.height - 4);
}

function drawSparkline(canvas, points, opts = {}) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const width = canvas.clientWidth;
  const height = canvas.height;
  if (canvas.width !== width) canvas.width = width;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!points.length) {
    ctx.fillStyle = 'rgba(148,163,184,0.6)';
    ctx.font = '12px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace';
    ctx.fillText('-', 8, 22);
    return;
  }

  const values = points.map((p) => p.v).filter((v) => typeof v === 'number' && !Number.isNaN(v));
  if (!values.length) return;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = 10;
  const span = max - min || 1;

  function x(i) {
    return pad + (i * (canvas.width - pad * 2)) / Math.max(1, points.length - 1);
  }
  function y(v) {
    return pad + ((max - v) * (canvas.height - pad * 2)) / span;
  }

  // grid
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, canvas.height - pad);
  ctx.lineTo(canvas.width - pad, canvas.height - pad);
  ctx.stroke();

  // line
  const gradient = ctx.createLinearGradient(0, canvas.height, canvas.width, 0);
  gradient.addColorStop(0, 'rgba(0,229,255,0.95)');
  gradient.addColorStop(0.5, 'rgba(255,43,214,0.95)');
  gradient.addColorStop(1, 'rgba(255,154,0,0.95)');

  ctx.strokeStyle = gradient;
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < points.length; i++) {
    const px = x(i);
    const py = y(points[i].v);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.stroke();

  // last dot
  const last = points[points.length - 1];
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.beginPath();
  ctx.arc(x(points.length - 1), y(last.v), 2.5, 0, Math.PI * 2);
  ctx.fill();

  // min/max labels
  ctx.fillStyle = 'rgba(148,163,184,0.65)';
  ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace';
  const fmt = opts.format || ((v) => String(v));
  ctx.fillText(fmt(max), pad, 14);
  ctx.fillText(fmt(min), pad, canvas.height - 4);
}

async function fetchJson(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `${res.status}`);
  return data;
}

const __CASHADDR_RE = /^(?:(?:bitcoincash|bchtest|bchreg):)?[qp][0-9a-z]{41,60}$/i;
const __LEGACY_BCH_RE = /^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$/;

function showActionModal({
  kicker = '',
  title = '',
  bodyHtml = '',
  primaryText = '',
  secondaryText = '',
} = {}) {
  const root = document.getElementById('action-modal');
  if (!root) return Promise.resolve('close');

  const elKicker = document.getElementById('action-modal-kicker');
  const elTitle = document.getElementById('action-modal-title');
  const elBody = document.getElementById('action-modal-body');
  const btnX = document.getElementById('action-modal-x');
  const btnPrimary = document.getElementById('action-modal-primary');
  const btnSecondary = document.getElementById('action-modal-secondary');

  if (elKicker) elKicker.textContent = kicker || '';
  if (elTitle) elTitle.textContent = title || '';
  if (elBody) elBody.innerHTML = bodyHtml || '';

  const setBtn = (btn, label) => {
    if (!btn) return;
    const text = String(label || '').trim();
    if (!text) {
      btn.classList.add('hidden');
      btn.textContent = '';
      return;
    }
    btn.textContent = text;
    btn.classList.remove('hidden');
  };
  setBtn(btnPrimary, primaryText);
  setBtn(btnSecondary, secondaryText);

  return new Promise((resolve) => {
    const close = (result) => {
      root.classList.add('hidden');
      if (btnX) btnX.onclick = null;
      if (btnPrimary) btnPrimary.onclick = null;
      if (btnSecondary) btnSecondary.onclick = null;
      root.onclick = null;
      resolve(result);
    };

    if (btnX) btnX.onclick = () => close('close');
    if (btnPrimary) btnPrimary.onclick = () => close('primary');
    if (btnSecondary) btnSecondary.onclick = () => close('secondary');
    root.onclick = (e) => {
      if (e && e.target === root) close('close');
    };
    document.addEventListener(
      'keydown',
      (e) => {
        if (e && e.key === 'Escape' && !root.classList.contains('hidden')) close('close');
      },
      { once: true }
    );

    root.classList.remove('hidden');
  });
}

async function showRestartRequiredModal({ title, bodyHtml }) {
  await showActionModal({
    kicker: 'Restart Required',
    title: title || 'Restart the app to apply changes',
    bodyHtml:
      bodyHtml ||
      `Your changes were saved, but they will not take effect until you restart Curtis BCH from 5tratumOS.<br><br>
       In 5tratumOS: open the Curtis BCH app page and click <span class="font-semibold text-slate-100">Restart</span>.`,
    primaryText: 'OK',
  });
}

function __getCashaddrModalEls() {
  return {
    root: document.getElementById('cashaddr-modal'),
    cashaddr: document.getElementById('cashaddr-modal-cashaddr'),
    legacy: document.getElementById('cashaddr-modal-legacy'),
    copy: document.getElementById('cashaddr-modal-copy'),
    close: document.getElementById('cashaddr-modal-close'),
  };
}

async function __copyToClipboard(text) {
  const t = String(text || '').trim();
  if (!t) return false;
  try {
    await navigator.clipboard.writeText(t);
    return true;
  } catch {}
  try {
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {}
  return false;
}

function __showCashaddrModal({ cashaddr, legacy }) {
  const els = __getCashaddrModalEls();
  if (!els.root) return;

  if (els.cashaddr) els.cashaddr.textContent = cashaddr ? String(cashaddr) : '';
  if (els.legacy) els.legacy.textContent = legacy ? String(legacy) : '';

  if (els.copy) {
    els.copy.textContent = 'Copy';
    els.copy.onclick = async () => {
      const ok = await __copyToClipboard(legacy);
      if (ok) els.copy.textContent = 'Copied';
      setTimeout(() => {
        if (els.copy) els.copy.textContent = 'Copy';
      }, 1200);
    };
  }

  const close = () => {
    els.root.classList.add('hidden');
  };

  if (els.close) els.close.onclick = close;
  els.root.onclick = (e) => {
    if (e && e.target === els.root) close();
  };
  document.addEventListener(
    'keydown',
    (e) => {
      if (e && e.key === 'Escape' && !els.root.classList.contains('hidden')) close();
    },
    { once: true }
  );

  els.root.classList.remove('hidden');
}

function showTab(tab) {
  const home = document.getElementById('view-home');
  const pool = document.getElementById('view-pool');
  const luck = document.getElementById('view-luck');
  const blocks = document.getElementById('view-blocks');
  const settings = document.getElementById('view-settings');
  const project = document.getElementById('view-project');
  const tHome = document.getElementById('tab-home');
  const tPool = document.getElementById('tab-pool');
  const tLuck = document.getElementById('tab-luck');
  const tBlocks = document.getElementById('tab-blocks');
  const tSet = document.getElementById('tab-settings');
  const tProject = document.getElementById('tab-project');

  const which = tab || 'home';
  home.classList.toggle('hidden', which !== 'home');
  pool.classList.toggle('hidden', which !== 'pool');
  if (luck) luck.classList.toggle('hidden', which !== 'luck');
  if (blocks) blocks.classList.toggle('hidden', which !== 'blocks');
  settings.classList.toggle('hidden', which !== 'settings');
  if (project) project.classList.toggle('hidden', which !== 'project');

  tHome.classList.toggle('axe-tab--active', which === 'home');
  tPool.classList.toggle('axe-tab--active', which === 'pool');
  if (tLuck) tLuck.classList.toggle('axe-tab--active', which === 'luck');
  if (tBlocks) tBlocks.classList.toggle('axe-tab--active', which === 'blocks');
  tSet.classList.toggle('axe-tab--active', which === 'settings');
  if (tProject) tProject.classList.toggle('axe-tab--active', which === 'project');

  window.__activeTab = which;
}

function escapeHtml(s) {
  const str = s == null ? '' : String(s);
  return str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function shortenLabel(s) {
  if (!s) return '';
  const str = String(s);
  if (str.length <= 28) return str;
  return `${str.slice(0, 10)}...${str.slice(-8)}`;
}

function formatBestShareWorkerLabel(v) {
  const s = v == null ? '' : String(v).trim();
  if (!s) return '-';
  const parts = splitWorkerIdent(s);
  const label = parts && parts.worker ? parts.worker : shortenLabel(s);
  return `by ${label}`;
}

function bestWorkerByField(rows, fieldName) {
  let best = null;
  let bestWorker = '';
  for (const r of rows || []) {
    if (!r || typeof r !== 'object') continue;
    const raw = r[fieldName];
    const n = raw == null ? null : Number(raw);
    if (!Number.isFinite(n) || n <= 0) continue;
    if (best == null || n > best) {
      best = n;
      bestWorker = r.workername != null ? String(r.workername) : '';
    }
  }
  return bestWorker;
}

function formatReadinessPill(ok, label) {
  return `<span class="${ok ? 'axe-pill axe-pill--ok' : 'axe-pill'}">${escapeHtml(label)}</span>`;
}

function formatReadinessCard(check) {
  const blocked = !(check && check.ok);
  const cardClass = blocked
    ? 'rounded-xl border border-red-500/25 bg-red-950/30 px-4 py-3'
    : 'rounded-xl border border-white/10 bg-black/25 px-4 py-3';
  return `
    <div class="${cardClass}">
      <div class="flex items-center justify-between gap-3">
        <div class="axe-stat__k">${escapeHtml((check && check.label) || 'Check')}</div>
        ${formatReadinessPill(check && check.ok, check && check.ok ? 'Ready' : 'Blocked')}
      </div>
      <div class="mt-2 text-sm ${blocked ? 'text-red-200' : 'text-slate-100'}">${escapeHtml((check && check.value) || '-')}</div>
      <div class="mt-1 text-xs text-slate-400">${escapeHtml((check && check.help) || '')}</div>
    </div>
  `;
}

function renderReadiness(state) {
  const checksEl = document.getElementById('readiness-checks');
  const pillEl = document.getElementById('readiness-pill');
  const gateEl = document.getElementById('readiness-gate');
  const nextEl = document.getElementById('readiness-next-step');
  const repairEl = document.getElementById('readiness-repair');
  const nodeEl = document.getElementById('readiness-node-status');
  const poolEl = document.getElementById('readiness-pool-status');
  const stratumEl = document.getElementById('readiness-stratum-status');
  const msgEl = document.getElementById('readiness-status-message');
  if (!checksEl) return;

  const checks = Array.isArray(state && state.checks) ? state.checks : [];
  const ready = checks.filter((c) => c && c.ok).length;
  const total = checks.length;
  checksEl.innerHTML = checks.map(formatReadinessCard).join('');
  if (pillEl) {
    pillEl.textContent = total ? `${ready}/${total} checks ready` : 'Checking...';
    pillEl.classList.toggle('axe-pill--ok', total > 0 && ready === total);
  }
  if (gateEl) gateEl.textContent = state && state.gate ? state.gate : '-';
  if (nextEl) nextEl.textContent = state && state.nextStep ? state.nextStep : '-';
  if (repairEl) repairEl.textContent = state && state.repair ? state.repair : 'No startup repair recorded.';
  if (nodeEl) nodeEl.textContent = state && state.nodeStatus ? state.nodeStatus : '-';
  if (poolEl) poolEl.textContent = state && state.poolStatus ? state.poolStatus : '-';
  if (stratumEl) stratumEl.textContent = state && state.stratumStatus ? state.stratumStatus : '-';
  if (msgEl) msgEl.textContent = state && state.message ? state.message : '-';
}

async function refresh() {
  let nodeStatus = 'Offline';
  let nodeMessage = 'Node RPC is offline or still starting.';
  let nodeGate = 'Node RPC is offline or still starting.';
  let nodeNextStep = 'Wait for BCHN to finish starting, then refresh.';
  let nodeIsSynced = false;
  let payoutConfigured = Boolean(window.__payoutAddress && String(window.__payoutAddress).trim());
  let poolLabel = 'Unavailable';
  let poolMessage = 'Pool backend has not reported yet.';
  let stratumLabel = 'Blocked';
  let stratumReason = 'Set a BCH payout address in Settings, then restart Curtis BCH.';
  let poolBackendOk = false;
  let stratumOpen = false;
  let repairMessage = 'No startup repair recorded.';

  try {
    const res = await fetch('/api/node', { cache: 'no-store' });
    const node = await res.json().catch(() => ({}));
    if (!res.ok) throw node;
    const ibd = !!node.initialblockdownload;
    const progress = ibd ? (node.verificationprogress || 0) : 1;
    const pct = Math.round(progress * 100);
    const cached = !!node.cached;

    const lastSeen = Number(node.lastSeen) || 0;
    const ageS = lastSeen ? Math.max(0, Math.floor(Date.now() / 1000 - lastSeen)) : 0;
    const ageM = Math.floor(ageS / 60);
    const ageText = lastSeen ? `Last seen ${ageM}m ago` : 'Last seen unknown';

    const cacheFreshS = 180;
    const cacheOfflineS = 900;
    const cacheFresh = cached && lastSeen && ageS <= cacheFreshS;
    const cacheStale = cached && lastSeen && ageS > cacheFreshS && ageS <= cacheOfflineS;

    if (cacheFresh || cacheStale) {
      const stateText = ibd ? `Syncing ${pct}%` : `Running`;
      document.getElementById('sync-text').textContent = cacheStale ? `${stateText} (stale)` : stateText;
      document.getElementById('sync-subtext').textContent = `${ageText} | ${node.chain ?? '-'} | ${node.subversion ?? ''}`.trim();
    } else if (cached) {
      document.getElementById('sync-text').textContent = 'Starting';
      document.getElementById('sync-subtext').textContent = `${ageText} | ${node.chain ?? '-'} | ${node.subversion ?? ''}`.trim();
    } else {
      document.getElementById('sync-text').textContent = ibd ? `Syncing ${pct}%` : `Synchronized ${pct}%`;
      document.getElementById('sync-subtext').textContent = `${node.chain ?? '-'} | ${node.subversion ?? ''}`.trim();
    }

    // Badges, ETA, and warnings
    const badges = [];
    if (node && (node.warmup || node.warmupMessage)) badges.push('Warmup');
    if (ibd) badges.push('IBD');
    if (node && node.pruned) badges.push('Pruned');
    if (node && node.reindexRequested) badges.push('Reindex scheduled');
    if (node && node.reindexRequired) badges.push('Reindex required');
    if (cacheStale) badges.push('Stale');
    const badgesEl = document.getElementById('sync-badges');
    if (badgesEl) badgesEl.textContent = badges.join(' • ');

    const etaEl = document.getElementById('sync-eta');
    if (etaEl) {
      const etaS = ibd ? computeSyncEtaSeconds(node, 'bchSyncRate') : null;
      if (ibd && etaS != null && Number.isFinite(etaS) && etaS > 0 && pct < 100) {
        etaEl.textContent = `Sync ETA: ${formatDuration(etaS)}`;
        etaEl.classList.remove('hidden');
      } else {
        etaEl.textContent = '';
        etaEl.classList.add('hidden');
      }
    }

    const lastEl = document.getElementById('last-block');
    if (lastEl) {
      const bt = Number(node && node.best_block_time);
      const mt = Number(node && node.median_time);
      const nowS = Math.floor(Date.now() / 1000);
      const parts = [];
      if (Number.isFinite(bt) && bt > 0) parts.push(`Last block ${formatAgo(nowS - bt)}`);
      if (Number.isFinite(mt) && mt > 0) parts.push(`median ${formatAgo(nowS - mt)}`);
      if (parts.length) {
        lastEl.textContent = parts.join(' | ');
        lastEl.classList.remove('hidden');
      } else {
        lastEl.textContent = '';
        lastEl.classList.add('hidden');
      }
    }

    const warnEl = document.getElementById('sync-warnings');
    if (warnEl) {
      const warnings = [];
      const conn = Number(node && node.connections);
      if (Number.isFinite(conn) && conn > 0 && conn < 3) warnings.push('Low peers');
      const w = node && node.warnings ? String(node.warnings).trim() : '';
      if (w) warnings.push(w);
      if (warnings.length) {
        warnEl.textContent = `Warning: ${warnings.join(' | ')}`;
        warnEl.classList.remove('hidden');
      } else {
        warnEl.textContent = '';
        warnEl.classList.add('hidden');
      }
    }

    document.getElementById('blocks').textContent = node.blocks ?? '-';
    document.getElementById('headers').textContent = node.headers ?? '-';
    const heightModern = document.getElementById('height');
    if (heightModern) {
      const b = Number(node.blocks), h = Number(node.headers);
      heightModern.textContent = Number.isFinite(b) && Number.isFinite(h) && h > 0
        ? `${b.toLocaleString()} / ${h.toLocaleString()}`
        : (node.blocks ?? '-');
    }
    const difficultyModern = document.getElementById('difficulty');
    if (difficultyModern) difficultyModern.textContent = formatBestShare(node.difficulty);
    const networkTitle = document.getElementById('network-title');
    if (networkTitle) {
      const chain = String(node.chain || '').toLowerCase();
      networkTitle.textContent = (chain === 'test' || chain === 'test4')
        ? 'Bitcoin Cash · Testnet4'
        : 'Bitcoin Cash · Mainnet';
    }
    const syncModern = document.getElementById('sync');
    if (syncModern) {
      const verifyPct = Math.max(0, Math.min(100, Number(node.verificationprogress || 0) * 100));
      const blockPct = Number(node.headers) > 0
        ? Math.max(0, Math.min(100, Number(node.blocks || 0) / Number(node.headers) * 100))
        : 0;
      syncModern.textContent = ibd
        ? `${verifyPct < 1 ? verifyPct.toFixed(4) : verifyPct.toFixed(2)}% verified · ${blockPct.toFixed(1)}% blocks`
        : '100%';
    }
    const lagEl = document.getElementById('chain-lag');
    const lagSubEl = document.getElementById('chain-lag-sub');
    if (lagEl) {
      const blocksN = Number(node.blocks);
      const headersN = Number(node.headers);
      if (Number.isFinite(blocksN) && Number.isFinite(headersN)) {
        const behind = Math.max(0, headersN - blocksN);
        const ahead = Math.max(0, blocksN - headersN);
        lagEl.textContent = `+${behind} / -${ahead}`;
        if (lagSubEl) lagSubEl.textContent = 'blocks behind / ahead';
      } else {
        lagEl.textContent = '-';
        if (lagSubEl) lagSubEl.textContent = '-';
      }
    }
    document.getElementById('peers').textContent = node.connections ?? '-';
    document.getElementById('mempool').textContent = bytesToMiB(node.mempool_bytes);
    const diskEl = document.getElementById('disk');
    if (diskEl) diskEl.textContent = bytesToGiB(node.size_on_disk);
    setRing(progress);

    const pill = document.getElementById('status-pill');
    const pillText = cached && !(cacheFresh || cacheStale) ? 'Starting' : ibd ? 'Syncing' : 'Running';
    pill.textContent = pillText;
    pill.classList.toggle('axe-pill--ok', pillText === 'Running');

    const templateReady = node && Object.prototype.hasOwnProperty.call(node, 'template_ready') ? node.template_ready : null;
    const templateErrorCode = node && Object.prototype.hasOwnProperty.call(node, 'template_error_code') ? node.template_error_code : null;
    const templateError = node && typeof node.template_error === 'string' ? node.template_error.trim() : '';
    const reindexRequested = Boolean(node && node.reindexRequested);
    const reindexRequired = Boolean(node && node.reindexRequired);

    nodeStatus = cached && !(cacheFresh || cacheStale) ? 'Starting' : ibd ? `Syncing (${pct}%)` : 'Synced';
    nodeMessage = cached && !(cacheFresh || cacheStale)
      ? 'Node RPC is starting and cached status is being used.'
      : ibd
      ? `Blockchain sync is still in progress at ${pct}%.`
      : 'Node RPC is online and synchronized.';
    nodeGate = ibd ? 'Blockchain sync is still in progress.' : 'Node side is ready.';
    nodeNextStep = ibd ? 'Wait for BCH sync to finish before expecting pool readiness.' : 'Node side is ready.';
    nodeIsSynced = !ibd;
    if (reindexRequired) {
      repairMessage = 'Node database repair is required before BCH can come online.';
    } else if (reindexRequested) {
      repairMessage = 'Chainstate reindex is queued and needs an app restart to begin.';
    }

    if (!ibd && templateReady === false) {
      nodeStatus = 'Mining ready: no';
      nodeMessage = templateErrorCode === -9
        ? 'Node RPC is up and peers are present, but BCH is not returning mining templates yet.'
        : templateError
        ? `BCH template generation is failing: ${templateError}`
        : 'BCH is not returning mining templates yet.';
      nodeGate = nodeMessage;
      nodeNextStep = 'Wait for BCH to become mining-ready before expecting pool readiness.';
    }
  } catch (err) {
    const reindexRequired = Boolean(err && err.reindexRequired);
    const reindexRequested = Boolean(err && err.reindexRequested);

    if (reindexRequired || reindexRequested) {
      document.getElementById('sync-text').textContent = reindexRequired ? 'Reindex required' : 'Reindex scheduled';
      document.getElementById('sync-subtext').textContent = reindexRequired
        ? 'Node was previously pruned. Restart the app to rebuild the database (chainstate reindex).'
        : 'Restart the app to rebuild the database (chainstate reindex).';
    } else {
      document.getElementById('sync-text').textContent = 'Node unavailable';
      document.getElementById('sync-subtext').textContent = 'Node is starting (after reboot) or offline.';
    }
    const badgesEl = document.getElementById('sync-badges');
    if (badgesEl) badgesEl.textContent = reindexRequired ? 'Reindex required' : reindexRequested ? 'Reindex scheduled' : '';
    const etaEl = document.getElementById('sync-eta');
    if (etaEl) etaEl.classList.add('hidden');
    const lastEl = document.getElementById('last-block');
    if (lastEl) lastEl.classList.add('hidden');
    const warnEl = document.getElementById('sync-warnings');
    if (warnEl) warnEl.classList.add('hidden');
    setRing(0);
    const lagEl = document.getElementById('chain-lag');
    if (lagEl) lagEl.textContent = '-';
    const lagSubEl = document.getElementById('chain-lag-sub');
    if (lagSubEl) lagSubEl.textContent = '-';
    const pill = document.getElementById('status-pill');
    pill.textContent = reindexRequired ? 'Reindex' : 'Offline';
    pill.classList.remove('axe-pill--ok');
    const diskEl = document.getElementById('disk');
    if (diskEl) diskEl.textContent = '-';
    nodeStatus = reindexRequired ? 'Reindex required' : reindexRequested ? 'Reindex scheduled' : 'Offline';
    nodeMessage = reindexRequired
      ? 'Node database needs a reindex before RPC can come online.'
      : reindexRequested
      ? 'Node reindex has been scheduled and needs a restart.'
      : 'Node RPC is offline or still starting.';
    nodeGate = reindexRequired
      ? 'Node database repair is blocking startup.'
      : reindexRequested
      ? 'Node restart is required to begin the BCH reindex.'
      : 'Node RPC is offline or still starting.';
    nodeNextStep = reindexRequired || reindexRequested
      ? 'Restart Curtis BCH from 5tratumOS to begin the requested reindex.'
      : 'Wait for BCHN to finish starting, then refresh.';
    nodeIsSynced = false;
    repairMessage = reindexRequired
      ? 'Node database repair is required before BCH can come online.'
      : reindexRequested
      ? 'Chainstate reindex is queued and needs an app restart to begin.'
      : repairMessage;
  }

  try {
    const pool = await fetchJson('/api/pool');
    const poolSettings = pool && pool.pool_settings && typeof pool.pool_settings === 'object' ? pool.pool_settings : null;
    const stratum = pool && pool.stratum && typeof pool.stratum === 'object' ? pool.stratum : null;
    payoutConfigured = Boolean((poolSettings && poolSettings.configured) || (window.__payoutAddress && String(window.__payoutAddress).trim()));
    const backendReady = pool && Object.prototype.hasOwnProperty.call(pool, 'backend_ready') ? Boolean(pool.backend_ready) : null;
    const backendReason = pool && typeof pool.backend_reason === 'string' && pool.backend_reason.trim()
      ? pool.backend_reason.trim()
      : '';
    poolBackendOk = backendReady !== null ? backendReady : !Boolean(pool && (pool.error || pool.Error));
    poolLabel = poolBackendOk ? 'Running' : 'Waiting';
    poolMessage = poolBackendOk
      ? (backendReason || 'Pool backend is online.')
      : (backendReason || String((pool && (pool.error || pool.Error)) || 'Pool backend is unavailable.'));
    stratumOpen = Boolean(stratum && stratum.status === 'open');
    stratumLabel =
      stratum && typeof stratum.status === 'string'
        ? stratum.status === 'open'
          ? 'Open'
          : stratum.status === 'locked'
          ? 'Locked'
          : stratum.status === 'error'
          ? 'Error'
          : 'Unknown'
        : 'Unavailable';
    stratumReason =
      stratum && typeof stratum.reason === 'string' && stratum.reason.trim()
        ? stratum.reason.trim()
        : stratumOpen
        ? 'Remote miners can connect.'
        : 'Stratum is not ready for miner connections yet.';

    if (!payoutConfigured) {
      stratumOpen = false;
      stratumLabel = 'Blocked';
      stratumReason = 'Set a BCH payout address in Settings, then restart Curtis BCH.';
    } else if (!nodeIsSynced) {
      stratumOpen = false;
      stratumLabel = 'Blocked';
      stratumReason = 'Wait for the BCH node to finish syncing before opening Stratum.';
    } else if (!poolBackendOk) {
      stratumOpen = false;
      stratumLabel = 'Blocked';
      stratumReason = poolMessage || 'Wait for the pool backend to finish starting and reconnect to the BCH node.';
    }

    document.getElementById('workers').textContent = pool.workers ?? '-';
    document.getElementById('hashrate').textContent = formatTHS(pool.hashrate_ths);
    const elBestSince = document.getElementById('bestshare-since');
    if (elBestSince) elBestSince.textContent = formatBestShare(pool.best_share_since_block);
    const elBestAll = document.getElementById('bestshare-alltime');
    if (elBestAll) elBestAll.textContent = formatBestShare(pool.best_share_all_time);
    const elEta = document.getElementById('eta');
    if (elEta) elEta.textContent = formatEtaText(pool.eta_text, pool.eta_seconds);
    document.getElementById('workers-summary').textContent = pool.workers ?? '-';
    document.getElementById('hashrate-summary').textContent = formatTHS(pool.hashrate_ths);
    const elEtaSummary = document.getElementById('eta-summary');
    if (elEtaSummary) elEtaSummary.textContent = formatEtaText(pool.eta_text, pool.eta_seconds);

    const elNetDiff = document.getElementById('network-difficulty');
    if (elNetDiff) elNetDiff.textContent = formatBestShare(pool.network_difficulty);
    try {
      window.__networkDifficulty = pool && pool.network_difficulty != null ? Number(pool.network_difficulty) : null;
    } catch {
      window.__networkDifficulty = null;
    }
    const elNetSub = document.getElementById('network-difficulty-sub');
    if (elNetSub) {
      const algo = pool.network_algo ? String(pool.network_algo).toUpperCase() : 'SHA256D';
      const height = pool.network_height != null ? String(pool.network_height) : '';
      elNetSub.textContent = height ? `${algo} | HEIGHT ${height}` : '-';
    }

    const elNetDiffSummary = document.getElementById('network-difficulty-summary');
    if (elNetDiffSummary) elNetDiffSummary.textContent = formatBestShare(pool.network_difficulty);
    const elNetSubSummary = document.getElementById('network-difficulty-summary-sub');
    if (elNetSubSummary) {
      const algo = pool.network_algo ? String(pool.network_algo).toUpperCase() : 'SHA256D';
      const height = pool.network_height != null ? String(pool.network_height) : '';
      elNetSubSummary.textContent = height ? `${algo} | height ${height}` : algo;
    }

    try {
      const w = await fetchJson('/api/pool/workers');
      const elLastShare = document.getElementById('last-share');
      if (elLastShare) elLastShare.textContent = formatAgo(w.lastshare_ago_s);

      const details = Array.isArray(w && w.workers_details) ? w.workers_details : [];

      const bestSinceWorkerEl = document.getElementById('bestshare-since-worker');
      const bestAllWorkerEl = document.getElementById('bestshare-alltime-worker');
      const sinceV = pool && pool.best_share_since_block != null ? Number(pool.best_share_since_block) : null;
      if (bestSinceWorkerEl) {
        const w = pool && pool.best_share_since_block_worker ? pool.best_share_since_block_worker : '';
        bestSinceWorkerEl.textContent = sinceV != null && Number.isFinite(sinceV) && sinceV > 0 ? formatBestShareWorkerLabel(w) : '-';
      }
      if (bestAllWorkerEl) bestAllWorkerEl.textContent = formatBestShareWorkerLabel(bestWorkerByField(details, 'bestever'));

      const payoutFull = window.__payoutAddress ? String(window.__payoutAddress) : '';
      const miners = details.map((row) => ({
        miner: payoutFull,
        worker: row && row.workername ? String(row.workername) : '',
        hashrate_ths: row && (row.hashrate_ths ?? row.hashrate_1m_ths),
        hashrate_ths_live_10m: row && (row.hashrate_ths ?? row.hashrate_1m_ths),
        lastShare: row && row.lastshare_ago_s != null ? Date.now() - Number(row.lastshare_ago_s) * 1000 : null,
        bestshare_since_block: row && row.bestshare_since_block != null ? Number(row.bestshare_since_block) : null,
        current_diff: row && row.current_diff != null ? Number(row.current_diff) : null,
      }));
      miners._totalWorkers = w && w.workers != null ? Number(w.workers) : null;

      try {
        renderWorkerDetails(miners);
      } catch (e) {
        try {
          console.error('Curtis BCH renderWorkerDetails failed:', e);
        } catch {}
        const status = document.getElementById('worker-details-status');
        const rows = document.getElementById('worker-details-rows');
        if (status) status.textContent = `Worker stats render error: ${e && e.message ? String(e.message) : 'unknown'}`;
        if (rows) rows.innerHTML = '<div class="px-3 py-2 text-xs text-slate-400">-</div>';
      }
    } catch (err) {
      try {
        console.error('Curtis BCH worker details failed:', err);
      } catch {}
      const elLastShare = document.getElementById('last-share');
      if (elLastShare) elLastShare.textContent = '-';
      const bestSinceWorkerEl = document.getElementById('bestshare-since-worker');
      const bestAllWorkerEl = document.getElementById('bestshare-alltime-worker');
      if (bestSinceWorkerEl) bestSinceWorkerEl.textContent = '-';
      if (bestAllWorkerEl) bestAllWorkerEl.textContent = '-';
      const status = document.getElementById('worker-details-status');
      const rows = document.getElementById('worker-details-rows');
      if (status) {
        const msg = err && typeof err === 'object' && 'message' in err ? String(err.message || '') : '';
        if (msg === 'redirect') {
          status.textContent = 'Worker stats unavailable (auth redirect). Open Curtis BCH via the same hostname you used for your OS portal (IP vs hostname).';
        } else if (msg) {
          status.textContent = `Worker stats unavailable (${msg}).`;
        } else {
          status.textContent = 'Worker stats unavailable (app starting).';
        }
      }
      if (rows) rows.innerHTML = '<div class="px-3 py-2 text-xs text-slate-400">-</div>';
    }

    const h = (pool && pool.hashrates_ths) || {};
    const el1m = document.getElementById('hashrate-1m');
    const el5m = document.getElementById('hashrate-5m');
    const el15m = document.getElementById('hashrate-15m');
    const el1h = document.getElementById('hashrate-1h');
    const el6h = document.getElementById('hashrate-6h');
    const el1d = document.getElementById('hashrate-1d');
    const el7d = document.getElementById('hashrate-7d');
    if (el1m) el1m.textContent = formatHashrateFromTHS(h['1m']);
    if (el5m) el5m.textContent = formatHashrateFromTHS(h['5m']);
    if (el15m) el15m.textContent = formatHashrateFromTHS(h['15m']);
    if (el1h) el1h.textContent = formatHashrateFromTHS(h['1h']);
    if (el6h) el6h.textContent = formatHashrateFromTHS(h['6h']);
    if (el1d) el1d.textContent = formatHashrateFromTHS(h['1d']);
    if (el7d) el7d.textContent = formatHashrateFromTHS(h['7d']);

    const lg1m = document.getElementById('legend-1m');
    const lg5m = document.getElementById('legend-5m');
    const lg15m = document.getElementById('legend-15m');
    const lg1h = document.getElementById('legend-1h');
    if (lg1m) lg1m.textContent = formatHashrateFromTHS(h['1m']);
    if (lg5m) lg5m.textContent = formatHashrateFromTHS(h['5m']);
    if (lg15m) lg15m.textContent = formatHashrateFromTHS(h['15m']);
    if (lg1h) lg1h.textContent = formatHashrateFromTHS(h['1h']);
  } catch {
    document.getElementById('workers').textContent = '-';
    document.getElementById('hashrate').textContent = '-';
    const elBestSince = document.getElementById('bestshare-since');
    if (elBestSince) elBestSince.textContent = '-';
    const elBestAll = document.getElementById('bestshare-alltime');
    if (elBestAll) elBestAll.textContent = '-';
    const bestSinceWorkerEl = document.getElementById('bestshare-since-worker');
    const bestAllWorkerEl = document.getElementById('bestshare-alltime-worker');
    if (bestSinceWorkerEl) bestSinceWorkerEl.textContent = '-';
    if (bestAllWorkerEl) bestAllWorkerEl.textContent = '-';
    const elEta = document.getElementById('eta');
    if (elEta) elEta.textContent = '-';
    document.getElementById('workers-summary').textContent = '-';
    document.getElementById('hashrate-summary').textContent = '-';
    const elEtaSummary = document.getElementById('eta-summary');
    if (elEtaSummary) elEtaSummary.textContent = '-';

    const elNetDiff = document.getElementById('network-difficulty');
    if (elNetDiff) elNetDiff.textContent = '-';
    const elNetSub = document.getElementById('network-difficulty-sub');
    if (elNetSub) elNetSub.textContent = '-';

    const elNetDiffSummary = document.getElementById('network-difficulty-summary');
    if (elNetDiffSummary) elNetDiffSummary.textContent = '-';
    const elNetSubSummary = document.getElementById('network-difficulty-summary-sub');
    if (elNetSubSummary) elNetSubSummary.textContent = '-';
    const elLastShare = document.getElementById('last-share');
    if (elLastShare) elLastShare.textContent = '-';
    const status = document.getElementById('worker-details-status');
    const rows = document.getElementById('worker-details-rows');
    if (status) status.textContent = '-';
    if (rows) rows.innerHTML = '';

    const ids = ['hashrate-1m', 'hashrate-5m', 'hashrate-15m', 'hashrate-1h', 'hashrate-6h', 'hashrate-1d', 'hashrate-7d'];
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) el.textContent = '-';
    }

    const legendIds = ['legend-1m', 'legend-5m', 'legend-15m', 'legend-1h'];
    for (const id of legendIds) {
      const el = document.getElementById(id);
      if (el) el.textContent = '-';
    }
    poolBackendOk = false;
    poolLabel = 'Unavailable';
    poolMessage = 'Pool backend is unavailable or still starting.';
    stratumOpen = false;
    stratumLabel = 'Blocked';
    stratumReason = payoutConfigured
      ? 'Wait for the pool backend to finish starting and reconnect to the BCH node.'
      : 'Set a BCH payout address in Settings, then restart Curtis BCH.';
  }

  {
    const checks = [
      {
        label: 'Node RPC',
        ok: nodeStatus !== 'Offline' && nodeStatus !== 'Reindex required',
        value: nodeStatus,
        help: nodeMessage,
      },
      {
        label: 'Blockchain sync',
        ok: nodeIsSynced,
        value: nodeIsSynced ? 'Synchronized' : nodeStatus,
        help: nodeIsSynced ? 'Chain is synchronized and ready for pool traffic.' : nodeGate,
      },
      {
        label: 'Payout address',
        ok: payoutConfigured,
        value: payoutConfigured ? 'Configured' : 'Missing',
        help: payoutConfigured ? 'Block rewards have a payout target.' : 'Set a BCH payout address in Settings.',
      },
      {
        label: 'Pool backend',
        ok: poolBackendOk,
        value: poolLabel,
        help: poolMessage,
      },
      {
        label: 'Stratum',
        ok: stratumOpen,
        value: stratumLabel,
        help: stratumReason,
      },
    ];

    const blocked = checks.find((c) => !c.ok);
    let nextStep = nodeNextStep;
    if (blocked) {
      if (blocked.label === 'Payout address') nextStep = 'Set a BCH payout address in Settings, then restart Curtis BCH.';
      else if (blocked.label === 'Pool backend') nextStep = poolMessage || 'Wait for ckpool to finish starting and reconnect to the node.';
      else if (blocked.label === 'Stratum') nextStep = stratumReason;
    } else {
      nextStep = 'Connect miners from the Pool tab once Stratum is open.';
    }

    renderReadiness({
      checks,
      nodeStatus,
      poolStatus: poolLabel,
      stratumStatus: stratumLabel,
      message: blocked ? blocked.help : 'Node, pool, and Stratum are all ready.',
      gate: blocked ? blocked.help : 'No blocking condition detected.',
      nextStep,
      repair: repairMessage,
    });
  }

  if (window.__activeTab === 'blocks') {
    await refreshBlocks();
  }
  if (window.__activeTab === 'luck') {
    await refreshLuck();
  }
}

function renderLuck(data) {
  const current = data && typeof data.current === 'object' ? data.current : {};
  const recent = Array.isArray(data && data.recent) ? data.recent : [];
  const summary = data && typeof data.summary === 'object' ? data.summary : {};

  const rawPct = current && current.luckPct;
  const pct = rawPct == null ? Number.NaN : Number(rawPct);
  const validPct = Number.isFinite(pct) && pct >= 0 ? pct : null;
  const rebuildingEffort = Boolean(current && current.effortRebuilding);
  const completeEffort = Boolean(current && current.effortCoverageComplete);
  const progress = validPct != null ? clamp(validPct, 0, 100) : 0;
  const progressFill = document.getElementById('luck-progress-fill');
  if (progressFill) {
    progressFill.style.width = `${progress}%`;
    progressFill.style.minWidth = validPct != null && validPct > 0 ? '6px' : '0';
    progressFill.classList.toggle('Curtis BCH-luck-progress__fill--over', validPct != null && validPct > 100);
  }

  const luckHeadline = document.getElementById('luck-current-headline');
  if (luckHeadline) luckHeadline.textContent = formatLuckPercent(validPct);
  const luckPctEl = document.getElementById('luck-current-pct');
  if (luckPctEl) luckPctEl.textContent = formatLuckPercent(validPct);

  const lastMinerRaw = String(current && current.lastBlockMiner || '').trim();
  const lastMinerParts = splitWorkerIdent(lastMinerRaw);
  const lastMiner = lastMinerParts.worker || shortenMiner(lastMinerRaw);
  const lastHeight = current && current.lastBlockHeight != null ? String(current.lastBlockHeight) : '';
  const currentSummary = document.getElementById('luck-current-summary');
  if (currentSummary) {
    if (validPct == null) {
      currentSummary.textContent = rebuildingEffort
        ? 'Rebuilding difficulty-weighted round effort from the pool log.'
        : 'Waiting for tracked shares to estimate round effort.';
    } else {
      const delta = Math.abs(100 - validPct);
      const direction = validPct >= 100 ? 'beyond' : 'below';
      const lastBlockText = lastHeight || lastMinerRaw
        ? ` Last block ${lastHeight || '-'}${lastMinerRaw ? ` by ${lastMiner || '-'}` : ''}.`
        : '';
      const coverageText = completeEffort ? '' : ' Partial history only.';
      currentSummary.textContent = `${formatSmallPercent(delta)} ${direction} expected effort so far.${lastBlockText}${coverageText}`;
    }
  }

  const progressNote = document.getElementById('luck-progress-note');
  if (progressNote) {
    if (validPct == null) {
      progressNote.textContent = 'Expected block at 100% effort.';
    } else if (validPct > 100) {
      progressNote.textContent = `${formatSmallPercent(validPct - 100)} beyond expected effort. The round is just running unlucky.`;
    } else {
      progressNote.textContent = `${formatSmallPercent(100 - validPct)} below expected effort so far.`;
    }
  }

  const sinceLabelEl = document.getElementById('luck-since-label');
  if (sinceLabelEl) {
    sinceLabelEl.textContent = current && current.lastBlockTime
      ? 'Since last block'
      : 'Since tracking began';
  }
  const sinceEl = document.getElementById('luck-since');
  if (sinceEl) {
    const sinceSeconds = Number(current && current.sinceSeconds);
    sinceEl.textContent = Number.isFinite(sinceSeconds) && sinceSeconds > 0 ? formatDuration(sinceSeconds) : '-';
  }
  const roundWorkEl = document.getElementById('luck-round-work');
  if (roundWorkEl) roundWorkEl.textContent = formatBestShare(current && current.totalDiff);
  const roundSharesEl = document.getElementById('luck-round-shares');
  if (roundSharesEl) {
    const rawShares = current && current.shares;
    const shares = rawShares == null ? Number.NaN : Number(rawShares);
    roundSharesEl.textContent = Number.isFinite(shares) && shares >= 0 ? String(Math.floor(shares)) : '-';
  }

  const averageEl = document.getElementById('luck-average');
  if (averageEl) averageEl.textContent = formatLuckPercent(summary && summary.averageLuckPct);
  const bestEl = document.getElementById('luck-best');
  if (bestEl) bestEl.textContent = formatLuckPercent(summary && summary.bestLuckPct);
  const worstEl = document.getElementById('luck-worst');
  if (worstEl) worstEl.textContent = formatLuckPercent(summary && summary.worstLuckPct);

  const statusEl = document.getElementById('luck-status');
  const rowsEl = document.getElementById('luck-rows');
  if (!rowsEl) return;

  const formatMinerLabel = (raw) => {
    const text = String(raw || '').trim();
    if (!text) return '-';
    const parts = splitWorkerIdent(text);
    return parts.worker || shortenMiner(text);
  };

  if (!recent.length) {
    if (statusEl) statusEl.textContent = 'Waiting for first found block.';
    rowsEl.innerHTML = '<div class="px-3 py-3 text-sm text-slate-400">No found blocks recorded yet. When the next block lands, this tab will show the miner and round effort immediately.</div>';
    return;
  }

  if (statusEl) statusEl.textContent = `${recent.length} shown`;
  rowsEl.innerHTML = '';
  for (const block of recent) {
    const height = block && block.height != null ? String(block.height) : '-';
    const minerRaw = String(block && (block.miner || block.solve_worker) || '').trim();
    const minerLabel = formatMinerLabel(minerRaw);
    const luckText = formatLuckPercent(block && (block.luck_pct ?? block.luckPct));
    const conf = block && block.confirmations != null ? Number(block.confirmations) : null;
    const statusText = conf != null && Number.isFinite(conf) && conf > 0 ? `confirmed (${conf})` : 'found';
    const age = block && block.t ? formatAge(block.t) : '-';
    rowsEl.insertAdjacentHTML(
      'beforeend',
      `<div class="grid grid-cols-12 gap-2 px-3 py-2 text-sm">
        <div class="col-span-3 text-slate-300">${escapeHtml(age)}</div>
        <div class="col-span-2 font-mono text-slate-100">${escapeHtml(height)}</div>
        <div class="col-span-3 truncate text-slate-300" title="${escapeHtml(minerRaw)}">${escapeHtml(minerLabel)}</div>
        <div class="col-span-2 text-slate-100">${escapeHtml(luckText)}</div>
        <div class="col-span-2 text-slate-300">${escapeHtml(statusText)}</div>
      </div>`
    );
  }
}

async function refreshLuck() {
  try {
    const data = await fetchJson('/api/luck');
    renderLuck(data);
  } catch {
    const statusEl = document.getElementById('luck-status');
    const rowsEl = document.getElementById('luck-rows');
    if (statusEl) statusEl.textContent = 'Luck unavailable.';
    if (rowsEl) rowsEl.innerHTML = '<div class="px-3 py-3 text-sm text-slate-400">Luck data unavailable.</div>';
  }
}

async function refreshBlocks() {
  const status = document.getElementById('blocks-status');
  const rows = document.getElementById('blocks-rows');
  if (!rows) return;
  try {
    const res = await fetchJson('/api/blocks');
    const events = Array.isArray(res && res.events) ? res.events : [];
    const backscan = res && res.backscan ? res.backscan : null;
    updateBackscanControls(backscan);

    const showWinModal = (e) => {
      try {
        if (!e || typeof e !== 'object') return;
        const hash = e.hash ? String(e.hash) : '';
        if (!hash) return;
        const key = `curtisbch_celebrated_${hash}`;
        if (localStorage.getItem(key)) return;

        const modal = document.getElementById('block-win-modal');
        if (!modal) return;
        const confettiEl = document.getElementById('block-win-confetti');
        const cardEl = modal.querySelector('.block-win-card');

        const heightEl = document.getElementById('block-win-height');
        const workerEl = document.getElementById('block-win-worker');
        const hitEl = document.getElementById('block-win-hit');
        const netEl = document.getElementById('block-win-net');
        const subEl = document.getElementById('block-win-sub');

        const height = e.height != null ? String(e.height) : '';
        const workerFull = e.solve_worker ? String(e.solve_worker) : '';
        const worker = workerFull ? splitWorkerIdent(workerFull).worker || workerFull : '';
        const hit = e.solve_diff != null ? formatBestShare(e.solve_diff) : '-';
        const net = e.network_difficulty != null ? formatBestShare(e.network_difficulty) : '-';
        const subtitle = formatBlockWinSubtitle(e);

        if (heightEl) heightEl.textContent = height || '-';
        if (workerEl) workerEl.textContent = worker || '-';
        if (hitEl) hitEl.textContent = hit;
        if (netEl) netEl.textContent = net;
        if (subEl) subEl.textContent = subtitle;

        const celebrate = () => {
          try {
            if (!confettiEl) return;
            confettiEl.innerHTML = '';
            if (cardEl) cardEl.classList.add('block-win--celebrate');
            const hues = [200, 270, 45, 140, 320];
            const count = 44;
            for (let i = 0; i < count; i++) {
              const piece = document.createElement('span');
              piece.className = 'piece';
              const x = Math.random() * 100;
              const dx = Math.random() * 100;
              const h = hues[i % hues.length];
              const r = `${Math.floor(Math.random() * 360)}deg`;
              const d = `${(Math.random() * 0.4).toFixed(2)}s`;
              piece.style.setProperty('--x', String(x.toFixed(2)));
              piece.style.setProperty('--dx', String(dx.toFixed(2)));
              piece.style.setProperty('--h', String(h));
              piece.style.setProperty('--r', r);
              piece.style.setProperty('--d', d);
              confettiEl.appendChild(piece);
            }
            window.setTimeout(() => {
              try {
                if (confettiEl) confettiEl.innerHTML = '';
                if (cardEl) cardEl.classList.remove('block-win--celebrate');
              } catch {}
            }, 2200);
          } catch {}
        };

        modal.classList.remove('hidden');
        celebrate();

        const close = () => {
          try {
            modal.classList.add('hidden');
            localStorage.setItem(key, String(Date.now()));
            if (confettiEl) confettiEl.innerHTML = '';
            if (cardEl) cardEl.classList.remove('block-win--celebrate');
          } catch {}
        };

        const btn = document.getElementById('block-win-close');
        if (btn) btn.onclick = close;
        modal.onclick = (ev) => {
          if (ev && ev.target === modal) close();
        };
      } catch {}
    };

    // Celebrate the newest block once per unique hash (works for backscan-discovered blocks too).
    if (events.length) {
      const newest = events[0];
      showWinModal(newest);
    }
    if (!events.length) {
      if (status) {
        const pctInfo = computeBackscanPct(backscan);
        const enabled = backscan ? backscan.enabled === true : false;
        const hasScan = Boolean(pctInfo) && !(backscan && backscan.complete);
        status.textContent = hasScan
          ? enabled
            ? `No blocks found yet. History scan ${pctInfo.pct}%`
            : `No blocks found yet. History scan paused`
          : 'No blocks found yet.';
      }
      const pctInfo = computeBackscanPct(backscan);
      const enabled = backscan ? backscan.enabled === true : false;
      const hasScan = Boolean(pctInfo) && !(backscan && backscan.complete);
      rows.innerHTML = hasScan
        ? `<div class="px-3 py-3 text-sm text-slate-400">No blocks found yet. ${enabled ? 'History scan' : 'History scan paused'} ${pctInfo.pct}% (height ${Math.floor(
            pctInfo.nextH
          )} / ${Math.floor(pctInfo.tipH)}).</div>`
        : '<div class="px-3 py-3 text-sm text-slate-400">No blocks found yet.</div>';
      return;
    }

    if (status) status.textContent = `${events.length} shown`;
    rows.innerHTML = '';

    for (const e of events) {
      const hash = e && e.hash ? String(e.hash) : '';
      const blockUrl = e && (e.explorer_block || e.explorer) ? String(e.explorer_block || e.explorer) : '';
      const txUrl = e && e.explorer_tx ? String(e.explorer_tx) : '';
      const txid = e && e.coinbase_txid ? String(e.coinbase_txid) : '';
      const height = e && e.height != null ? String(e.height) : '-';
      const conf = e && e.confirmations != null ? Number(e.confirmations) : null;
      const netDiff = e && e.network_difficulty != null ? Number(e.network_difficulty) : null;
      const solveDiff = e && e.solve_diff != null ? Number(e.solve_diff) : null;
      const luckPct = e && e.luck_pct != null ? Number(e.luck_pct) : (e && e.luckPct != null ? Number(e.luckPct) : null);
      const solveWorker = e && e.solve_worker ? String(e.solve_worker) : '';
      const t = e && e.t ? Number(e.t) * 1000 : null;
      const age = t ? formatAge(t) : '-';
      const shortHash = hash ? `${hash.slice(0, 10)}...${hash.slice(-8)}` : '-';
      const shortTx = txid ? `${txid.slice(0, 10)}...${txid.slice(-8)}` : '';
      const statusText = conf != null && Number.isFinite(conf) && conf > 0 ? `confirmed (${conf})` : 'found';
      const diffParts = [];
      if (netDiff != null && Number.isFinite(netDiff) && netDiff > 0) diffParts.push(`net ${formatBestShare(netDiff)}`);
      if (solveDiff != null && Number.isFinite(solveDiff) && solveDiff > 0) diffParts.push(`hit ${formatBestShare(solveDiff)}`);
      if (luckPct != null && Number.isFinite(luckPct) && luckPct >= 0) diffParts.push(`luck ${formatLuckPercent(luckPct)}`);
      const diffText = diffParts.length ? `Diff: ${diffParts.join(' / ')}` : '';
      const extIcon =
        '<svg viewBox="0 0 24 24" aria-hidden="true" class="fill-slate-100" style="width:14px;height:14px;opacity:.7"><path d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3z"></path><path d="M5 5h6v2H7v10h10v-4h2v6H5V5z"></path></svg>';
      const proofLine = txUrl
        ? `<a class="text-slate-100 hover:text-white" style="display:flex;align-items:center;gap:.5rem;" href="${escapeHtml(txUrl)}" target="_blank" rel="noreferrer"><span class="text-xs uppercase tracking-wider text-slate-400">Blockchair tx</span><span class="font-mono underline decoration-white/20 hover:decoration-white/50">${escapeHtml(shortTx)}</span>${extIcon}</a>`
        : blockUrl
          ? `<a class="text-slate-100 hover:text-white" style="display:flex;align-items:center;gap:.5rem;" href="${escapeHtml(blockUrl)}" target="_blank" rel="noreferrer"><span class="text-xs uppercase tracking-wider text-slate-400">Blockchair block</span><span class="font-mono underline decoration-white/20 hover:decoration-white/50">${escapeHtml(shortHash)}</span>${extIcon}</a>`
          : `<span class="font-mono text-slate-100">${escapeHtml(shortHash)}</span>`;

      rows.insertAdjacentHTML(
        'beforeend',
        `<div class="grid grid-cols-12 gap-2 px-3 py-2 text-sm">
          <div class="col-span-3 text-slate-300">${escapeHtml(age)}</div>
          <div class="col-span-2">
            ${
              blockUrl && height !== '-'
                ? `<a class="font-mono text-slate-100 underline decoration-white/20 hover:decoration-white/50" href="${escapeHtml(blockUrl)}" target="_blank" rel="noreferrer">${escapeHtml(height)}</a>`
                : `<span class="font-mono text-slate-100">${escapeHtml(height)}</span>`
            }
          </div>
          <div class="col-span-2 text-slate-300">${escapeHtml(statusText)}</div>
          <div class="col-span-5 min-w-0">
            ${solveWorker ? `<div class="truncate font-mono text-slate-100">${escapeHtml(solveWorker)}</div>` : ''}
            <div class="truncate">${proofLine}</div>
            <div class="mt-0.5 truncate font-mono text-xs text-slate-400">${escapeHtml(hash || '-')}</div>
            ${diffText ? `<div class="mt-0.5 text-xs text-slate-400">${escapeHtml(diffText)}</div>` : ''}
          </div>
        </div>`
      );
    }
  } catch {
    if (status) status.textContent = 'Blocks unavailable.';
    rows.innerHTML = '<div class="px-3 py-3 text-sm text-slate-400">Blocks unavailable.</div>';
  }
}

let __backscanControlsBound = false;
let __backscanMonthsBuilt = false;

function ensureBackscanMonthOptions() {
  if (__backscanMonthsBuilt) return;
  __backscanMonthsBuilt = true;

  const sel = document.getElementById('backscan-from-month');
  if (!sel) return;

  const now = new Date();
  for (let i = 0; i < 48; i++) {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
    const y = d.getUTCFullYear();
    const m = String(d.getUTCMonth() + 1).padStart(2, '0');
    const value = `${y}-${m}`;
    const label = d.toLocaleString(undefined, { month: 'long', year: 'numeric' });
    const o = document.createElement('option');
    o.value = value;
    o.textContent = label;
    sel.appendChild(o);
  }
}

function computeBackscanPct(scan) {
  if (!scan || typeof scan !== 'object') return null;
  const nextH = Number(scan.nextHeight);
  const tipH = Number(scan.tipHeightLast || scan.tipHeightAtStart);
  const startH = Number(scan.startHeight);
  const has = Number.isFinite(nextH) && Number.isFinite(tipH) && Number.isFinite(startH) && tipH >= startH;
  if (!has) return null;
  const pct = Math.max(0, Math.min(100, Math.round(((nextH - startH) / Math.max(1, tipH - startH + 1)) * 100)));
  return { pct, nextH, tipH, startH };
}

function getBackscanUiParams() {
  const fromMonth = (document.getElementById('backscan-from-month')?.value || '').trim();
  const speed = (document.getElementById('backscan-speed')?.value || 'normal').trim();
  const payload = { speed };
  if (fromMonth) payload.fromMonth = fromMonth;
  return payload;
}

function updateBackscanControls(scan) {
  ensureBackscanMonthOptions();

  const toggleWrap = document.getElementById('backscan-toggle-wrap');
  const toggle = document.getElementById('backscan-enabled');
  const rescan = document.getElementById('backscan-rescan');
  const reset = document.getElementById('backscan-reset');
  const prog = document.getElementById('backscan-progress');
  const fromMonthEl = document.getElementById('backscan-from-month');

  const complete = Boolean(scan && scan.complete);
  const stale = Boolean(scan && scan.stale);
  const enabled = scan ? scan.enabled === true : false;
  const pctInfo = computeBackscanPct(scan);

  const scanFromMonth = scan && scan.fromMonth ? String(scan.fromMonth) : '';
  if (fromMonthEl && scanFromMonth && !String(fromMonthEl.value || '').trim()) {
    fromMonthEl.value = scanFromMonth;
  }

  if (prog) {
    if (complete) prog.textContent = stale ? 'Complete (address changed)' : 'Complete';
    else if (enabled && pctInfo) prog.textContent = `Scanning ${pctInfo.pct}%`;
    else if (!enabled && pctInfo) prog.textContent = `Paused ${pctInfo.pct}%`;
    else prog.textContent = enabled ? 'Running' : '';
  }

  if (toggleWrap) toggleWrap.classList.toggle('hidden', complete);
  if (rescan) rescan.classList.toggle('hidden', !complete);
  if (reset) reset.classList.toggle('hidden', !complete);

  if (toggle) {
    toggle.checked = Boolean(enabled);
    toggle.disabled = complete;
  }

  if (__backscanControlsBound) return;
  __backscanControlsBound = true;

  if (toggle) {
    toggle.addEventListener('change', async () => {
      try {
        await postJson('/api/blocks/backscan', { enabled: Boolean(toggle.checked), ...getBackscanUiParams() });
      } catch {}
      await refreshBlocks();
    });
  }

  if (rescan) {
    rescan.addEventListener('click', async () => {
      try {
        await postJson('/api/blocks/backscan', { rescan: true, ...getBackscanUiParams() });
      } catch {}
      await refreshBlocks();
    });
  }

  if (reset) {
    reset.addEventListener('click', async () => {
      if (!confirm('Reset local block history and rescan from your install date?')) return;
      try {
        await postJson('/api/blocks/backscan', { resetAndRescan: true, ...getBackscanUiParams() });
      } catch {}
      await refreshBlocks();
    });
  }
}

function setStratumUrl() {
  const host = window.location && window.location.hostname ? String(window.location.hostname) : '';
  if (!host) return;
  if (host === 'localhost' || host === '127.0.0.1' || host === '::1' || host === '[::1]') return;

  const isIPv4 = (h) => {
    const m = /^(\d{1,3})(?:\.(\d{1,3})){3}$/.exec(h);
    if (!m) return false;
    const parts = h.split('.').map((p) => Number(p));
    return parts.length === 4 && parts.every((n) => Number.isInteger(n) && n >= 0 && n <= 255);
  };

  const isIPv6 = (h) => {
    if (!h.includes(':')) return false;
    return /^[0-9a-fA-F:]+$/.test(h);
  };

  // Never show a hostname (e.g. umbrel.local) in miner config: many miners can't resolve it.
  // Only populate the URL automatically when the UI is accessed via an IP literal.
  if (!isIPv4(host) && !isIPv6(host)) return;
  const url = `stratum+tcp://${host}:6387`;
  const ids = ['stratum-url', 'stratum-url-note'];
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) el.textContent = url;
  }
}

setStratumUrl();

const channelPill = document.getElementById('channel-pill');
try {
  const raw = channelPill ? String(channelPill.textContent || '').trim() : '';
  if (channelPill) {
    if (!raw) {
      channelPill.classList.add('hidden');
    } else {
      channelPill.classList.remove('hidden');
      const upper = raw.toUpperCase();
      const kind = upper.startsWith('RC') ? 'rc' : (upper === 'BETA' ? 'beta' : (upper === 'ALPHA' ? 'alpha' : ''));
      channelPill.classList.remove('axe-pill--alpha', 'axe-pill--beta', 'axe-pill--rc');
      if (kind) channelPill.classList.add(`axe-pill--${kind}`);
    }
  }

  const warn = document.getElementById('channel-warning');
  if (warn) {
    const upper = raw.toUpperCase();
    if (!raw) warn.textContent = '';
    else if (upper.startsWith('RC')) warn.textContent = 'RC build: near-stable, expect minor bugs. Verify your payout address.';
    else if (upper === 'BETA') warn.textContent = 'BETA build: expect minor bugs. Verify your payout address.';
    else if (upper === 'ALPHA') warn.textContent = 'ALPHA build: expect bugs and breaking changes. Verify your payout address.';
    else warn.textContent = `${raw} build: verify your payout address.`;
  }
} catch {}
refresh();
setInterval(refresh, 5000);

function shortenImageRef(s) {
  if (!s) return '-';
  const parts = String(s).split('@sha256:');
  if (parts.length === 2) return `${parts[0]}@sha256:${parts[1].slice(0, 12)}...`;
  return s;
}

async function loadPoolSettings() {
  const status = document.getElementById('pool-settings-status');
  const modernStatus = document.getElementById('poolSettingsStatus');
  const payoutEl = document.getElementById('payout-address');
  const payoutInput = document.getElementById('payoutAddress');
  const minerUser = document.getElementById('miner-username');
  const warn = document.getElementById('payout-warning');
  const mindiffEl = document.getElementById('mindiff');
  const startdiffEl = document.getElementById('startdiff');
  const maxdiffEl = document.getElementById('maxdiff');
  try {
    const s = await fetchJson('/api/pool/settings');
    const addr = (s && s.payoutAddress) || '';
    const configured = Boolean(s && s.configured);
    const warning = (s && s.warning) || '';
    const validationWarning = (s && s.validationWarning) || '';
    const mindiff = Number(s && s.mindiff);
    const startdiff = Number(s && s.startdiff);
    const maxdiff = Number(s && s.maxdiff);

    window.__payoutAddress = configured ? addr : '';

    if (payoutEl) payoutEl.textContent = configured ? addr : 'not set';
    if (payoutInput && payoutInput.value !== addr) payoutInput.value = addr;
    if (status) status.textContent = configured ? (validationWarning || '') : warning || 'Payout address not configured.';
    if (minerUser) minerUser.textContent = configured ? `${addr}.worker-name` : '(set payout first)';
    if (warn) warn.classList.toggle('hidden', configured);
    if (mindiffEl && Number.isFinite(mindiff) && mindiff > 0) mindiffEl.value = String(mindiff);
    if (startdiffEl && Number.isFinite(startdiff) && startdiff > 0) startdiffEl.value = String(startdiff);
    if (maxdiffEl && Number.isFinite(maxdiff) && maxdiff >= 0) maxdiffEl.value = String(maxdiff);

    __syncVardiffPresetFromValues({ mindiff, startdiff, maxdiff });
  } catch {
    if (payoutEl) payoutEl.textContent = 'unavailable';
    if (status) status.textContent = 'Pool settings unavailable (app starting).';
    if (minerUser) minerUser.textContent = 'unavailable';
    if (warn) warn.classList.remove('hidden');
  }
}

function __syncVardiffPresetFromValues({ mindiff, startdiff, maxdiff }) {
  const sel = document.getElementById('vardiffPreset');
  if (!sel) return;

  if (!Number.isFinite(mindiff) || !Number.isFinite(startdiff) || !Number.isFinite(maxdiff)) return;

  const key = `${Math.trunc(mindiff)}:${Math.trunc(startdiff)}:${Math.trunc(maxdiff)}`;
  const presets = {
    mixed: '1:16:0',
    micro: '1:1:0',
    small: '1:1:64',
    home: '1024:8192:0',
    farm: '8192:65536:0',
    mega: '65536:262144:0',
  };

  for (const [name, v] of Object.entries(presets)) {
    if (v === key) {
      sel.value = name;
      return;
    }
  }
  sel.value = 'custom';
}

function applyVardiffPreset(preset) {
  const mindiffEl = document.getElementById('mindiff');
  const startdiffEl = document.getElementById('startdiff');
  const maxdiffEl = document.getElementById('maxdiff');
  if (!mindiffEl || !startdiffEl || !maxdiffEl) return;

  if (preset === 'mixed') {
    mindiffEl.value = '1';
    startdiffEl.value = '16';
    maxdiffEl.value = '0';
    return;
  }

  if (preset === 'micro') {
    mindiffEl.value = '1';
    startdiffEl.value = '1';
    maxdiffEl.value = '0';
    return;
  }

  if (preset === 'small') {
    mindiffEl.value = '1';
    startdiffEl.value = '1';
    maxdiffEl.value = '64';
    return;
  }

  if (preset === 'home') {
    mindiffEl.value = '1024';
    startdiffEl.value = '8192';
    maxdiffEl.value = '0';
    return;
  }

  if (preset === 'farm') {
    mindiffEl.value = '8192';
    startdiffEl.value = '65536';
    maxdiffEl.value = '0';
    return;
  }

  if (preset === 'mega') {
    mindiffEl.value = '65536';
    startdiffEl.value = '262144';
    maxdiffEl.value = '0';
    return;
  }
}

async function loadBackendInfo() {
  const el = document.getElementById('backend-info');
  if (!el) return;
  try {
    const about = await fetchJson('/api/about');
    window.__networkIp = about && about.networkIp ? about.networkIp : window.__networkIp;
    setStratumUrl();
    const node = about.node;
    const sub = node && node.subversion ? node.subversion : 'node unavailable';
    const bchn = shortenImageRef(about.images && about.images.bchn);
    const ckpool = shortenImageRef(about.images && about.images.ckpool);
    const channel = about.channel ? ` | ${about.channel}` : '';
    el.textContent = `Backend: ${sub} | ckpool-solo (Stratum v1) | BCHN: ${bchn} | ckpool: ${ckpool}${channel}`;
  } catch {
    el.textContent = 'Backend info unavailable.';
  }
}

async function loadSettings() {
  try {
    const s = await fetchJson('/api/settings');
    document.getElementById('network').value = s.network || 'mainnet';
    const pruneValue = s.prune ?? 5500;
    const legacyPrune = document.getElementById('prune');
    if (legacyPrune) legacyPrune.value = pruneValue;
    const modernPrune = document.getElementById('pruneMiB');
    if (modernPrune) modernPrune.value = pruneValue;
    const networkSelect = document.getElementById('nodeNetwork');
    if (networkSelect) networkSelect.value = s.network || 'mainnet';
    document.getElementById('settings-status').textContent = '';
  } catch {
    document.getElementById('settings-status').textContent = 'Settings unavailable (node may be starting).';
  }
}

function getTrail() {
  const el = document.getElementById('trail');
  const saved = localStorage.getItem('bchTrail');
  if (saved && el && el.value !== saved) el.value = saved;
  return (el && el.value) || saved || '30m';
}

async function refreshCharts() {
  const trail = getTrail();
  try {
    const series = await fetchJson(`/api/timeseries/pool?trail=${encodeURIComponent(trail)}`);
    const points = (series && series.points) || [];
    const workers = points.map((p) => ({ v: Number(p.workers) || 0 }));
    drawSparkline(document.getElementById('chart-workers'), workers, { format: (v) => String(Math.round(v)) });

    const s1m = points.map((p) => ({ v: p.hashrate_1m_ths == null ? NaN : Number(p.hashrate_1m_ths) }));
    const s5m = points.map((p) => ({ v: p.hashrate_5m_ths == null ? NaN : Number(p.hashrate_5m_ths) }));
    const s15m = points.map((p) => ({ v: p.hashrate_15m_ths == null ? NaN : Number(p.hashrate_15m_ths) }));
    const s1h = points.map((p) => ({ v: p.hashrate_1h_ths == null ? NaN : Number(p.hashrate_1h_ths) }));
    drawSparklineMulti(
      document.getElementById('chart-hashrate'),
      [
        { label: '1m', color: '#00e5ff', points: s1m },
        { label: '5m', color: '#ff2bd6', points: s5m },
        { label: '15m', color: '#ff9a00', points: s15m },
        { label: '1h', color: '#22c55e', points: s1h },
      ],
      { format: (v) => v.toFixed(2) }
    );

    const net = points.map((p) => ({ v: p.network_difficulty == null ? NaN : Number(p.network_difficulty) }));
    drawSparkline(document.getElementById('chart-netdiff'), net, { format: (v) => formatBestShare(v) });
  } catch {
    drawSparkline(document.getElementById('chart-workers'), []);
    drawSparklineMulti(document.getElementById('chart-hashrate'), []);
    drawSparkline(document.getElementById('chart-netdiff'), []);
  }
}

let chartInterval = null;
function startChartInterval() {
  if (chartInterval) return;
  chartInterval = setInterval(() => {
    if (window.__activeTab === 'pool') refreshCharts();
  }, 30000);
}

document.getElementById('tab-home')?.addEventListener('click', () => showTab('home'));
document.getElementById('tab-pool')?.addEventListener('click', async () => {
  showTab('pool');
  startChartInterval();
  await refreshCharts();
  await refresh();
});
document.getElementById('tab-luck')?.addEventListener('click', async () => {
  showTab('luck');
  await refreshLuck();
});
document.getElementById('go-pool')?.addEventListener('click', async () => {
  showTab('pool');
  startChartInterval();
  await refreshCharts();
  await refresh();
});
document.getElementById('tab-blocks')?.addEventListener('click', async () => {
  showTab('blocks');
  await refreshBlocks();
});
document.getElementById('tab-settings')?.addEventListener('click', async () => {
  showTab('settings');
  await loadSettings();
  await loadPoolSettings();
});
document.getElementById('tab-project')?.addEventListener('click', () => {
  showTab('project');
});

// Support is via Discord (link in Settings).

document.getElementById('trail')?.addEventListener('change', async () => {
  localStorage.setItem('bchTrail', document.getElementById('trail').value);
  await refreshCharts();
});

document.getElementById('saveNodeSettings')?.addEventListener('click', async () => {
  const status = document.getElementById('nodeSettingsStatus');
  const input = document.getElementById('pruneMiB');
  const prune = Number(input && input.value);
  if (!Number.isInteger(prune) || (prune !== 0 && prune < 550)) {
    if (status) status.textContent = 'Enter 0 for unpruned, or at least 550 MiB.';
    return;
  }
  if (status) status.textContent = 'Saving…';
  try {
    const network = document.getElementById('nodeNetwork')?.value || 'mainnet';
    const res = await postJson('/api/settings', { prune, network });
    const legacy = document.getElementById('prune');
    if (legacy) legacy.value = prune;
    if (status) status.textContent = res && res.restartRequired
      ? `Saved. Restart Curtis BCH to apply ${network === 'testnet4' ? 'Testnet4' : 'Mainnet'} and prune ${prune.toLocaleString()} MiB.`
      : `Saved ${prune.toLocaleString()} MiB.`;
  } catch (err) {
    if (status) status.textContent = `Save failed: ${err && err.message ? err.message : String(err)}`;
  }
});

document.getElementById('settings-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const status = document.getElementById('settings-status');
  if (status) status.textContent = '';

  const choice = await showActionModal({
    kicker: 'Node Settings',
    title: 'Save node settings?',
    bodyHtml:
      `These settings update <span class="font-mono">bitcoin.conf</span> for your Bitcoin Cash node.<br><br>
       Changes apply after restarting Curtis BCH from 5tratumOS.<br><br>
       In 5tratumOS: open the Curtis BCH app page and click <span class="font-semibold text-slate-100">Restart</span>.`,
    primaryText: 'Save',
    secondaryText: 'Cancel',
  });
  if (choice !== 'primary') return;

  if (status) status.textContent = 'Saving...';
  try {
    const body = {
      network: document.getElementById('network').value,
      prune: Number(document.getElementById('prune').value),
    };
    const res = await postJson('/api/settings', body);
    if (status) status.textContent = res?.reindexRequired
      ? 'Saved. Restart Curtis BCH from 5tratumOS (chainstate reindex will run).'
      : 'Saved. Restart Curtis BCH from 5tratumOS to apply.';
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message || err}`;
  }
});

document.getElementById('pool-settings-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const status = document.getElementById('pool-settings-status');
  if (status) status.textContent = '';
  try {
    const payoutAddress = document.getElementById('payoutAddress').value;
    const payoutTrim = String(payoutAddress || '').trim();
    const inputWasCashaddr = __CASHADDR_RE.test(payoutTrim);
    const inputWasLegacy = __LEGACY_BCH_RE.test(payoutTrim);

    const mindiff = Number(document.getElementById('mindiff')?.value);
    const startdiff = Number(document.getElementById('startdiff')?.value);
    const maxdiff = Number(document.getElementById('maxdiff')?.value);

    const choice = await showActionModal({
      kicker: 'Pool Settings',
      title: 'Save pool settings?',
      bodyHtml:
        `Pool settings are applied on app restart because ckpool reads its config on startup.<br><br>
         After saving, restart Curtis BCH from 5tratumOS to apply the payout address and difficulty changes.<br><br>
         In 5tratumOS: open the Curtis BCH app page and click <span class="font-semibold text-slate-100">Restart</span>.`,
      primaryText: 'Save',
      secondaryText: 'Cancel',
    });
    if (choice !== 'primary') return;

    if (status) status.textContent = 'Saving...';
    const body = { payoutAddress, mindiff, startdiff, maxdiff };
    const res = await postJson('/api/pool/settings', body);
    if (status) status.textContent = 'Saved. Restart Curtis BCH from 5tratumOS to apply.';
    await loadPoolSettings();

    const legacyFromRes = String(
      (res && res.settings && res.settings.payoutAddress ? res.settings.payoutAddress : '') || ''
    ).trim();
    const validationWarning = String(
      (res && res.settings && res.settings.validationWarning ? res.settings.validationWarning : '') || ''
    );
    const serverConverted =
      !inputWasLegacy && __LEGACY_BCH_RE.test(legacyFromRes) && legacyFromRes && legacyFromRes !== payoutTrim;
    const serverMentionsConversion = /cashaddr/i.test(validationWarning) || /converted/i.test(validationWarning);

    if (inputWasCashaddr || serverConverted || serverMentionsConversion) {
      let legacy = '';
      try {
        legacy = legacyFromRes;
      } catch {}
      if (!legacy) {
        try {
          const s = await fetchJson('/api/pool/settings');
          legacy = String((s && s.payoutAddress) || '').trim();
        } catch {}
      }
      __showCashaddrModal({ cashaddr: payoutTrim, legacy });
    }
  } catch (err) {
    if (status) status.textContent = `Error: ${err.message || err}`;
  }
});

let __vardiffPresetApplying = false;
document.getElementById('vardiffPreset')?.addEventListener('change', (e) => {
  const v = String(e?.target?.value || '');
  __vardiffPresetApplying = true;
  try {
    applyVardiffPreset(v);
  } finally {
    __vardiffPresetApplying = false;
  }
});

function __maybeFlipPresetToCustom() {
  if (__vardiffPresetApplying) return;
  const sel = document.getElementById('vardiffPreset');
  if (!sel) return;
  if (sel.value === 'custom') return;
  sel.value = 'custom';
}
for (const id of ['mindiff', 'startdiff', 'maxdiff']) {
  const el = document.getElementById(id);
  if (!el) continue;
  el.addEventListener('input', __maybeFlipPresetToCustom);
  el.addEventListener('change', __maybeFlipPresetToCustom);
}

function __confirmBestshareReset() {
  const root = document.getElementById('bestshare-reset-modal');
  if (!root) return Promise.resolve(false);
  const okBtn = document.getElementById('bestshare-reset-confirm');
  const cancelBtn = document.getElementById('bestshare-reset-cancel');

  return new Promise((resolve) => {
    const close = (result) => {
      root.classList.add('hidden');
      if (okBtn) okBtn.onclick = null;
      if (cancelBtn) cancelBtn.onclick = null;
      root.onclick = null;
      resolve(result);
    };

    if (okBtn) okBtn.onclick = () => close(true);
    if (cancelBtn) cancelBtn.onclick = () => close(false);
    root.onclick = (e) => {
      if (e && e.target === root) close(false);
    };
    document.addEventListener(
      'keydown',
      (e) => {
        if (e && e.key === 'Escape' && !root.classList.contains('hidden')) close(false);
      },
      { once: true }
    );

    root.classList.remove('hidden');
  });
}

// init
window.__activeTab = 'home';
showTab('home');
startChartInterval();
loadBackendInfo();
loadPoolSettings();
try {
  const open = document.getElementById('bestshare-reset-open');
  const feedback = document.getElementById('bestshare-reset-feedback');
  if (open) {
    open.addEventListener('click', async () => {
      const ok = await __confirmBestshareReset();
      if (!ok) return;
      open.disabled = true;
      open.title = 'Resetting best share since block';
      if (feedback) feedback.textContent = 'Resetting...';
      try {
        await postJson('/api/pool/bestshare/reset', {});
        const sinceEl = document.getElementById('bestshare-since');
        const workerEl = document.getElementById('bestshare-since-worker');
        if (sinceEl) sinceEl.textContent = '-';
        if (workerEl) workerEl.textContent = '-';
        await refresh();
        open.title = 'Reset complete';
        if (feedback) feedback.textContent = 'Reset done';
        window.setTimeout(() => {
          open.title = 'Reset best share since block';
          open.disabled = false;
          if (feedback) feedback.textContent = '';
        }, 1800);
      } catch (e) {
        open.title = 'Reset best share since block';
        open.disabled = false;
        if (feedback) feedback.textContent = 'Reset failed';
        await showActionModal({
          kicker: 'Error',
          title: 'Reset failed',
          bodyHtml: escapeHtml(String(e && e.message ? e.message : e)),
          primaryText: 'OK',
        });
      }
    });
  }
} catch {}
try {
  const box = document.getElementById('workers-show-inactive');
  if (box) {
    box.checked = localStorage.getItem('bchShowInactiveWorkers') === '1';
    box.addEventListener('change', () => {
      localStorage.setItem('bchShowInactiveWorkers', box.checked ? '1' : '0');
      renderWorkerDetails(window.__lastWorkers || []);
    });
  }
} catch {}
try {
  const group = document.getElementById('odds-window');
  if (group) {
    const KEY = 'bchOddsWindow';
    const allowed = new Set(['7d', '1m', '1y']);
    let current = String(localStorage.getItem(KEY) || '7d').toLowerCase();
    if (!allowed.has(current)) current = '7d';
    window.__bchOddsWindow = current;

    const syncButtons = () => {
      const btns = group.querySelectorAll('.axe-odds-toggle__btn');
      btns.forEach((b) => {
        const w = String(b.getAttribute('data-window') || '').toLowerCase();
        b.classList.toggle('axe-odds-toggle__btn--active', w === window.__bchOddsWindow);
      });
    };

    group.addEventListener('click', (e) => {
      const t = e && e.target;
      const btn = t && t.closest ? t.closest('.axe-odds-toggle__btn') : null;
      if (!btn) return;
      const w = String(btn.getAttribute('data-window') || '').toLowerCase();
      if (!allowed.has(w)) return;
      window.__bchOddsWindow = w;
      try {
        localStorage.setItem(KEY, w);
      } catch {}
      syncButtons();
      renderWorkerDetails(window.__lastWorkers || []);
    });

    syncButtons();
  }
} catch {}
try {
  const trail = localStorage.getItem('bchTrail');
  if (trail) document.getElementById('trail').value = trail;
} catch {}


// Curtis BCH full-UI compatibility layer.
document.addEventListener('DOMContentLoaded', () => {
  refreshConnectInfo();
  wireCopyButton('copy-connect-url', 'connect-url');
  wireCopyButton('copy-connect-user', 'connect-user');
  wireCopyButton('copy-connect-pass', 'connect-pass');
  const titleMap = {home:'Mining Overview', pool:'Connected Miners', luck:'Current Round', blocks:'Block History', settings:'Settings', project:'About Curtis BCH'};
  document.querySelectorAll('[data-tab]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('[data-tab]').forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    const t = btn.getAttribute('data-tab');
    const h = document.getElementById('page-title');
    if (h) h.textContent = titleMap[t] || 'Curtis BCH';
  }));
});


// Curtis BCH 0.1.4 UI bridge: keep the redesigned controls synchronized with
// the legacy controller IDs while the controller is progressively refactored.
document.addEventListener('DOMContentLoaded', () => {
  const pairs = [
    ['payoutAddress','payout-address'],
    ['showInactiveWorkers','workers-show-inactive'],
    ['pruneMiB','prune']
  ];
  for (const [modernId, legacyId] of pairs) {
    const modern=document.getElementById(modernId), legacy=document.getElementById(legacyId);
    if (!modern || !legacy) continue;
    const sync=()=>{ if ('checked' in modern && modern.type==='checkbox') legacy.checked=modern.checked; else legacy.value=modern.value; legacy.dispatchEvent(new Event('change',{bubbles:true})); };
    modern.addEventListener('change',sync);
    modern.addEventListener('input',sync);
  }

  document.getElementById('savePoolSettings')?.addEventListener('click', async () => {
    const input = document.getElementById('payoutAddress');
    const status = document.getElementById('poolSettingsStatus');
    const payoutAddress = String(input?.value || '').trim();

    if (!payoutAddress) {
      if (status) status.textContent = 'Enter a BCH payout address first.';
      return;
    }

    if (status) status.textContent = 'Saving…';
    try {
      const res = await postJson('/api/pool/settings', { payoutAddress });
      const saved = String(res?.settings?.payoutAddress || '').trim();

      window.__payoutAddress = saved;
      const legacy = document.getElementById('payout-address');
      if (legacy) legacy.value = saved;

      if (status) status.textContent =
        'Saved. Restart Curtis BCH to reload CKPool with the new payout address.';

      await loadPoolSettings();
      await refreshConnectInfo();
    } catch (err) {
      if (status) status.textContent = `Save failed: ${err?.message || String(err)}`;
    }
  });
});

setInterval(() => { try { refreshConnectInfo(); } catch {} }, 15000);
