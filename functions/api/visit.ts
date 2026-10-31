interface Env {
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_CHAT_ID: string;
}

export async function onRequestPost({
  request,
  env
}: {
  request: Request;
  env: Env;
}) {
  if (request.headers.get("Origin") !== "https://infolokerkita.web.id") {
    return new Response("Forbidden", { status: 403 });
  }

  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
    return new Response("Configuration missing", { status: 500 });
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

    const allowedDevices = ["Mobile", "Tablet", "Desktop"];
    const device = allowedDevices.includes(data.device || "")
      ? data.device
      : "Tidak diketahui";

    const time = new Intl.DateTimeFormat("id-ID", {
      timeZone: "Asia/Jakarta",
      dateStyle: "long",
      timeStyle: "medium"
    }).format(new Date());

    const escape = (value: string) =>
      value.replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char] || char);

    const message = [
      "🔔 <b>Pengunjung Baru InfoLokerKita</b>",
      "",
      `📄 Halaman: <code>${escape(path)}</code>`,
      `🌐 Sumber: ${escape(referrer)}`,
      `📱 Perangkat: ${escape(device || "")}`,
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
      return new Response("Telegram notification failed", {
        status: 502
      });
    }

    return new Response("OK", { status: 200 });

  } catch {
    return new Response("Invalid request", { status: 400 });
  }
}
