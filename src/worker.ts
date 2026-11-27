interface Env {
  ASSETS: {
    fetch(request: Request): Promise<Response>;
  };
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
  HQ_USER_HASH?: string;
  HQ_PASS_HASH?: string;
}

const HQ_AUTH_SALT = "infolokerkita-hq-v1:";
const DEFAULT_HQ_USER_HASH = "a428618dff3dc754dc8c4bcbe51872607181d3ecdca150006235979463b1b888";
const DEFAULT_HQ_PASS_HASH = "c70f2a9bf7f0310fc789dcd2017cf63312d9d608a8612a6854e039873fc40f09";

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function timingSafeEqualHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/api/hq-login") {
      if (request.method !== "POST") {
        return new Response(JSON.stringify({ ok: false, error: "Method Not Allowed" }), {
          status: 405,
          headers: { "Content-Type": "application/json" }
        });
      }

      try {
        const body = await request.json() as { username?: string; password?: string };
        const username = String(body.username || "").trim().toLowerCase();
        const password = String(body.password || "");

        const expectedUserHash = (env.HQ_USER_HASH || DEFAULT_HQ_USER_HASH).trim().toLowerCase();
        const expectedPassHash = (env.HQ_PASS_HASH || DEFAULT_HQ_PASS_HASH).trim().toLowerCase();

        const [userHash, passHash] = await Promise.all([
          sha256Hex(HQ_AUTH_SALT + username),
          sha256Hex(HQ_AUTH_SALT + password)
        ]);

        if (timingSafeEqualHex(userHash, expectedUserHash) && timingSafeEqualHex(passHash, expectedPassHash)) {
          return new Response(JSON.stringify({ ok: true, user: "Dandimahesa", role: "CEO" }), {
            status: 200,
            headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
          });
        }

        return new Response(JSON.stringify({ ok: false, error: "Username atau password salah." }), {
          status: 401,
          headers: { "Content-Type": "application/json", "Cache-Control": "no-store" }
        });
      } catch {
        return new Response(JSON.stringify({ ok: false, error: "Format permintaan tidak valid." }), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        });
      }
    }

    if (url.pathname !== "/api/visit") {
      return env.ASSETS.fetch(request);
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", {
        status: 405
      });
    }

    if (request.headers.get("Origin") !== "https://infolokerkita.web.id") {
      return new Response("Forbidden", {
        status: 403
      });
    }

    if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
      return new Response("Configuration missing", {
        status: 500
      });
    }

    try {
      const data = await request.json() as {
        path?: string;
        referrer?: string;
        device?: string;
      };

      const path = (data.path || "/")
        .split("?")[0]
        .split("#")[0]
        .slice(0, 150);

      let referrer = "Langsung";

      try {
        if (data.referrer) {
          referrer = new URL(data.referrer).hostname;
        }
      } catch {}

      const device = ["Mobile", "Tablet", "Desktop"]
        .includes(data.device || "")
        ? data.device!
        : "Tidak diketahui";

      const time = new Intl.DateTimeFormat("id-ID", {
        timeZone: "Asia/Jakarta",
        dateStyle: "long",
        timeStyle: "medium"
      }).format(new Date());

      const escape = (value: string) =>
        value.replace(/[&<>"']/g, (char) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
          })[char] || char
        );

      const message = [
        "🔔 <b>Pengunjung Baru InfoLokerKita</b>",
        "",
        `📄 Halaman: <code>${escape(path)}</code>`,
        `🌐 Sumber: ${escape(referrer)}`,
        `📱 Perangkat: ${escape(device)}`,
        `🕒 Waktu: ${escape(time)}`,
        "",
        "Website: infolokerkita.web.id"
      ].join("\n");

      const response = await fetch(
        `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            chat_id: env.TELEGRAM_CHAT_ID,
            text: message,
            parse_mode: "HTML"
          })
        }
      );

      if (!response.ok) {
        return new Response("Telegram failed", {
          status: 502
        });
      }

      return new Response("OK");

    } catch {
      return new Response("Invalid request", {
        status: 400
      });
    }
  }
};
