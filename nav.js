// nav.js — shared navigation and footer injected on all pages
const CALENDLY_URL = "https://calendly.com/peter-sustr/peo-assessment"; // UPDATE THIS

document.addEventListener("DOMContentLoaded", () => {
  // ── Hamburger toggle ──
  const ham = document.querySelector(".hamburger");
  const mob = document.querySelector(".mobile-menu");
  if (ham && mob) {
    ham.addEventListener("click", () => mob.classList.toggle("open"));
  }

  // ── Active nav link ──
  const path = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a, .mobile-menu a").forEach(a => {
    if (a.getAttribute("href") === path) a.style.color = "#E8B84B";
  });

  // ── Smooth CTA scroll ──
  document.querySelectorAll('a[href="#assessment"]').forEach(a => {
    a.addEventListener("click", e => {
      const target = document.getElementById("assessment");
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: "smooth" }); }
    });
  });
});
