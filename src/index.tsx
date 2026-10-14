import {
  ButtonItem,
  ConfirmModal,
  DialogButton,
  Dropdown,
  Focusable,
  ModalRoot,
  PanelSection,
  PanelSectionRow,
  SliderField,
  SteamSpinner,
  TextField,
  ToggleField,
  showModal,
  staticClasses,
} from "@decky/ui";
import { addEventListener, definePlugin, removeEventListener, routerHook, toaster } from "@decky/api";
import { useEffect, useMemo, useRef, useState } from "react";
import type { FC } from "react";
import { FaImages } from "react-icons/fa";

import {
  EVENT,
  Job,
  MediaItem,
  ROUTE,
  SETUP_ROUTE,
  Settings,
  Status,
  TILE_MAX,
  TILE_MIN,
  enqueue,
  errText,
  getStatus,
  jobResult,
  listMedia,
  saveSettings,
  setLanguage,
} from "./backend";
import { dateLocale, lang, t } from "./i18n";
import { goBack, openFromPanel, openPage } from "./nav";
import { SendModal } from "./send";
import { Setup } from "./setup";

const TITLE = "Deck Clip Export";

// ------------------------------------------------------------------ helpers

declare const appStore: any;

const nameCache = new Map<number, string>();
function gameName(appid: number): string {
  if (nameCache.has(appid)) return nameCache.get(appid)!;
  let name = appid ? t("app_n", { id: appid }) : t("no_game");
  try {
    const o = appStore?.GetAppOverviewByAppID?.(appid);
    if (o?.display_name) name = o.display_name;
  } catch {
    /* ignore */
  }
  nameCache.set(appid, name);
  return name;
}

function mediaUrl(st: Status, kind: "thumb" | "file", id: string, bust = "") {
  return `http://127.0.0.1:${st.port}/${kind}?id=${id}&t=${encodeURIComponent(st.token)}${bust}`;
}

function fmtDuration(s: number | null) {
  if (!s) return "";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function dayLabel(ts: number) {
  const d = new Date(ts * 1000);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return t("today");
  if (d.toDateString() === yesterday.toDateString()) return t("yesterday");
  return d.toLocaleDateString(dateLocale(), {
    day: "numeric",
    month: "long",
    year: d.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

function timeLabel(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString(dateLocale(), { hour: "2-digit", minute: "2-digit" });
}

function jobLabel(job?: Job) {
  if (!job) return "";
  if (job.status === "queued") return t("queued");
  if (job.status === "running") return job.stage || t("working");
  if (job.status === "error") return t("failed_short");
  return "";
}

function isBusy(job?: Job) {
  return !!job && (job.status === "queued" || job.status === "running");
}

function clampTile(n: number) {
  return Math.max(TILE_MIN, Math.min(TILE_MAX, Math.round(n)));
}

function toast(body: string) {
  toaster.toast({ title: TITLE, body });
}

const ref = (i: MediaItem) => ({ id: i.id, name: gameName(i.appid) });

/** Applies a finished job's result to the items (fresh copies from the backend when present). */
function applyResult(list: MediaItem[], job: Job): MediaItem[] {
  if (job.status !== "done") return list;
  const r = jobResult(job);
  if (r.items?.length) {
    const fresh = new Map(r.items.map((i) => [i.id, i]));
    return list.map((i) => (fresh.has(i.id) ? { ...i, ...fresh.get(i.id) } : i));
  }
  const exported = new Set(r.exported ?? []);
  const deleted = new Set(r.deleted ?? []);
  if (!exported.size && !deleted.size) return list;
  return list.map((i) =>
    deleted.has(i.id)
      ? { ...i, exported: false, copies: false }
      : exported.has(i.id)
        ? { ...i, exported: true, copies: true }
        : i,
  );
}

function openSend(list: MediaItem[], onSent?: () => void) {
  if (!list.length) return;
  showModal(<SendModal items={list} refs={list.map(ref)} onSent={onSent} />);
}

function confirmDelete(list: MediaItem[], onOK: () => void) {
  if (!list.length) {
    toast(t("no_mp4"));
    return;
  }
  showModal(
    <ConfirmModal
      strTitle={list.length === 1 ? t("c_title_one") : t("c_title_n", { n: list.length })}
      strDescription={t("c_text")}
      strOKButtonText={t("c_ok")}
      strCancelButtonText={t("c_cancel")}
      bDestructiveWarning
      onOK={onOK}
    />,
  );
}

// ------------------------------------------------------------------ styles

const CSS = `
.dmg-page { position: absolute; inset: 40px 0 0 0; overflow-y: auto; padding: 14px 22px 70px; box-sizing: border-box; color: #dcdedf; }
.dmg-bars { display: flex; flex-direction: column; gap: 8px; margin-bottom: 6px; }
.dmg-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.dmg-bar .dmg-spacer { flex: 1; }
.dmg-bar .DialogButton, .dmg-bar button, .dmg-warnbar .DialogButton, .dmg-warnbar button { width: auto !important; min-width: 0 !important; padding: 0 16px !important; height: 36px; }
.dmg-chip-on { background: #1a9fff !important; color: #fff !important; }
.dmg-bar .dmg-game { min-width: 220px; }
.dmg-warnbar { display: flex; gap: 12px; align-items: center; margin: 8px 0; }
.dmg-day { font-size: 22px; font-weight: 700; margin: 22px 0 10px; color: #fff; letter-spacing: -0.01em; }
.dmg-day small { font-size: 13px; font-weight: 400; color: #8b929a; margin-left: 10px; }
.dmg-grid { display: grid; gap: 8px; }
.dmg-grid.dmg-flat { margin-top: 16px; }
.dmg-tile { position: relative; aspect-ratio: 16 / 10; background: #23262e; border-radius: 4px; overflow: hidden; cursor: pointer; }
.dmg-tile img { width: 100%; height: 100%; object-fit: cover; display: block; }
.dmg-tile .dmg-noimg { display: flex; width: 100%; height: 100%; align-items: center; justify-content: center; color: #8b929a; font-size: 12px; }
.dmg-tile.gpfocus, .dmg-tile.dmg-focus { box-shadow: 0 0 0 3px #fff, 0 6px 20px rgba(0,0,0,.6); transform: scale(1.04); z-index: 2; transition: transform .12s ease-out; }
.dmg-tile.dmg-sel::after { content: ""; position: absolute; inset: 0; border: 3px solid #1a9fff; background: rgba(26,159,255,.22); border-radius: 4px; pointer-events: none; }
.dmg-check { position: absolute; top: 6px; left: 6px; width: 22px; height: 22px; border-radius: 50%; background: #1a9fff; color: #fff; font-size: 14px; display: flex; align-items: center; justify-content: center; z-index: 1; }
.dmg-meta { position: absolute; left: 0; right: 0; bottom: 0; padding: 18px 8px 6px; display: flex; gap: 6px; align-items: flex-end; font-size: 11px; background: linear-gradient(transparent, rgba(0,0,0,.8)); }
.dmg-meta .dmg-game-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #fff; }
.dmg-pill { padding: 1px 6px; border-radius: 3px; background: rgba(0,0,0,.6); color: #fff; white-space: nowrap; }
.dmg-pill.dmg-mp4 { background: #3d4450; }
.dmg-small .dmg-meta { padding: 12px 5px 4px; font-size: 10px; }
.dmg-small .dmg-meta .dmg-game-name { display: none; }
.dmg-busy { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: 8px; background: rgba(10,14,20,.72); font-size: 12px; color: #fff; }
.dmg-busy.dmg-err { background: rgba(120,20,20,.75); }
.dmg-empty { margin: 80px auto; max-width: 520px; text-align: center; color: #8b929a; line-height: 1.5; }
.dmg-viewer { display: flex; flex-direction: column; gap: 12px; }
.dmg-stage { height: 56vh; background: #000; display: flex; align-items: center; justify-content: center; position: relative; border-radius: 4px; overflow: hidden; }
.dmg-stage img, .dmg-stage video { max-width: 100%; max-height: 100%; }
.dmg-stage .dmg-hint { position: absolute; bottom: 12px; left: 0; right: 0; text-align: center; font-size: 13px; color: #dcdedf; text-shadow: 0 1px 3px #000; }
.dmg-title { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.dmg-title b { font-size: 18px; color: #fff; }
.dmg-title span { color: #8b929a; font-size: 13px; }
.dmg-actions { display: flex; gap: 8px; width: 100%; box-sizing: border-box; }
.dmg-actions .DialogButton, .dmg-actions button { flex: 1 1 0 !important; width: auto !important; min-width: 0 !important; padding: 0 10px !important; white-space: normal; line-height: 1.2; }
.dmg-actions .dmg-nav { flex: 0 0 64px !important; }
.dmg-warn { font-size: 12px; color: #e4b100; }
`;

const Styles: FC = () => <style>{CSS}</style>;

// ------------------------------------------------------------------ viewer modal

const Viewer: FC<{
  closeModal?: () => void;
  items: MediaItem[];
  start: number;
  status: Status;
  initialJobs: Record<string, Job>;
  onDelete: (it: MediaItem) => void;
}> = ({ closeModal, items, start, status, initialJobs, onDelete }) => {
  const [idx, setIdx] = useState(start);
  const [list, setList] = useState<MediaItem[]>(items);
  const [jobs, setJobs] = useState<Record<string, Job>>(initialJobs);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onJob = (job: Job) => {
      if (job.action === "install") return;
      setJobs((j) => {
        const next = { ...j };
        for (const id of job.item_ids) next[id] = job;
        return next;
      });
      setList((l) => applyResult(l, job));
    };
    addEventListener<[Job]>(EVENT, onJob);
    return () => {
      removeEventListener(EVENT, onJob);
    };
  }, []);

  const it = list[idx];
  const job = jobs[it.id];
  const busy = isBusy(job);
  const name = gameName(it.appid);
  const isVideo = it.kind === "video";

  return (
    <ModalRoot closeModal={closeModal} bAllowFullSize>
      <div className="dmg-viewer">
        <div className="dmg-title">
          <b>{name}</b>
          <span>
            {dayLabel(it.mtime)}, {timeLabel(it.mtime)}
            {isVideo && it.duration ? ` · ${fmtDuration(it.duration)}` : ""}
          </span>
        </div>
        <div className="dmg-stage">
          {!isVideo && <img src={mediaUrl(status, "file", it.id)} />}
          {isVideo && it.exported && (
            <video ref={videoRef} src={mediaUrl(status, "file", it.id, "&v=1")} autoPlay controls />
          )}
          {isVideo && !it.exported && (
            <>
              <img src={mediaUrl(status, "thumb", it.id)} style={{ opacity: 0.6 }} />
              <div className="dmg-hint">{busy ? jobLabel(job) : t("v_export_hint")}</div>
            </>
          )}
          {busy && it.exported && <div className="dmg-hint">{jobLabel(job)}</div>}
        </div>
        {job?.status === "error" && <div className="dmg-warn">{t("v_failed", { err: job.error ?? "" })}</div>}
        {isVideo && !status.ffmpeg && <div className="dmg-warn">{t("v_no_ffmpeg")}</div>}
        <Focusable className="dmg-actions" flow-children="horizontal">
          <DialogButton className="dmg-nav" disabled={idx === 0} onClick={() => setIdx(idx - 1)}>
            {t("v_prev")}
          </DialogButton>
          {isVideo && it.exported && (
            <DialogButton
              onClick={() => {
                const v = videoRef.current;
                if (v) v.paused ? v.play() : v.pause();
              }}
            >
              {t("v_play")}
            </DialogButton>
          )}
          {isVideo && !it.exported && (
            <DialogButton disabled={busy || !status.ffmpeg} onClick={() => enqueue([ref(it)], "export")}>
              {t("v_save_mp4")}
            </DialogButton>
          )}
          <DialogButton disabled={busy || (isVideo && !it.exported && !status.ffmpeg)} onClick={() => openSend([it])}>
            {t("v_send")}
          </DialogButton>
          {(isVideo || it.copies) && (
            <DialogButton
              disabled={busy || !it.copies}
              onClick={() => {
                closeModal?.();
                onDelete(it);
              }}
            >
              {t("v_delete")}
            </DialogButton>
          )}
          <DialogButton className="dmg-nav" disabled={idx === list.length - 1} onClick={() => setIdx(idx + 1)}>
            {t("v_next")}
          </DialogButton>
        </Focusable>
      </div>
    </ModalRoot>
  );
};

// ------------------------------------------------------------------ tile

const Tile: FC<{
  item: MediaItem;
  status: Status;
  job?: Job;
  selected: boolean;
  sendLabel: string;
  onOpen: () => void;
  onToggle: () => void;
  onSend: () => void;
  onDelete: () => void;
}> = ({ item, status, job, selected, sendLabel, onOpen, onToggle, onSend, onDelete }) => {
  const [broken, setBroken] = useState(false);
  const isVideo = item.kind === "video";
  return (
    <Focusable
      className={`dmg-tile${selected ? " dmg-sel" : ""}`}
      focusClassName="dmg-focus"
      noFocusRing
      onActivate={onOpen}
      onOKActionDescription={t("t_open")}
      onSecondaryButton={onToggle}
      onSecondaryActionDescription={selected ? t("t_deselect") : t("t_select")}
      onOptionsButton={onSend}
      onOptionsActionDescription={sendLabel}
      onMenuButton={item.copies ? onDelete : undefined}
      onMenuActionDescription={item.copies ? t("t_delete") : undefined}
      onGamepadFocus={(e: any) => e?.currentTarget?.scrollIntoView?.({ block: "nearest", behavior: "smooth" })}
    >
      {broken ? (
        <div className="dmg-noimg">{isVideo ? t("no_preview") : t("cant_open")}</div>
      ) : (
        <img loading="lazy" src={mediaUrl(status, "thumb", item.id)} onError={() => setBroken(true)} />
      )}
      {selected && <div className="dmg-check">✓</div>}
      <div className="dmg-meta">
        <span className="dmg-game-name">{gameName(item.appid)}</span>
        {isVideo && item.exported && <span className="dmg-pill dmg-mp4">MP4</span>}
        {isVideo && <span className="dmg-pill">▶ {fmtDuration(item.duration) || t("video")}</span>}
      </div>
      {isBusy(job) && <div className="dmg-busy">{jobLabel(job)}</div>}
      {job?.status === "error" && <div className="dmg-busy dmg-err">{job.error}</div>}
    </Focusable>
  );
};

// ------------------------------------------------------------------ gallery page

type Filter = "all" | "screenshot" | "video";

const Gallery: FC = () => {
  const [status, setStatus] = useState<Status | null>(null);
  const [items, setItems] = useState<MediaItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [game, setGame] = useState<number>(-1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [jobs, setJobs] = useState<Record<string, Job>>({});
  // export and delete jobs run per item; a single toast summarises a batch
  const batch = useRef({ active: new Set<string>(), done: 0, failed: 0 });
  const [error, setError] = useState<string | null>(null);
  const [layout, setLayout] = useState<"days" | "grid">("days");
  const [tile, setTile] = useState(196);

  const reload = async () => {
    setItems(null);
    setError(null);
    try {
      await setLanguage(lang());
      const [st, list] = await Promise.all([getStatus(), listMedia()]);
      setStatus(st);
      setItems(list);
      setLayout(st.settings.ui_layout === "grid" ? "grid" : "days");
      setTile(clampTile(st.settings.ui_tile || 196));
    } catch (e) {
      setError(errText(e));
    }
  };

  useEffect(() => {
    reload();
    const onJob = (job: Job) => {
      if (job.action === "install") return;
      setJobs((prev) => {
        const next = { ...prev };
        for (const id of job.item_ids) next[id] = job;
        return next;
      });
      setItems((list) => (list ? applyResult(list, job) : list));

      const finished = job.status === "done" || job.status === "error";
      if (job.action === "send") {
        if (job.status === "done") {
          const r = jobResult(job);
          const d = r.deleted?.length ?? 0;
          const n = r.count ?? 0;
          const k = r.already ?? 0;
          const label = r.device ?? "";
          if (r.via === "syncthing") {
            toast(
              n === 0
                ? t("st_sent_none", { label })
                : k
                  ? t("st_sent_some", { label, n, k })
                  : t("st_sent", { label, n }),
            );
          } else {
            toast(
              d ? t("sent_to_deleted", { device: label, n, d }) : t("sent_to", { device: label, n }),
            );
          }
        } else if (job.status === "error") {
          toast(t("send_failed", { err: job.error ?? "" }));
        }
        return;
      }
      if (job.auto) return; // automatic removal after delivery: no notifications
      const b = batch.current;
      if (!finished) {
        b.active.add(job.id);
      } else {
        b.active.delete(job.id);
        job.status === "done" ? b.done++ : b.failed++;
        if (b.active.size === 0) {
          toast(b.failed ? t("done_failed", { n: b.done, f: b.failed }) : t("done_n", { n: b.done }));
          b.done = 0;
          b.failed = 0;
        }
      }
    };
    addEventListener<[Job]>(EVENT, onJob);
    return () => {
      removeEventListener(EVENT, onJob);
    };
  }, []);

  const games = useMemo(() => {
    const ids = Array.from(new Set((items ?? []).map((i) => i.appid)));
    return ids.map((id) => ({ data: id, label: gameName(id) })).sort((a, b) => a.label.localeCompare(b.label));
  }, [items]);

  const visible = useMemo(
    () =>
      (items ?? []).filter((i) => (filter === "all" || i.kind === filter) && (game === -1 || i.appid === game)),
    [items, filter, game],
  );

  const days = useMemo(() => {
    const out: { label: string; items: MediaItem[] }[] = [];
    for (const it of visible) {
      const label = dayLabel(it.mtime);
      if (!out.length || out[out.length - 1].label !== label) out.push({ label, items: [] });
      out[out.length - 1].items.push(it);
    }
    return out;
  }, [visible]);

  const toggle = (id: string) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const pickItems = (ids: string[]) => (items ?? []).filter((i) => ids.includes(i.id));

  const exportVideos = (ids: string[]) => {
    const list = pickItems(ids).filter((i) => i.kind === "video" && !i.exported);
    if (!list.length) {
      toast(t("nothing_to_export"));
      return;
    }
    enqueue(list.map(ref), "export");
    setSelected(new Set());
  };

  const askDelete = (ids: string[]) => {
    const list = pickItems(ids).filter((i) => i.copies);
    confirmDelete(list, () => {
      enqueue(list.map(ref), "delete");
      setSelected(new Set());
    });
  };

  const changeLayout = (l: "days" | "grid") => {
    setLayout(l);
    saveSettings({ ui_layout: l }).catch(() => undefined);
  };

  const changeTile = (delta: number) => {
    const next = clampTile(tile + delta);
    setTile(next);
    saveSettings({ ui_tile: next }).catch(() => undefined);
  };

  if (error) {
    return (
      <Focusable className="dmg-page" onCancelButton={goBack}>
        <Styles />
        <div className="dmg-empty">
          {t("not_responding", { err: error })}
          <br />
          {t("logs_hint")}
          <Focusable style={{ marginTop: 16 }}>
            <DialogButton onClick={reload}>{t("retry")}</DialogButton>
          </Focusable>
        </div>
      </Focusable>
    );
  }

  if (!status || !items) {
    return (
      <Focusable className="dmg-page" onCancelButton={goBack}>
        <Styles />
        <SteamSpinner />
      </Focusable>
    );
  }

  const allMp4 = items.filter((i) => i.copies).map((i) => i.id);
  const chip = (f: Filter, label: string) => (
    <DialogButton className={filter === f ? "dmg-chip-on" : ""} onClick={() => setFilter(f)}>
      {label}
    </DialogButton>
  );

  const sel = Array.from(selected);
  const stProblem = !!status.syncthing && !(status.syncthing.running && status.syncthing.outbox_shared);
  const selMp4 = pickItems(sel).filter((i) => i.copies).length;
  const gridClass = `dmg-grid${tile < 170 ? " dmg-small" : ""}`;
  const gridStyle = { gridTemplateColumns: `repeat(auto-fill, minmax(${tile}px, 1fr))` };
  const renderTile = (it: MediaItem) => (
    <Tile
      key={it.id}
      item={it}
      status={status}
      job={jobs[it.id]}
      selected={selected.has(it.id)}
      sendLabel={sel.length ? t("send_n", { n: new Set([...sel, it.id]).size }) : t("t_send")}
      onToggle={() => toggle(it.id)}
      onSend={() =>
        // with a selection, Y sends the whole selection (plus the focused item)
        sel.length
          ? openSend(pickItems(Array.from(new Set([...sel, it.id]))), () => setSelected(new Set()))
          : openSend([it])
      }
      onDelete={() => askDelete([it.id])}
      onOpen={() =>
        showModal(
          <Viewer
            items={visible}
            start={visible.indexOf(it)}
            status={status}
            initialJobs={jobs}
            onDelete={(x) => askDelete([x.id])}
          />,
        )
      }
    />
  );

  return (
    <Focusable className="dmg-page" onCancelButton={goBack}>
      <Styles />
      <Focusable className="dmg-bars" flow-children="column">
        <Focusable className="dmg-bar" flow-children="horizontal">
          {chip("all", t("f_all"))}
          {chip("screenshot", t("f_screenshots"))}
          {chip("video", t("f_videos"))}
          <div className="dmg-game">
            <Dropdown
              rgOptions={[{ data: -1, label: t("all_games") }, ...games]}
              selectedOption={game}
              onChange={(o: { data: number }) => setGame(o.data)}
            />
          </div>
          <div className="dmg-spacer" />
          <DialogButton onClick={() => changeLayout(layout === "days" ? "grid" : "days")}>
            {layout === "days" ? t("view_days") : t("view_grid")}
          </DialogButton>
          <DialogButton disabled={tile <= TILE_MIN} onClick={() => changeTile(-40)}>
            −
          </DialogButton>
          <DialogButton disabled={tile >= TILE_MAX} onClick={() => changeTile(40)}>
            +
          </DialogButton>
        </Focusable>
        <Focusable className="dmg-bar" flow-children="horizontal">
          {sel.length > 0 ? (
            <>
              <DialogButton
                className="dmg-chip-on"
                onClick={() => openSend(pickItems(sel), () => setSelected(new Set()))}
              >
                {t("send_n", { n: sel.length })}
              </DialogButton>
              <DialogButton onClick={() => exportVideos(sel)}>{t("export_mp4")}</DialogButton>
              <DialogButton disabled={selMp4 === 0} onClick={() => askDelete(sel)}>
                {t("delete_n", { n: selMp4 })}
              </DialogButton>
              <DialogButton onClick={() => setSelected(new Set())}>{t("clear_sel")}</DialogButton>
            </>
          ) : (
            <>
              <DialogButton onClick={() => setSelected(new Set(visible.map((i) => i.id)))}>
                {t("select_all")}
              </DialogButton>
              <DialogButton onClick={reload}>{t("refresh")}</DialogButton>
              {allMp4.length > 0 && (
                <DialogButton onClick={() => askDelete(allMp4)}>
                  {t("delete_all_mp4", { n: allMp4.length })}
                </DialogButton>
              )}
            </>
          )}
        </Focusable>
      </Focusable>

      {(stProblem || (!status.ffmpeg && items.some((i) => i.kind === "video"))) && (
        <Focusable className="dmg-warnbar" flow-children="horizontal">
          <div className="dmg-warn">
            {stProblem ? t("sync_problem", { msg: status.syncthing?.message ?? "" }) : t("v_no_ffmpeg")}
          </div>
          <DialogButton
            onClick={() => openPage(SETUP_ROUTE)}
          >
            {t("fix")}
          </DialogButton>
        </Focusable>
      )}

      {visible.length === 0 && <div className="dmg-empty">{t("empty")}</div>}

      {layout === "days" ? (
        <Focusable flow-children="column">
          {days.map((day) => (
            <div key={day.label}>
              <div className="dmg-day">
                {day.label}
                <small>{day.items.length}</small>
              </div>
              <Focusable className={gridClass} style={gridStyle} flow-children="grid">
                {day.items.map(renderTile)}
              </Focusable>
            </div>
          ))}
        </Focusable>
      ) : (
        <Focusable className={`${gridClass} dmg-flat`} style={gridStyle} flow-children="grid">
          {visible.map(renderTile)}
        </Focusable>
      )}
    </Focusable>
  );
};

// ------------------------------------------------------------------ quick access panel

const Panel: FC = () => {
  const [st, setSt] = useState<Status | null>(null);
  const [form, setForm] = useState<Settings | null>(null);
  const [extra, setExtra] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const tileTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = (s: Status) => {
    setSt(s);
    setForm(s.settings);
    setExtra(s.settings.extra_recording_dirs.join("; "));
  };

  // toggles and the slider are saved right away, without the button
  const patch = async (p: Partial<Settings>) => {
    setForm((f) => (f ? { ...f, ...p } : f));
    try {
      setSt(await saveSettings(p));
    } catch (e) {
      toast(t("not_saved", { err: errText(e) }));
    }
  };

  useEffect(() => {
    setLanguage(lang())
      .then(() => getStatus())
      .then(load)
      .catch((e) => setErr(errText(e)));
  }, []);

  const go = (route: string) => openFromPanel(route);

  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => go(ROUTE)}>
            {t("open_gallery")}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => go(SETUP_ROUTE)}>
            {t("open_setup")}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      {err && (
        <PanelSection title={t("error_title")}>
          <PanelSectionRow>
            <div style={{ fontSize: 12, color: "#e4b100" }}>{t("plugin_failed", { err })}</div>
          </PanelSectionRow>
        </PanelSection>
      )}

      {st && form && (
        <>
          <PanelSection title={t("status")}>
            <PanelSectionRow>
              <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                <div>{st.ffmpeg ? t("ffmpeg_ok") : t("ffmpeg_missing")}</div>
                <div>{st.last_device ? t("last_device", { name: st.last_device }) : t("no_devices")}</div>
                {st.syncthing && <div>{t("syncthing_line", { msg: st.syncthing.message })}</div>}
              </div>
            </PanelSectionRow>
          </PanelSection>

          <PanelSection title={t("delete_section")}>
            <PanelSectionRow>
              <ToggleField
                label={t("auto_delete")}
                description={t("auto_delete_desc")}
                checked={form.auto_delete}
                onChange={(v: boolean) => patch({ auto_delete: v })}
              />
            </PanelSectionRow>
          </PanelSection>

          <PanelSection title={t("st_section")}>
            <PanelSectionRow>
              <ToggleField
                label={t("st_toggle")}
                description={t("st_toggle_desc")}
                checked={form.syncthing_enabled}
                onChange={(v: boolean) => patch({ syncthing_enabled: v })}
              />
            </PanelSectionRow>
            {form.syncthing_enabled && (
              <PanelSectionRow>
                <ToggleField
                  label={t("per_game")}
                  checked={form.per_game_folders}
                  onChange={(v: boolean) => patch({ per_game_folders: v })}
                />
              </PanelSectionRow>
            )}
          </PanelSection>

          <PanelSection title={t("view_section")}>
            <PanelSectionRow>
              <ToggleField
                label={t("group_by_day")}
                checked={form.ui_layout !== "grid"}
                onChange={(v: boolean) => patch({ ui_layout: v ? "days" : "grid" })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label={t("tile_size")}
                value={clampTile(form.ui_tile || 196)}
                min={TILE_MIN}
                max={TILE_MAX}
                step={20}
                showValue
                onChange={(v: number) => {
                  setForm((f) => (f ? { ...f, ui_tile: v } : f));
                  if (tileTimer.current) clearTimeout(tileTimer.current);
                  tileTimer.current = setTimeout(() => patch({ ui_tile: v }), 400);
                }}
              />
            </PanelSectionRow>
          </PanelSection>

          <PanelSection title={t("settings_section")}>
            <PanelSectionRow>
              <TextField
                label={t("export_dir")}
                value={form.export_dir}
                onChange={(e: { target: { value: string } }) => setForm({ ...form, export_dir: e.target.value })}
              />
            </PanelSectionRow>
            {form.syncthing_enabled && (
              <PanelSectionRow>
                <TextField
                  label={t("outbox_dir")}
                  value={form.outbox_dir}
                  onChange={(e: { target: { value: string } }) => setForm({ ...form, outbox_dir: e.target.value })}
                />
              </PanelSectionRow>
            )}
            <PanelSectionRow>
              <TextField
                label={t("extra_dirs")}
                value={extra}
                onChange={(e: { target: { value: string } }) => setExtra(e.target.value)}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                onClick={async () => {
                  try {
                    load(
                      await saveSettings({
                        export_dir: form.export_dir,
                        outbox_dir: form.outbox_dir,
                        extra_recording_dirs: extra
                          .split(";")
                          .map((x) => x.trim())
                          .filter(Boolean),
                      }),
                    );
                    toast(t("saved"));
                  } catch (e) {
                    toast(t("not_saved", { err: errText(e) }));
                  }
                }}
              >
                {t("save_settings")}
              </ButtonItem>
            </PanelSectionRow>
          </PanelSection>
        </>
      )}
    </>
  );
};

// ------------------------------------------------------------------ plugin

export default definePlugin(() => {
  setLanguage(lang()).catch(() => undefined);
  routerHook.addRoute(ROUTE, Gallery, { exact: true });
  routerHook.addRoute(SETUP_ROUTE, Setup, { exact: true });
  return {
    name: TITLE,
    titleView: <div className={staticClasses.Title}>{TITLE}</div>,
    content: <Panel />,
    icon: <FaImages />,
    onDismount() {
      routerHook.removeRoute(ROUTE);
      routerHook.removeRoute(SETUP_ROUTE);
    },
  };
});
