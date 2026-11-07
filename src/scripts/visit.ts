const canonical = document.querySelector<HTMLLinkElement>(
  'link[rel="canonical"]'
);

const currentPath = location.pathname.replace(/\/+$/, "");

if (currentPath === "/lowongan/detail") {
  const slug = new URLSearchParams(location.search).get("slug");

  if (slug) {
    const url = new URL(location.pathname, location.origin);
    url.searchParams.set("slug", slug);

    canonical?.setAttribute("href", url.href);

    document
      .querySelector('meta[property="og:url"]')
      ?.setAttribute("content", url.href);
  }
}

try {
  const ua = navigator.userAgent;

  const device = /tablet|ipad/i.test(ua)
    ? "Tablet"
    : /mobile|android|iphone/i.test(ua)
      ? "Mobile"
      : "Desktop";

  void fetch("/api/visit", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      path: location.pathname,
      referrer: document.referrer,
      device
    }),
    keepalive: true
  }).catch(() => {});
} catch {}
