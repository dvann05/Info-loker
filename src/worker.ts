interface Env {
  ASSETS: {
    fetch(request: Request): Promise<Response>;
  };
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

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
