/**
 * Planet Fitness Check-In Lovelace card.
 *
 * Compact PF-logo button → person list → auto-unlock guest if needed → QR.
 *
 * type: custom:pf-checkin-card
 * entity: image.planet_fitness_…_check_in_qr
 * name: PF          # optional button label
 */
(() => {
  const CARD_TYPE = "pf-checkin-card";
  const ICON_URL = "/planet_fitness_checkin_static/icon.png?v=2.1.2";
  const PURPLE = "#5c2d91";

  const STYLE = `
    :host {
      display: block;
      height: 100%;
    }
    .btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      width: 100%;
      height: 100%;
      min-height: 96px;
      padding: 12px 8px;
      border: none;
      border-radius: var(--ha-card-border-radius, 12px);
      background: var(--card-background-color, var(--ha-card-background, #fff));
      color: var(--primary-text-color);
      box-shadow: var(--ha-card-box-shadow, none);
      border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
      cursor: pointer;
      box-sizing: border-box;
      transition: transform 0.08s ease, filter 0.15s ease;
    }
    .btn:active { transform: scale(0.96); }
    .btn:disabled { opacity: 0.6; cursor: wait; }
    .logo-wrap {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: ${PURPLE};
      display: grid;
      place-items: center;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,.25);
    }
    .logo-wrap img {
      width: 30px;
      height: 30px;
      object-fit: contain;
      /* yellow thumbs-up on purple — no invert (that washed the full logo white) */
    }
    .label {
      font-size: 0.85rem;
      font-weight: 500;
      line-height: 1.1;
      text-align: center;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    dialog {
      border: none;
      border-radius: 16px;
      padding: 0;
      max-width: min(420px, 94vw);
      width: 100%;
      background: var(--card-background-color, #fff);
      color: var(--primary-text-color);
      box-shadow: 0 12px 40px rgba(0,0,0,.35);
    }
    dialog::backdrop {
      background: rgba(0,0,0,.55);
    }
    .dlg-head {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--divider-color);
    }
    .dlg-head img {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: ${PURPLE};
      padding: 4px;
      box-sizing: border-box;
      object-fit: contain;
    }
    .dlg-head h2 {
      margin: 0;
      font-size: 1.05rem;
      font-weight: 600;
      flex: 1;
    }
    .dlg-head button {
      border: none;
      background: transparent;
      color: var(--secondary-text-color);
      font-size: 1.4rem;
      line-height: 1;
      cursor: pointer;
      padding: 4px 8px;
    }
    .list { padding: 8px; max-height: 60vh; overflow: auto; }
    .person {
      display: flex;
      align-items: center;
      gap: 12px;
      width: 100%;
      text-align: left;
      border: none;
      background: transparent;
      color: inherit;
      padding: 12px 10px;
      border-radius: 10px;
      cursor: pointer;
    }
    .person:hover, .person:focus-visible {
      background: var(--secondary-background-color, rgba(0,0,0,.06));
      outline: none;
    }
    .avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: ${PURPLE};
      color: #fff;
      display: grid;
      place-items: center;
      font-weight: 700;
      font-size: 0.95rem;
      flex-shrink: 0;
    }
    .avatar.guest { background: #333; }
    .meta { flex: 1; min-width: 0; }
    .meta .name {
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .meta .sub {
      font-size: 0.8rem;
      color: var(--secondary-text-color);
    }
    .chip {
      font-size: 0.7rem;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--secondary-background-color, rgba(0,0,0,.08));
      color: var(--secondary-text-color);
      flex-shrink: 0;
    }
    .chip.on { background: rgba(92,45,145,.15); color: ${PURPLE}; }
    .qr-pane {
      padding: 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }
    .qr-pane img.qr {
      width: min(320px, 78vw);
      height: auto;
      background: #fff;
      padding: 12px;
      border-radius: 12px;
      box-sizing: border-box;
    }
    .qr-pane .who {
      font-weight: 600;
      font-size: 1.05rem;
    }
    .qr-pane .hint {
      font-size: 0.8rem;
      color: var(--secondary-text-color);
      text-align: center;
    }
    .status {
      padding: 24px 16px;
      text-align: center;
      color: var(--secondary-text-color);
    }
    .err { color: var(--error-color, #c62828); padding: 12px 16px; text-align: center; }
    .back {
      border: none;
      background: transparent;
      color: ${PURPLE};
      font-weight: 600;
      cursor: pointer;
      padding: 8px 12px;
    }
  `;

  function initials(name) {
    const parts = String(name || "?")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function cacheBust(url) {
    if (!url) return url;
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}_=${Date.now()}`;
  }

  class PfCheckinCard extends HTMLElement {
    constructor() {
      super();
      this._hass = null;
      this._config = {};
      this._busy = false;
      this._people = null;
      this._view = "list"; // list | qr | loading | error
      this._selected = null;
      this._error = null;
      this.attachShadow({ mode: "open" });
    }

    static getStubConfig() {
      return { name: "PF" };
    }

    static getConfigElement() {
      return document.createElement("pf-checkin-card-editor");
    }

    setConfig(config) {
      if (!config || !config.entity) {
        throw new Error("Set entity to your Planet Fitness check-in QR image");
      }
      this._config = config;
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      // Keep button label fresh; dialog re-renders on open.
      if (!this.shadowRoot.querySelector("dialog[open]")) {
        this._renderButtonOnly();
      }
    }

    getCardSize() {
      return 1;
    }

    connectedCallback() {
      this._render();
    }

    _render() {
      const name = this._config.name || "PF";
      this.shadowRoot.innerHTML = `
        <style>${STYLE}</style>
        <button class="btn" part="button" type="button" aria-label="${name} check-in">
          <span class="logo-wrap"><img src="${ICON_URL}" alt="" /></span>
          <span class="label">${name}</span>
        </button>
        <dialog>
          <div class="dlg-head">
            <img src="${ICON_URL}" alt="" />
            <h2 class="dlg-title">Planet Fitness</h2>
            <button type="button" class="dlg-close" aria-label="Close">×</button>
          </div>
          <div class="dlg-body"></div>
        </dialog>
      `;
      this.shadowRoot.querySelector(".btn").addEventListener("click", () => this._open());
      this.shadowRoot.querySelector(".dlg-close").addEventListener("click", () => this._close());
      const dialog = this.shadowRoot.querySelector("dialog");
      dialog.addEventListener("click", (ev) => {
        if (ev.target === dialog) this._close();
      });
      dialog.addEventListener("cancel", (ev) => {
        ev.preventDefault();
        if (this._view === "qr" || this._view === "loading" || this._view === "error") {
          this._showList();
        } else {
          this._close();
        }
      });
    }

    _renderButtonOnly() {
      const btn = this.shadowRoot.querySelector(".btn .label");
      if (btn) btn.textContent = this._config.name || "PF";
    }

    async _open() {
      if (!this._hass) return;
      this._view = "loading";
      this._selected = null;
      this._error = null;
      this._paintDialog();
      this.shadowRoot.querySelector("dialog").showModal();
      try {
        const result = await this._hass.connection.sendMessagePromise({
          type: "planet_fitness_checkin/people",
          entity_id: this._config.entity,
        });
        this._people = result.people || [];
        const title = this.shadowRoot.querySelector(".dlg-title");
        if (title) title.textContent = result.title || "Planet Fitness";
        if (this._people.length === 1) {
          await this._selectPerson(this._people[0]);
        } else {
          this._showList();
        }
      } catch (err) {
        this._error = err?.message || String(err);
        this._view = "error";
        this._paintDialog();
      }
    }

    _close() {
      const dialog = this.shadowRoot.querySelector("dialog");
      if (dialog?.open) dialog.close();
      this._busy = false;
      this.shadowRoot.querySelector(".btn").disabled = false;
    }

    async _showList() {
      this._view = "list";
      this._selected = null;
      this._error = null;
      this._syncUnlockedFromHass();
      this._paintDialog();
      // Re-fetch so chips match server-side guest state after unlock/lock
      try {
        const result = await this._hass.connection.sendMessagePromise({
          type: "planet_fitness_checkin/people",
          entity_id: this._config.entity,
        });
        this._people = result.people || [];
        if (this._view === "list") this._paintDialog();
      } catch (_) {
        /* keep local sync if refresh fails */
      }
    }

    _syncUnlockedFromHass() {
      if (!this._people || !this._hass) return;
      for (const person of this._people) {
        if (!person.access_entity) continue;
        const state = this._hass.states[person.access_entity];
        if (state) person.unlocked = state.state === "on";
      }
    }

    _paintDialog() {
      const body = this.shadowRoot.querySelector(".dlg-body");
      if (!body) return;

      if (this._view === "loading") {
        body.innerHTML = `<div class="status">Loading…</div>`;
        return;
      }
      if (this._view === "error") {
        body.innerHTML = `
          <div class="err">${this._escape(this._error || "Something went wrong")}</div>
          <div style="text-align:center;padding-bottom:12px">
            <button type="button" class="back">Back</button>
          </div>`;
        body.querySelector(".back")?.addEventListener("click", () => this._showList());
        return;
      }
      if (this._view === "qr" && this._selected) {
        const state = this._hass.states[this._selected.qr_entity] || {};
        const pic = state.attributes?.entity_picture;
        const src = pic ? cacheBust(pic) : "";
        body.innerHTML = `
          <div class="qr-pane">
            <div class="who">${this._escape(this._selected.name)}</div>
            ${
              src
                ? `<img class="qr" src="${src}" alt="Check-in QR" />`
                : `<div class="status">Waiting for QR…</div>`
            }
            <div class="hint">Hold up to the scanner. Code refreshes every ~30s.</div>
            <button type="button" class="back">← Choose someone else</button>
          </div>`;
        body.querySelector(".back")?.addEventListener("click", () => this._showList());
        return;
      }

      // list
      const people = this._people || [];
      if (!people.length) {
        body.innerHTML = `<div class="status">No people found for this account.</div>`;
        return;
      }
      body.innerHTML = `<div class="list"></div>`;
      const list = body.querySelector(".list");
      for (const person of people) {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "person";
        const isGuest = person.kind === "guest";
        row.innerHTML = `
          <span class="avatar ${isGuest ? "guest" : ""}">${this._escape(initials(person.name))}</span>
          <span class="meta">
            <div class="name">${this._escape(person.name)}</div>
            <div class="sub">${this._escape(person.label || (isGuest ? "Guest pass" : "My keytag"))}</div>
          </span>
          ${
            isGuest
              ? `<span class="chip ${person.unlocked ? "on" : ""}">${
                  person.unlocked ? "Unlocked" : "Locked"
                }</span>`
              : ""
          }
        `;
        row.addEventListener("click", () => this._selectPerson(person));
        list.appendChild(row);
      }
    }

    async _selectPerson(person) {
      if (this._busy) return;
      this._busy = true;
      this._selected = person;
      this._view = "loading";
      this._paintDialog();
      this.shadowRoot.querySelector(".btn").disabled = true;

      try {
        if (person.kind === "guest" && person.access_entity) {
          const access = this._hass.states[person.access_entity];
          if (!access || access.state !== "on") {
            await this._hass.callService("switch", "turn_on", {
              entity_id: person.access_entity,
            });
          }
          person.unlocked = true;
          await this._waitForQr(person.qr_entity, 20000);
        } else if (person.qr_entity) {
          // Member QR is always local — nudge a refresh so the PNG is fresh.
          // Ignore failures if no refresh button exists.
          try {
            await this._refreshMemberQr(person.qr_entity);
          } catch (_) {
            /* ignore */
          }
        }

        if (!person.qr_entity) {
          throw new Error("No QR entity for this person");
        }
        const state = this._hass.states[person.qr_entity];
        if (!state || state.state === "unavailable" || !state.attributes?.entity_picture) {
          throw new Error(
            "QR is not ready yet. Try again in a moment, or check Club access on the guest device."
          );
        }
        this._view = "qr";
        this._paintDialog();
      } catch (err) {
        this._error = err?.message || String(err);
        this._view = "error";
        this._paintDialog();
      } finally {
        this._busy = false;
        this.shadowRoot.querySelector(".btn").disabled = false;
      }
    }

    async _refreshMemberQr(qrEntity) {
      // Find a refresh_qr button on the same device via people list context —
      // best-effort: call all refresh_qr buttons matching the account slug.
      const parts = qrEntity.replace(/^image\./, "").replace(/_check_in_qr$/, "");
      const refreshId = `button.${parts}_refresh_qr`;
      if (this._hass.states[refreshId]) {
        await this._hass.callService("button", "press", { entity_id: refreshId });
      }
    }

    async _waitForQr(entityId, timeoutMs) {
      if (!entityId) throw new Error("Missing guest QR entity");
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        // Force a state refresh from the connection
        await this._hass.connection.sendMessagePromise({ type: "ping" }).catch(() => null);
        const state = this._hass.states[entityId];
        if (
          state &&
          state.state !== "unavailable" &&
          state.state !== "unknown" &&
          state.attributes?.entity_picture
        ) {
          return;
        }
        this._paintWaiting(entityId, Date.now() - start);
        await new Promise((r) => setTimeout(r, 400));
      }
      throw new Error("Timed out waiting for guest QR after unlock");
    }

    _paintWaiting(entityId, elapsed) {
      const body = this.shadowRoot.querySelector(".dlg-body");
      if (!body) return;
      const name = this._selected?.name || "guest";
      body.innerHTML = `
        <div class="status">
          Unlocking <strong>${this._escape(name)}</strong>…<br/>
          <span style="font-size:0.85em">(${Math.round(elapsed / 1000)}s)</span>
        </div>`;
    }

    _escape(text) {
      return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }
  }

  class PfCheckinCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = { ...config };
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
    }

    _render() {
      if (!this._config) return;
      this.innerHTML = `
        <div style="display:grid;gap:12px;padding:4px 0">
          <label style="display:grid;gap:4px;font-size:0.9rem">
            Name
            <input class="name" type="text" value="${this._escape(this._config.name || "")}"
              style="padding:8px;border-radius:8px;border:1px solid var(--divider-color);background:var(--card-background-color);color:inherit" />
          </label>
          <label style="display:grid;gap:4px;font-size:0.9rem">
            Member check-in QR image entity
            <input class="entity" type="text" value="${this._escape(this._config.entity || "")}"
              placeholder="image.planet_fitness_…_check_in_qr"
              style="padding:8px;border-radius:8px;border:1px solid var(--divider-color);background:var(--card-background-color);color:inherit" />
          </label>
          <p style="margin:0;color:var(--secondary-text-color);font-size:0.85rem">
            Guests on that account appear automatically. Tapping a locked guest unlocks them and shows their QR.
          </p>
        </div>
      `;
      this.querySelector(".name").addEventListener("change", (ev) => {
        this._config = { ...this._config, name: ev.target.value };
        this._fire();
      });
      this.querySelector(".entity").addEventListener("change", (ev) => {
        this._config = { ...this._config, entity: ev.target.value.trim() };
        this._fire();
      });
    }

    _escape(text) {
      return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;");
    }

    _fire() {
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config: this._config },
          bubbles: true,
          composed: true,
        })
      );
    }
  }

  if (!customElements.get(CARD_TYPE)) {
    customElements.define(CARD_TYPE, PfCheckinCard);
  }
  if (!customElements.get("pf-checkin-card-editor")) {
    customElements.define("pf-checkin-card-editor", PfCheckinCardEditor);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === CARD_TYPE)) {
    window.customCards.push({
      type: CARD_TYPE,
      name: "Planet Fitness Check-In",
      description:
        "PF logo button that opens a person picker and shows the check-in QR (auto-unlocks guests).",
      preview: true,
    });
  }

  console.info(
    `%c PF Check-In Card %c loaded `,
    "background:#5c2d91;color:#fff;padding:2px 4px;border-radius:4px 0 0 4px",
    "background:transparent;color:#5c2d91;padding:2px 4px"
  );
})();
