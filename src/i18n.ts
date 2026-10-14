// UI strings. The language follows the Steam client language: Russian for Russian,
// English for everything else. To add a language, copy the "en" block.

const en = {
  // quick access panel
  open_gallery: "Open gallery",
  open_setup: "Setup",
  status: "Status",
  ffmpeg_ok: "ffmpeg: installed",
  ffmpeg_missing: "ffmpeg: not installed",
  last_device: "Last receiving device: {name}",
  no_devices: "No files have been sent yet",
  error_title: "Error",
  plugin_failed: "The plugin failed to start: {err}. Log: ~/homebrew/logs/deck-clip-export/",
  delete_section: "Storage",
  auto_delete: "Remove copies after sending",
  auto_delete_desc:
    "LocalSend: the MP4 file is deleted once it has been sent. Syncthing: the MP4 file and the outgoing copy are removed once another device has received the file in full. Steam recordings and files on other devices are kept.",
  syncthing_line: "Syncthing: {msg}",
  st_section: "Syncthing",
  st_toggle: "Send via Syncthing",
  st_toggle_desc: "Automatic synchronisation with a folder on other devices. Set up in Setup.",
  outbox_dir: "Outgoing folder (Syncthing)",
  per_game: "Sort into per-game folders",
  view_section: "Gallery view",
  group_by_day: "Group by day",
  tile_size: "Tile size",
  settings_section: "Settings",
  export_dir: "MP4 folder",
  extra_dirs: "Additional recording folders (separated by ;)",
  save_settings: "Save",
  saved: "Settings saved",
  not_saved: "Could not save settings: {err}",

  // gallery
  f_all: "All",
  f_screenshots: "Screenshots",
  f_videos: "Videos",
  all_games: "All games",
  no_game: "No game",
  app_n: "App {id}",
  send_n: "Send ({n})",
  export_mp4: "Save videos as MP4",
  delete_n: "Remove copies ({n})",
  clear_sel: "Clear selection",
  select_all: "Select all",
  refresh: "Refresh",
  delete_all_mp4: "Remove all copies ({n})",
  view_days: "View: by day",
  view_grid: "View: grid",
  fix: "Open setup",
  empty: "No screenshots or recordings yet. Take a screenshot or record a clip in Steam, then select Refresh.",
  not_responding: "The plugin is not responding: {err}",
  logs_hint: "See the log for details: ~/homebrew/logs/deck-clip-export/",
  retry: "Retry",
  today: "Today",
  yesterday: "Yesterday",
  queued: "Queued",
  working: "In progress…",
  failed_short: "Error",
  done_n: "Completed: {n}",
  done_failed: "Completed: {n}, failed: {f}",
  sent_to: "Sent to {device}: {n}",
  sent_to_deleted: "Sent to {device}: {n}. MP4 files deleted: {d}",
  st_sent: "Added to the Syncthing folder “{label}”: {n}",
  st_sent_some: "Added to the Syncthing folder “{label}”: {n}, already there: {k}",
  st_sent_none: "The files are already in the Syncthing folder “{label}”",
  sync_problem: "{msg}. Sending via Syncthing is unavailable.",
  send_failed: "Sending failed. {err}",
  nothing_to_export: "No videos to save",

  // tile
  t_open: "Open",
  t_select: "Select",
  t_deselect: "Deselect",
  t_send: "Send",
  t_delete: "Remove copies",
  no_preview: "No preview",
  cant_open: "Cannot open",
  video: "video",

  // viewer
  v_prev: "◀",
  v_next: "▶",
  v_play: "Play / pause",
  v_save_mp4: "Save as MP4",
  v_send: "Send",
  v_delete: "Remove copies",
  v_export_hint: "Save the recording as MP4 to play it here",
  v_failed: "Error: {err}",
  v_no_ffmpeg: "ffmpeg is not installed, so videos cannot be saved. It can be installed in Setup.",

  // delete confirmation
  c_title_one: "Remove copies from this device?",
  c_title_n: "Remove copies of {n} items?",
  c_text:
    "The MP4 files and the outgoing Syncthing copies will be deleted from this device. Steam screenshots and recordings are kept, and the copies can be created again at any time. Files already sent to other devices are not affected.",
  c_ok: "Remove",
  c_cancel: "Cancel",
  no_mp4: "No copies to remove",

  // send dialog
  sd_title_one: "Send file",
  sd_title_n: "Send files ({n})",
  sd_hint:
    "LocalSend: the receiving device must have LocalSend open and be connected to the same network. The transfer may need to be accepted on that device.",
  sd_ls: "LocalSend",
  sd_st: "Syncthing",
  sd_st_folder: "Folder “{label}”",
  sd_st_hint: "The files are added to the synced folder and reach the receiving devices automatically.",
  sd_searching: "Searching for devices…",
  sd_none: "No devices found. Make sure LocalSend is open on the receiving device, then search again.",
  sd_available: "available",
  sd_not_found: "not found",
  sd_saved: "saved",
  sd_search: "Search again",
  sd_pin: "PIN (only if required by the receiving device)",
  sd_address: "Device address (IP)",
  sd_add: "Connect",
  sd_cancel: "Cancel",
  sd_size: "Total size: {size}",
  sd_videos: "Recordings are saved as MP4 before sending.",

  // setup
  s_title: "Setup",
  s_ffmpeg_desc: "Required to save Steam recordings in MP4 format.",
  s_ffmpeg_found: "Found: {path}",
  s_ffmpeg_own: "Installed by the plugin.",
  s_ffmpeg_missing: "Not installed.",
  s_install: "Install ({size})",
  s_failed: "Error: {err}",
  s_this: "This device",
  s_this_desc: "Name shown on receiving devices: {name}",
  s_this_addr: "Network address: {addr}",
  s_this_offline: "No network connection.",
  s_receivers: "Receiving devices (LocalSend)",
  s_step1:
    "1. Install LocalSend on the device that will receive files. The app is free and available for Android, iPhone and iPad, Windows, macOS and Linux (localsend.org).",
  s_step2: "2. Open LocalSend on that device. Both devices must be connected to the same network.",
  s_step3:
    "3. Select Search. Found devices are offered automatically when sending. By default, each transfer is accepted on the receiving device; to receive files without confirmation, enable Quick Save in LocalSend.",
  s_search: "Search",
  s_found: "Available devices",
  s_saved: "Saved devices",
  s_forget: "Forget",
  s_none: "No devices found.",
  s_manual:
    "If a device is not found automatically, enter its address. It is shown in LocalSend on the receiving device, on the Receive tab.",
  s_hotspot: "When this device is connected to a smartphone's hotspot, the smartphone's address is usually {addr}.",
  s_added: "Device added: {name}",
  s_st_desc:
    "Optional. Keeps a folder synchronised with your other devices over the local network or the internet: sent files arrive automatically, without confirmation.",
  s_st_off: "Sending via Syncthing is turned off.",
  s_st_enable: "Turn on",
  s_st_disable: "Turn off",
  s_st_external: "Using the Syncthing installation already present on this device.",
  s_st_external_stopped: "Syncthing is installed but not running. Start it and return to this screen.",
  s_st_own_running: "Running (installed by the plugin).",
  s_st_own_stopped: "Installed by the plugin but not running.",
  s_start: "Start",
  s_st_missing: "Not installed.",
  s_st_receivers: "Receiving devices (Syncthing)",
  s_receivers_need_st: "Install or start Syncthing first.",
  s_st_step1:
    "1. Install Syncthing on the device that will receive files: Syncthing-Fork for Android, Möbius Sync for iPhone and iPad, or Syncthing for a computer.",
  s_st_step2: "2. In the app, add a new device and scan this QR code or enter the device ID shown here.",
  s_st_step3:
    "3. Approve the request on this screen, then accept the “Deck Clip Export” folder on the receiving device. " +
    "Keep the default folder type, “Send & Receive”. On a smartphone, it is recommended to place the folder in DCIM so that files appear in the photo gallery.",
  s_waiting: "Waiting for a connection request…",
  s_pending: "Connection request: {name}",
  s_connect: "Approve",
  s_devices: "Connected devices",
  s_online: "online",
  s_offline: "offline",
  s_shared: "receives files",
  s_share: "Send files to this device",
  s_connected_toast: "Connection approved. Accept the folder on the receiving device.",
  s_st_ready: "Syncthing is set up. Files can now be sent to the folder.",
  s_st_ready_short: "Ready",
  l_status: "Status",
  l_name: "Name on receiving devices",
  l_address: "Network address",
  l_search: "Search the network",
  l_search_desc: "Finds devices with LocalSend open on the same network",
  l_folder: "Outgoing folder",
  l_qr: "ID of this device",
  h_devices: "Receiving devices",
  h_add: "Add by address",
  h_help: "How to connect",
  h_pair: "Connect a device",
  ls_h1: "1. Install LocalSend on the receiving device",
  ls_d1: "Free for Android, iPhone and iPad, Windows, macOS and Linux: localsend.org",
  ls_h2: "2. Open LocalSend",
  ls_d2: "Both devices must be connected to the same network",
  ls_h3: "3. Select Search",
  ls_d3:
    "Found devices are offered automatically when sending. To receive files without confirmation, enable Quick Save in LocalSend.",
  st_h1: "1. Install Syncthing on the receiving device",
  st_d1: "Syncthing-Fork for Android, Möbius Sync for iPhone and iPad, or Syncthing for a computer",
  st_h2: "2. Add this device",
  st_d2: "In the app, add a new device and scan this QR code or enter the ID",
  st_h3: "3. Approve the request and accept the folder",
  st_d3:
    "The request appears above on this screen. Then accept the “Deck Clip Export” folder on the receiving device. Keep the type “Send & Receive”; on a smartphone, place the folder in DCIM so that files appear in the gallery.",
};

export type Key = keyof typeof en;

const ru: Record<Key, string> = {
  open_gallery: "Открыть галерею",
  open_setup: "Настройка",
  status: "Состояние",
  ffmpeg_ok: "ffmpeg: установлен",
  ffmpeg_missing: "ffmpeg: не установлен",
  last_device: "Последнее устройство-получатель: {name}",
  no_devices: "Файлы ещё не отправлялись",
  error_title: "Ошибка",
  plugin_failed: "Не удалось запустить плагин: {err}. Журнал: ~/homebrew/logs/deck-clip-export/",
  delete_section: "Хранилище",
  auto_delete: "Удалять копии после отправки",
  auto_delete_desc:
    "LocalSend: файл MP4 удаляется после отправки. Syncthing: файл MP4 и копия для отправки удаляются, когда другое устройство полностью получило файл. Записи Steam и файлы на других устройствах сохраняются.",
  syncthing_line: "Syncthing: {msg}",
  st_section: "Syncthing",
  st_toggle: "Отправка через Syncthing",
  st_toggle_desc: "Автоматическая синхронизация с папкой на других устройствах. Настраивается в разделе «Настройка».",
  outbox_dir: "Папка для отправки (Syncthing)",
  per_game: "Раскладывать по папкам игр",
  view_section: "Вид галереи",
  group_by_day: "Группировать по дням",
  tile_size: "Размер плиток",
  settings_section: "Параметры",
  export_dir: "Папка для MP4",
  extra_dirs: "Дополнительные папки записей (через ;)",
  save_settings: "Сохранить",
  saved: "Параметры сохранены",
  not_saved: "Не удалось сохранить параметры: {err}",

  f_all: "Все",
  f_screenshots: "Скриншоты",
  f_videos: "Видео",
  all_games: "Все игры",
  no_game: "Без игры",
  app_n: "Приложение {id}",
  send_n: "Отправить ({n})",
  export_mp4: "Сохранить видео в MP4",
  delete_n: "Удалить копии ({n})",
  clear_sel: "Снять выделение",
  select_all: "Выделить все",
  refresh: "Обновить",
  delete_all_mp4: "Удалить все копии ({n})",
  view_days: "Вид: по дням",
  view_grid: "Вид: сетка",
  fix: "Открыть настройку",
  empty: "Скриншотов и записей пока нет. Сделайте скриншот или запишите клип в Steam, затем нажмите «Обновить».",
  not_responding: "Плагин не отвечает: {err}",
  logs_hint: "Подробности в журнале: ~/homebrew/logs/deck-clip-export/",
  retry: "Повторить",
  today: "Сегодня",
  yesterday: "Вчера",
  queued: "В очереди",
  working: "Выполняется…",
  failed_short: "Ошибка",
  done_n: "Выполнено: {n}",
  done_failed: "Выполнено: {n}, с ошибкой: {f}",
  sent_to: "Отправлено на устройство {device}: {n}",
  sent_to_deleted: "Отправлено на устройство {device}: {n}. Удалено файлов MP4: {d}",
  st_sent: "Добавлено в папку Syncthing «{label}»: {n}",
  st_sent_some: "Добавлено в папку Syncthing «{label}»: {n}, уже были в ней: {k}",
  st_sent_none: "Файлы уже находятся в папке Syncthing «{label}»",
  sync_problem: "{msg}. Отправка через Syncthing недоступна.",
  send_failed: "Не удалось отправить. {err}",
  nothing_to_export: "Нет видео для сохранения",

  t_open: "Открыть",
  t_select: "Выделить",
  t_deselect: "Снять выделение",
  t_send: "Отправить",
  t_delete: "Удалить копии",
  no_preview: "Нет превью",
  cant_open: "Не удаётся открыть",
  video: "видео",

  v_prev: "◀",
  v_next: "▶",
  v_play: "Воспроизведение / пауза",
  v_save_mp4: "Сохранить в MP4",
  v_send: "Отправить",
  v_delete: "Удалить копии",
  v_export_hint: "Для воспроизведения сохраните запись в MP4",
  v_failed: "Ошибка: {err}",
  v_no_ffmpeg: "ffmpeg не установлен, поэтому сохранение видео недоступно. Установить его можно в разделе «Настройка».",

  c_title_one: "Удалить копии с этого устройства?",
  c_title_n: "Удалить копии ({n})?",
  c_text:
    "Файлы MP4 и копии для отправки через Syncthing будут удалены с этого устройства. Скриншоты и записи Steam сохранятся, копии можно создать повторно в любой момент. Файлы, уже отправленные на другие устройства, не затрагиваются.",
  c_ok: "Удалить",
  c_cancel: "Отмена",
  no_mp4: "Нет копий для удаления",

  sd_title_one: "Отправка файла",
  sd_title_n: "Отправка файлов ({n})",
  sd_hint:
    "LocalSend: на устройстве-получателе должно быть открыто приложение LocalSend, оба устройства должны находиться в одной сети. Передачу может потребоваться подтвердить на устройстве-получателе.",
  sd_ls: "LocalSend",
  sd_st: "Syncthing",
  sd_st_folder: "Папка «{label}»",
  sd_st_hint: "Файлы добавляются в синхронизируемую папку и поступают на устройства-получатели автоматически.",
  sd_searching: "Поиск устройств…",
  sd_none: "Устройства не найдены. Убедитесь, что LocalSend открыт на устройстве-получателе, и повторите поиск.",
  sd_available: "доступно",
  sd_not_found: "не найдено",
  sd_saved: "сохранено",
  sd_search: "Повторить поиск",
  sd_pin: "PIN-код (только если его требует устройство-получатель)",
  sd_address: "Адрес устройства (IP)",
  sd_add: "Подключить",
  sd_cancel: "Отмена",
  sd_size: "Общий размер: {size}",
  sd_videos: "Перед отправкой записи сохраняются в MP4.",

  s_title: "Настройка",
  s_ffmpeg_desc: "Требуется для сохранения записей Steam в формате MP4.",
  s_ffmpeg_found: "Найден: {path}",
  s_ffmpeg_own: "Установлен плагином.",
  s_ffmpeg_missing: "Не установлен.",
  s_install: "Установить ({size})",
  s_failed: "Ошибка: {err}",
  s_this: "Это устройство",
  s_this_desc: "Имя, отображаемое на устройствах-получателях: {name}",
  s_this_addr: "Сетевой адрес: {addr}",
  s_this_offline: "Нет подключения к сети.",
  s_receivers: "Устройства-получатели (LocalSend)",
  s_step1:
    "1. Установите LocalSend на устройство, которое будет получать файлы. Приложение бесплатно и доступно для Android, iPhone и iPad, Windows, macOS и Linux (localsend.org).",
  s_step2: "2. Откройте LocalSend на этом устройстве. Оба устройства должны быть подключены к одной сети.",
  s_step3:
    "3. Нажмите «Найти». Найденные устройства будут предложены при отправке автоматически. По умолчанию каждую передачу нужно подтвердить на устройстве-получателе; чтобы принимать файлы без подтверждения, включите в LocalSend функцию Quick Save («Быстрое сохранение»).",
  s_search: "Найти",
  s_found: "Доступные устройства",
  s_saved: "Сохранённые устройства",
  s_forget: "Забыть",
  s_none: "Устройства не найдены.",
  s_manual:
    "Если устройство не находится автоматически, введите его адрес. Он отображается в LocalSend на устройстве-получателе на вкладке «Получить».",
  s_hotspot: "Если это устройство подключено к точке доступа смартфона, адрес смартфона обычно {addr}.",
  s_added: "Устройство добавлено: {name}",
  s_st_desc:
    "Дополнительно. Поддерживает папку синхронизированной с другими устройствами по локальной сети или через интернет: отправленные файлы поступают автоматически, без подтверждения.",
  s_st_off: "Отправка через Syncthing выключена.",
  s_st_enable: "Включить",
  s_st_disable: "Выключить",
  s_st_external: "Используется Syncthing, ранее установленный на этом устройстве.",
  s_st_external_stopped: "Syncthing установлен, но не запущен. Запустите его и вернитесь на этот экран.",
  s_st_own_running: "Работает (установлен плагином).",
  s_st_own_stopped: "Установлен плагином, но не запущен.",
  s_start: "Запустить",
  s_st_missing: "Не установлен.",
  s_st_receivers: "Устройства-получатели (Syncthing)",
  s_receivers_need_st: "Сначала установите или запустите Syncthing.",
  s_st_step1:
    "1. Установите Syncthing на устройство, которое будет получать файлы: Syncthing-Fork для Android, Möbius Sync для iPhone и iPad или Syncthing для компьютера.",
  s_st_step2: "2. Добавьте в приложении новое устройство и отсканируйте QR-код или введите указанный здесь идентификатор.",
  s_st_step3:
    "3. Одобрите запрос на этом экране, затем примите папку «Deck Clip Export» на устройстве-получателе. " +
    "Оставьте тип папки по умолчанию: «Отправка и получение». На смартфоне рекомендуется разместить папку в DCIM, чтобы файлы отображались в галерее.",
  s_waiting: "Ожидание запроса на подключение…",
  s_pending: "Запрос на подключение: {name}",
  s_connect: "Одобрить",
  s_devices: "Подключённые устройства",
  s_online: "в сети",
  s_offline: "не в сети",
  s_shared: "получает файлы",
  s_share: "Отправлять файлы на это устройство",
  s_connected_toast: "Подключение одобрено. Примите папку на устройстве-получателе.",
  s_st_ready: "Syncthing настроен. Теперь можно отправлять файлы в папку.",
  s_st_ready_short: "Готово",
  l_status: "Состояние",
  l_name: "Имя на устройствах-получателях",
  l_address: "Сетевой адрес",
  l_search: "Поиск в сети",
  l_search_desc: "Находит устройства с открытым LocalSend в той же сети",
  l_folder: "Папка для отправки",
  l_qr: "Идентификатор этого устройства",
  h_devices: "Устройства-получатели",
  h_add: "Добавление по адресу",
  h_help: "Как подключить",
  h_pair: "Подключение устройства",
  ls_h1: "1. Установите LocalSend на устройство-получатель",
  ls_d1: "Бесплатно для Android, iPhone и iPad, Windows, macOS и Linux: localsend.org",
  ls_h2: "2. Откройте LocalSend",
  ls_d2: "Оба устройства должны быть подключены к одной сети",
  ls_h3: "3. Нажмите «Найти»",
  ls_d3:
    "Найденные устройства будут предложены при отправке автоматически. Чтобы принимать файлы без подтверждения, включите в LocalSend функцию Quick Save («Быстрое сохранение»).",
  st_h1: "1. Установите Syncthing на устройство-получатель",
  st_d1: "Syncthing-Fork для Android, Möbius Sync для iPhone и iPad или Syncthing для компьютера",
  st_h2: "2. Добавьте это устройство",
  st_d2: "Добавьте в приложении новое устройство и отсканируйте этот QR-код или введите идентификатор",
  st_h3: "3. Одобрите запрос и примите папку",
  st_d3:
    "Запрос появится выше на этом экране. Затем примите папку «Deck Clip Export» на устройстве-получателе. Тип папки — «Отправка и получение»; на смартфоне разместите её в DCIM, чтобы файлы отображались в галерее.",
};

const TABLES = { en, ru };
export type Lang = keyof typeof TABLES;

let current: Lang | null = null;

export function lang(): Lang {
  if (current) return current;
  const candidates: unknown[] = [];
  try {
    const w = window as any;
    // Steam's own UI language ("russian", "english", ...)
    candidates.push(w.LocalizationManager?.m_rgLocalesToUse?.[0]);
    candidates.push(document?.documentElement?.lang);
  } catch {
    /* ignore */
  }
  candidates.push(typeof navigator !== "undefined" ? navigator.language : undefined);
  // the first known value wins: Steam's language beats the system locale
  const first = candidates.find((c) => typeof c === "string" && c.length > 0) as string | undefined;
  current = first && /^(ru|russian)/i.test(first) ? "ru" : "en";
  return current;
}

export function t(key: Key, vars?: Record<string, string | number>): string {
  let text: string = TABLES[lang()][key] ?? en[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) text = text.split(`{${k}}`).join(String(v));
  }
  return text;
}

export function dateLocale(): string {
  return lang() === "ru" ? "ru-RU" : "en-US";
}

export function fmtSize(bytes: number): string {
  const ru = lang() === "ru";
  const units = ru ? ["Б", "КБ", "МБ", "ГБ"] : ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  const num = v.toFixed(i >= 2 ? 1 : 0);
  return `${ru ? num.replace(".", ",") : num} ${units[i]}`;
}
