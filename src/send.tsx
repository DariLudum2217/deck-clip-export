import { DialogButton, Focusable, ModalRoot, TextField } from "@decky/ui";
import { useEffect, useState } from "react";
import type { FC } from "react";

import {
  Device,
  ItemRef,
  MediaItem,
  SYNCTHING_TARGET,
  SyncthingStatus,
  Target,
  addDevice,
  discover,
  errText,
  getSetupInfo,
  getStatus,
  mergeDevices,
  sendItems,
} from "./backend";
import { fmtSize, t } from "./i18n";

export const SEND_CSS = `
.dmg-send { display: flex; flex-direction: column; gap: 12px; min-width: 560px; }
.dmg-send h2 { margin: 0; font-size: 22px; color: #fff; }
.dmg-send h3 { margin: 4px 0 0; font-size: 13px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: #8b929a; }
.dmg-send .dmg-muted { color: #8b929a; font-size: 13px; line-height: 1.45; }
.dmg-send .dmg-err { color: #e4b100; font-size: 13px; }
.dmg-devs { display: flex; flex-direction: column; gap: 6px; }
.dmg-devs .DialogButton, .dmg-devs button { text-align: left !important; padding: 8px 16px !important; height: auto !important; }
.dmg-dev-name { font-size: 16px; color: inherit; }
.dmg-dev-sub { font-size: 12px; color: inherit; opacity: .65; margin-top: 2px; }
.dmg-dev-sub .dmg-avail { color: #7fd26a; }
.gpfocus .dmg-dev-sub .dmg-avail, .dmg-devs .DialogButton:focus .dmg-avail { color: #2b7a17; }
.dmg-send-row { display: flex; gap: 8px; align-items: flex-end; }
.dmg-send-row > div:first-child { flex: 1; }
.dmg-send-row .DialogButton, .dmg-send-row button, .dmg-send-btns .DialogButton, .dmg-send-btns button { width: auto !important; min-width: 0 !important; padding: 0 18px !important; }
.dmg-send-btns { display: flex; gap: 8px; justify-content: flex-end; }
.dmg-searching { display: flex; align-items: center; gap: 10px; color: #8b929a; font-size: 13px; }
.dmg-spin { width: 16px; height: 16px; border: 2px solid #3d4450; border-top-color: #1a9fff; border-radius: 50%; animation: dmg-rot .8s linear infinite; flex: none; }
@keyframes dmg-rot { to { transform: rotate(360deg); } }
`;

/** Device subtitle: model, address and whether it answered the last search. */
function deviceLine(d: Device, found: Device[] | null) {
  const parts: string[] = [];
  if (d.deviceModel) parts.push(d.deviceModel);
  parts.push(d.ip);
  if (d.known) parts.push(t("sd_saved"));
  const seen = found?.some((f) => f.fingerprint === d.fingerprint);
  return (
    <div className="dmg-dev-sub">
      {parts.join(" · ")}
      {seen && <span className="dmg-avail"> · {t("sd_available")}</span>}
      {found !== null && !seen && <span> · {t("sd_not_found")}</span>}
    </div>
  );
}

export const SendModal: FC<{
  closeModal?: () => void;
  items: MediaItem[];
  refs: ItemRef[];
  onSent?: () => void;
}> = ({ closeModal, items, refs, onSent }) => {
  const [saved, setSaved] = useState<Device[]>([]);
  const [found, setFound] = useState<Device[] | null>(null);
  const [gateways, setGateways] = useState<string[]>([]);
  const [pin, setPin] = useState("");
  const [addr, setAddr] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [st, setSt] = useState<SyncthingStatus | null>(null);

  const search = () => {
    setFound(null);
    discover()
      .then(setFound)
      .catch((e) => {
        setFound([]);
        setError(errText(e));
      });
  };

  useEffect(() => {
    getSetupInfo()
      .then((i) => {
        setSaved(i.known);
        setGateways(i.gateways);
      })
      .catch(() => undefined);
    getStatus()
      .then((s) => setSt(s.syncthing))
      .catch(() => undefined);
    search();
  }, []);

  const pick = async (d: Target) => {
    try {
      await sendItems(refs, d, pin.trim());
      onSent?.();
      closeModal?.();
    } catch (e) {
      setError(errText(e));
    }
  };

  const add = async () => {
    if (!addr.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const r = await addDevice(addr.trim());
      if (r.ok && r.device) {
        const dev = r.device;
        setSaved((s) => mergeDevices(s, [dev]));
        setFound((f) => mergeDevices(f ?? [], [dev]));
        setAddr("");
      } else {
        setError(r.error ?? "");
      }
    } catch (e) {
      setError(errText(e));
    }
    setAdding(false);
  };

  const devices = mergeDevices(saved, found ?? []);
  const total = items.reduce((n, i) => n + (i.size || 0), 0);
  const hasVideo = items.some((i) => i.kind === "video" && !i.exported);

  return (
    <ModalRoot closeModal={closeModal}>
      <style>{SEND_CSS}</style>
      <div className="dmg-send">
        <h2>{items.length === 1 ? t("sd_title_one") : t("sd_title_n", { n: items.length })}</h2>
        <div className="dmg-muted">
          {hasVideo ? t("sd_videos") : t("sd_size", { size: fmtSize(total) })}
        </div>

        {st && (
          <>
            <h3>{t("sd_st")}</h3>
            {st.running && st.outbox_shared ? (
              <Focusable className="dmg-devs" flow-children="column">
                <DialogButton onClick={() => pick(SYNCTHING_TARGET)}>
                  <div className="dmg-dev-name">{t("sd_st_folder", { label: st.folder_label ?? "Syncthing" })}</div>
                  <div className="dmg-dev-sub">{t("sd_st_hint")}</div>
                </DialogButton>
              </Focusable>
            ) : (
              <div className="dmg-err">{t("sync_problem", { msg: st.message })}</div>
            )}
            <h3>{t("sd_ls")}</h3>
          </>
        )}
        <div className="dmg-muted">{t("sd_hint")}</div>

        <Focusable className="dmg-devs" flow-children="column">
          {devices.map((d) => (
            <DialogButton key={d.fingerprint} onClick={() => pick(d)}>
              <div className="dmg-dev-name">{d.alias}</div>
              {deviceLine(d, found)}
            </DialogButton>
          ))}
        </Focusable>

        {found === null && (
          <div className="dmg-searching">
            <div className="dmg-spin" />
            {t("sd_searching")}
          </div>
        )}
        {found !== null && devices.length === 0 && (
          <div className="dmg-muted">
            {t("sd_none")}
            {gateways.length > 0 ? ` ${t("s_hotspot", { addr: gateways.join(", ") })}` : ""}
          </div>
        )}
        {error && <div className="dmg-err">{error}</div>}

        <Focusable className="dmg-send-row" flow-children="horizontal">
          <div>
            <TextField
              label={t("sd_address")}
              value={addr}
              onChange={(e: { target: { value: string } }) => setAddr(e.target.value)}
            />
          </div>
          <DialogButton disabled={adding || !addr.trim()} onClick={add}>
            {t("sd_add")}
          </DialogButton>
        </Focusable>
        <TextField
          label={t("sd_pin")}
          value={pin}
          onChange={(e: { target: { value: string } }) => setPin(e.target.value)}
        />

        <Focusable className="dmg-send-btns" flow-children="horizontal">
          <DialogButton disabled={found === null} onClick={search}>
            {t("sd_search")}
          </DialogButton>
          <DialogButton onClick={() => closeModal?.()}>{t("sd_cancel")}</DialogButton>
        </Focusable>
      </div>
    </ModalRoot>
  );
};
