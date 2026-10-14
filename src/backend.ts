import { callable } from "@decky/api";

export const ROUTE = "/deck-clip-export";
export const SETUP_ROUTE = "/deck-clip-export/setup";
export const EVENT = "dmg_job";
export const TILE_MIN = 120;
export const TILE_MAX = 400;

export type Kind = "screenshot" | "video";

export interface MediaItem {
  id: string;
  kind: Kind;
  appid: number;
  mtime: number;
  size: number;
  duration: number | null;
  exported: boolean;
  clip: boolean;
  /** the plugin's own files for this item take space (MP4, outgoing Syncthing copy) */
  copies: boolean;
}

export interface Settings {
  export_dir: string;
  extra_recording_dirs: string[];
  auto_delete: boolean;
  ui_layout: "days" | "grid";
  ui_tile: number;
  syncthing_enabled: boolean;
  outbox_dir: string;
  per_game_folders: boolean;
  st_managed: boolean;
}

export interface SyncthingStatus {
  found: boolean;
  running: boolean;
  managed: boolean;
  outbox_shared: boolean;
  folder_label: string | null;
  message: string;
}

export interface Status {
  port: number;
  token: string;
  ffmpeg: string | null;
  settings: Settings;
  alias: string;
  last_device: string | null;
  known_count: number;
  /** null while sending via Syncthing is turned off */
  syncthing: SyncthingStatus | null;
}

export interface JobResult {
  device?: string;
  via?: "localsend" | "syncthing";
  count?: number;
  already?: number;
  exported?: string[];
  deleted?: string[];
  /** the affected items as they are after the job */
  items?: MediaItem[];
}

export interface Job {
  id: string;
  item_ids: string[];
  item_id: string;
  action: "export" | "send" | "delete" | "install";
  auto?: boolean;
  status: "queued" | "running" | "done" | "error";
  stage: string;
  error: string | null;
  result?: JobResult | string | null;
}

/** A LocalSend receiver. */
export interface Device {
  fingerprint: string;
  alias: string;
  ip: string;
  port: number;
  protocol: "http" | "https";
  deviceType: string;
  deviceModel: string | null;
  known: boolean;
  last: boolean;
}

export const SYNCTHING_TARGET = { kind: "syncthing" as const };
export type Target = Device | typeof SYNCTHING_TARGET;

export interface StDevice {
  id: string;
  name: string;
  connected: boolean;
  shared: boolean;
}

export interface SetupInfo {
  ffmpeg: string | null;
  ffmpeg_own: boolean;
  alias: string;
  known: Device[];
  gateways: string[];
  addresses: string[];
  syncthing_enabled: boolean;
  syncthing: SyncthingStatus | null;
  st_installed: boolean;
  outbox: string;
  my_id: string | null;
  devices: StDevice[];
  pending: { id: string; name: string }[];
}

export type ItemRef = { id: string; name?: string };

export const setLanguage = callable<[code: string], string>("set_language");
export const getStatus = callable<[], Status>("get_status");
export const listMedia = callable<[], MediaItem[]>("list_media");
export const enqueue = callable<[items: ItemRef[], action: "export" | "delete"], Job[]>("enqueue");
export const sendItems = callable<[items: ItemRef[], target: Target, pin: string], Job | null>("send");
export const discover = callable<[], Device[]>("discover");
export const addDevice = callable<[host: string], { ok: boolean; device?: Device; error?: string }>("add_device");
export const forgetDevice = callable<[fingerprint: string], boolean>("forget_device");
export const saveSettings = callable<[settings: Partial<Settings>], Status>("save_settings");
export const installComponent = callable<[component: "ffmpeg" | "syncthing"], Job | null>("install");
export const getSetupInfo = callable<[], SetupInfo>("setup_info");
export const connectDevice = callable<[deviceId: string, name: string], { ok: boolean; error?: string }>(
  "connect_device",
);
export const startSyncthing = callable<[], { ok: boolean; error?: string }>("start_syncthing");

export function errText(e: unknown): string {
  return String((e as any)?.message ?? e);
}

export function jobResult(job: Job): JobResult {
  return job.result && typeof job.result === "object" ? job.result : {};
}

/** Merges saved and discovered devices; the discovered address wins. */
export function mergeDevices(saved: Device[], found: Device[]): Device[] {
  const out = new Map<string, Device>();
  for (const d of saved) out.set(d.fingerprint, d);
  for (const d of found) out.set(d.fingerprint, { ...out.get(d.fingerprint), ...d });
  return Array.from(out.values()).sort(
    (a, b) =>
      Number(b.last) - Number(a.last) ||
      Number(b.known) - Number(a.known) ||
      (a.alias || "").localeCompare(b.alias || ""),
  );
}
