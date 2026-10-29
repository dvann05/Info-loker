import { supabase } from "../lib/supabase";

export const prerender = true;

const SITE_URL = "https://infolokerkita.web.id";

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET() {
  const today = new Date().toISOString().slice(0, 10);

  const { data: jobs, error } = await supabase
    .from("jobs")
    .select("slug, published_at")
    .eq("status", "published")
    .or(`deadline.is.null,deadline.gte.${today}`)
    .order("published_at", { ascending: false });

  if (error) {
    console.error("Gagal mengambil data sitemap:", error.message);

    return new Response("Gagal membuat sitemap", {
      status: 500,
    });
  }

  const urls = [
    {
      loc: `${SITE_URL}/`,
      priority: "1.0",
    },
    {
      loc: `${SITE_URL}/lowongan/`,
      priority: "0.9",
    },
    ...(jobs || []).map((job) => ({
      loc: `${SITE_URL}/lowongan/detail/?slug=${encodeURIComponent(job.slug)}`,
      priority: "0.8",
      lastmod: job.published_at,
    })),
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (url) => `  <url>
    <loc>${escapeXml(url.loc)}</loc>
    ${"lastmod" in url && url.lastmod ? `<lastmod>${new Date(url.lastmod).toISOString()}</lastmod>` : ""}
    <priority>${url.priority}</priority>
  </url>`
  )
  .join("\n")}
</urlset>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
    },
  });
}