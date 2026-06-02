const drawForm = document.querySelector("[data-draw-form]");
const winnerCards = Array.from(document.querySelectorAll(".winner-card"));

function parseColor(value) {
  const trimmed = String(value || "").trim();
  const hex = trimmed.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (hex) {
    const raw = hex[1].length === 3
      ? hex[1].split("").map((item) => item + item).join("")
      : hex[1];
    return [
      Number.parseInt(raw.slice(0, 2), 16),
      Number.parseInt(raw.slice(2, 4), 16),
      Number.parseInt(raw.slice(4, 6), 16),
    ];
  }

  const rgb = trimmed.match(/rgba?\(([^)]+)\)/i);
  if (!rgb) {
    return null;
  }
  return rgb[1].split(",").slice(0, 3).map((item) => Number.parseFloat(item.trim()));
}

function relativeLuminance([red, green, blue]) {
  const values = [red, green, blue].map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
}

function syncShowtimeTheme() {
  if (!document.body.classList.contains("showtime")) {
    return;
  }

  const styles = window.getComputedStyle(document.body);
  const sample = styles.getPropertyValue("--showtime-bg-sample") || styles.backgroundColor;
  const color = parseColor(sample);
  if (!color) {
    return;
  }

  const lightBackground = relativeLuminance(color) > 0.5;
  document.body.classList.toggle("theme-light-bg", lightBackground);
  document.body.classList.toggle("theme-dark-bg", !lightBackground);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getCandidates() {
  const source = document.querySelector("[data-candidates]");
  if (!source) {
    return [];
  }

  try {
    return JSON.parse(source.value);
  } catch {
    return [];
  }
}

async function createDrawSession(form) {
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: {
      "Accept": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
  });
  const payload = await response.json();

  if (!response.ok || !payload.ok) {
    window.location.href = payload.redirect_url || form.action;
    throw new Error("Draw request failed.");
  }

  return payload;
}

async function runDrawIntro(form, winners) {
  const display = document.querySelector("[data-draw-display]");
  const countdown = document.querySelector("[data-countdown]");
  const tickers = Array.from(document.querySelectorAll("[data-ticker]"));
  const tickerNames = Array.from(document.querySelectorAll("[data-ticker-name]"));
  const rollNames = document.querySelector("[data-roll-names]")?.value === "1";
  const candidates = getCandidates();
  const timers = [];
  let settled = false;

  function settleWinners() {
    if (settled) {
      return;
    }
    settled = true;
    timers.forEach((timer) => clearInterval(timer));
    tickers.forEach((ticker) => ticker.classList.remove("is-spinning"));
    tickerNames.forEach((tickerName, slotIndex) => {
      tickerName.textContent = winners[slotIndex] || "";
    });
  }

  form.classList.add("is-running");
  form.querySelector("button[type='submit']").disabled = true;
  display?.classList.remove("is-idle");

  if (rollNames && tickerNames.length && candidates.length) {
    tickerNames.forEach((tickerName, slotIndex) => {
      if (slotIndex >= candidates.length) {
        tickerName.textContent = "";
        return;
      }
      tickers[slotIndex]?.classList.add("is-spinning");
      tickerName.textContent = candidates[slotIndex % candidates.length];
      timers.push(setInterval(() => {
        const index = Math.floor(Math.random() * candidates.length);
        tickerName.textContent = candidates[(index + slotIndex) % candidates.length];
      }, 70 + slotIndex * 8));
    });
  }

  if (countdown) {
    const seconds = Math.max(1, Math.min(10, Number(countdown.dataset.seconds) || 3));
    countdown.hidden = false;
    for (let value = seconds; value > 0; value -= 1) {
      countdown.textContent = value;
      countdown.classList.remove("pulse");
      countdown.offsetWidth;
      countdown.classList.add("pulse");
      await sleep(1000);
    }
    settleWinners();
    countdown.textContent = "0";
    await sleep(700);
  } else if (tickerNames.length) {
    await sleep(1600);
    settleWinners();
    await sleep(700);
  }

  settleWinners();
}

if (drawForm) {
  const requestIdInput = drawForm.querySelector("input[name='request_id']");
  requestIdInput.value = crypto.randomUUID();

  drawForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    drawForm.classList.add("is-running");
    drawForm.querySelector("button[type='submit']").disabled = true;
    try {
      const payload = await createDrawSession(drawForm);
      await runDrawIntro(drawForm, payload.winners || []);
      window.location.href = payload.result_url;
    } catch {
      drawForm.classList.remove("is-running");
      drawForm.querySelector("button[type='submit']").disabled = false;
    }
  });
}

syncShowtimeTheme();

if (winnerCards.length) {
  const animated = document.body.classList.contains("animate-winners");

  winnerCards.forEach((card, index) => {
    if (!animated) {
      card.classList.add("show");
      return;
    }

    setTimeout(() => {
      card.classList.add("show");
    }, 350 + index * 320);
  });
}
