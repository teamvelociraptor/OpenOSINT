// Live GitHub stars/forks + PyPI monthly downloads for openosint.tech.
// Populates any element with a data-metric="stars|forks|pypi-downloads"
// attribute. On fetch failure (offline, rate-limited, CORS-blocked) the
// static fallback text already in the element is left untouched.
(function () {
  var GITHUB_REPO = "OpenOSINT/OpenOSINT";
  var PYPI_PACKAGE = "openosint";
  var GITHUB_CACHE_KEY = "openosint_github_stats";
  var GITHUB_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour — stay under the 60 req/hr unauthenticated limit

  function formatNumber(n) {
    return Number(n).toLocaleString("en-US");
  }

  function setMetric(name, value) {
    var els = document.querySelectorAll('[data-metric="' + name + '"]');
    for (var i = 0; i < els.length; i++) {
      els[i].textContent = value;
    }
  }

  function applyGithubStats(stats) {
    if (typeof stats.stars === "number") setMetric("stars", formatNumber(stats.stars));
    if (typeof stats.forks === "number") setMetric("forks", formatNumber(stats.forks));
  }

  function loadGithubStats() {
    try {
      var cached = JSON.parse(localStorage.getItem(GITHUB_CACHE_KEY) || "null");
      if (cached && Date.now() - cached.ts < GITHUB_CACHE_TTL_MS) {
        applyGithubStats(cached.data);
        return;
      }
    } catch (e) {
      // corrupt cache entry — ignore and refetch
    }

    fetch("https://api.github.com/repos/" + GITHUB_REPO)
      .then(function (res) {
        if (!res.ok) throw new Error("GitHub API error " + res.status);
        return res.json();
      })
      .then(function (data) {
        var stats = { stars: data.stargazers_count, forks: data.forks_count };
        applyGithubStats(stats);
        try {
          localStorage.setItem(GITHUB_CACHE_KEY, JSON.stringify({ ts: Date.now(), data: stats }));
        } catch (e) {
          // localStorage unavailable (private browsing, quota) — skip caching
        }
      })
      .catch(function () {
        // keep the static fallback already rendered in the page
      });
  }

  function loadPypiDownloads() {
    fetch("https://pypistats.org/api/packages/" + PYPI_PACKAGE + "/recent")
      .then(function (res) {
        if (!res.ok) throw new Error("pypistats API error " + res.status);
        return res.json();
      })
      .then(function (data) {
        var lastMonth = data && data.data && data.data.last_month;
        if (typeof lastMonth === "number") setMetric("pypi-downloads", formatNumber(lastMonth));
      })
      .catch(function () {
        // keep the static fallback already rendered in the page
      });
  }

  loadGithubStats();
  loadPypiDownloads();
})();
