/* Shared accessible mobile navigation. Safe to include on any page with .nav. */
document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".topbar-inner > .nav");
  const headerInner = document.querySelector(".topbar-inner");
  if (!nav || !headerInner) return;

  if (!nav.id) nav.id = "primaryNavigation";
  if (!nav.hasAttribute("aria-label")) nav.setAttribute("aria-label", "Primary navigation");
  nav.querySelectorAll("a.active").forEach((link) => link.setAttribute("aria-current", "page"));

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "nav-toggle";
  toggle.setAttribute("aria-controls", nav.id);
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open navigation menu");
  toggle.innerHTML = '<span class="nav-toggle-icon" aria-hidden="true"><span></span><span></span><span></span></span><span>Menu</span>';
  nav.before(toggle);

  const closeMenu = ({ returnFocus = false } = {}) => {
    nav.classList.remove("is-mobile-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation menu");
    if (returnFocus) toggle.focus();
  };

  toggle.addEventListener("click", () => {
    const opening = toggle.getAttribute("aria-expanded") !== "true";
    nav.classList.toggle("is-mobile-open", opening);
    toggle.setAttribute("aria-expanded", String(opening));
    toggle.setAttribute("aria-label", opening ? "Close navigation menu" : "Open navigation menu");
  });

  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) closeMenu();
  });

  document.addEventListener("click", (event) => {
    if (!headerInner.contains(event.target)) closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.classList.contains("is-mobile-open")) {
      closeMenu({ returnFocus: true });
    }
  });

  const desktopQuery = window.matchMedia("(min-width: 821px)");
  const resetForViewport = () => {
    if (desktopQuery.matches) closeMenu();
  };
  if (desktopQuery.addEventListener) desktopQuery.addEventListener("change", resetForViewport);
  else desktopQuery.addListener(resetForViewport);
});
