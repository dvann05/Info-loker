import { supabase } from "../lib/supabase";
import {
  SITE_URL,
  fetchAllSupabaseRows,
  getJakartaToday,
  getJobDetailPath,
  getNewsDetailPath,
  toIsoOrUndefined,
} from "../lib/seo";

export const prerender = true;

interface SitemapRow {
  slug: string | null;
  published_at: string | null;
  updated_at: string | null;
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function latestIso(dates: Array<string | null | undefined>, fallback: string): string {
  let latestMs = 0;
  for (const d of dates) {
    if (!d) continue;
    const ms = Date.parse(d);
    if (!Number.isNaN(ms) && ms > latestMs) {
      latestMs = ms;
    }
  }
  return latestMs > 0 ? new Date(latestMs).toISOString() : fallback;
}

function dedupeBySlug(rows: SitemapRow[]): Array<SitemapRow & { slug: string }> {
  const seen = new Set<string>();
  const result: Array<SitemapRow & { slug: string }> = [];
  for (const row of rows) {
    const slug = (row.slug || "").trim();
    if (!slug || seen.has(slug)) continue;
    seen.add(slug);
    result.push({ ...row, slug });
  }
  return result;
}

export async function GET() {
  const todayWib = getJakartaToday();
  const buildNowIso = new Date().toISOString();

  let jobs: SitemapRow[];
  let news: SitemapRow[];

  try {
    // Filter disinkronkan persis dengan src/pages/lowongan/[slug].astro agar tidak ada URL 404 di sitemap
    jobs = await fetchAllSupabaseRows<SitemapRow>((from, to) =>
      supabase
        .from("jobs")
        .select("slug, published_at, updated_at")
        .eq("status", "published")
        .not("slug", "is", null)
        .not("published_at", "is", null)
        .not("deadline", "is", null)
        .gte("deadline", todayWib)
        .order("published_at", { ascending: false })
        .order("slug", { ascending: true })
        .range(from, to)
    );

    news = await fetchAllSupabaseRows<SitemapRow>((from, to) =>
      supabase
        .from("news")
        .select("slug, published_at, updated_at")
        .eq("status", "published")
        .not("slug", "is", null)
        .order("published_at", { ascending: false })
        .order("slug", { ascending: true })
        .range(from, to)
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("Gagal mengambil data untuk sitemap:", message);
    return new Response("Gagal membuat sitemap", { status: 500 });
  }

  const validJobs = dedupeBySlug(jobs);
  const validNews = dedupeBySlug(news);

  const latestJobMod = latestIso(
    validJobs.map((j) => j.updated_at || j.published_at),
    buildNowIso
  );
  const latestNewsMod = latestIso(
    validNews.map((n) => n.updated_at || n.published_at),
    buildNowIso
  );
  const latestSiteMod = latestIso([latestJobMod, latestNewsMod], buildNowIso);

  const urls: Array<{ loc: string; priority: string; lastmod?: string }> = [
    {
      loc: `${SITE_URL}/`,
      priority: "1.0",
      lastmod: latestSiteMod,
    },
    {
      loc: `${SITE_URL}/lowongan/`,
      priority: "0.9",
      lastmod: latestJobMod,
    },
    {
      loc: `${SITE_URL}/berita/`,
      priority: "0.9",
      lastmod: latestNewsMod,
    },
    ...validJobs.map((job) => ({
      loc: `${SITE_URL}${getJobDetailPath(job.slug)}`,
      priority: "0.8",
      lastmod: toIsoOrUndefined(job.updated_at || job.published_at),
    })),
    ...validNews.map((article) => ({
      loc: `${SITE_URL}${getNewsDetailPath(article.slug)}`,
      priority: "0.7",
      lastmod: toIsoOrUndefined(article.updated_at || article.published_at),
    })),
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map((url) => {
    const lines = [
      "  <url>",
      `    <loc>${escapeXml(url.loc)}</loc>`,
    ];
    if (url.lastmod) {
      lines.push(`    <lastmod>${escapeXml(url.lastmod)}</lastmod>`);
    }
    lines.push(`    <priority>${url.priority}</priority>`);
    lines.push("  </url>");
    return lines.join("\n");
  })
  .join("\n")}
</urlset>
`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
    },
  });
}
