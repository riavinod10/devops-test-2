"use strict";

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function getJson(url, options) {
  const res = await fetch(url, options);
  let body = null;
  try { body = await res.json(); } catch (_) { /* non-JSON */ }
  return { ok: res.ok, status: res.status, body };
}

async function refreshHealth() {
  const badge = $("health");
  try {
    const { ok, body } = await getJson("/backend-health");
    badge.textContent = ok ? `Backend: ${body.status} (v${body.version}, ${body.environment})` : "Backend: unhealthy";
    badge.className = "badge " + (ok ? "badge-ok" : "badge-bad");
  } catch (_) {
    badge.textContent = "Backend: unreachable";
    badge.className = "badge badge-bad";
  }
}

async function refreshData() {
  try {
    const [p, n, s] = await Promise.all([
      getJson("/api/payments"), getJson("/api/notifications"), getJson("/api/stats"),
    ]);
    if (p.ok) {
      $("payments").innerHTML = p.body.payments.length
        ? p.body.payments.map((x) => `<tr><td>${esc(x.created_at)}</td><td>${esc(x.payer)}</td><td>${esc(x.payee)}</td>` +
            `<td>${esc(x.currency)} ${esc(x.amount)}</td><td>${esc(x.method)}</td><td>${esc(x.status)}</td></tr>`).join("")
        : '<tr><td colspan="6">No payments yet</td></tr>';
    }
    if (n.ok) {
      $("notifications").innerHTML = n.body.notifications.length
        ? n.body.notifications.map((x) => `<li>[${esc(x.channel)} → ${esc(x.recipient)}] ${esc(x.message)}</li>`).join("")
        : "<li>No notifications yet</li>";
    }
    if (s.ok) {
      const totals = Object.entries(s.body.totals_by_currency)
        .map(([cur, amt]) => `${esc(cur)} ${esc(amt)}`).join(", ") || "—";
      $("stats").innerHTML = `Payments: <b>${s.body.payment_count}</b><br>Notifications: <b>${s.body.notification_count}</b><br>Totals: ${totals}`;
    }
  } catch (err) {
    console.error("refresh failed", err);
  }
}

$("payment-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const msg = $("form-msg");
  const button = form.querySelector("button");
  const data = Object.fromEntries(new FormData(form).entries());
  button.disabled = true;
  msg.textContent = "";
  try {
    const { ok, status, body } = await getJson("/api/payments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (ok) {
      msg.className = "msg-ok";
      msg.textContent = `Payment ${body.payment.id.slice(0, 8)} completed.`;
      form.reset();
      await refreshData();
    } else {
      msg.className = "msg-bad";
      const details = body && body.details ? Object.entries(body.details).map(([k, v]) => `${k} ${v}`).join("; ") : "";
      msg.textContent = `Error ${status}: ${(body && body.error) || "request failed"}${details ? " - " + details : ""}`;
    }
  } catch (_) {
    msg.className = "msg-bad";
    msg.textContent = "Backend unreachable.";
  } finally {
    button.disabled = false;
  }
});

refreshHealth();
refreshData();
setInterval(refreshHealth, 10000);
setInterval(refreshData, 10000);
