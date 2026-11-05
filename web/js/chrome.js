// Top bar: reading-progress line (--read on the header) and the current
// chapter name, taken from the last [data-chapter] section above mid-screen.
(function () {
  const header = document.querySelector(".site-header");
  const inner = header && header.querySelector(".site-header__inner");
  if (!inner) return;
  const label = document.createElement("span");
  label.className = "site-header__chapter";
  label.setAttribute("aria-hidden", "true");
  inner.insertBefore(label, inner.querySelector("nav"));
  const chapters = [...document.querySelectorAll("[data-chapter]")];

  // tally marks (short-version page): one mark per 1,000 tries
  document.querySelectorAll("[data-tally]").forEach((el) => {
    el.innerHTML = "<i></i>".repeat(+el.dataset.tally || 0);
  });

  let queued = false;
  const update = () => {
    queued = false;
    const max = document.documentElement.scrollHeight - innerHeight;
    header.style.setProperty("--read", max > 0 ? Math.min(1, scrollY / max).toFixed(4) : 0);
    let name = "";
    for (const c of chapters) if (c.getBoundingClientRect().top < innerHeight * 0.45) name = c.dataset.chapter;
    if (label.textContent !== name) label.textContent = name;
  };
  addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  addEventListener("resize", update);
  update();
})();
