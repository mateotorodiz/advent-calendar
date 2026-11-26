const byId = (id) => document.getElementById(id);
const views = ["loading", "login", "calendar", "gift"].map(byId);
const form = byId("sign-in");
const passphrase = byId("passphrase");
const unlock = byId("unlock");
const loginError = byId("login-error");
const grid = byId("doors");
const shelf = byId("shelf");
const shelfArt = byId("shelf-art");
const calendarMessage = byId("calendar-message");
const giftTitle = byId("gift-title");
const giftMessage = byId("gift-message");
const giftContent = byId("gift-content");
const retryGift = byId("retry-gift");
const giftDate = new Intl.DateTimeFormat("en-US", {
  month: "long",
  day: "numeric",
  timeZone: "UTC",
});

// Match the tags printed on the artwork, four boxes per shelf.
const shelfOrder = [
  17, 4, 22, 9,
  2, 15, 7, 24,
  13, 20, 1, 11,
  6, 18, 12, 3,
  23, 8, 16, 5,
  10, 21, 14, 19,
];

let doors = null;
let calendarRequest = null;
let activeDay = null;
let giftRequest = 0;

function show(view) {
  for (const section of views) section.hidden = section.id !== view;
}

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function clearGift() {
  giftRequest += 1;
  activeDay = null;
  const audio = giftContent.querySelector("audio");
  if (audio) {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
  }
  giftContent.replaceChildren();
  giftMessage.textContent = "";
  retryGift.hidden = true;
}

function requireSignIn(message) {
  doors = null;
  grid.replaceChildren();
  clearGift();
  if (message) loginError.textContent = message;
  show("login");
}

function showShelfArtwork() {
  if (shelfArt.naturalWidth > 0) shelf.classList.add("has-artwork");
}

function drawDoors(previousDoors) {
  if (JSON.stringify(previousDoors) === JSON.stringify(doors)) return;

  const focusedId = document.activeElement?.id;
  grid.replaceChildren(...shelfOrder.map((day) => {
    const { unlocked = false, today = false } = doors.find((door) => door.day === day) ?? {};
    const item = node("li");
    const button = node("button", null, "door");
    button.type = "button";
    button.id = `calendar-day-${day}`;
    button.disabled = !unlocked;
    const state = today ? "Today" : unlocked ? "Open" : "Locked";
    button.setAttribute("aria-label", `Door ${day}, ${state.toLowerCase()}`);
    if (today) button.setAttribute("aria-current", "date");
    button.append(node("span", String(day), "door-number"));
    button.addEventListener("click", () => { location.hash = `door-${day}`; });
    item.append(button);
    return item;
  }));
  if (focusedId?.startsWith("calendar-day-")) byId(focusedId)?.focus({ preventScroll: true });
}

function drawGift(day, gift) {
  for (const text of [gift.note, gift.joke]) {
    if (text) giftContent.append(node("p", text, "gift-text"));
  }
  if (gift.photo) {
    const photo = node("img", null, "gift-photo");
    photo.alt = `Photo for door ${day}`;
    photo.src = gift.photo;
    photo.addEventListener("error", () => {
      photo.replaceWith(node("p", "The photo couldn’t load."));
    });
    giftContent.append(photo);
  }
  if (gift.audio) {
    const group = node("div", null, "gift-audio");
    const label = node("p", "Voice note");
    label.id = "voice-note-label";
    const audio = node("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.setAttribute("aria-labelledby", label.id);
    audio.src = gift.audio;
    audio.addEventListener("error", () => {
      audio.replaceWith(node("p", "The voice note couldn’t load."));
    });
    group.append(label, audio);
    giftContent.append(group);
  }
  if (gift.song) {
    const link = node("a", "Listen to the song", "action");
    link.href = gift.song;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    giftContent.append(link);
  }
}

async function renderRoute() {
  if (!doors) return;
  const match = /^#door-([1-9]\d?)$/.exec(location.hash);
  const day = match ? Number(match[1]) : null;
  const door = doors.find((item) => item.day === day);
  if (!door?.unlocked) {
    const previousDay = activeDay;
    const wasHidden = byId("calendar").hidden;
    clearGift();
    const message = day === null ? "" : door ? `Door ${day} is still locked.` : "That door isn’t in this calendar.";
    calendarMessage.textContent = message;
    show("calendar");
    if (wasHidden) (byId(`calendar-day-${previousDay}`) ?? byId("calendar-title")).focus();
    return;
  }
  if (activeDay === day) return;

  clearGift();
  activeDay = day;
  const requestId = giftRequest;
  giftTitle.textContent = door.releaseDate ? giftDate.format(new Date(door.releaseDate)) : "Your gift";
  giftMessage.textContent = "Opening your gift…";
  show("gift");
  giftTitle.focus();

  try {
    const response = await fetch(`/api/doors/${day}`);
    if (requestId !== giftRequest) return;
    if (response.status === 401) {
      requireSignIn("Your session ended. Enter the passphrase again.");
      return;
    }
    if (!response.ok) throw new Error("Gift unavailable");
    const { gift } = await response.json();
    if (requestId !== giftRequest) return;
    drawGift(day, gift);
    giftMessage.textContent = "";
  } catch {
    if (requestId !== giftRequest) return;
    giftMessage.textContent = "This gift couldn’t load. Please try again.";
    retryGift.hidden = false;
  }
}

function refreshCalendar() {
  if (calendarRequest) return calendarRequest;
  calendarRequest = (async () => {
    try {
      const response = await fetch("/api/calendar");
      if (response.status === 401) {
        requireSignIn(doors ? "Your session ended. Enter the passphrase again." : "");
        return;
      }
      if (!response.ok) throw new Error("Calendar unavailable");
      const previousDoors = doors;
      ({ doors } = await response.json());
      drawDoors(previousDoors);
      void renderRoute();
    } catch {
      if (doors) {
        calendarMessage.textContent = "The calendar couldn’t refresh. Try reopening this page.";
      } else {
        byId("loading-message").textContent = "The calendar couldn’t load.";
        byId("retry-calendar").hidden = false;
        show("loading");
      }
    } finally {
      calendarRequest = null;
    }
  })();
  return calendarRequest;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.textContent = "";
  passphrase.removeAttribute("aria-invalid");
  unlock.disabled = true;
  unlock.textContent = "Unlocking…";
  try {
    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ passphrase: passphrase.value }),
    });
    if (response.ok) {
      form.reset();
      if (calendarRequest) await calendarRequest;
      await refreshCalendar();
      if (!doors && !byId("login").hidden) {
        loginError.textContent = "Allow cookies for this site, then try again.";
      }
    } else if (response.status === 401) {
      loginError.textContent = "That passphrase didn’t match. Try again.";
      passphrase.setAttribute("aria-invalid", "true");
      passphrase.select();
    } else if (response.status === 429) {
      loginError.textContent = "Too many tries. Wait one minute and try again.";
    } else {
      throw new Error("Sign-in unavailable");
    }
  } catch {
    loginError.textContent = "Couldn’t sign in. Please try again.";
  } finally {
    unlock.disabled = false;
    unlock.textContent = "Unlock calendar";
  }
});

byId("retry-calendar").addEventListener("click", refreshCalendar);
shelfArt.addEventListener("load", showShelfArtwork);
showShelfArtwork();
retryGift.addEventListener("click", () => {
  activeDay = null;
  void renderRoute();
});
window.addEventListener("hashchange", renderRoute);
window.addEventListener("focus", refreshCalendar);
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void refreshCalendar();
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) void refreshCalendar();
});
void refreshCalendar();
