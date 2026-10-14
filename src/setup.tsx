// Setup screen in the style of Steam's own settings: a sidebar with sections
// (ffmpeg, LocalSend, Syncthing) and standard settings rows, so that controller
// navigation and scrolling work like everywhere else in Steam.
import {
  ButtonItem,
  DialogBody,
  Focusable,
  DialogControlsSection,
  DialogControlsSectionHeader,
  Field,
  SidebarNavigation,
  SteamSpinner,
  TextField,
  ToggleField,
} from "@decky/ui";
import { addEventListener, removeEventListener, toaster } from "@decky/api";
import { useEffect, useMemo, useState } from "react";
import type { FC, ReactNode } from "react";
import { FaFilm, FaPaperPlane, FaSyncAlt } from "react-icons/fa";

import qrcodeImpl from "./qrcode";
import {
  Device,
  EVENT,
  Job,
  SetupInfo,
  addDevice,
  connectDevice,
  discover,
  errText,
  forgetDevice,
  getSetupInfo,
  installComponent,
  saveSettings,
  startSyncthing,
} from "./backend";
import { lang, t } from "./i18n";
import { goBack } from "./nav";

interface QrCode {
  addData(data: string): void;
  make(): void;
  createDataURL(cellSize?: number, margin?: number): string;
}
const qrcode = qrcodeImpl as unknown as (typeNumber: number, level: "L" | "M" | "Q" | "H") => QrCode;

const CSS = `
.dmg-val { color: #8b929a; font-size: 14px; text-align: right; word-break: break-all; }
.dmg-ok { color: #7fd26a; }
.dmg-warn { color: #e4b100; }
.dmg-bad { color: #e06c5f; }
.dmg-qr { width: 180px; height: 180px; image-rendering: pixelated; background: #fff; padding: 6px; border-radius: 4px; display: block; }
.dmg-id { font-family: monospace; font-size: 12px; color: #b8bcbf; word-break: break-all; line-height: 1.5; margin-top: 8px; }
`;

const SIZE_MB = { ffmpeg: 30, syncthing: 12 };
const size = (c: "ffmpeg" | "syncthing") => `${SIZE_MB[c]} ${lang() === "ru" ? "МБ" : "MB"}`;

function toast(body: string) {
  toaster.toast({ title: "Deck Clip Export", body });
}

const Qr: FC<{ text: string }> = ({ text }) => {
  const src = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    return qr.createDataURL(6, 2);
  }, [text]);
  return <img className="dmg-qr" src={src} />;
};

/** A read-only row: label on the left, value on the right; focusable so the page scrolls to it. */
const Info: FC<{ label: ReactNode; value?: ReactNode; tone?: "ok" | "warn" | "bad"; description?: ReactNode }> = ({
  label,
  value,
  tone,
  description,
}) => (
  <Field label={label} description={description} focusable>
    {value !== undefined && <div className={`dmg-val${tone ? ` dmg-${tone}` : ""}`}>{value}</div>}
  </Field>
);

/** An instruction step: short title with the details below it. */
const Step: FC<{ title: string; text: string }> = ({ title, text }) => (
  <Field label={title} description={text} focusable />
);

const InstallRow: FC<{ component: "ffmpeg" | "syncthing"; label: string; job?: Job; hint?: string }> = ({
  component,
  label,
  job,
  hint,
}) => {
  const busy = !!job && (job.status === "queued" || job.status === "running");
  return (
    <ButtonItem
      layout="inline"
      label={label}
      description={
        job?.status === "error" ? (
          <span className="dmg-warn">{t("s_failed", { err: job.error ?? "" })}</span>
        ) : busy ? (
          job?.stage || "…"
        ) : (
          hint
        )
      }
      disabled={busy}
      onClick={() => installComponent(component)}
    >
      {t("s_install", { size: size(component) })}
    </ButtonItem>
  );
};

// ------------------------------------------------------------------ pages

const FfmpegPage: FC<{ info: SetupInfo; job?: Job }> = ({ info, job }) => (
  <DialogBody>
    <DialogControlsSection>
      <DialogControlsSectionHeader>ffmpeg</DialogControlsSectionHeader>
      {info.ffmpeg ? (
        <Info
          label={info.ffmpeg_own ? t("s_ffmpeg_own") : t("s_ffmpeg_found", { path: info.ffmpeg })}
          description={t("s_ffmpeg_desc")}
          value={t("s_st_ready_short")}
          tone="ok"
        />
      ) : (
        <InstallRow component="ffmpeg" label={t("s_ffmpeg_missing")} job={job} hint={t("s_ffmpeg_desc")} />
      )}
    </DialogControlsSection>
  </DialogBody>
);

const LocalSendPage: FC<{ info: SetupInfo; refresh: () => void }> = ({ info, refresh }) => {
  const [found, setFound] = useState<Device[] | null | undefined>(undefined); // undefined: not searched yet
  const [addr, setAddr] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const search = () => {
    setFound(null);
    discover()
      .then((list) => {
        setFound(list);
        refresh();
      })
      .catch((e) => {
        setFound([]);
        setAddError(errText(e));
      });
  };

  const add = async () => {
    if (!addr.trim()) return;
    setAdding(true);
    setAddError(null);
    try {
      const r = await addDevice(addr.trim());
      if (r.ok && r.device) {
        const dev = r.device;
        toast(t("s_added", { name: dev.alias }));
        setAddr("");
        setFound((f) => [...(f ?? []).filter((x) => x.fingerprint !== dev.fingerprint), dev]);
        refresh();
      } else {
        setAddError(r.error ?? "");
      }
    } catch (e) {
      setAddError(errText(e));
    }
    setAdding(false);
  };

  const savedIds = new Set(info.known.map((d) => d.fingerprint));
  const foundIds = new Set((found ?? []).map((d) => d.fingerprint));
  const newDevices = (found ?? []).filter((d) => !savedIds.has(d.fingerprint));
  const sub = (d: Device) => [d.deviceModel, d.ip].filter(Boolean).join(" · ");

  return (
    <DialogBody>
      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("s_this")}</DialogControlsSectionHeader>
        <Info label={t("l_name")} value={info.alias} />
        <Info
          label={t("l_address")}
          value={info.addresses.length ? info.addresses.join(", ") : t("s_this_offline")}
          tone={info.addresses.length ? undefined : "bad"}
        />
      </DialogControlsSection>

      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("h_devices")}</DialogControlsSectionHeader>
        <ButtonItem
          layout="inline"
          label={t("l_search")}
          description={found === null ? t("sd_searching") : t("l_search_desc")}
          disabled={found === null}
          onClick={search}
        >
          {t("s_search")}
        </ButtonItem>
        {newDevices.map((d) => (
          <Info key={d.fingerprint} label={d.alias} description={sub(d)} value={t("sd_available")} tone="ok" />
        ))}
        {info.known.map((d) => (
          <ButtonItem
            key={d.fingerprint}
            layout="inline"
            label={d.alias}
            description={
              <>
                {sub(d)} · {t("sd_saved")}
                {found ? (
                  foundIds.has(d.fingerprint) ? (
                    <span className="dmg-ok"> · {t("sd_available")}</span>
                  ) : (
                    <span> · {t("sd_not_found")}</span>
                  )
                ) : null}
              </>
            }
            onClick={async () => {
              await forgetDevice(d.fingerprint).catch(() => undefined);
              refresh();
            }}
          >
            {t("s_forget")}
          </ButtonItem>
        ))}
        {found && found.length === 0 && info.known.length === 0 && <Info label={t("s_none")} />}
      </DialogControlsSection>

      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("h_add")}</DialogControlsSectionHeader>
        <Field
          label={t("sd_address")}
          description={
            <>
              {t("s_manual")}
              {info.gateways.length > 0 ? ` ${t("s_hotspot", { addr: info.gateways.join(", ") })}` : ""}
            </>
          }
          childrenLayout="below"
          bottomSeparator="none"
        >
          <TextField value={addr} onChange={(e: { target: { value: string } }) => setAddr(e.target.value)} />
        </Field>
        <ButtonItem layout="below" disabled={adding || !addr.trim()} onClick={add}>
          {t("sd_add")}
        </ButtonItem>
        {addError && <Info label={<span className="dmg-warn">{addError}</span>} />}
      </DialogControlsSection>

      <DialogControlsSection>
        <DialogControlsSectionHeader>{t("h_help")}</DialogControlsSectionHeader>
        <Step title={t("ls_h1")} text={t("ls_d1")} />
        <Step title={t("ls_h2")} text={t("ls_d2")} />
        <Step title={t("ls_h3")} text={t("ls_d3")} />
      </DialogControlsSection>
    </DialogBody>
  );
};

const SyncthingPage: FC<{ info: SetupInfo; job?: Job; refresh: () => void }> = ({ info, job, refresh }) => {
  const [busy, setBusy] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const st = info.syncthing;

  const setEnabled = async (enabled: boolean) => {
    try {
      await saveSettings({ syncthing_enabled: enabled });
    } catch (e) {
      toast(t("not_saved", { err: errText(e) }));
    }
    refresh();
  };

  const connect = async (id: string, name: string) => {
    setBusy(id);
    try {
      const r = await connectDevice(id, name);
      toast(r.ok ? t("s_connected_toast") : t("s_failed", { err: r.error ?? "" }));
    } catch (e) {
      toast(t("s_failed", { err: errText(e) }));
    }
    setBusy(null);
    refresh();
  };

  let state: ReactNode = null;
  if (info.syncthing_enabled && st) {
    if (st.found && !st.managed) {
      state = (
        <Info
          label={t("l_status")}
          value={st.running ? t("s_st_external") : t("s_st_external_stopped")}
          tone={st.running ? "ok" : "bad"}
        />
      );
    } else if (st.managed && st.running) {
      state = <Info label={t("l_status")} value={t("s_st_own_running")} tone="ok" />;
    } else if (st.managed) {
      state = (
        <ButtonItem
          layout="inline"
          label={t("s_st_own_stopped")}
          description={startError ? <span className="dmg-warn">{t("s_failed", { err: startError })}</span> : undefined}
          onClick={async () => {
            const r = await startSyncthing();
            setStartError(r.ok ? null : (r.error ?? ""));
            refresh();
          }}
        >
          {t("s_start")}
        </ButtonItem>
      );
    } else {
      state = <InstallRow component="syncthing" label={t("s_st_missing")} job={job} />;
    }
  }

  const anyShared = info.devices.some((d) => d.shared);
  const ready = !!st?.running && !!st?.outbox_shared;

  return (
    <DialogBody>
      <DialogControlsSection>
        <DialogControlsSectionHeader>Syncthing</DialogControlsSectionHeader>
        <ToggleField
          label={t("st_toggle")}
          description={t("s_st_desc")}
          checked={info.syncthing_enabled}
          onChange={setEnabled}
        />
        {state}
        {info.syncthing_enabled && st && st.running && (
          <Info
            label={t("l_folder")}
            description={info.outbox}
            value={ready ? t("s_st_ready_short") : st.message}
            tone={ready ? "ok" : "warn"}
          />
        )}
      </DialogControlsSection>

      {info.syncthing_enabled && st?.running && info.my_id && (
        <>
          <DialogControlsSection>
            <DialogControlsSectionHeader>{t("s_st_receivers")}</DialogControlsSectionHeader>
            {info.pending.map((p) => (
              <ButtonItem
                key={p.id}
                layout="inline"
                label={t("s_pending", { name: p.name })}
                disabled={busy === p.id}
                onClick={() => connect(p.id, p.name)}
              >
                {t("s_connect")}
              </ButtonItem>
            ))}
            {info.devices.map((d) =>
              d.shared ? (
                <Info
                  key={d.id}
                  label={d.name}
                  value={`${d.connected ? t("s_online") : t("s_offline")} · ${t("s_shared")}`}
                  tone={d.connected ? "ok" : undefined}
                />
              ) : (
                <ButtonItem
                  key={d.id}
                  layout="inline"
                  label={d.name}
                  description={d.connected ? t("s_online") : t("s_offline")}
                  disabled={busy === d.id}
                  onClick={() => connect(d.id, d.name)}
                >
                  {t("s_share")}
                </ButtonItem>
              ),
            )}
            {info.pending.length === 0 && !anyShared && <Info label={t("s_waiting")} />}
          </DialogControlsSection>

          <DialogControlsSection>
            <DialogControlsSectionHeader>{t("h_pair")}</DialogControlsSectionHeader>
            <Step title={t("st_h1")} text={t("st_d1")} />
            <Field label={t("st_h2")} description={t("st_d2")} childrenLayout="below" focusable>
              <Qr text={info.my_id} />
              <div className="dmg-id">{info.my_id}</div>
            </Field>
            <Step title={t("st_h3")} text={t("st_d3")} />
          </DialogControlsSection>
        </>
      )}
    </DialogBody>
  );
};

// ------------------------------------------------------------------ screen

export const Setup: FC = () => {
  const [info, setInfo] = useState<SetupInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Record<string, Job>>({});

  const refresh = () =>
    getSetupInfo()
      .then((i) => {
        setInfo(i);
        setError(null);
      })
      .catch((e) => setError(errText(e)));

  useEffect(() => {
    refresh();
    const onJob = (j: Job) => {
      if (j.action !== "install") return;
      setJobs((all) => ({ ...all, [j.item_id]: j }));
      if (j.status === "done") refresh();
    };
    addEventListener<[Job]>(EVENT, onJob);
    return () => {
      removeEventListener(EVENT, onJob);
    };
  }, []);

  // Syncthing connection requests and device states change on their own
  const polling = !!info?.syncthing_enabled;
  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, [polling]);

  if (!info) {
    return (
      <Focusable style={{ marginTop: 60, padding: 24, color: "#dcdedf" }} onCancelButton={goBack}>
        {error ? t("not_responding", { err: error }) : <SteamSpinner />}
      </Focusable>
    );
  }

  // B anywhere on the screen returns to where it was opened from
  const back = (content: ReactNode) => (
    <Focusable onCancelButton={goBack} style={{ height: "100%" }}>
      {content}
    </Focusable>
  );

  return (
    <Focusable onCancelButton={goBack} style={{ height: "100%", width: "100%" }}>
      <style>{CSS}</style>
      <SidebarNavigation
        title={t("s_title")}
        showTitle
        pages={[
          {
            title: "ffmpeg",
            identifier: "ffmpeg",
            icon: <FaFilm />,
            content: back(<FfmpegPage info={info} job={jobs.ffmpeg} />),
          },
          {
            title: "LocalSend",
            identifier: "localsend",
            icon: <FaPaperPlane />,
            content: back(<LocalSendPage info={info} refresh={refresh} />),
          },
          {
            title: "Syncthing",
            identifier: "syncthing",
            icon: <FaSyncAlt />,
            content: back(<SyncthingPage info={info} job={jobs.syncthing} refresh={refresh} />),
          },
        ]}
      />
    </Focusable>
  );
};
