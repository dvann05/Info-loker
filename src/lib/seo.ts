export const SITE_URL = "https://infolokerkita.web.id";
export const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`;
export const JAKARTA_TIME_ZONE = "Asia/Jakarta";

export function getJakartaToday(date: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: JAKARTA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function formatJakartaDate(
  value: string | null | undefined,
  options: Intl.DateTimeFormatOptions = {
    day: "numeric",
    month: "long",
    year: "numeric",
  }
): string {
  if (!value) return "Tanggal tidak tersedia";
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? `${value}T00:00:00+07:00`
    : value;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return "Tanggal tidak tersedia";
  return new Intl.DateTimeFormat("id-ID", {
    ...options,
    timeZone: JAKARTA_TIME_ZONE,
  }).format(parsed);
}

export function toIsoOrUndefined(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value.trim())
    ? `${value.trim()}T00:00:00+07:00`
    : value;
  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString();
}

export function cleanMetaText(value: string | null | undefined, maxLength = 160): string {
  const cleaned = (value || "")
    .replace(/\\r\\n|\\n|\r|\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "";
  if (cleaned.length <= maxLength) return cleaned;
  return `${cleaned.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

export function toCanonicalUrl(pathname: string): string {
  const cleanPath = (pathname || "/").split("?")[0].split("#")[0];
  const hasFileExtension = /\.[a-z0-9]{1,8}$/i.test(cleanPath);
  let normalized = cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`;
  if (normalized !== "/" && !hasFileExtension && !normalized.endsWith("/")) {
    normalized = `${normalized}/`;
  }
  return new URL(normalized, SITE_URL).href;
}

export function toAbsoluteUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  if (trimmed.startsWith("/")) {
    return `${SITE_URL}${trimmed}`;
  }
  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return parsed.href;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

/**
 * Google Rich Results (NewsArticle, JobPosting) dan Open Graph tidak mendukung format SVG.
 * Gunakan hanya URL gambar raster (PNG, JPEG, WebP, GIF, AVIF, dll).
 */
export function toRasterImageUrl(value: string | null | undefined): string | undefined {
  const absolute = toAbsoluteUrl(value);
  if (!absolute) return undefined;
  try {
    const parsed = new URL(absolute);
    if (/\.svg$/i.test(parsed.pathname)) {
      return undefined;
    }
    return parsed.href;
  } catch {
    return undefined;
  }
}

export function getJobDetailPath(slug: string): string {
  return `/lowongan/${encodeURIComponent(slug)}/`;
}

export function getNewsDetailPath(slug: string): string {
  return `/berita/${encodeURIComponent(slug)}/`;
}

export function mapEmploymentType(raw: string | null | undefined): string {
  const text = (raw || "").trim().toLowerCase();
  if (!text || text === "tidak dicantumkan") return "FULL_TIME";
  if (text.includes("full") || text.includes("penuh") || text.includes("tetap") || text.includes("permanen")) {
    return "FULL_TIME";
  }
  if (text.includes("part") || text.includes("paruh")) {
    return "PART_TIME";
  }
  if (text.includes("kontrak") || text.includes("contract") || text.includes("pkwt") || text.includes("freelance") || text.includes("lepas")) {
    return "CONTRACTOR";
  }
  if (text.includes("magang") || text.includes("intern") || text.includes("praktik")) {
    return "INTERN";
  }
  if (text.includes("sementara") || text.includes("temporary") || text.includes("musiman")) {
    return "TEMPORARY";
  }
  if (text.includes("relawan") || text.includes("volunteer")) {
    return "VOLUNTEER";
  }
  if (text.includes("harian") || text.includes("per diem")) {
    return "PER_DIEM";
  }
  return "OTHER";
}

export interface JobSchemaInput {
  slug: string;
  title: string;
  company_name?: string | null;
  company_logo?: string | null;
  location?: string | null;
  city?: string | null;
  province?: string | null;
  employment_type?: string | null;
  description?: string | null;
  requirements?: string[] | null;
  benefits?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  published_at?: string | null;
  deadline?: string | null;
}

export function buildJobPostingJsonLd(job: JobSchemaInput): Record<string, unknown> {
  const rawMin = typeof job.salary_min === "number" && job.salary_min > 0 ? job.salary_min : null;
  const rawMax = typeof job.salary_max === "number" && job.salary_max > 0 ? job.salary_max : null;
  let minSalary = rawMin;
  let maxSalary = rawMax;
  if (minSalary !== null && maxSalary !== null && minSalary > maxSalary) {
    [minSalary, maxSalary] = [maxSalary, minSalary];
  }

  let salaryValue: Record<string, unknown> | undefined;
  if (minSalary !== null && maxSalary !== null) {
    salaryValue =
      minSalary === maxSalary
        ? { "@type": "QuantitativeValue", value: minSalary, unitText: "MONTH" }
        : { "@type": "QuantitativeValue", minValue: minSalary, maxValue: maxSalary, unitText: "MONTH" };
  } else if (minSalary !== null) {
    salaryValue = { "@type": "QuantitativeValue", value: minSalary, unitText: "MONTH" };
  } else if (maxSalary !== null) {
    salaryValue = { "@type": "QuantitativeValue", value: maxSalary, unitText: "MONTH" };
  }

  const baseSalary = salaryValue
    ? {
        "@type": "MonetaryAmount",
        currency: "IDR",
        value: salaryValue,
      }
    : undefined;

  let datePosted = toIsoOrUndefined(job.published_at) || new Date().toISOString();

  const parsedValidThrough =
    job.deadline && /^\d{4}-\d{2}-\d{2}$/.test(job.deadline.trim())
      ? `${job.deadline.trim()}T23:59:59+07:00`
      : toIsoOrUndefined(job.deadline);

  // Google Search Console mewajibkan validThrough untuk lowongan yang memiliki batas waktu;
  // sediakan fallback +30 hari dari datePosted agar kolom validThrough tidak pernah hilang.
  const validThrough =
    parsedValidThrough ||
    new Date(Date.parse(datePosted) + 30 * 24 * 60 * 60 * 1000).toISOString();

  // Pastikan datePosted tidak lebih baru dari validThrough agar valid di Google Jobs
  const postedMs = Date.parse(datePosted);
  const validMs = Date.parse(validThrough);
  if (!Number.isNaN(postedMs) && !Number.isNaN(validMs) && postedMs > validMs) {
    datePosted = new Date(validMs).toISOString();
  }

  const descParts: string[] = [];
  const mainDesc = (job.description || "").replace(/\\n/g, "\n").trim();
  if (mainDesc) {
    descParts.push(mainDesc);
  }
  const reqList = Array.isArray(job.requirements) ? job.requirements.filter(Boolean) : [];
  if (reqList.length > 0) {
    descParts.push(`Persyaratan:\n- ${reqList.join("\n- ")}`);
  }
  if (job.benefits && job.benefits.trim()) {
    descParts.push(`Benefit:\n${job.benefits.trim()}`);
  }
  const fullDescription = descParts.join("\n\n") || `Informasi lowongan kerja ${job.title} di ${job.company_name || "Indonesia"}.`;

  const logoUrl = toRasterImageUrl(job.company_logo);

  const schema: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: fullDescription,
    identifier: {
      "@type": "PropertyValue",
      name: "Info Loker Kita",
      value: job.slug,
    },
    url: `${SITE_URL}${getJobDetailPath(job.slug)}`,
    datePosted,
    validThrough,
    employmentType: mapEmploymentType(job.employment_type),
    hiringOrganization: {
      "@type": "Organization",
      name: job.company_name || "Perusahaan",
      ...(logoUrl ? { logo: logoUrl } : {}),
    },
    jobLocation: {
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: job.city || job.location || "Indonesia",
        addressRegion: job.province || job.city || "Indonesia",
        addressCountry: "ID",
      },
    },
    ...(baseSalary ? { baseSalary } : {}),
  };

  return schema;
}

export interface BreadcrumbItem {
  name: string;
  url: string;
}

export function buildBreadcrumbJsonLd(items: BreadcrumbItem[]): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url.startsWith("http") ? item.url : toCanonicalUrl(item.url),
    })),
  };
}

export function serializeJsonLd(schema: unknown): string {
  return JSON.stringify(schema).replace(/</g, "\\u003c");
}

/**
 * Mengambil seluruh baris dari Supabase dengan paginasi 1.000 baris per batch
 * agar getStaticPaths dan sitemap.xml tidak terpotong batas default PostgREST.
 */
export async function fetchAllSupabaseRows<T>(
  buildQuery: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>,
  batchSize = 1000
): Promise<T[]> {
  const allRows: T[] = [];
  let from = 0;

  while (true) {
    const to = from + batchSize - 1;
    const { data, error } = await buildQuery(from, to);
    if (error) {
      throw new Error(error.message);
    }
    const batch = data ?? [];
    allRows.push(...batch);
    if (batch.length < batchSize) {
      break;
    }
    from += batchSize;
  }

  return allRows;
}
