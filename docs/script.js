/* OpenOSINT — docs JavaScript */

/* ─── Terminal Demo Typewriter ─────────────────────────────────────────── */
const DEMO_FRAMES = [
  { text: "openosint ❯ ", cls: "t-prompt", delay: 0 },
  { text: "investigate john.doe@example.com\n", cls: "", delay: 40 },
  { text: "\n", cls: "", delay: 200 },
  { text: "  Target  ", cls: "t-bold", delay: 0 },
  { text: "  john.doe@example.com\n\n", cls: "", delay: 0 },
  { text: "  › ", cls: "t-cyan", delay: 100 },
  { text: "check_email  ", cls: "t-magenta", delay: 0 },
  { text: "email ", cls: "t-dim", delay: 0 },
  { text: "john.doe@example.com\n", cls: "", delay: 0 },
  { text: "    ✓ ", cls: "t-green", delay: 600 },
  { text: "valid=True  provider=example.com  mx=mail.example.com\n", cls: "", delay: 0 },
  { text: "\n  › ", cls: "t-cyan", delay: 400 },
  { text: "check_breach  ", cls: "t-magenta", delay: 0 },
  { text: "email ", cls: "t-dim", delay: 0 },
  { text: "john.doe@example.com\n", cls: "", delay: 0 },
  { text: "    ✓ ", cls: "t-green", delay: 900 },
  { text: "breaches=", cls: "", delay: 0 },
  { text: "3  ", cls: "t-yellow", delay: 0 },
  { text: "latest=LinkedIn (2021)\n", cls: "", delay: 0 },
  { text: "\n  › ", cls: "t-cyan", delay: 300 },
  { text: "check_username  ", cls: "t-magenta", delay: 0 },
  { text: "username ", cls: "t-dim", delay: 0 },
  { text: "johndoe\n", cls: "", delay: 0 },
  { text: "    ✓ ", cls: "t-green", delay: 1400 },
  { text: "found on ", cls: "", delay: 0 },
  { text: "6", cls: "t-cyan", delay: 0 },
  { text: " platforms  GitHub · Reddit · Twitter/X · Instagram · GitLab · Medium\n", cls: "", delay: 0 },
  { text: "\n  › ", cls: "t-cyan", delay: 300 },
  { text: "generate_dorks  ", cls: "t-magenta", delay: 0 },
  { text: "target ", cls: "t-dim", delay: 0 },
  { text: "john.doe@example.com  type=email\n", cls: "", delay: 0 },
  { text: "    ✓ ", cls: "t-green", delay: 400 },
  { text: "generated ", cls: "", delay: 0 },
  { text: "7", cls: "t-cyan", delay: 0 },
  { text: " dork queries\n\n", cls: "", delay: 0 },
  { text: "━━━━━━━━━━━━━━━━━━━  INTELLIGENCE REPORT  ━━━━━━━━━━━━━━━━━━━\n\n", cls: "t-cyan", delay: 600 },
  { text: "## Target Overview\n", cls: "t-bold", delay: 0 },
  { text: "john.doe@example.com — corporate email, valid MX, 3 breach exposures.\n\n", cls: "t-dim", delay: 0 },
  { text: "## Account Discovery\n", cls: "t-bold", delay: 0 },
  { text: "Confirmed: GitHub, Reddit, Twitter/X, Instagram, GitLab, Medium\n", cls: "t-dim", delay: 0 },
];

function runTerminalDemo() {
  const el = document.getElementById("hero-demo");
  if (!el) return;

  let html = "";
  let frameIdx = 0;

  function renderFrame() {
    if (frameIdx >= DEMO_FRAMES.length) return;
    const frame = DEMO_FRAMES[frameIdx++];
    const safe = frame.text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    if (frame.cls) {
      html += `<span class="${frame.cls}">${safe}</span>`;
    } else {
      html += safe;
    }
    el.innerHTML = html;

    // auto-scroll terminal
    const body = el.closest(".terminal-body");
    if (body) body.scrollTop = body.scrollHeight;

    const delay = frame.delay !== undefined ? frame.delay : 30;
    setTimeout(renderFrame, delay);
  }

  renderFrame();
}

/* ─── Nav active link highlight ────────────────────────────────────────── */
function initNavHighlight() {
  const sections = document.querySelectorAll("section[id]");
  const links = document.querySelectorAll(".nav-links a[href^='#']");
  if (!sections.length || !links.length) return;

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          links.forEach((a) => a.classList.remove("active"));
          const active = document.querySelector(`.nav-links a[href="#${entry.target.id}"]`);
          if (active) active.classList.add("active");
        }
      });
    },
    { rootMargin: "-40% 0px -55% 0px" }
  );

  sections.forEach((s) => observer.observe(s));
}

/* ─── Init ──────────────────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  runTerminalDemo();
  initNavHighlight();
  Prism.highlightAll();
});
