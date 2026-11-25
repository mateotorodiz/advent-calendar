function releaseDates(month: number, firstDay: number, count: number): string[] {
  return Array.from({ length: count }, (_, index) =>
    new Date(Date.UTC(2026, month - 1, firstDay + index)).toISOString().slice(0, 10),
  );
}

const schedules = {
  demo: releaseDates(11, 25, 6),
  production: releaseDates(12, 1, 24),
};

const rome = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Rome",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function calendar(schedule: keyof typeof schedules, now: Date) {
  const parts = Object.fromEntries(rome.formatToParts(now).map(({ type, value }) => [type, value]));
  const localDate = `${parts.year}-${parts.month}-${parts.day}`;

  return schedules[schedule].map((releaseDate, index) => ({
    day: index + 1,
    unlocked: releaseDate <= localDate,
    today: releaseDate === localDate,
  }));
}
