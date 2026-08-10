import { createSDKI18n, resolveApiErrorMessage, resolvePlaybackDrivenEncoderFps, resolveUploadVideoSize, resolveRtcPublishFps, createCanvasPosterUrl, isMobilePublishEnvironment, drawSourceCover, DEFAULT_SESSION_TARGET_SIZE } from './chunk-G57L4HQX.js';
export { API_ERROR_MESSAGES, DEFAULT_SESSION_TARGET_SIZE, MAX_UPLOAD_VIDEO_PIXELS, MEDIA_TIME_EPSILON_S, MEDIA_TIME_LOOP_JUMP_S, MIN_UPLOAD_VIDEO_PIXELS, MOBILE_PUBLISH_MAX_WIDTH_PX, PREVIEW_CONTAINER_ASPECT_RATIO, RTC_PUBLISH_FPS_MOBILE, RTC_PUBLISH_FPS_WEB, RTC_PUBLISH_FRAME_INTERVAL_MS, RTC_PUBLISH_FRAME_INTERVAL_S, createSDKI18n, createVideoFileStream, getDefaultMessages, isMobilePublishEnvironment, resolveAdaptiveRtcVideoSize, resolveApiErrorMessage, resolvePreviewAspectRatio, resolveRtcPublishFps, resolveRtcPublishFrameIntervalS, resolveSessionTargetSize, resolveUploadPublishSize, resolveUploadVideoSize, shouldSampleAtMediaTime } from './chunk-G57L4HQX.js';
import COS from 'cos-js-sdk-v5';
import VERTC, { VideoSourceType, MediaType, StreamIndex, RoomProfileType, MirrorType, AudioSourceType, VideoCodecType, VideoRenderMode } from '@volcengine/rtc';

// src/shared/error-utils.ts
function notifyError(error, notifier, fallbackMessage) {
  const resolved = error instanceof Error ? error : Object.assign(new Error(fallbackMessage), { cause: error });
  if (!resolved.__XmaxNotified && notifier) {
    resolved.__XmaxNotified = true;
    const message = resolved.message || fallbackMessage;
    notifier(message, error);
  }
  return resolved;
}

// src/api/client.ts
var XMAX_OPEN_API_BASE_URLS = {
  // 国内 — @xmaxai/sdk
  cn: "https://cloud.xmax.22duck.cn/open/api/v1",
  // 海外 — @xmaxai/sdk-global
  global: "https://api.xmax.cloud/open/api/v1"
};
var XMAX_SDK_BUILD_REGION = "cn";
var XMAX_OPEN_API_PRODUCTION_BASE_URL = XMAX_OPEN_API_BASE_URLS[XMAX_SDK_BUILD_REGION];
var ACTIVE_STATUS = "ACTIVE";
var STS_TTL_MS = 30 * 60 * 1e3;
var STS_REFRESH_BUFFER_MS = 5 * 60 * 1e3;
var HEARTBEAT_CONSECUTIVE_FAILURE_LIMIT = 3;
function isBrowserFile(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (typeof File !== "undefined" && value instanceof File) {
    return true;
  }
  return Object.prototype.toString.call(value) === "[object File]" && typeof value.name === "string" && typeof value.type === "string" && typeof value.slice === "function";
}
function isBrowserBlob(value) {
  if (!value || typeof value !== "object") {
    return false;
  }
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return true;
  }
  return Object.prototype.toString.call(value) === "[object Blob]" && typeof value.type === "string" && typeof value.slice === "function" && typeof value.size === "number";
}
function normalizeUploadFile(value, expectedTypePrefix) {
  if (isBrowserFile(value)) {
    return value;
  }
  if (!isBrowserBlob(value)) {
    return null;
  }
  const fallbackType = expectedTypePrefix.startsWith("video/") ? "video/mp4" : "image/jpeg";
  const type = value.type?.trim() || fallbackType;
  const extension = type.includes("/") ? type.split("/")[1]?.split("+")[0] || (expectedTypePrefix.startsWith("video/") ? "mp4" : "jpg") : expectedTypePrefix.startsWith("video/") ? "mp4" : "jpg";
  return new File([value], `upload.${extension}`, { type });
}
function sanitizeFileName(fileName) {
  return fileName.trim().replace(/[^\w.\-一-龥]/g, "_").replace(/_+/g, "_");
}
function buildCosFileUrl(endpoint, bucket, key) {
  const trimmed = endpoint.trim();
  const url = new URL(
    /^https?:\/\//i.test(trimmed) ? trimmed.endsWith("/") ? trimmed : `${trimmed}/` : `https://${trimmed.replace(/^\/+/, "")}${trimmed.endsWith("/") ? "" : "/"}`
  );
  if (url.hostname.startsWith("cos.") && !url.hostname.startsWith(`${bucket}.`)) {
    url.hostname = `${bucket}.${url.hostname}`;
  }
  return new URL(key.replace(/^\/+/, ""), url.toString()).toString();
}
function resolveCosUploadUrl(raw, sts, key) {
  const location = raw?.Location?.trim();
  if (location) {
    return /^https?:\/\//i.test(location) ? location : `https://${location.replace(/^\/+/, "")}`;
  }
  const endpoint = sts.endpoint?.trim();
  if (endpoint) {
    return buildCosFileUrl(endpoint, sts.bucket, key);
  }
  return `https://${sts.bucket}.cos.${sts.region}.myqcloud.com/${key.replace(/^\/+/, "")}`;
}
var XmaxOpenClient = class {
  constructor(options) {
    this.stsCache = null;
    this.heartbeatIntervalId = null;
    this.suppressErrorNotification = false;
    this.teardownAbortController = null;
    this.pendingRequestControllers = /* @__PURE__ */ new Set();
    const i18n = options.i18n ?? createSDKI18n({ locale: options.locale });
    if (!options.apiKey?.trim()) {
      throw new Error(i18n.t("errors.apiKeyEmpty"));
    }
    if (!options.baseUrl?.trim()) {
      throw new Error(i18n.t("errors.baseUrlEmpty"));
    }
    this.apiKey = options.apiKey;
    this.authToken = options.authToken;
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 1e4;
    this.i18n = i18n;
    this.onError = options.onError;
  }
  throwError(message, cause) {
    const error = new Error(message);
    if (cause !== void 0) {
      error.cause = cause;
    }
    if (this.suppressErrorNotification) {
      throw error;
    }
    throw notifyError(error, this.onError, message);
  }
  /** Stop heartbeat, abort in-flight API requests, and suppress error notifications during teardown. */
  beginTeardown() {
    this.suppressErrorNotification = true;
    this.stopHeartbeat();
    if (this.teardownAbortController) {
      this.teardownAbortController.abort();
    }
    this.teardownAbortController = new AbortController();
    this.pendingRequestControllers.forEach((controller) => {
      controller.abort();
    });
    this.pendingRequestControllers.clear();
  }
  endTeardown() {
    this.suppressErrorNotification = false;
    this.teardownAbortController = null;
  }
  isAbortError(error) {
    return error instanceof DOMException && error.name === "AbortError";
  }
  async request(method, path, body) {
    const controller = new AbortController();
    this.pendingRequestControllers.add(controller);
    const onAbort = () => controller.abort();
    this.teardownAbortController?.signal.addEventListener("abort", onAbort);
    const timeoutId = window.setTimeout(() => controller.abort(), this.timeoutMs);
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Api-Key": this.apiKey
    };
    if (this.authToken) {
      headers["Authorization"] = `Bearer ${this.authToken}`;
    }
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: body === void 0 ? void 0 : JSON.stringify(body),
        signal: controller.signal
      });
      const text = await response.text();
      let payload;
      try {
        payload = text ? JSON.parse(text) : null;
      } catch (parseError) {
        throw this.throwError(this.i18n.t("errors.invalidJson"), parseError);
      }
      if (typeof payload !== "object" || payload === null) {
        throw this.throwError(this.i18n.t("errors.invalidPayload"));
      }
      const p = payload;
      if (response.ok && p.success === true) {
        return p.data;
      }
      const mappedMessage = resolveApiErrorMessage(p.code, this.i18n.locale);
      const backendMessage = typeof p.message === "string" && p.message.trim() ? p.message.trim() : void 0;
      const errorMessage = mappedMessage ?? backendMessage ?? this.i18n.t("errors.requestRetry");
      throw new Error(errorMessage);
    } catch (error) {
      if (this.isAbortError(error)) {
        if (this.suppressErrorNotification) {
          throw new Error(this.i18n.t("errors.requestTimeout"));
        }
        throw this.throwError(this.i18n.t("errors.requestTimeout"), error);
      } else if (error instanceof Error) {
        if (this.suppressErrorNotification) {
          throw error;
        }
        throw notifyError(error, this.onError, error.message || this.i18n.t("errors.requestFailed"));
      } else {
        throw this.throwError(this.i18n.t("errors.requestFailed"), error);
      }
    } finally {
      this.teardownAbortController?.signal.removeEventListener("abort", onAbort);
      this.pendingRequestControllers.delete(controller);
      window.clearTimeout(timeoutId);
    }
  }
  async createSession(model) {
    if (!model.trim()) {
      this.throwError(this.i18n.t("errors.modelEmpty"));
    }
    return this.request("POST", "/session", { model });
  }
  async getSession(sessionUid) {
    return this.request("GET", `/session/${sessionUid}`);
  }
  async heartbeatSession(sessionUid) {
    return this.request("PUT", `/session/${sessionUid}/heartbeat`);
  }
  async closeSession(sessionUid) {
    const previousSuppress = this.suppressErrorNotification;
    this.suppressErrorNotification = true;
    try {
      return await this.request("DELETE", `/session/${sessionUid}`);
    } catch {
      return null;
    } finally {
      this.suppressErrorNotification = previousSuppress;
    }
  }
  async getCosSts(forceRefresh = false) {
    const now = Date.now();
    if (!forceRefresh && this.stsCache && now - this.stsCache.fetchedAt < STS_TTL_MS - STS_REFRESH_BUFFER_MS) {
      return this.stsCache.value;
    }
    const sts = await this.request("GET", "/cos/sts");
    this.stsCache = {
      value: sts,
      fetchedAt: now
    };
    return sts;
  }
  async uploadObject(file, expectedTypePrefix) {
    const uploadFile = normalizeUploadFile(file, expectedTypePrefix);
    if (!uploadFile) {
      this.throwError(this.i18n.t("errors.invalidFile"));
    }
    if (!uploadFile.type.startsWith(expectedTypePrefix)) {
      this.throwError(this.i18n.t("errors.invalidFileType", { type: uploadFile.type || "(empty)" }));
    }
    const sts = await this.getCosSts();
    const safeFileName = sanitizeFileName(uploadFile.name) || "image";
    const key = `${sts.prefix}${Date.now()}_${safeFileName}`;
    const cos = new COS({
      SecretId: sts.credentials.accessKeyId,
      SecretKey: sts.credentials.secretAccessKey,
      SecurityToken: sts.credentials.sessionToken
    });
    const raw = await new Promise((resolve, reject) => {
      cos.putObject(
        {
          Bucket: sts.bucket,
          Region: sts.region,
          Key: key,
          Body: uploadFile,
          ContentType: uploadFile.type
        },
        (error, data) => {
          if (error) {
            reject(error);
            return;
          }
          resolve(data);
        }
      );
    });
    return {
      key,
      url: resolveCosUploadUrl(raw, sts, key),
      raw,
      sts
    };
  }
  async uploadImage(file) {
    return this.uploadObject(file, "image/");
  }
  async uploadVideo(file) {
    return this.uploadObject(file, "video/");
  }
  /**
   * Upload an image then run `/cos/image/check`.
   * Returns the checked URL. Existing {@link uploadImage} is unchanged.
   */
  async uploadAndCheckImage(file) {
    const uploaded = await this.uploadImage(file);
    const data = await this.request("POST", "/cos/image/check", {
      url: uploaded.url
    });
    if (!data?.url) {
      this.throwError(this.i18n.t("errors.imageCheckMissingUrl"));
    }
    if (data.safe === false) {
      this.throwError(this.i18n.t("errors.imageCheckUnsafe"));
    }
    return data.url;
  }
  startHeartbeat(sessionUid, intervalMs = 1e4, onHeartbeat, onError) {
    this.stopHeartbeat();
    let consecutiveFailures = 0;
    let heartbeatInFlight = false;
    const heartbeat = async () => {
      if (heartbeatInFlight) {
        return;
      }
      heartbeatInFlight = true;
      try {
        const session = await this.heartbeatSession(sessionUid);
        consecutiveFailures = 0;
        onHeartbeat?.(session);
        if (session.status !== ACTIVE_STATUS) {
          this.stopHeartbeat();
        }
      } catch (error) {
        consecutiveFailures += 1;
        const definitelyOffline = typeof navigator !== "undefined" && navigator.onLine === false;
        if (definitelyOffline || consecutiveFailures >= HEARTBEAT_CONSECUTIVE_FAILURE_LIMIT) {
          onError?.(error);
          this.stopHeartbeat();
        }
      } finally {
        heartbeatInFlight = false;
      }
    };
    heartbeat();
    this.heartbeatIntervalId = window.setInterval(heartbeat, intervalMs);
  }
  stopHeartbeat() {
    if (this.heartbeatIntervalId !== null) {
      clearInterval(this.heartbeatIntervalId);
      this.heartbeatIntervalId = null;
    }
  }
  getRtcJoinInfo(session) {
    const roomId = session.modelExtra?.room_id?.trim();
    const appId = session.modelExtra?.rtc_app_id?.trim();
    const token = session.modelExtra?.room_token?.trim();
    const userId = session.modelExtra?.user_id?.trim() || session.userUid?.trim() || "";
    if (!roomId || !appId || !token || !userId) {
      this.throwError(this.i18n.t("errors.sessionJoinInfoIncomplete"));
    }
    return {
      appId,
      roomId,
      userId,
      token,
      botName: session.modelExtra?.bot_name
    };
  }
};

// src/rtc/rtc-events.ts
function createTaskUid() {
  const now = Date.now();
  if (now !== lastTaskUidTimestamp) {
    lastTaskUidTimestamp = now;
    sameTickSequence = 0;
  } else {
    sameTickSequence += 1;
  }
  const randomPart = createRandomUint32();
  return `task-${now}-${sameTickSequence}-${randomPart}`;
}
var lastTaskUidTimestamp = 0;
var sameTickSequence = 0;
function createRandomUint32() {
  if (typeof globalThis.crypto?.getRandomValues === "function") {
    const value = new Uint32Array(1);
    globalThis.crypto.getRandomValues(value);
    return value[0];
  }
  return Math.floor(Math.random() * 4294967296);
}
function createStartRtcRoomEvent(input) {
  const resolvedPrompt = input.prompt?.trim() ?? "";
  const refImagePath = input.refImagePath?.trim() || input.refImage?.trim() || void 0;
  const useRefImage = !!refImagePath;
  const staticImagePath = input.staticImagePath?.trim() || void 0;
  return {
    event: "start",
    user_id: input.userId?.trim() || void 0,
    uid: input.uid?.trim() || void 0,
    session_uid: input.sessionUid?.trim() || void 0,
    params: {
      model: input.model.trim(),
      size: input.size,
      prompt: resolvedPrompt,
      ref_image_path: useRefImage ? refImagePath : void 0,
      ref_image: useRefImage ? refImagePath : void 0,
      // Omit when false/undefined so starts never carry leftover `static_generate`.
      static_generate: input.staticGenerate === true ? true : void 0,
      static_image_path: staticImagePath,
      ...input.extraParams ?? {},
      mirror: input.mirror
    }
  };
}
function createChangeConditionRtcRoomEvent(input) {
  const resolvedPrompt = input.prompt?.trim() ?? "";
  const refImagePath = input.refImagePath?.trim() || input.refImage?.trim() || void 0;
  const useRefImage = !!refImagePath;
  const staticImagePath = input.staticImagePath?.trim() || void 0;
  return {
    event: "change_condition",
    user_id: input.userId?.trim() || void 0,
    session_uid: input.sessionUid?.trim() || void 0,
    params: {
      model: input.model.trim(),
      size: input.size,
      prompt: resolvedPrompt,
      ref_image_path: useRefImage ? refImagePath : void 0,
      ref_image: useRefImage ? refImagePath : void 0,
      static_generate: input.staticGenerate === true ? true : void 0,
      static_image_path: staticImagePath,
      ...input.extraParams ?? {}
    }
  };
}
function createStopRtcRoomEvent(input) {
  return {
    event: "stop",
    user_id: input.userId?.trim() || void 0,
    session_uid: input.sessionUid?.trim() || void 0
  };
}
function createTracksRtcRoomEvent(input) {
  return {
    event: "tracks",
    user_id: input.userId?.trim() || void 0,
    uid: input.uid?.trim() || void 0,
    session_uid: input.sessionUid?.trim() || void 0,
    tracks: input.tracks
  };
}

// src/realtime/default.ts
var DEFAULT_REALTIME_STREAM_MAX_KBPS = 1200;
var DEFAULT_REALTIME_STREAM_CONTENT_HINT = "detail";
var DEFAULT_REALTIME_HEARTBEAT_INTERVAL_MS = 1e4;
var DEFAULT_METADATA_TIMEOUT_MS = 1e3;
var DEFAULT_REALTIME_AUTO_START = true;
var DEFAULT_REALTIME_START_EVENT_MODEL = "default";
var DEFAULT_REALTIME_PLAYBACK_SETTING = {
  playbackRate: 1
};
var DEFAULT_REALTIME_RENDER_SETTING = {
  mirror: false,
  dragEnabled: true
};
var DEFAULT_CAMERA_REALTIME_SETTINGS = {
  desktop: {
    width: 1472,
    height: 832,
    fps: 24,
    maxKbps: DEFAULT_REALTIME_STREAM_MAX_KBPS,
    contentHint: DEFAULT_REALTIME_STREAM_CONTENT_HINT
  },
  mobile: {
    width: 960,
    height: 1280,
    fps: 24,
    maxKbps: DEFAULT_REALTIME_STREAM_MAX_KBPS,
    contentHint: DEFAULT_REALTIME_STREAM_CONTENT_HINT
  }
};

// src/rtc/render/preview-media-layout.ts
var PREVIEW_UPLOAD_LAYOUT_ATTR = "data-preview-upload-layout";
var PREVIEW_UPLOAD_FIT_ATTR = "data-preview-upload-fit";
var PREVIEW_OUTPUT_LAYOUT_ATTR = "data-preview-output-layout";
var PREVIEW_CONTAIN_ATTR = "data-preview-contain";
var PREVIEW_COVER_ATTR = "data-preview-cover";
function hasFitPreviewLayout(container) {
  return container.hasAttribute(PREVIEW_UPLOAD_LAYOUT_ATTR) || container.hasAttribute(PREVIEW_OUTPUT_LAYOUT_ATTR) || container.hasAttribute(PREVIEW_CONTAIN_ATTR) || container.closest(`[${PREVIEW_UPLOAD_LAYOUT_ATTR}]`) !== null || container.closest(`[${PREVIEW_OUTPUT_LAYOUT_ATTR}]`) !== null || container.closest(`[${PREVIEW_CONTAIN_ATTR}]`) !== null;
}
function hasCoverPreviewLayout(container) {
  return container.hasAttribute(PREVIEW_COVER_ATTR) || container.closest(`[${PREVIEW_COVER_ATTR}]`) !== null;
}
function applyUploadPreviewMediaLayout(container) {
  if (hasCoverPreviewLayout(container)) {
    return;
  }
  if (!hasFitPreviewLayout(container)) {
    return;
  }
  container.style.overflow = "hidden";
  container.style.display = "flex";
  container.style.alignItems = "center";
  container.style.justifyContent = "center";
  container.querySelectorAll("div").forEach((node) => {
    if (node === container) {
      return;
    }
    const el = node;
    el.style.width = "100%";
    el.style.height = "100%";
    el.style.display = "flex";
    el.style.alignItems = "center";
    el.style.justifyContent = "center";
    el.style.overflow = "hidden";
  });
  container.querySelectorAll("video, canvas").forEach((node) => {
    const el = node;
    el.style.display = "block";
    el.style.objectFit = "contain";
    el.style.objectPosition = "center";
    el.style.position = "relative";
    el.style.left = "auto";
    el.style.right = "auto";
    el.style.top = "auto";
    el.style.bottom = "auto";
    el.style.transform = "none";
    el.style.width = "100%";
    el.style.height = "100%";
    el.style.maxWidth = "none";
    el.style.maxHeight = "none";
    el.style.margin = "0";
  });
}
function observeUploadPreviewMediaLayout(container) {
  if (!hasFitPreviewLayout(container) && !hasCoverPreviewLayout(container)) {
    return () => {
    };
  }
  let rafId = null;
  const apply = () => applyUploadPreviewMediaLayout(container);
  const scheduleApply = () => {
    if (rafId !== null) {
      return;
    }
    rafId = requestAnimationFrame(() => {
      rafId = null;
      apply();
    });
  };
  apply();
  const observer = new MutationObserver(() => scheduleApply());
  observer.observe(container, {
    childList: true,
    subtree: true,
    attributes: true
  });
  return () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
    observer.disconnect();
  };
}

// src/rtc/sei.ts
var SESSION_SEI_INTERVAL_MS = 200;
var DEFAULT_SEI_REPEAT_COUNT = 4;
var SEI_TIMEOUT_MS = 2e3;
var SEI_TIMEOUT_CONSOLE_PATTERN = /timeout for sei message/i;
var seiTimeoutConsoleFilterDepth = 0;
var originalConsoleError = null;
function acquireSeiTimeoutConsoleFilter() {
  if (seiTimeoutConsoleFilterDepth === 0) {
    originalConsoleError = console.error.bind(console);
    console.error = (...args) => {
      const first = args[0];
      if (typeof first === "string" && SEI_TIMEOUT_CONSOLE_PATTERN.test(first)) {
        return;
      }
      originalConsoleError?.(...args);
    };
  }
  seiTimeoutConsoleFilterDepth += 1;
  let released = false;
  return () => {
    if (released) {
      return;
    }
    released = true;
    seiTimeoutConsoleFilterDepth = Math.max(0, seiTimeoutConsoleFilterDepth - 1);
    if (seiTimeoutConsoleFilterDepth === 0 && originalConsoleError) {
      console.error = originalConsoleError;
      originalConsoleError = null;
    }
  };
}
function normalizeSei(value) {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }
  return normalized.startsWith("task-") ? normalized.slice("task-".length) : normalized;
}
function decodeSeiMessage(sei) {
  try {
    return new TextDecoder().decode(sei);
  } catch {
    return null;
  }
}
var RtcSeiSender = class {
  /** Create a sender backed by the owning RTC manager's readiness and send operations. */
  constructor(options) {
    this.options = options;
    this.message = null;
    this.repeatCount = DEFAULT_SEI_REPEAT_COUNT;
    this.timer = null;
    this.hasReportedError = false;
    this.releaseConsoleFilter = null;
    this.releaseConsoleFilterTimer = null;
  }
  /** Replace the active task message and stop any timer that belonged to the previous task. */
  configure(message, options, frameRate) {
    this.stop();
    this.message = message;
    this.repeatCount = resolveRepeatCount(options.repeatCount, frameRate);
    this.hasReportedError = false;
  }
  /** Whether a task message is currently configured for sending. */
  get configured() {
    return this.message !== null;
  }
  /** Start sending immediately and continue at the configured cadence. */
  start() {
    this.stop();
    if (!this.message) {
      return;
    }
    this.holdSeiTimeoutConsoleFilter();
    this.sendIfReady();
    this.timer = setInterval(() => this.sendIfReady(), SESSION_SEI_INTERVAL_MS);
  }
  /** Stop future sends without changing the configured task message. */
  stop() {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.scheduleReleaseSeiTimeoutConsoleFilter();
  }
  /** Send one SEI message when RTC publishing is ready, and stop after a synchronous failure. */
  sendIfReady() {
    if (!this.message || !this.options.canSend()) {
      return;
    }
    try {
      this.options.send(this.message, this.repeatCount);
    } catch (error) {
      if (!this.hasReportedError) {
        this.hasReportedError = true;
        this.options.onError(error);
      }
      this.stop();
    }
  }
  holdSeiTimeoutConsoleFilter() {
    if (this.releaseConsoleFilterTimer !== null) {
      clearTimeout(this.releaseConsoleFilterTimer);
      this.releaseConsoleFilterTimer = null;
    }
    if (!this.releaseConsoleFilter) {
      this.releaseConsoleFilter = acquireSeiTimeoutConsoleFilter();
    }
  }
  scheduleReleaseSeiTimeoutConsoleFilter() {
    if (!this.releaseConsoleFilter || this.releaseConsoleFilterTimer !== null) {
      return;
    }
    this.releaseConsoleFilterTimer = setTimeout(() => {
      this.releaseConsoleFilterTimer = null;
      this.releaseConsoleFilter?.();
      this.releaseConsoleFilter = null;
    }, SEI_TIMEOUT_MS);
  }
};
function resolveRepeatCount(value, frameRate) {
  const maxRepeatCount = Math.min(30, Math.max(0, Math.floor(frameRate * 2)));
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return Math.min(DEFAULT_SEI_REPEAT_COUNT, maxRepeatCount);
  }
  return Math.max(0, Math.min(maxRepeatCount, Math.floor(value)));
}
function resolveVideoRenderMode(container, fit) {
  if (fit === "contain") {
    return VideoRenderMode.RENDER_MODE_FIT;
  }
  if (fit === "cover") {
    return VideoRenderMode.RENDER_MODE_HIDDEN;
  }
  if (container.hasAttribute(PREVIEW_UPLOAD_LAYOUT_ATTR) || container.hasAttribute(PREVIEW_OUTPUT_LAYOUT_ATTR) || container.hasAttribute("data-preview-contain") || container.hasAttribute(PREVIEW_UPLOAD_FIT_ATTR) || container.closest(`[${PREVIEW_UPLOAD_LAYOUT_ATTR}]`) || container.closest(`[${PREVIEW_OUTPUT_LAYOUT_ATTR}]`) || container.closest("[data-preview-contain]") || container.closest(`[${PREVIEW_UPLOAD_FIT_ATTR}]`)) {
    return VideoRenderMode.RENDER_MODE_FIT;
  }
  if (container.hasAttribute("data-preview-cover") || container.hasAttribute("data-upload-preview-cover") || container.closest("[data-preview-cover]") || container.closest("[data-upload-preview-cover]")) {
    return VideoRenderMode.RENDER_MODE_HIDDEN;
  }
  const rect = container.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return VideoRenderMode.RENDER_MODE_FIT;
  }
  const isCompactPreview = rect.width <= 160;
  const isPortraitFrame = rect.height > rect.width;
  return isCompactPreview || isPortraitFrame ? VideoRenderMode.RENDER_MODE_HIDDEN : VideoRenderMode.RENDER_MODE_FIT;
}
function readRtcVideoStat(stats, keys) {
  for (const key of keys) {
    const value = stats[key];
    if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
      return value;
    }
  }
  return 0;
}
var REMOTE_OUTPUT_STALL_MS = 2e4;
var REMOTE_OUTPUT_RECOVERY_COOLDOWN_MS = 6e4;
var REMOTE_FIRST_OUTPUT_TIMEOUT_MS = 15e3;
var DEFAULT_VIDEO_FRAME_RATE = 24;
var _RtcManager = class _RtcManager {
  constructor(options = {}) {
    this.engine = null;
    this.leaveTask = null;
    this.users = /* @__PURE__ */ new Set();
    this.currentJoinInfo = null;
    this.joined = false;
    this.preserveRemoteDom = false;
    this.localVideoPublished = false;
    this.localAudioPublished = false;
    this.internalVideoCaptureStarted = false;
    this.internalAudioCaptureStarted = false;
    this.localVideoSourceType = VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL;
    this.externalVideoTrack = null;
    this.externalAudioTrack = null;
    this.remoteVideoUserId = null;
    this.pendingRemoteVideoUserId = null;
    this.pendingRemoteVideoMediaType = MediaType.VIDEO;
    /** Subscribed to RTC media; render may still wait on SEI match. */
    this.subscribedRemoteUserId = null;
    this.subscribedRemoteMediaType = MediaType.VIDEO;
    this.remoteFirstOutputTimer = null;
    this.onRemoteFirstOutputTimeout = null;
    this.localVideoContainer = null;
    this.remoteVideoContainer = null;
    this.expectedRemoteSei = null;
    this.lastRemoteSei = null;
    this.lastRemoteSeiUserId = null;
    this.localVideoFrameRate = DEFAULT_VIDEO_FRAME_RATE;
    this.seiSupport = "unknown";
    this.hasLoggedSeiUnsupported = false;
    this.lastDebugSeiMatched = null;
    this.lastDebugRemoteSei = null;
    this.remoteFrameWatchStop = null;
    this.uploadPreviewLayoutObserverStop = null;
    this.remoteOutputRecoveryCooldownUntil = 0;
    this.joinedAtMs = 0;
    this.publishStartedAtMs = 0;
    this.lastRoomStartEventAtMs = 0;
    this.localStreamStatsCount = 0;
    this.firstNonZeroSentFrameRateAtMs = 0;
    this.lastObservedSentFrameRate = 0;
    this.localOutboundWatch = null;
    this.seiGateFallbackTimer = null;
    this.seiMatchedDelayTimer = null;
    this.lastSentResolution = "";
    this.lastReceivedResolution = "";
    this.renderFit = options.renderFit;
    this.playRemoteAudio = options.playRemoteAudio === true;
    this.onLog = options.onLog;
    this.onStateChange = options.onStateChange;
    this.onSeiGateChange = options.onSeiGateChange;
    this.onRemoteVideoFirstFrame = options.onRemoteVideoFirstFrame;
    this.onRemoteSeiReceived = options.onRemoteSeiReceived;
    this.onRemoteOutputStalled = options.onRemoteOutputStalled;
    this.onRoomEvent = options.onRoomEvent;
    this.onUserJoined = options.onUserJoined;
    this.debug = options.debug ?? false;
    this.i18n = options.i18n ?? createSDKI18n();
    this.seiSender = new RtcSeiSender({
      canSend: () => Boolean(
        this.engine && this.joined && this.localVideoPublished && this.firstNonZeroSentFrameRateAtMs > 0 && this.seiSupport === "supported"
      ),
      send: (message, repeatCount) => {
        this.engine?.sendSEIMessage(StreamIndex.STREAM_INDEX_MAIN, message, repeatCount);
      },
      onError: (error) => {
        this.log("warn", this.i18n.t("rtc.sendSeiFailed"), error);
      }
    });
  }
  emitSeiGateState() {
    const matched = this.isSeiMatched();
    this.onSeiGateChange?.({
      expectedSei: this.expectedRemoteSei,
      sei: this.lastRemoteSei,
      userId: this.lastRemoteSeiUserId,
      matched
    });
    if (matched && this.expectedRemoteSei && this.lastRemoteSei === this.expectedRemoteSei) {
      this.clearRemoteFirstOutputWatch();
    }
  }
  setOnRemoteOutputStalled(handler) {
    this.onRemoteOutputStalled = handler;
  }
  setOnRemoteVideoFirstFrame(handler) {
    this.onRemoteVideoFirstFrame = handler;
  }
  /**
   * Arm first-output deadline after `start` is sent.
   * Timer origin: sendRoomEvent(start) completion time (caller arms immediately after).
   */
  armRemoteFirstOutputWatch(options) {
    this.clearRemoteFirstOutputWatch();
    const timeoutMs = options.timeoutMs ?? REMOTE_FIRST_OUTPUT_TIMEOUT_MS;
    this.onRemoteFirstOutputTimeout = options.onTimeout;
    this.remoteFirstOutputTimer = setTimeout(() => {
      this.remoteFirstOutputTimer = null;
      const cb = this.onRemoteFirstOutputTimeout;
      this.onRemoteFirstOutputTimeout = null;
      cb?.();
    }, timeoutMs);
  }
  clearRemoteFirstOutputWatch() {
    if (this.remoteFirstOutputTimer !== null) {
      clearTimeout(this.remoteFirstOutputTimer);
      this.remoteFirstOutputTimer = null;
    }
    this.onRemoteFirstOutputTimeout = null;
  }
  /**
   * Passively watch RTC outbound stats after start. It never touches the source track,
   * canvas, or encoder; only sustained zero fps (or an ended track) triggers failure.
   */
  armLocalOutboundWatch(options) {
    this.clearLocalOutboundWatch();
    const nowMs = performance.now();
    const track = this.externalVideoTrack ?? this.engine?.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video") ?? null;
    const state = {
      onStalled: options.onStalled,
      minZeroSamples: options.minZeroSamples ?? 3,
      minStallMs: options.minStallMs ?? 6e3,
      resumeGraceMs: options.resumeGraceMs ?? 5e3,
      consecutiveZeroStats: 0,
      lastPositiveAtMs: nowMs,
      graceUntilMs: nowMs + (options.startGraceMs ?? 6e3),
      triggered: false,
      track,
      onTrackEnded: () => {
        this.triggerLocalOutboundStall("track-ended");
      },
      onTrackMute: () => {
        const watch = this.localOutboundWatch;
        if (!watch || watch.triggered) {
          return;
        }
        if (watch.muteTimer !== null) {
          clearTimeout(watch.muteTimer);
        }
        watch.muteTimer = setTimeout(() => {
          watch.muteTimer = null;
          if (!this.localOutboundWatch || this.localOutboundWatch !== watch || watch.triggered) {
            return;
          }
          if (typeof document !== "undefined" && document.visibilityState === "hidden") {
            return;
          }
          this.triggerLocalOutboundStall("track-muted");
        }, watch.muteTriggerMs);
      },
      onTrackUnmute: () => {
        const watch = this.localOutboundWatch;
        if (!watch) {
          return;
        }
        if (watch.muteTimer !== null) {
          clearTimeout(watch.muteTimer);
          watch.muteTimer = null;
        }
        watch.consecutiveZeroStats = 0;
        watch.lastPositiveAtMs = performance.now();
        watch.graceUntilMs = performance.now() + watch.resumeGraceMs;
      },
      onVisibilityChange: () => {
        const watch = this.localOutboundWatch;
        if (!watch) {
          return;
        }
        watch.consecutiveZeroStats = 0;
        watch.lastPositiveAtMs = performance.now();
        watch.graceUntilMs = document.visibilityState === "hidden" ? Number.POSITIVE_INFINITY : performance.now() + watch.resumeGraceMs;
      },
      muteTimer: null,
      muteTriggerMs: 1500
    };
    this.localOutboundWatch = state;
    track?.addEventListener("ended", state.onTrackEnded);
    track?.addEventListener("mute", state.onTrackMute);
    track?.addEventListener("unmute", state.onTrackUnmute);
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", state.onVisibilityChange);
      if (document.visibilityState === "hidden") {
        state.graceUntilMs = Number.POSITIVE_INFINITY;
      }
    }
    if (track?.readyState === "ended") {
      queueMicrotask(() => this.triggerLocalOutboundStall("track-ended"));
    }
  }
  clearLocalOutboundWatch() {
    const state = this.localOutboundWatch;
    if (!state) {
      return;
    }
    if (state.muteTimer !== null) {
      clearTimeout(state.muteTimer);
      state.muteTimer = null;
    }
    state.track?.removeEventListener("ended", state.onTrackEnded);
    state.track?.removeEventListener("mute", state.onTrackMute);
    state.track?.removeEventListener("unmute", state.onTrackUnmute);
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", state.onVisibilityChange);
    }
    this.localOutboundWatch = null;
  }
  setPreserveRemoteDom(preserve) {
    this.preserveRemoteDom = preserve;
  }
  setOnRemotePlayerMounted(callback) {
    this.onRemotePlayerMounted = callback;
  }
  setOnRoomEvent(callback) {
    this.onRoomEvent = callback;
  }
  setOnUserJoined(callback) {
    this.onUserJoined = callback;
  }
  setLocalVideoContainer(container) {
    const previous = this.localVideoContainer;
    const changed = previous !== container;
    this.localVideoContainer = container;
    if (previous && changed) {
      previous.replaceChildren();
    }
    if (container && changed) {
      container.replaceChildren();
    }
    if (container && this.localVideoPublished && this.engine) {
      this.bindLocalVideoPlayer();
    }
  }
  setRemoteVideoContainer(container) {
    const previous = this.remoteVideoContainer;
    if (previous === container) {
      if (this.debug && container && container.childElementCount === 0 && (this.remoteVideoUserId || this.pendingRemoteVideoUserId)) {
        this.debugLog("setRemoteVideoContainer skipped but container empty", {
          remoteVideoUserId: this.remoteVideoUserId,
          pendingRemoteVideoUserId: this.pendingRemoteVideoUserId
        });
      }
      return;
    }
    this.remoteVideoContainer = container;
    this.debugLog("setRemoteVideoContainer", {
      hadPrevious: !!previous,
      next: !!container,
      remoteVideoUserId: this.remoteVideoUserId,
      pendingRemoteVideoUserId: this.pendingRemoteVideoUserId
    });
    if (previous) {
      previous.replaceChildren();
    }
    if (container && this.engine && this.joined && (this.remoteVideoUserId || this.pendingRemoteVideoUserId)) {
      void this.refreshRemoteVideoBinding();
    }
  }
  /** Tag every local encoded frame with the task id and gate display on matching remote SEI. */
  configureSessionSei(sessionId, options = {}) {
    const normalizedSessionId = normalizeSei(sessionId);
    const previousExpectedRemoteSei = this.expectedRemoteSei;
    this.seiSender.configure(normalizedSessionId, options, this.localVideoFrameRate);
    this.clearSeiGateFallbackTimer();
    this.clearSeiMatchedDelayTimer();
    this.expectedRemoteSei = this.seiSupport === "unsupported" ? null : normalizedSessionId;
    this.lastRemoteSei = null;
    this.lastRemoteSeiUserId = null;
    if (previousExpectedRemoteSei !== this.expectedRemoteSei && this.remoteVideoUserId && !this.preserveRemoteDom) {
      this.pendingRemoteVideoUserId = this.remoteVideoUserId;
      this.remoteVideoUserId = null;
    }
    this.emitSeiGateState();
    if (previousExpectedRemoteSei !== this.expectedRemoteSei && !this.preserveRemoteDom) {
      this.clearContainer(this.remoteVideoContainer);
    }
    this.scheduleSeiGateFallback(normalizedSessionId);
    if (!normalizedSessionId) {
      return;
    }
    this.ensureSeiSupport();
    if (this.seiSupport === "supported") {
      this.seiSender.start();
    }
  }
  clearSeiGateFallbackTimer() {
    if (this.seiGateFallbackTimer !== null) {
      clearTimeout(this.seiGateFallbackTimer);
      this.seiGateFallbackTimer = null;
    }
  }
  clearSeiMatchedDelayTimer() {
    if (this.seiMatchedDelayTimer !== null) {
      clearTimeout(this.seiMatchedDelayTimer);
      this.seiMatchedDelayTimer = null;
    }
  }
  /** Mark SEI matched if remote SEI never arrives — display gate only; RTC bind is not blocked. */
  scheduleSeiGateFallback(expectedSei) {
    this.clearSeiGateFallbackTimer();
    if (!expectedSei) {
      return;
    }
    this.seiGateFallbackTimer = setTimeout(() => {
      this.seiGateFallbackTimer = null;
      if (this.expectedRemoteSei !== expectedSei || this.isSeiMatched()) {
        return;
      }
      this.log("warn", this.i18n.t("rtc.seiGateFallback"), { expectedSei });
      this.expectedRemoteSei = null;
      this.emitSeiGateState();
      void this.refreshRemoteVideoBinding({ force: true });
    }, _RtcManager.SEI_GATE_FALLBACK_MS);
  }
  get snapshot() {
    return {
      roomId: this.currentJoinInfo?.roomId ?? null,
      userId: this.currentJoinInfo?.userId ?? null,
      appId: this.currentJoinInfo?.appId ?? null,
      botUserId: this.currentJoinInfo?.botName ?? null,
      joined: this.joined,
      localVideoPublished: this.localVideoPublished,
      remoteVideoUserId: this.remoteVideoUserId,
      users: Array.from(this.users)
    };
  }
  getLocalVideoSize() {
    if (!this.engine || !this.joined) {
      return null;
    }
    const track = this.engine.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video");
    if (!track) {
      return null;
    }
    const settings = track.getSettings?.();
    const width = typeof settings?.width === "number" ? settings.width : 0;
    const height = typeof settings?.height === "number" ? settings.height : 0;
    if (!width || !height) {
      return null;
    }
    return { width, height };
  }
  getInternalVideoTrack() {
    if (!this.engine || !this.internalVideoCaptureStarted) {
      return null;
    }
    return this.engine.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video") ?? null;
  }
  async prepareEngine(joinInfo) {
    await this.leave();
    this.currentJoinInfo = joinInfo;
    this.users.clear();
    this.users.add(joinInfo.userId);
    this.localVideoPublished = false;
    this.localAudioPublished = false;
    this.internalVideoCaptureStarted = false;
    this.internalAudioCaptureStarted = false;
    this.remoteVideoUserId = null;
    this.pendingRemoteVideoUserId = null;
    this.pendingRemoteVideoMediaType = MediaType.VIDEO;
    this.lastRemoteSei = null;
    this.lastRemoteSeiUserId = null;
    this.clearVideoContainers();
    const createEngineStartedAt = performance.now();
    const engine = VERTC.createEngine(joinInfo.appId);
    this.engine = engine;
    this.bindEngineEvents(engine);
    this.logTiming("\u521B\u5EFA\u5E76\u7ED1\u5B9A RTC Engine", createEngineStartedAt, {
      appId: joinInfo.appId
    });
  }
  async joinPreparedRoom() {
    const engine = this.engine;
    const joinInfo = this.currentJoinInfo;
    if (!engine || !joinInfo) {
      throw new Error(this.i18n.t("errors.rtcNotJoined"));
    }
    if (this.joined) {
      this.log("info", this.i18n.t("rtc.alreadyInRoom"), joinInfo);
      return;
    }
    this.log("info", this.i18n.t("rtc.joiningRoom"), joinInfo);
    const joinRoomStartedAt = performance.now();
    await engine.joinRoom(
      joinInfo.token,
      joinInfo.roomId,
      {
        userId: joinInfo.userId
      },
      {
        isAutoPublish: false,
        isAutoSubscribeAudio: false,
        isAutoSubscribeVideo: true,
        roomProfileType: RoomProfileType.communication
      }
    );
    this.logTiming("joinRoom", joinRoomStartedAt, { roomId: joinInfo.roomId });
    this.joined = true;
    this.joinedAtMs = performance.now();
    this.ensureSeiSupport();
    this.emitState();
    this.log("success", this.i18n.t("rtc.joinSuccess"), this.snapshot);
    this.log("info", this.i18n.t("rtc.roomUsers", { users: this.snapshot.users.join(", ") }), this.snapshot.users);
  }
  async join(joinInfo) {
    if (this.currentJoinInfo?.roomId === joinInfo.roomId && this.joined) {
      this.log("info", this.i18n.t("rtc.alreadyInRoom"), joinInfo);
      return;
    }
    await this.prepareEngine(joinInfo);
    await this.joinPreparedRoom();
  }
  async startInternalVideoCapture(options) {
    if (!this.engine || !this.currentJoinInfo) {
      throw new Error(this.i18n.t("errors.rtcNotJoined"));
    }
    this.localVideoFrameRate = options?.encoderFps ?? DEFAULT_VIDEO_FRAME_RATE;
    if (options?.facingMode) {
      const captureDeviceStartedAt = performance.now();
      await this.engine.setVideoCaptureDevice(options.facingMode);
      this.logTiming("setVideoCaptureDevice", captureDeviceStartedAt, {
        facingMode: options.facingMode
      });
    }
    if (options?.encoderSize) {
      const encoderFrameRate = options.encoderFps ?? DEFAULT_VIDEO_FRAME_RATE;
      const encoderConfigStartedAt = performance.now();
      await this.applyVideoEncoderPreference(options.encoderSize, {
        highQuality: true,
        fps: encoderFrameRate,
        maxKbps: options.encoderMaxKbps,
        contentHint: options.encoderContentHint
      });
      this.logTiming("setVideoEncoderConfig", encoderConfigStartedAt, {
        width: options.encoderSize[0],
        height: options.encoderSize[1],
        frameRate: encoderFrameRate
      });
    }
    if (this.internalVideoCaptureStarted) {
      return this.engine.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video")?.getSettings?.() ?? {};
    }
    this.bindLocalVideoPlayer();
    await this.switchToInternalVideoSource();
    const captureStartedAt = performance.now();
    const captureSettings = await this.engine.startVideoCapture();
    this.internalVideoCaptureStarted = true;
    this.logTiming("startVideoCapture", captureStartedAt, { captureSettings });
    return captureSettings ?? {};
  }
  async publishInternalVideo() {
    if (!this.engine || !this.currentJoinInfo || !this.joined) {
      throw new Error(this.i18n.t("errors.rtcNotJoined"));
    }
    if (!this.internalVideoCaptureStarted) {
      throw new Error(this.i18n.t("errors.videoTrackMissing"));
    }
    if (this.localVideoPublished) {
      this.log("info", this.i18n.t("rtc.localVideoAlreadyPublished"));
      const existingTrack = this.engine.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video");
      if (!existingTrack) {
        throw new Error(this.i18n.t("errors.videoTrackMissing"));
      }
      return existingTrack;
    }
    const publishWithAudio = this.internalAudioCaptureStarted;
    const mediaType = publishWithAudio ? MediaType.AUDIO_AND_VIDEO : MediaType.VIDEO;
    const publishStreamStartedAt = performance.now();
    try {
      await this.engine.publishStream(mediaType);
    } catch (error) {
      if (!publishWithAudio) {
        throw error;
      }
      this.log("warn", "[RTC Diagnose] internal A/V publish failed; fallback to video-only", error);
      const maybeStopAudioCapture = this.engine.stopAudioCapture;
      if (typeof maybeStopAudioCapture === "function") {
        try {
          await maybeStopAudioCapture.call(this.engine);
        } catch {
        }
      }
      this.internalAudioCaptureStarted = false;
      await this.switchToInternalAudioSource();
      await this.engine.publishStream(MediaType.VIDEO);
    }
    this.logTiming("publishStream", publishStreamStartedAt);
    const publishStartedAtMs = performance.now();
    const track = this.engine.getLocalStreamTrack(StreamIndex.STREAM_INDEX_MAIN, "video");
    if (!track) {
      throw new Error(this.i18n.t("errors.videoTrackMissing"));
    }
    this.localVideoPublished = true;
    this.localAudioPublished = this.internalAudioCaptureStarted;
    this.publishStartedAtMs = publishStartedAtMs;
    this.localStreamStatsCount = 0;
    this.firstNonZeroSentFrameRateAtMs = 0;
    this.lastObservedSentFrameRate = 0;
    this.ensureSeiSupport();
    this.emitState();
    this.log("success", this.i18n.t("rtc.localVideoPublished"));
    return track;
  }
  async startInternalAudioCapture() {
    if (!this.engine || !this.currentJoinInfo) {
      throw new Error(this.i18n.t("errors.rtcNotJoined"));
    }
    if (this.internalAudioCaptureStarted) {
      return;
    }
    const maybeStartAudioCapture = this.engine.startAudioCapture;
    if (typeof maybeStartAudioCapture !== "function") {
      this.log("warn", "[Xmax][RTC] startAudioCapture API is unavailable");
      return;
    }
    try {
      await maybeStartAudioCapture.call(this.engine);
      this.internalAudioCaptureStarted = true;
    } catch (error) {
      this.internalAudioCaptureStarted = false;
      this.log("warn", "[RTC Diagnose] startAudioCapture failed; fallback to video-only", error);
    }
  }
  async startExternalVideoPublishing(track, encoderSize, publishOptions) {
    if (!this.engine || !this.currentJoinInfo || !this.joined) {
      throw new Error(this.i18n.t("errors.rtcNotJoined"));
    }
    if (this.localVideoPublished) {
      this.log("info", this.i18n.t("rtc.localVideoAlreadyPublished"));
      return;
    }
    const publishStartedAtMs = performance.now();
    const requestedAudioTrack = publishOptions.audioTrack;
    this.log("info", "[Xmax][RTC] external publish tracks", {
      hasVideoTrack: true,
      hasAudioTrack: Boolean(requestedAudioTrack),
      audioReadyState: requestedAudioTrack?.readyState ?? null
    });
    const encoderOptions = publishOptions.highQuality !== false ? {
      ...publishOptions,
      highQuality: true,
      fps: publishOptions.fps ?? resolvePlaybackDrivenEncoderFps(track)
    } : publishOptions;
    this.localVideoFrameRate = encoderOptions.fps ?? DEFAULT_VIDEO_FRAME_RATE;
    this.bindLocalVideoPlayer();
    await this.switchToExternalVideoSource(track);
    let audioTrack = requestedAudioTrack;
    if (audioTrack) {
      try {
        await this.switchToExternalAudioSource(audioTrack);
      } catch (error) {
        audioTrack = void 0;
        this.externalAudioTrack = null;
        await this.switchToInternalAudioSource();
      }
    }
    await this.applyVideoEncoderPreference(
      encoderSize,
      encoderOptions
    );
    try {
      await this.engine.publishStream(audioTrack ? MediaType.AUDIO_AND_VIDEO : MediaType.VIDEO);
    } catch (error) {
      if (!audioTrack) {
        throw error;
      }
      this.externalAudioTrack = null;
      audioTrack = void 0;
      await this.switchToInternalAudioSource();
      await this.engine.publishStream(MediaType.VIDEO);
    }
    this.localVideoPublished = true;
    this.localAudioPublished = Boolean(audioTrack);
    this.publishStartedAtMs = publishStartedAtMs;
    this.localStreamStatsCount = 0;
    this.firstNonZeroSentFrameRateAtMs = 0;
    this.lastObservedSentFrameRate = 0;
    this.ensureSeiSupport();
    this.emitState();
    this.log("success", this.i18n.t("rtc.externalVideoPublished"));
  }
  async stopVideoPublishing(options) {
    this.clearLocalOutboundWatch();
    if (!this.engine) {
      return;
    }
    this.seiSender.stop();
    if (this.localVideoPublished || this.localAudioPublished) {
      const mediaType = this.localVideoPublished && this.localAudioPublished ? MediaType.AUDIO_AND_VIDEO : this.localAudioPublished ? MediaType.AUDIO : MediaType.VIDEO;
      await this.engine.unpublishStream(mediaType);
    }
    if (this.localVideoSourceType === VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL && this.internalVideoCaptureStarted) {
      await this.engine.stopVideoCapture();
      this.internalVideoCaptureStarted = false;
    }
    const maybeStopAudioCapture = this.engine.stopAudioCapture;
    if (this.internalAudioCaptureStarted && typeof maybeStopAudioCapture === "function") {
      await maybeStopAudioCapture.call(this.engine);
      this.internalAudioCaptureStarted = false;
    }
    if (this.externalVideoTrack) {
      if (!options?.preserveExternalTrack) {
        try {
          this.externalVideoTrack.stop();
        } catch {
        }
      }
      this.externalVideoTrack = null;
    }
    if (this.externalAudioTrack) {
      if (!options?.preserveExternalTrack) {
        try {
          this.externalAudioTrack.stop();
        } catch {
        }
      }
      this.externalAudioTrack = null;
    }
    await this.switchToInternalVideoSource(false);
    await this.switchToInternalAudioSource();
    this.clearUploadPreviewLayoutObserver();
    this.clearContainer(this.localVideoContainer);
    if (!options?.preserveRemote) {
      this.clearRemoteVideo();
    }
    this.localVideoPublished = false;
    this.localAudioPublished = false;
    this.internalAudioCaptureStarted = false;
    this.publishStartedAtMs = 0;
    this.lastSentResolution = "";
    this.emitState();
    this.log("warn", this.i18n.t("rtc.localVideoStopped"));
  }
  async leave(options) {
    if (this.leaveTask) {
      await this.leaveTask;
      return;
    }
    const engine = this.engine;
    if (!engine) {
      return;
    }
    this.leaveTask = (async () => {
      try {
        if (this.localVideoPublished || this.localAudioPublished || this.internalVideoCaptureStarted || this.internalAudioCaptureStarted || this.externalVideoTrack || this.externalAudioTrack) {
          await this.stopVideoPublishing(options);
        }
        if (this.joined) {
          await engine.leaveRoom();
        }
      } catch (error) {
        this.log("warn", this.i18n.t("rtc.leaveRoomError"), error);
      } finally {
        try {
          engine.destroy();
        } catch {
        }
        if (this.engine === engine) {
          this.engine = null;
        }
        this.currentJoinInfo = null;
        this.users.clear();
        this.joined = false;
        this.localVideoPublished = false;
        this.localAudioPublished = false;
        this.internalVideoCaptureStarted = false;
        this.internalAudioCaptureStarted = false;
        this.localVideoSourceType = VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL;
        this.externalVideoTrack = null;
        this.externalAudioTrack = null;
        this.remoteVideoUserId = null;
        this.pendingRemoteVideoUserId = null;
        this.pendingRemoteVideoMediaType = MediaType.VIDEO;
        this.subscribedRemoteUserId = null;
        this.subscribedRemoteMediaType = MediaType.VIDEO;
        this.seiSender.stop();
        this.clearSeiGateFallbackTimer();
        this.clearSeiMatchedDelayTimer();
        this.clearRemoteFirstOutputWatch();
        this.clearLocalOutboundWatch();
        this.stopRemoteFrameWatch();
        this.joinedAtMs = 0;
        this.publishStartedAtMs = 0;
        this.lastRoomStartEventAtMs = 0;
        this.localStreamStatsCount = 0;
        this.firstNonZeroSentFrameRateAtMs = 0;
        this.lastSentResolution = "";
        this.lastReceivedResolution = "";
        this.clearVideoContainers();
        this.emitState();
        this.log("info", this.i18n.t("rtc.engineDestroyed"));
      }
    })();
    try {
      await this.leaveTask;
    } finally {
      this.leaveTask = null;
    }
  }
  /** Subscribe to the remote output stream before start. */
  async prepareRemoteVideoForGeneration() {
    const botUserId = this.currentJoinInfo?.botName?.trim();
    if (!botUserId || !this.engine || !this.joined) {
      return;
    }
    this.pendingRemoteVideoUserId = botUserId;
    this.pendingRemoteVideoMediaType = MediaType.VIDEO;
    await this.ensureRemoteStreamSubscribed(botUserId, MediaType.VIDEO);
  }
  async sendRoomEvent(event) {
    this.ensureReadyForMessaging();
    const payload = JSON.stringify(event);
    const eventName = typeof event === "object" && event !== null && "event" in event ? String(event.event ?? "unknown") : "unknown";
    if (eventName === "start") {
      this.lastRoomStartEventAtMs = performance.now();
    }
    await this.engine?.sendRoomMessage(payload);
    this.log("success", this.i18n.t("rtc.roomEventSent"), event);
  }
  /** Send a control event directly to one user in the current RTC room. */
  async sendUserEvent(userId, event) {
    this.ensureReadyForMessaging();
    const targetUserId = userId.trim();
    if (!targetUserId) {
      return;
    }
    const payload = JSON.stringify(event);
    await this.engine?.sendUserMessage(targetUserId, payload);
    this.log("success", this.i18n.t("rtc.roomEventSent"), {
      targetUserId,
      event
    });
  }
  /** Best-effort room control message. Returns false instead of throwing or blocking callers. */
  async trySendRoomEvent(event) {
    const engine = this.engine;
    if (!engine || !this.joined) {
      return false;
    }
    try {
      const payload = JSON.stringify(event);
      const sendTask = engine.sendRoomMessage(payload);
      if (!sendTask) {
        return false;
      }
      await sendTask;
      this.log("success", this.i18n.t("rtc.roomEventSent"), event);
      return true;
    } catch (error) {
      this.log("warn", this.i18n.t("rtc.roomEventSent"), { event, error });
      return false;
    }
  }
  /** Best-effort direct control message. Returns false instead of throwing or blocking callers. */
  async trySendUserEvent(userId, event) {
    const engine = this.engine;
    const targetUserId = userId.trim();
    if (!engine || !this.joined || !targetUserId) {
      return false;
    }
    try {
      const payload = JSON.stringify(event);
      const sendTask = engine.sendUserMessage(targetUserId, payload);
      if (!sendTask) {
        return false;
      }
      await sendTask;
      this.log("success", this.i18n.t("rtc.roomEventSent"), {
        targetUserId,
        event
      });
      return true;
    } catch (error) {
      this.log("warn", this.i18n.t("rtc.roomEventSent"), {
        targetUserId,
        event,
        error
      });
      return false;
    }
  }
  clearRemoteVideo(options) {
    this.stopRemoteFrameWatch();
    if (!options?.preserveDom && !this.preserveRemoteDom) {
      this.clearContainer(this.remoteVideoContainer);
    }
    if (this.remoteVideoUserId) {
      this.pendingRemoteVideoUserId = this.remoteVideoUserId;
      this.remoteVideoUserId = null;
      this.emitState();
    }
  }
  async refreshRemoteVideoBinding(options) {
    const targetUserId = this.remoteVideoUserId ?? this.pendingRemoteVideoUserId;
    if (!this.engine || !targetUserId || !this.remoteVideoContainer) {
      return;
    }
    await this.ensureRemoteStreamSubscribed(targetUserId, this.pendingRemoteVideoMediaType);
    if (!this.canRenderRemoteVideo(targetUserId)) {
      this.debugLog("refreshRemoteVideoBinding blocked by SEI gate", {
        targetUserId,
        expectedRemoteSei: this.expectedRemoteSei,
        lastRemoteSei: this.lastRemoteSei
      });
      return;
    }
    if (!options?.force && this.remoteVideoUserId === targetUserId && this.remoteVideoContainer && this.remoteVideoContainer.childElementCount > 0) {
      this.debugLog("refreshRemoteVideoBinding skipped (already mounted)", { targetUserId });
      return;
    }
    try {
      await this.mountRemoteVideoPlayer(
        targetUserId,
        this.remoteVideoContainer,
        this.pendingRemoteVideoMediaType,
        options?.force
      );
      this.remoteVideoUserId = targetUserId;
      this.pendingRemoteVideoUserId = null;
      this.emitState();
      this.startRemoteFrameWatch(targetUserId);
      this.emitRemotePlayerMounted();
      this.log("info", this.i18n.t("rtc.remotePlayerRefreshed", { userId: targetUserId }));
    } catch (error) {
      this.log("warn", this.i18n.t("rtc.remotePlayerRefreshFailed"), error);
    }
  }
  bindEngineEvents(engine) {
    const roomMessageHandler = (payload) => {
      const event = this.parseRoomEventPayload(payload);
      this.debugLog("room message received", {
        raw: payload,
        parsed: event
      });
      if (event) {
        this.onRoomEvent?.(event);
      }
    };
    const roomMessageEventNames = /* @__PURE__ */ new Set([
      "onRoomMessageReceived",
      "onUserMessageReceived"
    ]);
    const sdkRoomMessageEventName = VERTC.events.onRoomMessageReceived;
    if (sdkRoomMessageEventName) {
      roomMessageEventNames.add(sdkRoomMessageEventName);
    }
    roomMessageEventNames.forEach((eventName) => {
      engine.on(eventName, roomMessageHandler);
    });
    engine.on(VERTC.events.onUserJoined, (event) => {
      const userId = event.userInfo.userId;
      this.users.add(userId);
      this.emitState();
      try {
        this.onUserJoined?.(userId);
      } catch {
      }
      this.log("success", this.i18n.t("rtc.userJoined", { userId }), event);
      this.log("info", this.i18n.t("rtc.roomUsers", { users: this.snapshot.users.join(", ") }), this.snapshot.users);
    });
    engine.on(VERTC.events.onUserLeave, (event) => {
      this.users.delete(event.userInfo.userId);
      if (this.remoteVideoUserId === event.userInfo.userId) {
        this.remoteVideoUserId = null;
        this.clearContainer(this.remoteVideoContainer);
      }
      if (this.pendingRemoteVideoUserId === event.userInfo.userId) {
        this.pendingRemoteVideoUserId = null;
      }
      this.emitState();
      this.log("warn", this.i18n.t("rtc.userLeft", { userId: event.userInfo.userId }), event);
      this.log("info", this.i18n.t("rtc.roomUsers", { users: this.snapshot.users.join(", ") }), this.snapshot.users);
    });
    engine.on(VERTC.events.onConnectionStateChanged, (event) => {
      this.log("info", this.i18n.t("rtc.connectionStateChanged"), event);
    });
    engine.on(VERTC.events.onUserPublishStream, (event) => {
      this.log("success", this.i18n.t("rtc.userPublished", { userId: event.userId }), event);
      if (this.supportsVideo(event.mediaType)) {
        void this.attachRemoteVideo(event.userId, event.mediaType);
      }
    });
    engine.on(VERTC.events.onUserUnpublishStream, (event) => {
      this.log("warn", this.i18n.t("rtc.userUnpublished", { userId: event.userId }), event);
      this.debugLog("onUserUnpublishStream", {
        userId: event.userId,
        mediaType: event.mediaType,
        remoteVideoUserId: this.remoteVideoUserId,
        expectedRemoteSei: this.expectedRemoteSei,
        lastRemoteSei: this.lastRemoteSei
      });
      if (this.remoteVideoUserId === event.userId && this.supportsVideo(event.mediaType)) {
        this.pendingRemoteVideoUserId = event.userId;
        this.pendingRemoteVideoMediaType = event.mediaType;
        this.remoteVideoUserId = null;
        this.stopRemoteFrameWatch();
        if (!this.preserveRemoteDom) {
          this.clearContainer(this.remoteVideoContainer);
        }
        this.emitState();
        return;
      }
    });
    engine.on(VERTC.events.onSEIMessageReceived, (event) => {
      const userId = event.remoteStreamKey.userId;
      const sei = normalizeSei(decodeSeiMessage(event.sei));
      if (sei && this.isRemoteSeiUser(userId)) {
        this.onRemoteSeiReceived?.({ sei, userId });
      }
      this.lastRemoteSei = sei;
      this.lastRemoteSeiUserId = userId;
      const matched = this.isSeiMatched();
      const seiStateChanged = this.lastDebugSeiMatched !== matched || this.lastDebugRemoteSei !== sei;
      if (this.debug && seiStateChanged) {
        this.debugLog("onSEIMessageReceived", {
          userId,
          sei,
          matched,
          expectedRemoteSei: this.expectedRemoteSei
        });
        this.lastDebugSeiMatched = matched;
        this.lastDebugRemoteSei = sei;
      }
      if (!matched) {
        this.onSeiGateChange?.({
          expectedSei: this.expectedRemoteSei,
          sei,
          userId,
          matched: false
        });
        return;
      }
      if (this.seiMatchedDelayTimer !== null) {
        return;
      }
      this.clearSeiGateFallbackTimer();
      this.seiMatchedDelayTimer = setTimeout(() => {
        this.seiMatchedDelayTimer = null;
        if (!this.isSeiMatched()) {
          return;
        }
        this.onSeiGateChange?.({
          expectedSei: this.expectedRemoteSei,
          sei,
          userId,
          matched: true
        });
        if (this.remoteVideoUserId === userId) {
          return;
        }
        void this.attachRemoteVideo(userId, this.pendingRemoteVideoMediaType);
      }, _RtcManager.SEI_MATCHED_DISPLAY_DELAY_MS);
    });
    engine.on(VERTC.events.onError, (event) => {
      this.log("error", this.i18n.t("rtc.error", { code: String(event.errorCode) }), event);
    });
    engine.on(VERTC.events.onPublishResult, (event) => {
      this.debugLog("onPublishResult", {
        ...event,
        elapsedSincePublishMs: this.publishStartedAtMs > 0 ? Number((performance.now() - this.publishStartedAtMs).toFixed(1)) : null
      });
    });
    engine.on(VERTC.events.onRemoteVideoFirstFrame, (event) => {
      if (event.isScreen || !this.isRemoteSeiUser(event.userId)) {
        return;
      }
      this.onRemoteVideoFirstFrame?.({
        userId: event.userId,
        width: event.width,
        height: event.height
      });
    });
    engine.on(VERTC.events.onLocalStreamStats, (stats) => {
      this.logLocalStreamStats(stats);
      if (stats.videoStats) {
        const videoStats = stats.videoStats;
        const width = readRtcVideoStat(videoStats, ["sentResolutionWidth", "encodedFrameWidth", "width"]);
        const height = readRtcVideoStat(videoStats, ["sentResolutionHeight", "encodedFrameHeight", "height"]);
        const sentFrameRate = readRtcVideoStat(videoStats, ["sentFrameRate", "encodeFrameRate"]);
        this.logVideoFrameDiagnostics("send", width, height, sentFrameRate, void 0, {
          configuredFrameRate: this.localVideoFrameRate,
          inputFrameRate: readRtcVideoStat(videoStats, ["inputFrameRate"]),
          encoderOutputFrameRate: readRtcVideoStat(videoStats, ["encoderOutputFrameRate", "encodeFrameRate"]),
          sentKBitrate: readRtcVideoStat(videoStats, ["sentKBitrate"]),
          targetKBitrate: readRtcVideoStat(videoStats, ["targetKBitrate"]),
          encodedBitrate: readRtcVideoStat(videoStats, ["encodedBitrate"]),
          videoLossRate: readRtcVideoStat(videoStats, ["videoLossRate"]),
          rtt: readRtcVideoStat(videoStats, ["rtt"]),
          statsInterval: readRtcVideoStat(videoStats, ["statsInterval"]),
          elapsedSincePublishMs: this.publishStartedAtMs > 0 ? Number((performance.now() - this.publishStartedAtMs).toFixed(1)) : 0
        });
        const res = `${width}x${height}`;
        if (width > 0 && height > 0 && res !== this.lastSentResolution) {
          this.lastSentResolution = res;
        }
      }
    });
    engine.on(VERTC.events.onRemoteStreamStats, (stats) => {
      if (stats?.videoStats) {
        const videoStats = stats.videoStats;
        const w = readRtcVideoStat(videoStats, ["width", "receivedResolutionWidth", "decodedFrameWidth"]);
        const h = readRtcVideoStat(videoStats, ["height", "receivedResolutionHeight", "decodedFrameHeight"]);
        const receivedFrameRate = readRtcVideoStat(videoStats, ["receivedFrameRate", "decoderOutputFrameRate", "renderFrameRate"]);
        this.logVideoFrameDiagnostics("receive", w, h, receivedFrameRate, stats?.userId);
        const res = `${w}x${h}`;
        if (w > 0 && h > 0 && res !== this.lastReceivedResolution) {
          this.lastReceivedResolution = res;
        }
      }
    });
    engine.on(VERTC.events.onLocalStatsException, (exception) => {
      this.debugLog("onLocalStatsException", {
        exception,
        elapsedSincePublishMs: this.publishStartedAtMs > 0 ? Number((performance.now() - this.publishStartedAtMs).toFixed(1)) : null
      });
    });
    engine.on(VERTC.events.onTrackMute, (event) => {
      this.debugLog("onTrackMute", event);
    });
    engine.on(VERTC.events.onTrackUnmute, (event) => {
      this.debugLog("onTrackUnmute", event);
    });
  }
  emitState() {
    this.onStateChange?.(this.snapshot);
  }
  ensureReadyForMessaging() {
    if (!this.engine || !this.joined) {
      throw new Error(this.i18n.t("errors.rtcNotJoinedForMessaging"));
    }
  }
  bindLocalVideoPlayer(force = false) {
    if (!this.localVideoContainer) {
      return;
    }
    const container = this.getRequiredContainer(this.localVideoContainer, "local");
    if (!force && container.childElementCount > 0) {
      this.bindUploadPreviewLayout(container);
      return;
    }
    container.replaceChildren();
    this.engine?.setLocalVideoMirrorType(MirrorType.MIRROR_TYPE_NONE);
    this.engine?.setLocalVideoPlayer(StreamIndex.STREAM_INDEX_MAIN, {
      renderDom: container,
      renderMode: resolveVideoRenderMode(container, this.renderFit)
    });
    this.bindUploadPreviewLayout(container);
  }
  bindUploadPreviewLayout(container) {
    this.uploadPreviewLayoutObserverStop?.();
    this.uploadPreviewLayoutObserverStop = null;
    applyUploadPreviewMediaLayout(container);
    this.uploadPreviewLayoutObserverStop = observeUploadPreviewMediaLayout(container);
  }
  clearUploadPreviewLayoutObserver() {
    this.uploadPreviewLayoutObserverStop?.();
    this.uploadPreviewLayoutObserverStop = null;
  }
  /** Re-bind local preview after the container becomes visible or is resized. */
  refreshLocalVideoPreview(options) {
    if (!this.engine || !this.localVideoPublished || !this.localVideoContainer) {
      return;
    }
    this.bindLocalVideoPlayer(options?.force);
  }
  getLastObservedSentFrameRate() {
    return this.lastObservedSentFrameRate;
  }
  async switchToExternalVideoSource(track) {
    if (!this.engine) {
      return;
    }
    this.externalVideoTrack = track;
    await this.engine.setVideoSourceType(StreamIndex.STREAM_INDEX_MAIN, VideoSourceType.VIDEO_SOURCE_TYPE_EXTERNAL);
    await this.engine.setExternalVideoTrack(StreamIndex.STREAM_INDEX_MAIN, track);
    this.localVideoSourceType = VideoSourceType.VIDEO_SOURCE_TYPE_EXTERNAL;
  }
  async switchToExternalAudioSource(track) {
    if (!this.engine) {
      return;
    }
    const engine = this.engine;
    if (typeof engine.setAudioSourceType !== "function") {
      this.log("warn", "[Xmax][RTC] setAudioSourceType API is unavailable");
      return;
    }
    if (typeof engine.setExternalAudioTrack !== "function") {
      this.log("warn", "[Xmax][RTC] setExternalAudioTrack API is unavailable");
      return;
    }
    await engine.setAudioSourceType(
      StreamIndex.STREAM_INDEX_MAIN,
      AudioSourceType.AUDIO_SOURCE_TYPE_EXTERNAL
    );
    this.externalAudioTrack = track;
    await engine.setExternalAudioTrack(StreamIndex.STREAM_INDEX_MAIN, track);
    this.log("info", "[Xmax][RTC] external audio track attached", {
      readyState: track.readyState,
      enabled: track.enabled,
      muted: track.muted
    });
  }
  async switchToInternalAudioSource() {
    if (!this.engine) {
      return;
    }
    const engine = this.engine;
    if (typeof engine.setAudioSourceType !== "function") {
      return;
    }
    await engine.setAudioSourceType(
      StreamIndex.STREAM_INDEX_MAIN,
      AudioSourceType.AUDIO_SOURCE_TYPE_INTERNAL
    );
  }
  async switchToInternalVideoSource(shouldSetConfig = true) {
    if (!this.engine) {
      return;
    }
    if (this.localVideoSourceType === VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL) {
      return;
    }
    await this.engine.setVideoSourceType(StreamIndex.STREAM_INDEX_MAIN, VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL);
    this.localVideoSourceType = VideoSourceType.VIDEO_SOURCE_TYPE_INTERNAL;
    if (shouldSetConfig && this.externalVideoTrack) {
      this.externalVideoTrack = null;
    }
  }
  async applyVideoEncoderPreference(size, publishOptions) {
    if (!this.engine) {
      return false;
    }
    const width = size[0];
    const height = size[1];
    const frameRate = publishOptions.fps ?? 24;
    const maxKbps = publishOptions.maxKbps ?? DEFAULT_REALTIME_STREAM_MAX_KBPS;
    const contentHint = publishOptions.contentHint ?? DEFAULT_REALTIME_STREAM_CONTENT_HINT;
    const diagnostics = {
      width,
      height,
      frameRate,
      maxKbps,
      contentHint,
      preferCodecName: VideoCodecType.H264
    };
    try {
      await this.engine.setVideoEncoderConfig({
        width,
        height,
        frameRate,
        maxKbps,
        contentHint,
        preferCodecName: VideoCodecType.H264
      });
      this.log("info", this.i18n.t("rtc.encoderPreferenceSet"), size);
      return true;
    } catch (error) {
      this.log("warn", this.i18n.t("rtc.encoderPreferenceFailed"), error);
      this.log("error", "[Xmax][RTC] setVideoEncoderConfig failed", {
        ...diagnostics,
        error
      });
      return false;
    }
  }
  async attachRemoteVideo(userId, mediaType) {
    if (!this.engine || !this.currentJoinInfo) {
      return;
    }
    const preferredBotUserId = this.currentJoinInfo.botName?.trim() || null;
    const shouldReplaceCurrent = this.remoteVideoUserId === null || userId === preferredBotUserId || this.remoteVideoUserId !== preferredBotUserId;
    if (!shouldReplaceCurrent) {
      return;
    }
    const subscriptionMediaType = this.resolveRemoteSubscriptionMediaType(mediaType);
    this.pendingRemoteVideoUserId = userId;
    this.pendingRemoteVideoMediaType = subscriptionMediaType;
    await this.ensureRemoteStreamSubscribed(userId, subscriptionMediaType);
    if (!this.canRenderRemoteVideo(userId)) {
      this.log("info", this.i18n.t("rtc.remoteWaitSei", { userId }), {
        expectedRemoteSei: this.expectedRemoteSei,
        lastRemoteSei: this.lastRemoteSei,
        lastRemoteSeiUserId: this.lastRemoteSeiUserId
      });
      return;
    }
    const container = this.remoteVideoContainer;
    if (!container) {
      this.log("warn", this.i18n.t("rtc.remoteContainerNotReady"), { userId, mediaType });
      return;
    }
    await this.mountRemoteVideoPlayer(userId, container, subscriptionMediaType);
    this.remoteVideoUserId = userId;
    this.pendingRemoteVideoUserId = null;
    this.emitState();
    this.startRemoteFrameWatch(userId);
    this.emitRemotePlayerMounted();
    this.log("success", this.i18n.t("rtc.remotePlayerBound", { userId }));
  }
  async ensureRemoteStreamSubscribed(userId, mediaType) {
    if (!this.engine) {
      return;
    }
    const sameUserSubscribed = this.subscribedRemoteUserId === userId;
    if (sameUserSubscribed && this.isSubscriptionCovered(this.subscribedRemoteMediaType, mediaType)) {
      return;
    }
    await this.engine.subscribeStream(userId, mediaType);
    this.subscribedRemoteUserId = userId;
    this.subscribedRemoteMediaType = mediaType;
    this.debugLog("ensureRemoteStreamSubscribed", { userId, mediaType });
  }
  bindRemoteVideoPlayerToContainer(userId, container) {
    if (!this.engine) {
      return;
    }
    this.engine.setRemoteVideoPlayer(StreamIndex.STREAM_INDEX_MAIN, {
      userId,
      renderDom: container,
      renderMode: resolveVideoRenderMode(container, this.renderFit)
    });
    this.bindUploadPreviewLayout(container);
  }
  async mountRemoteVideoPlayer(userId, container, mediaType, force = false) {
    if (!this.engine) {
      return;
    }
    if (!force && this.remoteVideoUserId === userId && container === this.remoteVideoContainer && container.childElementCount > 0) {
      this.debugLog("mountRemoteVideoPlayer skipped (already mounted)", { userId });
      return;
    }
    this.debugLog(force ? "mountRemoteVideoPlayer (force)" : "mountRemoteVideoPlayer", {
      userId,
      mediaType,
      childCountBefore: container.childElementCount
    });
    this.stopRemoteFrameWatch();
    container.replaceChildren();
    await this.ensureRemoteStreamSubscribed(userId, mediaType);
    this.bindRemoteVideoPlayerToContainer(userId, container);
  }
  startRemoteFrameWatch(userId) {
    this.stopRemoteFrameWatch();
    let lastFrameAt = 0;
    let hadFirstFrame = false;
    let rvfcHandle = null;
    let watchedVideo = null;
    const onFrame = () => {
      lastFrameAt = Date.now();
      hadFirstFrame = true;
      if (!this.expectedRemoteSei || this.seiSupport === "unsupported") {
        this.clearRemoteFirstOutputWatch();
      }
    };
    const bindRvfc = (video) => {
      if (watchedVideo === video && rvfcHandle !== null) {
        return;
      }
      if (watchedVideo && watchedVideo !== video) {
        watchedVideo.removeEventListener("timeupdate", onFrame);
      }
      watchedVideo = video;
      const rvfcVideo = video;
      if (rvfcVideo.requestVideoFrameCallback) {
        const schedule = () => {
          if (this.remoteVideoUserId !== userId) {
            return;
          }
          rvfcHandle = rvfcVideo.requestVideoFrameCallback(() => {
            onFrame();
            schedule();
          });
        };
        schedule();
        return;
      }
      video.addEventListener("timeupdate", onFrame);
    };
    const pollTimer = setInterval(() => {
      if (this.remoteVideoUserId !== userId || !this.remoteVideoContainer) {
        return;
      }
      const video = this.remoteVideoContainer.querySelector("video");
      if (video) {
        bindRvfc(video);
      }
      if (!hadFirstFrame || lastFrameAt === 0) {
        return;
      }
      const stallMs = Date.now() - lastFrameAt;
      if (stallMs < REMOTE_OUTPUT_STALL_MS) {
        return;
      }
      if (Date.now() < this.remoteOutputRecoveryCooldownUntil) {
        return;
      }
      this.remoteOutputRecoveryCooldownUntil = Date.now() + REMOTE_OUTPUT_RECOVERY_COOLDOWN_MS;
      this.debugLog("remote output stalled", { userId, stallMs });
      this.log("warn", this.i18n.t("rtc.remoteOutputStalled"), { userId, stallMs });
      this.onRemoteOutputStalled?.({ userId, stallMs });
      hadFirstFrame = false;
      lastFrameAt = 0;
    }, 3e3);
    this.remoteFrameWatchStop = () => {
      clearInterval(pollTimer);
      if (watchedVideo) {
        watchedVideo.removeEventListener("timeupdate", onFrame);
      }
      if (rvfcHandle !== null && watchedVideo) {
        const rvfcVideo = watchedVideo;
        rvfcVideo.cancelVideoFrameCallback?.(rvfcHandle);
      }
      rvfcHandle = null;
      watchedVideo = null;
    };
  }
  stopRemoteFrameWatch() {
    this.remoteFrameWatchStop?.();
    this.remoteFrameWatchStop = null;
  }
  isRemoteSeiUser(userId) {
    const localUserId = this.currentJoinInfo?.userId?.trim();
    if (localUserId && userId === localUserId) {
      return false;
    }
    const botUserId = this.currentJoinInfo?.botName?.trim();
    if (botUserId) {
      return userId === botUserId;
    }
    return true;
  }
  /** Always mount remote player — SEI gate only affects display matching, not subscription. */
  canRenderRemoteVideo(_userId) {
    return true;
  }
  /** Whether remote SEI matches the active task (display gate). */
  isSeiMatched() {
    if (this.seiSupport === "unsupported") {
      return true;
    }
    if (!this.expectedRemoteSei) {
      return true;
    }
    return this.lastRemoteSei === this.expectedRemoteSei;
  }
  /** Detect whether the browser can send and receive H.264 SEI messages. */
  ensureSeiSupport() {
    if (this.seiSupport !== "unknown") {
      return;
    }
    void VERTC.getSupportedCodecs().then((codecs) => {
      const supported = codecs.some((c) => c.toLowerCase() === "h264" || c.toLowerCase() === "h.264");
      this.seiSupport = supported ? "supported" : "unsupported";
      if (this.seiSupport === "unsupported" && !this.hasLoggedSeiUnsupported) {
        this.hasLoggedSeiUnsupported = true;
        this.log("warn", this.i18n.t("rtc.seiUnsupported"), codecs);
      }
      if (this.seiSupport === "unsupported") {
        this.expectedRemoteSei = null;
        this.emitSeiGateState();
        void this.refreshRemoteVideoBinding();
      } else if (this.seiSender.configured) {
        this.seiSender.start();
        this.emitSeiGateState();
        void this.refreshRemoteVideoBinding();
      }
    }).catch((error) => {
      this.seiSupport = "unsupported";
      if (!this.hasLoggedSeiUnsupported) {
        this.hasLoggedSeiUnsupported = true;
        this.log("warn", this.i18n.t("rtc.getCodecsFailed"), error);
      }
      this.expectedRemoteSei = null;
      this.emitSeiGateState();
      void this.refreshRemoteVideoBinding();
    });
  }
  supportsVideo(mediaType) {
    return mediaType === MediaType.VIDEO || mediaType === MediaType.AUDIO_AND_VIDEO;
  }
  supportsAudio(mediaType) {
    return mediaType === MediaType.AUDIO || mediaType === MediaType.AUDIO_AND_VIDEO;
  }
  resolveRemoteSubscriptionMediaType(publishedMediaType) {
    if (this.playRemoteAudio || !this.supportsAudio(publishedMediaType)) {
      return publishedMediaType;
    }
    return MediaType.VIDEO;
  }
  isSubscriptionCovered(current, requested) {
    const currentHasVideo = this.supportsVideo(current);
    const currentHasAudio = this.supportsAudio(current);
    const requestedHasVideo = this.supportsVideo(requested);
    const requestedHasAudio = this.supportsAudio(requested);
    return (!requestedHasVideo || currentHasVideo) && (!requestedHasAudio || currentHasAudio);
  }
  clearVideoContainers() {
    this.stopRemoteFrameWatch();
    this.clearContainer(this.localVideoContainer);
    this.clearContainer(this.remoteVideoContainer);
  }
  clearContainer(container) {
    container?.replaceChildren();
  }
  getRequiredContainer(container, containerType) {
    if (!container) {
      throw new Error(`missing ${containerType} video container`);
    }
    return container;
  }
  emitRemotePlayerMounted() {
    this.onRemotePlayerMounted?.();
  }
  parseRoomEventPayload(payload) {
    const getMessageText = (input) => {
      if (typeof input === "string") {
        return input.trim() || null;
      }
      if (!input || typeof input !== "object") {
        return null;
      }
      const obj = input;
      const direct = obj.message ?? obj.msg ?? obj.data ?? obj.payload;
      if (typeof direct === "string") {
        return direct.trim() || null;
      }
      return null;
    };
    const text = getMessageText(payload);
    if (!text) {
      return null;
    }
    try {
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object") {
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }
  log(level, message, data) {
    this.onLog?.({ level, message, data });
  }
  logTiming(stage, startedAt, data) {
    {
      return;
    }
  }
  /** RTC stream stats are emitted about every two seconds, so this does not log per frame. */
  logVideoFrameDiagnostics(direction, width, height, frameRate, userId, details) {
    const label = direction === "send" ? "Send" : "Receive";
    const resolution = width > 0 && height > 0 ? `${width}x${height}` : "unknown";
    const fps = Number(frameRate.toFixed(2));
    this.log("info", `[Xmax][RTC] ${label} video: ${resolution} @ ${fps} fps`, {
      direction,
      width,
      height,
      frameRate: fps,
      ...userId ? { userId } : {},
      ...details
    });
  }
  logLocalStreamStats(stats) {
    if (!this.localVideoPublished) {
      return;
    }
    this.localStreamStatsCount += 1;
    const nowMs = performance.now();
    const sentFrameRate = stats.videoStats?.sentFrameRate ?? 0;
    if (sentFrameRate > 0 && this.firstNonZeroSentFrameRateAtMs === 0) {
      this.firstNonZeroSentFrameRateAtMs = nowMs;
    }
    this.lastObservedSentFrameRate = sentFrameRate;
    this.evaluateLocalOutboundWatch(sentFrameRate, nowMs);
  }
  evaluateLocalOutboundWatch(sentFrameRate, nowMs) {
    const state = this.localOutboundWatch;
    if (!state || state.triggered) {
      return;
    }
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      state.consecutiveZeroStats = 0;
      return;
    }
    if (sentFrameRate > 0) {
      state.consecutiveZeroStats = 0;
      state.lastPositiveAtMs = nowMs;
      return;
    }
    if (nowMs < state.graceUntilMs) {
      state.consecutiveZeroStats = 0;
      return;
    }
    state.consecutiveZeroStats += 1;
    const stallMs = nowMs - state.lastPositiveAtMs;
    if (state.consecutiveZeroStats >= state.minZeroSamples && stallMs >= state.minStallMs) {
      this.triggerLocalOutboundStall("zero-sent-frame-rate");
    }
  }
  triggerLocalOutboundStall(reason) {
    const state = this.localOutboundWatch;
    if (!state || state.triggered) {
      return;
    }
    state.triggered = true;
    const nowMs = performance.now();
    const info = {
      reason,
      consecutiveZeroStats: state.consecutiveZeroStats,
      stallMs: Math.max(0, Math.round(nowMs - state.lastPositiveAtMs)),
      lastSentFrameRate: this.lastObservedSentFrameRate
    };
    this.debugLog("local outbound stalled", info);
    state.onStalled(info);
  }
  debugLog(message, data) {
    if (!this.debug) {
      return;
    }
    this.log("info", `[debug] ${message}`, data);
  }
};
_RtcManager.SEI_GATE_FALLBACK_MS = 6e3;
_RtcManager.SEI_MATCHED_DISPLAY_DELAY_MS = 200;
var RtcManager = _RtcManager;

// src/rtc/media/image-file-stream.ts
function loadImageElement(url, crossOrigin) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    if (crossOrigin) {
      image.crossOrigin = "anonymous";
    }
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("failed to load image"));
    image.src = url;
  });
}
async function createImageFileStream(fileOrUrl, options = {}) {
  const i18n = options.i18n ?? createSDKI18n();
  const isUrl = typeof fileOrUrl === "string";
  const url = isUrl ? fileOrUrl : URL.createObjectURL(fileOrUrl);
  let imageEl;
  try {
    imageEl = await loadImageElement(url, isUrl);
  } catch {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.imageLoadFailed"));
  }
  const sourceWidth = imageEl.naturalWidth || imageEl.width || 0;
  const sourceHeight = imageEl.naturalHeight || imageEl.height || 0;
  if (!sourceWidth || !sourceHeight) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.imageTrackMissing"));
  }
  const [outputWidth, outputHeight] = options.targetSize ?? resolveUploadVideoSize(sourceWidth, sourceHeight);
  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.captureStreamUnsupported"));
  }
  const fps = resolveRtcPublishFps({ mobile: options.mobile, fps: options.fps });
  const frameIntervalMs = Math.max(1, Math.round(1e3 / fps));
  const captureStreamFn = canvas.captureStream ?? canvas.mozCaptureStream;
  if (!captureStreamFn) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.captureStreamUnsupported"));
  }
  const previewStream = captureStreamFn.call(canvas, fps);
  const videoTrack = previewStream.getVideoTracks()[0];
  if (!videoTrack) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.imageTrackMissing"));
  }
  let intervalId = null;
  let destroyed = false;
  const drawFrame = () => {
    if (destroyed) {
      return;
    }
    drawSourceCover(
      ctx,
      imageEl,
      outputWidth,
      outputHeight,
      sourceWidth,
      sourceHeight,
      options.backgroundColor
    );
  };
  drawFrame();
  const posterUrl = await createCanvasPosterUrl(canvas, options.poster);
  intervalId = setInterval(drawFrame, frameIntervalMs);
  const videoEl = document.createElement("video");
  videoEl.muted = true;
  videoEl.playsInline = true;
  const destroy = () => {
    destroyed = true;
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
    try {
      videoTrack.stop();
    } catch {
    }
    try {
      previewStream.getTracks().forEach((track) => {
        if (track.readyState !== "ended") {
          track.stop();
        }
      });
    } catch {
    }
    try {
      imageEl.src = "";
    } catch {
    }
    try {
      videoEl.remove();
    } catch {
    }
    if (posterUrl) {
      URL.revokeObjectURL(posterUrl);
    }
    if (!isUrl) URL.revokeObjectURL(url);
  };
  return {
    url,
    ...posterUrl ? { posterUrl } : {},
    previewStream,
    videoEl,
    videoTrack,
    fps,
    width: outputWidth,
    height: outputHeight,
    sourceWidth,
    sourceHeight,
    destroy
  };
}

// src/rtc/media/heic-image.ts
var HEIC_EXTENSION_RE = /\.(?:heic|heif)$/i;
var HEIC_MIME_TYPES = /* @__PURE__ */ new Set([
  "image/heic",
  "image/heif",
  "image/heic-sequence",
  "image/heif-sequence"
]);
var HEIF_BRANDS = /* @__PURE__ */ new Set([
  "heic",
  "heix",
  "hevc",
  "hevx",
  "heim",
  "heis",
  "hevm",
  "hevs",
  "mif1",
  "msf1"
]);
function readAscii(bytes, offset, length) {
  let value = "";
  for (let index = offset; index < offset + length && index < bytes.length; index += 1) {
    value += String.fromCharCode(bytes[index]);
  }
  return value;
}
async function hasHeifFileSignature(file) {
  const bytes = new Uint8Array(await file.slice(0, 64).arrayBuffer());
  if (bytes.length < 12 || readAscii(bytes, 4, 4) !== "ftyp") {
    return false;
  }
  const brands = [];
  for (let offset = 8; offset + 4 <= bytes.length; offset += 4) {
    brands.push(readAscii(bytes, offset, 4).toLowerCase());
  }
  if (brands.includes("avif") || brands.includes("avis")) {
    return false;
  }
  return brands.some((brand) => HEIF_BRANDS.has(brand));
}
async function isHeicImageFile(file) {
  const mime = file.type.toLowerCase();
  if (HEIC_EXTENSION_RE.test(file.name) || HEIC_MIME_TYPES.has(mime)) {
    return true;
  }
  return hasHeifFileSignature(file);
}
async function normalizeHeicImageFile(file, options = {}) {
  if (!await isHeicImageFile(file)) {
    return file;
  }
  const { heicTo, isHeic } = await import('heic-to/csp');
  if (!await isHeic(file)) {
    throw new Error("The selected file is not a valid HEIC/HEIF image");
  }
  const blob = await heicTo({
    blob: file,
    type: "image/jpeg",
    quality: options.quality ?? 0.9
  });
  const baseName = file.name.replace(/\.(?:heic|heif)$/i, "") || "image";
  return new File([blob], `${baseName}.jpg`, {
    type: "image/jpeg",
    lastModified: file.lastModified
  });
}

// src/rtc/media/media-file-stream.ts
function isImageMediaFile(file) {
  if (typeof file === "string") {
    return /\.(png|jpe?g|webp|gif|bmp|heic|heif)$/i.test(file.split("?")[0]);
  }
  if (file.type.startsWith("image/")) {
    return true;
  }
  const name = "name" in file && typeof file.name === "string" ? file.name.toLowerCase() : "";
  return /\.(png|jpe?g|webp|gif|bmp|heic|heif)$/.test(name);
}
function isVideoMediaFile(file) {
  if (typeof file === "string") {
    return /\.(mp4|mov|webm|m4v|avi|mkv)$/i.test(file.split("?")[0]);
  }
  if (file.type.startsWith("video/")) {
    return true;
  }
  const name = "name" in file && typeof file.name === "string" ? file.name.toLowerCase() : "";
  return /\.(mp4|mov|webm|m4v|avi|mkv)$/.test(name);
}
async function createMediaFileStream(fileOrUrl, options = {}) {
  const normalizedFileOrUrl = typeof fileOrUrl === "string" ? fileOrUrl : typeof File !== "undefined" && fileOrUrl instanceof File ? await normalizeHeicImageFile(fileOrUrl) : fileOrUrl;
  if (isImageMediaFile(normalizedFileOrUrl)) {
    return createImageFileStream(normalizedFileOrUrl, options);
  }
  if (isVideoMediaFile(normalizedFileOrUrl)) {
    const { createVideoFileStream: createVideoFileStream2 } = await import('./video-file-stream-VU5HCKJ3.js');
    return createVideoFileStream2(normalizedFileOrUrl, options);
  }
  const i18n = options.i18n ?? createSDKI18n();
  const typeStr = typeof normalizedFileOrUrl === "string" ? "url" : normalizedFileOrUrl.type || "unknown";
  throw new Error(i18n.t("errors.invalidMediaFileType", { type: typeStr }));
}

// src/rtc/media/camera-errors.ts
var CAMERA_ACCESS_ERROR_NAMES = /* @__PURE__ */ new Set([
  "NotFoundError",
  "NotAllowedError",
  "PermissionDeniedError",
  "NotReadableError",
  "OverconstrainedError",
  "ConstraintNotSatisfiedError",
  "AbortError",
  "SecurityError"
]);
function getCameraEnvironmentIssue() {
  if (typeof window === "undefined") {
    return "api-unavailable";
  }
  if (!window.isSecureContext) {
    return "insecure-context";
  }
  if (typeof navigator?.mediaDevices !== "object") {
    return "api-unavailable";
  }
  return null;
}
function isCameraAccessError(error) {
  return classifyCameraAccessError(error) !== null;
}
function classifyCameraAccessError(error) {
  if (error instanceof DOMException) {
    switch (error.name) {
      case "NotFoundError":
        return "not-found";
      case "NotAllowedError":
        return "not-allowed";
      case "PermissionDeniedError":
        return "permission-denied";
      case "NotReadableError":
        return "in-use";
      case "OverconstrainedError":
      case "ConstraintNotSatisfiedError":
        return "overconstrained";
      case "TypeError":
      case "AbortError":
      case "SecurityError":
        return "generic";
      default:
        return CAMERA_ACCESS_ERROR_NAMES.has(error.name) ? "generic" : null;
    }
  }
  if (error instanceof Error) {
    if (error.message.includes("Camera is not supported")) {
      return "unsupported";
    }
    if (error.message.includes("captureStream is not supported")) {
      return "capture-unsupported";
    }
    if (error.message.includes("No active video track")) {
      return "in-use";
    }
  }
  return null;
}

// src/files/ref-image.ts
async function resolveRefImageUrl(client, input) {
  if (input instanceof File) {
    return (await client.uploadImage(input)).url;
  }
  const raw = input.trim();
  if (!raw) {
    return "";
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  const res = await fetch(raw);
  if (!res.ok) {
    throw new Error(`Failed to load ref image: ${res.status}`);
  }
  const blob = await res.blob();
  const mime = blob.type || "image/png";
  const ext = mime === "image/jpeg" ? "jpg" : mime === "image/webp" ? "webp" : mime === "image/gif" ? "gif" : "png";
  const file = new File([blob], `ref.${ext}`, { type: mime });
  return (await client.uploadImage(file)).url;
}

// src/files/download.ts
async function prefetchRemoteFile(url) {
  return Boolean(url.trim());
}
function isRemoteFilePrefetched(url) {
  return Boolean(url.trim());
}
function clearPrefetchedRemoteFile(_url) {
}
async function downloadRemoteFile(url, options = {}) {
  const trimmed = url.trim();
  if (!trimmed || typeof document === "undefined") {
    return false;
  }
  const anchor = document.createElement("a");
  anchor.href = trimmed;
  anchor.rel = "noopener";
  const filename = options.filename?.trim();
  if (filename) {
    anchor.download = filename;
  }
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  return true;
}

// src/files/client.ts
function createFileClient(client) {
  return {
    uploadImage: (file) => client.uploadImage(file),
    uploadVideo: (file) => client.uploadVideo(file),
    upload: (file) => client.uploadImage(file),
    uploadAndCheckImage: (file) => client.uploadAndCheckImage(file)
  };
}

// src/rtc/media/camera-frame-readiness.ts
var SAMPLE_SIZE = 16;
var DEFAULT_CONSECUTIVE_FRAMES = 2;
var DEFAULT_TIMEOUT_MS = 1e3;
var MIN_AVERAGE_LUMINANCE = 5;
var MIN_LUMINANCE_DEVIATION = 3;
var VISIBLE_PIXEL_LUMINANCE = 12;
var MIN_VISIBLE_PIXEL_RATIO = 0.02;
function isCameraFrameVisuallyReady(pixels) {
  const pixelCount = Math.floor(pixels.length / 4);
  if (pixelCount === 0) {
    return false;
  }
  let luminanceSum = 0;
  let luminanceSquareSum = 0;
  let visiblePixels = 0;
  for (let offset = 0; offset < pixelCount * 4; offset += 4) {
    const luminance = pixels[offset] * 0.2126 + pixels[offset + 1] * 0.7152 + pixels[offset + 2] * 0.0722;
    luminanceSum += luminance;
    luminanceSquareSum += luminance * luminance;
    if (luminance > VISIBLE_PIXEL_LUMINANCE) {
      visiblePixels += 1;
    }
  }
  const averageLuminance = luminanceSum / pixelCount;
  const variance = Math.max(
    0,
    luminanceSquareSum / pixelCount - averageLuminance * averageLuminance
  );
  const luminanceDeviation = Math.sqrt(variance);
  const visiblePixelRatio = visiblePixels / pixelCount;
  return averageLuminance > MIN_AVERAGE_LUMINANCE || luminanceDeviation > MIN_LUMINANCE_DEVIATION || visiblePixelRatio > MIN_VISIBLE_PIXEL_RATIO;
}
async function waitForCameraTrackReady(track, options = {}) {
  const requiredFrames = Math.max(
    1,
    Math.floor(options.consecutiveFrames ?? DEFAULT_CONSECUTIVE_FRAMES)
  );
  const timeoutMs = Math.max(0, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const startedAt = performance.now();
  if (track.readyState === "ended") {
    return {
      ready: false,
      checkedFrames: 0,
      consecutiveReadyFrames: 0,
      elapsedMs: 0,
      reason: "track-ended"
    };
  }
  return new Promise((resolve) => {
    const video = document.createElement("video");
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { willReadFrequently: true });
    let checkedFrames = 0;
    let consecutiveReadyFrames = 0;
    let settled = false;
    let frameCallbackHandle = null;
    let animationFrameHandle = null;
    let lastFallbackMediaTime = -1;
    canvas.width = SAMPLE_SIZE;
    canvas.height = SAMPLE_SIZE;
    video.muted = true;
    video.playsInline = true;
    video.autoplay = true;
    video.srcObject = new MediaStream([track]);
    video.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;opacity:0;pointer-events:none;";
    document.body.appendChild(video);
    const finish = (ready, reason) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeoutHandle);
      if (frameCallbackHandle !== null) {
        video.cancelVideoFrameCallback?.(frameCallbackHandle);
      }
      if (animationFrameHandle !== null) {
        window.cancelAnimationFrame(animationFrameHandle);
      }
      video.pause();
      video.srcObject = null;
      video.remove();
      resolve({
        ready,
        checkedFrames,
        consecutiveReadyFrames,
        elapsedMs: Number((performance.now() - startedAt).toFixed(1)),
        reason
      });
    };
    const inspectFrame = () => {
      if (!context || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        return;
      }
      try {
        context.drawImage(video, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE);
        const pixels = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE).data;
        checkedFrames += 1;
        consecutiveReadyFrames = isCameraFrameVisuallyReady(pixels) ? consecutiveReadyFrames + 1 : 0;
        if (consecutiveReadyFrames >= requiredFrames) {
          finish(true, "visible-frame");
        }
      } catch {
      }
    };
    const scheduleFrameCheck = () => {
      if (settled) {
        return;
      }
      if (video.requestVideoFrameCallback) {
        frameCallbackHandle = video.requestVideoFrameCallback((_now, metadata) => {
          lastFallbackMediaTime = metadata.mediaTime;
          inspectFrame();
          scheduleFrameCheck();
        });
        return;
      }
      animationFrameHandle = window.requestAnimationFrame(() => {
        if (video.currentTime !== lastFallbackMediaTime) {
          lastFallbackMediaTime = video.currentTime;
          inspectFrame();
        }
        scheduleFrameCheck();
      });
    };
    const timeoutHandle = window.setTimeout(
      () => finish(false, "timeout"),
      timeoutMs
    );
    void video.play().then(scheduleFrameCheck).catch(() => finish(false, "play-failed"));
  });
}

// src/drag/map-viewport.ts
function clamp(n, min, max) {
  return Math.min(Math.max(n, min), max);
}
function getFitContentRect(rect, targetSize, fitMode = "contain") {
  const [targetWidth, targetHeight] = targetSize;
  if (!targetWidth || !targetHeight || !rect.width || !rect.height) {
    return {
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height
    };
  }
  const scale = fitMode === "cover" ? Math.max(rect.width / targetWidth, rect.height / targetHeight) : Math.min(rect.width / targetWidth, rect.height / targetHeight);
  const width = targetWidth * scale;
  const height = targetHeight * scale;
  return {
    left: rect.left + (rect.width - width) / 2,
    top: rect.top + (rect.height - height) / 2,
    width,
    height
  };
}
function findDragMediaElement(dragSurface) {
  const root = dragSurface.parentElement ?? dragSurface;
  if (typeof root.querySelector !== "function") {
    return null;
  }
  const videoHost = root.querySelector("[data-xmax-remote-video]") ?? root;
  if (typeof videoHost.querySelector !== "function") {
    return null;
  }
  const media = videoHost.querySelector("video, canvas");
  return media ?? null;
}
function toContentRect(rect) {
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height
  };
}
function isMediaInsetInContainer(mediaRect, containerRect) {
  if (!mediaRect.width || !mediaRect.height || !containerRect.width || !containerRect.height) {
    return false;
  }
  const widthRatio = mediaRect.width / containerRect.width;
  const heightRatio = mediaRect.height / containerRect.height;
  return widthRatio < 0.98 || heightRatio < 0.98;
}
function resolveMappingContext(dragSurface, targetSize, fitMode = "cover") {
  const containerRect = dragSurface.getBoundingClientRect();
  const media = findDragMediaElement(dragSurface);
  if (media) {
    const mediaRect = media.getBoundingClientRect();
    if (mediaRect.width > 0 && mediaRect.height > 0 && isMediaInsetInContainer(mediaRect, containerRect)) {
      const content2 = toContentRect(mediaRect);
      return { content: content2, hitRect: content2, source: "media" };
    }
  }
  const content = getFitContentRect(containerRect, targetSize, fitMode);
  return {
    content,
    hitRect: toContentRect(containerRect),
    source: "fit"
  };
}
function mapViewportPointToCoordinateSpace(e, container, targetSize, options = {}) {
  const fitMode = options.fitMode ?? "cover";
  const mirrored = options.mirrored ?? false;
  const [targetWidth, targetHeight] = targetSize;
  if (!targetWidth || !targetHeight) {
    return null;
  }
  const { content, hitRect } = resolveMappingContext(container, targetSize, fitMode);
  if (!content.width || !content.height) {
    return null;
  }
  if (e.clientX < hitRect.left || e.clientY < hitRect.top || e.clientX > hitRect.left + hitRect.width || e.clientY > hitRect.top + hitRect.height) {
    return null;
  }
  const x = Math.round((e.clientX - content.left) * targetWidth / content.width);
  const y = Math.round((e.clientY - content.top) * targetHeight / content.height);
  const normalizedX = mirrored ? targetWidth - 1 - x : x;
  return [
    clamp(normalizedX, 0, targetWidth - 1),
    clamp(y, 0, targetHeight - 1)
  ];
}
function mapTargetPointToCanvas(point, container, targetSize, dpr, options = {}) {
  const fitMode = options.fitMode ?? "cover";
  const mirrored = options.mirrored ?? false;
  const containerRect = container.getBoundingClientRect();
  const [targetWidth, targetHeight] = targetSize;
  const { content } = resolveMappingContext(container, targetSize, fitMode);
  if (!targetWidth || !targetHeight || !content.width || !content.height) {
    return null;
  }
  const displayX = mirrored ? targetWidth - 1 - point[0] : point[0];
  const originX = (content.left - containerRect.left) * dpr;
  const originY = (content.top - containerRect.top) * dpr;
  const contentW = content.width * dpr;
  const contentH = content.height * dpr;
  return [
    originX + displayX / targetWidth * contentW,
    originY + point[1] / targetHeight * contentH
  ];
}

// src/drag/drag-track-controller.ts
var TRAIL_FADE_ALPHA = 0.05;
var TRAIL_IDLE_FADE_FRAMES = 64;
var TRAIL_COLOR = { r: 0, g: 255, b: 100 };
var TRAIL_CORE_COLOR = { r: 255, g: 255, b: 255 };
var TRAIL_VISUAL = {
  outerWidth: 18,
  outerBlur: 12,
  outerAlpha: 0.35,
  middleWidth: 10,
  middleBlur: 6,
  middleAlpha: 0.75,
  coreWidth: 3,
  headRadius: 5,
  headGlowRadius: 14,
  headGlowAlpha: 0.9,
  ringCount: 2,
  ringStartRadius: 10,
  ringSpacing: 14,
  ringLineWidth: 2,
  ringPulseSpeed: 1.2,
  ringMaxAlpha: 0.6,
  particleCount: 4,
  particleRadius: 3,
  particleOrbitRadius: 22,
  particleSpeed: 0.06,
  particleAlpha: 0.6
};
function trailRgba(alpha) {
  return `rgba(${TRAIL_COLOR.r},${TRAIL_COLOR.g},${TRAIL_COLOR.b},${alpha})`;
}
function coreRgba(alpha) {
  return `rgba(${TRAIL_CORE_COLOR.r},${TRAIL_CORE_COLOR.g},${TRAIL_CORE_COLOR.b},${alpha})`;
}
function fadeTrailCanvas(ctx) {
  ctx.save();
  ctx.globalCompositeOperation = "destination-out";
  ctx.fillStyle = `rgba(0,0,0,${TRAIL_FADE_ALPHA})`;
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.restore();
}
function drawTrailSegments(ctx, segs, container, targetSize, dpr, fitMode, mirrored, fastMode) {
  if (segs.length === 0) {
    return;
  }
  const strokeSegs = (opts) => {
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = opts.width * dpr;
    ctx.strokeStyle = opts.color === "core" ? coreRgba(opts.alpha) : trailRgba(opts.alpha);
    ctx.shadowBlur = fastMode ? 0 : opts.shadowBlur * dpr;
    ctx.shadowColor = fastMode || opts.color === "core" ? "transparent" : trailRgba(opts.alpha);
    ctx.beginPath();
    for (const seg of segs) {
      const start = mapTargetPointToCanvas(seg.a, container, targetSize, dpr, { fitMode, mirrored });
      const end = mapTargetPointToCanvas(seg.b, container, targetSize, dpr, { fitMode, mirrored });
      if (!start || !end) {
        continue;
      }
      ctx.moveTo(start[0], start[1]);
      ctx.lineTo(end[0], end[1]);
    }
    ctx.stroke();
    ctx.restore();
  };
  strokeSegs({
    width: TRAIL_VISUAL.outerWidth,
    shadowBlur: TRAIL_VISUAL.outerBlur,
    alpha: TRAIL_VISUAL.outerAlpha,
    color: "trail"
  });
  strokeSegs({
    width: TRAIL_VISUAL.middleWidth,
    shadowBlur: TRAIL_VISUAL.middleBlur,
    alpha: TRAIL_VISUAL.middleAlpha,
    color: "trail"
  });
  strokeSegs({
    width: TRAIL_VISUAL.coreWidth,
    shadowBlur: 0,
    alpha: 1,
    color: "core"
  });
}
function drawHeadGlow(ctx, x, y, dpr) {
  const glowRadius = TRAIL_VISUAL.headGlowRadius * dpr;
  const headRadius = TRAIL_VISUAL.headRadius * dpr;
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, glowRadius);
  gradient.addColorStop(0, trailRgba(TRAIL_VISUAL.headGlowAlpha));
  gradient.addColorStop(0.4, trailRgba(TRAIL_VISUAL.headGlowAlpha * 0.6));
  gradient.addColorStop(1, trailRgba(0));
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(x, y, glowRadius, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = coreRgba(1);
  ctx.beginPath();
  ctx.arc(x, y, headRadius, 0, Math.PI * 2);
  ctx.fill();
}
function drawPulsingRings(ctx, x, y, dpr, startTime, now) {
  const elapsed = (now - startTime) / 1e3;
  ctx.lineWidth = TRAIL_VISUAL.ringLineWidth * dpr;
  for (let index = 0; index < TRAIL_VISUAL.ringCount; index += 1) {
    const baseRadius = (TRAIL_VISUAL.ringStartRadius + index * TRAIL_VISUAL.ringSpacing) * dpr;
    const pulseOffset = elapsed * TRAIL_VISUAL.ringPulseSpeed + index * 0.5;
    const pulse = (Math.sin(pulseOffset * Math.PI * 2) + 1) / 2;
    const radius = baseRadius + pulse * 6 * dpr;
    const alpha = TRAIL_VISUAL.ringMaxAlpha * (1 - index * 0.2) * (0.5 + pulse * 0.5);
    ctx.strokeStyle = trailRgba(alpha);
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.stroke();
  }
}
function drawOrbitParticles(ctx, x, y, dpr, startTime, now) {
  const elapsed = (now - startTime) / 1e3;
  const particleRadius = TRAIL_VISUAL.particleRadius * dpr;
  for (let index = 0; index < TRAIL_VISUAL.particleCount; index += 1) {
    const baseAngle = index / TRAIL_VISUAL.particleCount * Math.PI * 2;
    const direction = index % 2 === 0 ? 1 : -1;
    const angle = baseAngle + elapsed * TRAIL_VISUAL.particleSpeed * direction;
    const orbitRadius = TRAIL_VISUAL.particleOrbitRadius * dpr;
    const particleX = x + Math.cos(angle) * orbitRadius;
    const particleY = y + Math.sin(angle) * orbitRadius;
    const alpha = TRAIL_VISUAL.particleAlpha * (0.6 + Math.sin(elapsed * 3 + index) * 0.4);
    const gradient = ctx.createRadialGradient(
      particleX,
      particleY,
      0,
      particleX,
      particleY,
      particleRadius * 2
    );
    gradient.addColorStop(0, trailRgba(alpha));
    gradient.addColorStop(1, trailRgba(0));
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(particleX, particleY, particleRadius * 2, 0, Math.PI * 2);
    ctx.fill();
  }
}
function clearCanvas(ctx) {
  if (!ctx) {
    return;
  }
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  ctx.restore();
}
var DragTrackController = class {
  constructor(container, options) {
    this.strokeActive = false;
    this.hasTrailPixels = false;
    this.idleFadeFrames = 0;
    this.activePointers = /* @__PURE__ */ new Map();
    this.lastTargetPoints = /* @__PURE__ */ new Map();
    this.segQueue = [];
    this.sampleTimer = null;
    this.sampleInFlight = false;
    this.rafId = null;
    this.resizeObserver = null;
    this.container = container;
    this.onTracks = options.onTracks;
    this.onStrokeStart = options.onStrokeStart;
    this.onStrokeEnd = options.onStrokeEnd;
    this.targetSize = options.targetSize;
    this.fitMode = options.fitMode ?? "cover";
    this.mirrored = options.mirrored ?? false;
    this.enabled = options.enabled ?? true;
    this.trailCanvas = document.createElement("canvas");
    this.trailCanvas.className = "Xmax-drag-track-canvas";
    this.trailCanvas.style.cssText = "position:absolute;inset:0;z-index:21;width:100%;height:100%;pointer-events:none;";
    container.appendChild(this.trailCanvas);
    this.fxCanvas = document.createElement("canvas");
    this.fxCanvas.className = "Xmax-drag-track-fx-canvas";
    this.fxCanvas.style.cssText = "position:absolute;inset:0;z-index:22;width:100%;height:100%;pointer-events:none;";
    container.appendChild(this.fxCanvas);
    this.onWindowResize = () => this.resizeCanvas();
    this.onPointerDown = (e) => this.handlePointerDown(e);
    this.onPointerMove = (e) => this.handlePointerMove(e);
    this.onPointerUp = (e) => this.handlePointerUp(e);
    this.onPointerCancel = (e) => this.handlePointerCancel(e);
    this.resizeCanvas();
    this.bindResizeObserver();
    this.bindPointerEvents();
    this.applyInteractionStyle();
  }
  setEnabled(enabled) {
    this.enabled = enabled;
    this.applyInteractionStyle();
    if (!enabled) {
      this.finishStroke();
    }
  }
  setTargetSize(targetSize) {
    this.targetSize = targetSize;
  }
  setFitMode(fitMode) {
    this.fitMode = fitMode;
  }
  setMirrored(mirrored) {
    this.mirrored = mirrored;
  }
  destroy() {
    this.finishStroke();
    this.unbindPointerEvents();
    this.unbindResizeObserver();
    this.trailCanvas.remove();
    this.fxCanvas.remove();
  }
  applyInteractionStyle() {
    this.container.style.pointerEvents = this.enabled ? "auto" : "none";
    this.container.style.touchAction = this.enabled ? "none" : "auto";
  }
  bindResizeObserver() {
    const ResizeObserverCtor = globalThis.ResizeObserver;
    if (ResizeObserverCtor) {
      this.resizeObserver = new ResizeObserverCtor(() => this.resizeCanvas());
      this.resizeObserver.observe(this.container);
      return;
    }
    window.addEventListener("resize", this.onWindowResize);
  }
  unbindResizeObserver() {
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    window.removeEventListener("resize", this.onWindowResize);
  }
  bindPointerEvents() {
    this.container.addEventListener("pointerdown", this.onPointerDown);
    this.container.addEventListener("pointermove", this.onPointerMove);
    this.container.addEventListener("pointerup", this.onPointerUp);
    this.container.addEventListener("pointercancel", this.onPointerCancel);
  }
  unbindPointerEvents() {
    this.container.removeEventListener("pointerdown", this.onPointerDown);
    this.container.removeEventListener("pointermove", this.onPointerMove);
    this.container.removeEventListener("pointerup", this.onPointerUp);
    this.container.removeEventListener("pointercancel", this.onPointerCancel);
    this.activePointers.clear();
    this.lastTargetPoints.clear();
    this.sampleInFlight = false;
  }
  clearVisuals() {
    clearCanvas(this.trailCanvas.getContext("2d"));
    clearCanvas(this.fxCanvas.getContext("2d"));
    this.hasTrailPixels = false;
    this.idleFadeFrames = 0;
  }
  resizeCanvas() {
    const rect = this.container.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const cssW = Math.max(1, Math.round(rect.width));
    const cssH = Math.max(1, Math.round(rect.height));
    const nextW = Math.max(1, Math.round(cssW * dpr));
    const nextH = Math.max(1, Math.round(cssH * dpr));
    let resized = false;
    for (const canvas of [this.trailCanvas, this.fxCanvas]) {
      if (canvas.width !== nextW || canvas.height !== nextH) {
        canvas.width = nextW;
        canvas.height = nextH;
        canvas.style.width = `${cssW}px`;
        canvas.style.height = `${cssH}px`;
        resized = true;
      }
    }
    if (resized) {
      this.clearVisuals();
    }
  }
  toTargetPoint(e) {
    return mapViewportPointToCoordinateSpace(e, this.container, this.targetSize, {
      fitMode: this.fitMode,
      mirrored: this.mirrored
    });
  }
  stopDrawLoop() {
    if (this.rafId !== null) {
      window.cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }
  renderPointerFx(ctx, dpr) {
    clearCanvas(ctx);
    if (this.activePointers.size === 0) {
      return;
    }
    const now = Date.now();
    const isMultiTouch = this.activePointers.size > 1;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    for (const pointer of Array.from(this.activePointers.values())) {
      const targetPoint = this.lastTargetPoints.get(pointer.pointerId) ?? this.toTargetPoint(pointer);
      if (!targetPoint) {
        continue;
      }
      const canvasPoint = mapTargetPointToCanvas(
        targetPoint,
        this.container,
        this.targetSize,
        dpr,
        { fitMode: this.fitMode, mirrored: this.mirrored }
      );
      if (!canvasPoint) {
        continue;
      }
      if (!isMultiTouch) {
        drawPulsingRings(
          ctx,
          canvasPoint[0],
          canvasPoint[1],
          dpr,
          pointer.startTime,
          now
        );
        drawOrbitParticles(
          ctx,
          canvasPoint[0],
          canvasPoint[1],
          dpr,
          pointer.startTime,
          now
        );
      }
      drawHeadGlow(ctx, canvasPoint[0], canvasPoint[1], dpr);
    }
    ctx.restore();
  }
  startDrawLoop() {
    if (this.rafId !== null) {
      return;
    }
    const tick = () => {
      const trailContext = this.trailCanvas.getContext("2d");
      const fxContext = this.fxCanvas.getContext("2d");
      if (!trailContext || !fxContext) {
        this.rafId = null;
        return;
      }
      const dpr = window.devicePixelRatio || 1;
      if (this.hasTrailPixels) {
        fadeTrailCanvas(trailContext);
      }
      const segments = this.segQueue.splice(0);
      if (segments.length > 0) {
        drawTrailSegments(
          trailContext,
          segments,
          this.container,
          this.targetSize,
          dpr,
          this.fitMode,
          this.mirrored,
          this.activePointers.size > 1
        );
        this.hasTrailPixels = true;
        this.idleFadeFrames = 0;
      }
      this.renderPointerFx(fxContext, dpr);
      if (this.activePointers.size > 0) {
        this.idleFadeFrames = 0;
      } else if (this.hasTrailPixels) {
        this.idleFadeFrames += 1;
        if (this.idleFadeFrames > TRAIL_IDLE_FADE_FRAMES) {
          clearCanvas(trailContext);
          this.hasTrailPixels = false;
          this.idleFadeFrames = 0;
        }
      }
      if (this.activePointers.size > 0 || this.segQueue.length > 0 || this.hasTrailPixels) {
        this.rafId = window.requestAnimationFrame(tick);
      } else {
        this.rafId = null;
      }
    };
    this.rafId = window.requestAnimationFrame(tick);
  }
  stopSampling() {
    if (this.sampleTimer !== null) {
      window.clearInterval(this.sampleTimer);
      this.sampleTimer = null;
    }
  }
  collectCurrentTracks() {
    const tracks = [];
    for (const pointer of Array.from(this.activePointers.values())) {
      const point = this.toTargetPoint(pointer);
      if (point) {
        tracks.push(point);
      }
    }
    return tracks;
  }
  flushTracks() {
    if (this.sampleInFlight) {
      return;
    }
    const tracks = this.collectCurrentTracks();
    if (!tracks.length) {
      return;
    }
    this.sampleInFlight = true;
    Promise.resolve(this.onTracks(tracks)).catch(() => {
    }).finally(() => {
      this.sampleInFlight = false;
    });
  }
  startSampling() {
    if (this.sampleTimer !== null) {
      return;
    }
    this.flushTracks();
    this.sampleTimer = window.setInterval(() => {
      this.flushTracks();
    }, 30);
  }
  finishStroke(emitEnd = false, preserveTrail = false) {
    const wasActive = this.strokeActive;
    this.strokeActive = false;
    this.stopSampling();
    clearCanvas(this.fxCanvas.getContext("2d"));
    if (preserveTrail) {
      if (this.segQueue.length > 0 || this.hasTrailPixels) {
        this.startDrawLoop();
      } else {
        this.stopDrawLoop();
      }
    } else {
      this.stopDrawLoop();
      this.segQueue.length = 0;
      this.activePointers.clear();
      this.lastTargetPoints.clear();
      this.clearVisuals();
    }
    if (emitEnd && wasActive && this.onStrokeEnd) {
      Promise.resolve(this.onStrokeEnd()).catch(() => {
      });
    }
  }
  handlePointerDown(e) {
    if (!this.enabled) {
      return;
    }
    try {
      this.container.setPointerCapture(e.pointerId);
    } catch {
    }
    this.resizeCanvas();
    if (this.activePointers.size === 0) {
      this.idleFadeFrames = 0;
    }
    this.activePointers.set(e.pointerId, {
      pointerId: e.pointerId,
      clientX: e.clientX,
      clientY: e.clientY,
      startTime: Date.now()
    });
    const targetPoint = this.toTargetPoint(e);
    if (targetPoint) {
      this.lastTargetPoints.set(e.pointerId, targetPoint);
    }
    const strokeWasActive = this.strokeActive;
    this.strokeActive = true;
    if (!strokeWasActive && this.onStrokeStart) {
      Promise.resolve(this.onStrokeStart()).catch(() => {
      });
    }
    this.startDrawLoop();
    this.startSampling();
  }
  handlePointerMove(e) {
    if (!this.enabled || !this.activePointers.has(e.pointerId)) {
      return;
    }
    const activePointer = this.activePointers.get(e.pointerId);
    const nextTargetPoint = this.toTargetPoint(e);
    const last = this.lastTargetPoints.get(e.pointerId);
    if (last && nextTargetPoint) {
      this.segQueue.push({ a: last, b: nextTargetPoint });
    }
    if (nextTargetPoint) {
      this.lastTargetPoints.set(e.pointerId, nextTargetPoint);
    }
    this.activePointers.set(e.pointerId, {
      pointerId: e.pointerId,
      clientX: e.clientX,
      clientY: e.clientY,
      startTime: activePointer?.startTime ?? Date.now()
    });
  }
  handlePointerUp(e) {
    if (!this.activePointers.has(e.pointerId)) {
      return;
    }
    this.activePointers.delete(e.pointerId);
    this.lastTargetPoints.delete(e.pointerId);
    try {
      this.container.releasePointerCapture(e.pointerId);
    } catch {
    }
    if (this.activePointers.size === 0) {
      this.finishStroke(true, true);
    }
  }
  handlePointerCancel(e) {
    if (!this.activePointers.has(e.pointerId)) {
      return;
    }
    this.activePointers.delete(e.pointerId);
    this.lastTargetPoints.delete(e.pointerId);
    if (this.activePointers.size === 0) {
      this.finishStroke(true, true);
    }
  }
};
function createDragTrackController(container, options) {
  return new DragTrackController(container, options);
}

// src/drag/remote-view-host.ts
function createRemoteViewHost(wrapper) {
  const computed = getComputedStyle(wrapper);
  if (computed.position === "static") {
    wrapper.style.position = "relative";
  }
  const videoHost = document.createElement("div");
  videoHost.setAttribute("data-xmax-remote-video", "true");
  videoHost.style.cssText = "position:relative;z-index:0;width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;";
  const dragHost = document.createElement("div");
  dragHost.setAttribute("data-xmax-drag-surface", "true");
  dragHost.style.cssText = "position:absolute;inset:0;z-index:20;pointer-events:none;touch-action:auto;";
  wrapper.replaceChildren();
  wrapper.appendChild(videoHost);
  wrapper.appendChild(dragHost);
  return { wrapper, videoHost, dragHost };
}

// src/realtime/utils.ts
function normalizeRealtimeContext(context) {
  const prompt = context.prompt.trim();
  const refImageUrl = context.refImageUrl?.trim();
  return Object.freeze({
    prompt,
    ...refImageUrl ? { refImageUrl } : {}
  });
}
function isPositiveFinite(value) {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}
function requirePositive(value, name) {
  if (!isPositiveFinite(value)) {
    throw new TypeError(`${name} must be a positive number`);
  }
  return value;
}
function validateRealtimeStreamSetting(setting) {
  if (!setting) {
    return;
  }
  const hasWidth = setting.width !== void 0;
  const hasHeight = setting.height !== void 0;
  if (hasWidth !== hasHeight) {
    throw new TypeError("stream.width and stream.height must be provided together");
  }
  if (hasWidth && hasHeight) {
    requirePositive(setting.width, "stream.width");
    requirePositive(setting.height, "stream.height");
  }
  if (setting.fps !== void 0) {
    requirePositive(setting.fps, "stream.fps");
  }
  if (setting.maxKbps !== void 0) {
    requirePositive(setting.maxKbps, "stream.maxKbps");
  }
  if (setting.contentHint !== void 0 && !["text", "motion", "detail"].includes(setting.contentHint)) {
    throw new TypeError("stream.contentHint must be 'text', 'motion', or 'detail'");
  }
}
function readTrackMediaSetting(track, fallback) {
  const settings = track.getSettings?.();
  const width = isPositiveFinite(settings?.width) ? settings.width : isPositiveFinite(fallback?.width) ? fallback.width : 0;
  const height = isPositiveFinite(settings?.height) ? settings.height : isPositiveFinite(fallback?.height) ? fallback.height : 0;
  const fps = isPositiveFinite(settings?.frameRate) ? settings.frameRate : resolveRtcPublishFps({ fps: fallback?.fps });
  return { width, height, fps };
}
function applyIntrinsicVideoSize(setting, intrinsic) {
  if (!isPositiveFinite(intrinsic.width) || !isPositiveFinite(intrinsic.height)) {
    return setting;
  }
  return {
    ...setting,
    width: intrinsic.width,
    height: intrinsic.height
  };
}
async function readMediaStreamSourceSetting(track, options = {}) {
  const fallback = readTrackMediaSetting(track);
  if (typeof document === "undefined" || typeof MediaStream === "undefined" || track.readyState === "ended") {
    return fallback;
  }
  const timeoutMs = Math.max(0, options.timeoutMs ?? DEFAULT_METADATA_TIMEOUT_MS);
  return new Promise((resolve) => {
    const video = document.createElement("video");
    let settled = false;
    let timeoutHandle = null;
    const finish = () => {
      if (settled) {
        return;
      }
      settled = true;
      const intrinsic = {
        width: video.videoWidth,
        height: video.videoHeight
      };
      if (timeoutHandle !== null) {
        window.clearTimeout(timeoutHandle);
      }
      video.removeEventListener("loadedmetadata", handleMetadata);
      video.removeEventListener("resize", handleMetadata);
      try {
        video.pause();
        video.srcObject = null;
      } catch {
      }
      video.remove();
      resolve(applyIntrinsicVideoSize(fallback, intrinsic));
    };
    const handleMetadata = () => {
      if (isPositiveFinite(video.videoWidth) && isPositiveFinite(video.videoHeight)) {
        finish();
      }
    };
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;opacity:0;pointer-events:none;";
    video.addEventListener("loadedmetadata", handleMetadata);
    video.addEventListener("resize", handleMetadata);
    video.srcObject = new MediaStream([track]);
    document.body?.appendChild(video);
    timeoutHandle = window.setTimeout(finish, timeoutMs);
    void video.play().then(handleMetadata).catch(() => finish());
    handleMetadata();
  });
}
function resolveRealtimeStreamSetting(options, source) {
  validateRealtimeStreamSetting(options.stream);
  let size;
  if (options.stream?.width !== void 0 && options.stream.height !== void 0) {
    size = [options.stream.width, options.stream.height];
  } else if (source.width > 0 && source.height > 0) {
    size = resolveUploadVideoSize(source.width, source.height);
  } else {
    size = DEFAULT_SESSION_TARGET_SIZE;
  }
  const fps = resolveRtcPublishFps({
    fps: options.stream?.fps ?? source.fps
  });
  return Object.freeze({
    width: size[0],
    height: size[1],
    fps,
    maxKbps: options.stream?.maxKbps ?? DEFAULT_REALTIME_STREAM_MAX_KBPS,
    contentHint: options.stream?.contentHint ?? DEFAULT_REALTIME_STREAM_CONTENT_HINT
  });
}

// src/realtime/camera.ts
function resolveDefaultCameraRealtimeSetting(mobile = isMobilePublishEnvironment()) {
  return {
    ...mobile ? DEFAULT_CAMERA_REALTIME_SETTINGS.mobile : DEFAULT_CAMERA_REALTIME_SETTINGS.desktop
  };
}
function resolveCameraRtcEncoderSize(setting, mobile = isMobilePublishEnvironment()) {
  return mobile ? [setting.height, setting.width] : [setting.width, setting.height];
}
function fillRealtimeMediaSetting(setting, fallback) {
  return {
    width: setting?.width ?? fallback.width,
    height: setting?.height ?? fallback.height,
    fps: setting?.fps ?? fallback.fps,
    maxKbps: setting?.maxKbps ?? fallback.maxKbps,
    contentHint: setting?.contentHint ?? fallback.contentHint
  };
}
function resolveCameraRealtimeStreamSetting(options, mobile = isMobilePublishEnvironment()) {
  validateRealtimeStreamSetting(options.stream);
  const defaults = resolveDefaultCameraRealtimeSetting(mobile);
  return fillRealtimeMediaSetting(options.stream, defaults);
}

// src/realtime/local-stream-preview.ts
function mountLocalStreamPreview(container, stream, fit) {
  const video = document.createElement("video");
  video.autoplay = true;
  video.muted = true;
  video.playsInline = true;
  video.style.display = "block";
  video.style.width = "100%";
  video.style.height = "100%";
  video.style.objectFit = fit;
  video.style.objectPosition = "center";
  video.setAttribute("playsinline", "true");
  video.setAttribute("aria-hidden", "true");
  video.srcObject = stream;
  container.replaceChildren(video);
  void video.play().catch(() => void 0);
  return () => {
    try {
      video.pause();
      if (video.srcObject === stream) {
        video.srcObject = null;
      }
    } catch {
    }
    video.remove();
  };
}

// src/realtime/rtc-console-log.ts
var RTC_CONSOLE_LOG_PREFIX = "[Xmax]";
function writeRtcLogToConsole(entry) {
  if (!entry.message.startsWith(RTC_CONSOLE_LOG_PREFIX)) {
    return;
  }
  const args = entry.data === void 0 ? [entry.message] : [entry.message, entry.data];
  if (entry.level === "error") {
    console.error(...args);
  } else if (entry.level === "warn") {
    console.warn(...args);
  } else {
    console.info(...args);
  }
}
function getVideoTrack(stream) {
  const track = stream.getVideoTracks()[0];
  if (!track) {
    throw new Error("Missing video track in MediaStream");
  }
  return track;
}
function getAudioTrack(stream) {
  return stream.getAudioTracks().find((track) => track.readyState === "live");
}
function createManagedLocalVideoHost(wrapper) {
  const computed = getComputedStyle(wrapper);
  if (computed.position === "static") {
    wrapper.style.position = "relative";
  }
  wrapper.style.overflow = "hidden";
  const host = document.createElement("div");
  host.setAttribute("data-xmax-local-video", "true");
  host.style.cssText = "position:relative;width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;";
  wrapper.replaceChildren(host);
  return host;
}
function observeManagedVideoStyle(host, fit, mirrored) {
  host.style.transform = mirrored ? "scaleX(-1)" : "none";
  host.style.transformOrigin = "center";
  const apply = () => {
    host.querySelectorAll("video, canvas").forEach((node) => {
      const element = node;
      element.style.width = "100%";
      element.style.height = "100%";
      element.style.objectFit = fit;
      element.style.objectPosition = "center";
    });
  };
  apply();
  const MutationObserverCtor = globalThis.MutationObserver;
  if (!MutationObserverCtor) {
    return () => {
    };
  }
  const observer = new MutationObserverCtor(apply);
  observer.observe(host, { childList: true, subtree: true });
  return () => observer.disconnect();
}
var PREPARED_REALTIME_MEDIA = /* @__PURE__ */ Symbol("preparedRealtimeMedia");
var LOCAL_CAMERA_PREVIEW_REVEAL_MS = 300;
function isLikelyMobileRuntime() {
  if (typeof navigator === "undefined") {
    return false;
  }
  const ua = navigator.userAgent || "";
  if (/iPhone|iPad|iPod|Android/i.test(ua)) {
    return true;
  }
  return navigator.maxTouchPoints > 1 && /Macintosh/i.test(ua);
}
function withPreparedRealtimeMedia(options, prepared) {
  return Object.assign({}, options, { [PREPARED_REALTIME_MEDIA]: prepared });
}
var RealtimeSessionImpl = class _RealtimeSessionImpl {
  constructor(client, rtc, reportError, options, media, prepared, clientOptions, notifyUserError, sdkI18n) {
    this.renderCleanup = [];
    this.sessionUid = null;
    this.taskUid = null;
    this.currentState = "idle";
    this.currentContext = Object.freeze({ prompt: "" });
    this.runningContext = null;
    this.disconnected = false;
    /** True only after `connect()` bootstrap succeeds — gates `onDisconnect`. */
    this.sessionEstablished = false;
    this.disconnectNotified = false;
    this.mediaCleaned = false;
    this.heartbeatStarted = false;
    this.heartbeatIntervalMs = DEFAULT_REALTIME_HEARTBEAT_INTERVAL_MS;
    this.pendingDisconnectReason = "client";
    this.remoteViewHost = null;
    this.dragController = null;
    this.dragTrackFitMode = "cover";
    this.hiddenRemoteElement = null;
    this.remoteStreamNotifyTimer = null;
    this.lastNotifiedRemoteStream = null;
    /** change_condition 固定使用首次 start 的分辨率，避免中途被替换。 */
    this.firstStartEventSize = null;
    this.client = client;
    this.rtc = rtc;
    this.reportError = reportError;
    this.notifyUserError = notifyUserError;
    this.sdkI18n = sdkI18n ?? createSDKI18n();
    this.mediaValue = Object.freeze(media);
    const localContainer = options.render?.localContainer ?? null;
    this.localElement = localContainer ? createManagedLocalVideoHost(localContainer) : null;
    this.localRenderMirror = options.render?.mirror ?? DEFAULT_REALTIME_RENDER_SETTING.mirror;
    this.onRemoteStream = options.onRemoteStream;
    this.onDisconnect = options.onDisconnect;
    this.onStateChange = options.onStateChange;
    this.onPublishPipelineWaitChange = clientOptions?.onPublishPipelineWaitChange;
    this.onRoomEvent = options.onRoomEvent;
    this.rtcLogEnabled = options.log?.rtc === true;
    this.ownsMedia = prepared.owned === true;
    this.shouldMirrorCameraInput = prepared.internalCamera?.mirrorInput === true;
    this.cleanupMedia = prepared.cleanup;
    this.dragTrackFitMode = options.render?.fit ?? (media.kind === "image" || media.kind === "video" ? "contain" : "cover");
    this.dragSetting = options.render?.drag;
    if (this.localElement && !prepared.internalCamera) {
      this.renderCleanup.push(
        mountLocalStreamPreview(this.localElement, prepared.stream, this.dragTrackFitMode)
      );
    }
    this.rtc.setOnRemoteOutputStalled(() => {
      this.failOverloaded("remote_output_stalled");
    });
    this.rtc.setOnRoomEvent((event) => {
      this.onRoomEvent?.(event);
    });
    this.rtc.setOnRemoteVideoFirstFrame(() => {
      this.startHeartbeatAfterFirstRemoteFrame();
    });
    const remoteElement = options.render?.remoteContainer;
    if (remoteElement) {
      this.remoteElement = remoteElement;
      this.remoteViewHost = createRemoteViewHost(this.remoteElement);
      this.renderCleanup.push(observeManagedVideoStyle(
        this.remoteViewHost.videoHost,
        this.dragTrackFitMode,
        false
      ));
      if (this.localElement) {
        this.renderCleanup.push(observeManagedVideoStyle(
          this.localElement,
          this.dragTrackFitMode,
          this.localRenderMirror
        ));
      }
      return;
    }
    if (options.onRemoteStream) {
      const hidden = document.createElement("div");
      hidden.setAttribute("data-Xmax-remote-host", "true");
      hidden.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden";
      document.body.appendChild(hidden);
      this.hiddenRemoteElement = hidden;
      this.remoteElement = hidden;
      this.remoteViewHost = createRemoteViewHost(hidden);
      if (this.localElement) {
        this.renderCleanup.push(observeManagedVideoStyle(
          this.localElement,
          this.dragTrackFitMode,
          this.localRenderMirror
        ));
      }
      this.rtc.setOnRemotePlayerMounted(() => {
        this.scheduleNotifyRemoteStream();
      });
      return;
    }
    this.remoteElement = null;
    if (this.localElement) {
      this.renderCleanup.push(observeManagedVideoStyle(
        this.localElement,
        this.dragTrackFitMode,
        this.localRenderMirror
      ));
    }
  }
  get media() {
    return this.mediaValue;
  }
  get remoteVideoContainer() {
    return this.remoteViewHost?.videoHost ?? this.remoteElement;
  }
  get state() {
    return this.currentState;
  }
  get context() {
    return this.currentContext;
  }
  logTiming(stage, startedAt, data) {
    {
      return;
    }
  }
  hideLocalCameraPreview() {
    if (!this.localElement) {
      return;
    }
    this.localElement.style.transition = "none";
    this.localElement.style.opacity = "0";
  }
  revealLocalCameraPreview() {
    if (!this.localElement) {
      return;
    }
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    this.localElement.style.transition = reduceMotion ? "none" : `opacity ${LOCAL_CAMERA_PREVIEW_REVEAL_MS}ms ease-out`;
    this.localElement.style.opacity = "1";
  }
  async measureTiming(stage, operation, data) {
    const startedAt = performance.now();
    try {
      const result = await operation();
      this.logTiming(stage, startedAt, data);
      return result;
    } catch (error) {
      this.logTiming(stage, startedAt, { ...data, failed: true });
      throw error;
    }
  }
  static async connect(stream, options, clientOptions) {
    const connectStartedAt = performance.now();
    const internalPrepared = options[PREPARED_REALTIME_MEDIA];
    const prepared = internalPrepared ?? {
      kind: "stream",
      stream,
      publishTrack: getVideoTrack(stream),
      publishAudioTrack: getAudioTrack(stream),
      owned: false
    };
    const sdkI18n = createSDKI18n({});
    const notifyUserError = options.onError ?? clientOptions.onError;
    const reportError = (error, fallbackMessage) => {
      throw notifyError(error, notifyUserError, fallbackMessage ?? sdkI18n.t("errors.requestFailed"));
    };
    const modelName = options.model.name.trim();
    if (!modelName) {
      prepared.cleanup?.();
      throw new Error("model.name is required");
    }
    const client = new XmaxOpenClient({
      apiKey: clientOptions.apiKey,
      authToken: clientOptions.authToken,
      baseUrl: clientOptions.baseUrl ?? XMAX_OPEN_API_PRODUCTION_BASE_URL,
      onError: notifyUserError
    });
    const rtcLogEnabled = options.log?.rtc === true;
    const rtc = new RtcManager({
      renderFit: options.render?.fit,
      playRemoteAudio: options.audio?.subscribe === true,
      onLog: rtcLogEnabled ? writeRtcLogToConsole : void 0,
      onRemoteSeiReceived: clientOptions.onRemoteSei,
      onSeiGateChange: clientOptions.onSeiGateChange,
      i18n: sdkI18n
    });
    const publishTrack = prepared.internalCamera ? void 0 : prepared.publishTrack ?? getVideoTrack(prepared.stream);
    if (!prepared.sourceSetting && !publishTrack) {
      throw new Error("Missing media source setting");
    }
    const sourceSetting = prepared.sourceSetting ?? readTrackMediaSetting(publishTrack);
    const streamSetting = resolveRealtimeStreamSetting(options, sourceSetting);
    const media = Object.freeze({
      kind: prepared.kind,
      stream: prepared.stream,
      sourceSetting: Object.freeze({ ...sourceSetting }),
      streamSetting
    });
    if (prepared.internalCamera && rtcLogEnabled) {
      writeRtcLogToConsole({
        level: "info",
        message: "[Xmax][RTC] connection options",
        data: {
          facingMode: prepared.internalCamera.facingMode,
          stream: streamSetting
        }
      });
    }
    const session = new _RealtimeSessionImpl(
      client,
      rtc,
      reportError,
      options,
      media,
      prepared,
      clientOptions,
      notifyUserError,
      sdkI18n
    );
    try {
      await session.bootstrap(
        prepared,
        options,
        modelName,
        clientOptions.heartbeatIntervalMs ?? DEFAULT_REALTIME_HEARTBEAT_INTERVAL_MS
      );
      session.sessionEstablished = true;
      session.logTiming("SDK \u5B9E\u65F6\u8FDE\u63A5\u603B\u8017\u65F6", connectStartedAt, {
        mediaKind: prepared.kind
      });
      return session;
    } catch (error) {
      session.logTiming("SDK \u5B9E\u65F6\u8FDE\u63A5\u603B\u8017\u65F6", connectStartedAt, {
        mediaKind: prepared.kind,
        failed: true
      });
      await session.safeDisconnect();
      throw reportError(error);
    }
  }
  /** Tear down the session when outbound or first remote frames never become ready. */
  failOverloaded(_cause) {
    if (this.disconnected) {
      return;
    }
    const message = this.sdkI18n.t("errors.systemOverloaded");
    notifyError(new Error(message), this.notifyUserError, message);
    void this.safeDisconnect({ reason: "overloaded" });
  }
  /**
   * Any failure that blocks output: send stop (if generation active), leave RTC,
   * close session, then fire `onDisconnect`.
   */
  failOutputAndDisconnect(error, reason = "error") {
    if (!this.disconnected) {
      void this.safeDisconnect({ reason });
    }
    this.reportError(error);
  }
  async bootstrap(prepared, options, modelName, heartbeatIntervalMs) {
    const createdSession = await this.measureTiming(
      "\u521B\u5EFA\u670D\u52A1\u7AEF Session",
      () => this.client.createSession(modelName),
      { modelName }
    );
    if (!createdSession.sessionUid?.trim()) {
      throw new Error("Session uid is missing");
    }
    this.sessionUid = createdSession.sessionUid;
    this.heartbeatIntervalMs = heartbeatIntervalMs;
    const joinInfo = this.client.getRtcJoinInfo(createdSession);
    if (prepared.internalCamera) {
      const internalCamera = prepared.internalCamera;
      const encoderSize = resolveCameraRtcEncoderSize(this.media.streamSetting);
      this.hideLocalCameraPreview();
      await this.rtc.prepareEngine(joinInfo);
      if (this.localElement) {
        this.rtc.setLocalVideoContainer(this.localElement);
      }
      if (this.remoteVideoContainer) {
        this.rtc.setRemoteVideoContainer(this.remoteVideoContainer);
      }
      const captureSettings = await this.rtc.startInternalVideoCapture({
        encoderSize,
        encoderFps: this.media.streamSetting.fps,
        encoderMaxKbps: this.media.streamSetting.maxKbps,
        encoderContentHint: this.media.streamSetting.contentHint,
        facingMode: internalCamera.facingMode
      });
      this.updateCameraSourceSetting(captureSettings);
      if (internalCamera.withAudio) {
        await this.rtc.startInternalAudioCapture();
      }
      await this.rtc.joinPreparedRoom();
      const cameraTrack = this.rtc.getInternalVideoTrack();
      if (!cameraTrack) {
        throw new Error("Missing internal camera track");
      }
      const cameraReadyStartedAt = performance.now();
      const cameraReady = await waitForCameraTrackReady(cameraTrack, {
        consecutiveFrames: 2,
        timeoutMs: 1e3
      });
      this.logTiming("\u7B49\u5F85\u6444\u50CF\u5934\u753B\u9762\u5C31\u7EEA", cameraReadyStartedAt, cameraReady);
      this.revealLocalCameraPreview();
      const track = await this.rtc.publishInternalVideo();
      prepared.stream.addTrack(track);
    } else {
      await this.rtc.join(joinInfo);
      if (this.remoteVideoContainer) {
        this.rtc.setRemoteVideoContainer(this.remoteVideoContainer);
      }
      await this.measureTiming(
        "\u5916\u90E8\u89C6\u9891\u53D1\u5E03",
        () => this.rtc.startExternalVideoPublishing(
          prepared.publishTrack ?? getVideoTrack(prepared.stream),
          [this.media.streamSetting.width, this.media.streamSetting.height],
          {
            highQuality: true,
            fps: this.media.streamSetting.fps,
            maxKbps: this.media.streamSetting.maxKbps,
            contentHint: this.media.streamSetting.contentHint,
            audioTrack: prepared.publishAudioTrack
          }
        )
      );
    }
    const initialContext = normalizeRealtimeContext(options.context ?? { prompt: "" });
    this.currentContext = initialContext;
    if (this.localElement && prepared.internalCamera) {
      queueMicrotask(() => this.rtc.refreshLocalVideoPreview());
    }
    const autoStart = options.autoStart ?? DEFAULT_REALTIME_AUTO_START;
    if (autoStart) {
      await this.runStart({
        prompt: this.currentContext.prompt,
        refImage: this.currentContext.refImageUrl ?? void 0
      });
      this.runningContext = this.currentContext;
      this.setState("running");
    }
  }
  /** Replace the provisional camera source metadata with the actual RTC capture result. */
  updateCameraSourceSetting(settings) {
    const previous = this.media.sourceSetting;
    const sourceSetting = Object.freeze({
      width: isPositiveFinite(settings.width) ? settings.width : previous.width,
      height: isPositiveFinite(settings.height) ? settings.height : previous.height,
      fps: isPositiveFinite(settings.frameRate) ? settings.frameRate : previous.fps
    });
    this.mediaValue = Object.freeze({
      ...this.media,
      sourceSetting
    });
  }
  /** Start billing heartbeat once, after the client renders the first remote output frame. */
  startHeartbeatAfterFirstRemoteFrame() {
    if (this.heartbeatStarted || this.disconnected || !this.sessionUid || !this.taskUid) {
      return;
    }
    this.heartbeatStarted = true;
    this.client.startHeartbeat(
      this.sessionUid,
      this.heartbeatIntervalMs,
      (heartbeatSession) => {
        if (heartbeatSession.status !== ACTIVE_STATUS) {
          void this.safeDisconnect({ reason: "session_inactive" });
        }
      },
      () => {
        void this.safeDisconnect({ reason: "heartbeat_error" });
      }
    );
  }
  setState(state) {
    if (this.currentState === state) {
      return;
    }
    this.currentState = state;
    try {
      this.onStateChange?.(state);
    } catch {
    }
  }
  assertConnected() {
    if (this.currentState === "disconnected") {
      throw new Error("Realtime session is disconnected");
    }
  }
  async start(context) {
    return this.startWithInternalOptions(context);
  }
  async set(context) {
    this.assertConnected();
    const nextContext = normalizeRealtimeContext({
      ...this.currentContext,
      ...context,
      ...context.refImageUrl === null ? { refImageUrl: void 0 } : {}
    });
    if (this.currentState === "running") {
      try {
        await this.runChangeCondition({
          prompt: nextContext.prompt,
          refImage: nextContext.refImageUrl ?? void 0
        });
        this.currentContext = nextContext;
        this.runningContext = nextContext;
        this.setState("running");
      } catch (error) {
        this.failOutputAndDisconnect(error);
      }
      return;
    }
    await this.runStart({
      prompt: nextContext.prompt,
      refImage: nextContext.refImageUrl ?? void 0
    });
    this.currentContext = nextContext;
    this.runningContext = nextContext;
    this.setState("running");
  }
  async startWithInternalOptions(context, options = {}) {
    this.assertConnected();
    const nextContext = context ? normalizeRealtimeContext({
      ...this.currentContext,
      ...context,
      ...context.refImageUrl === null ? { refImageUrl: void 0 } : {}
    }) : this.currentContext;
    try {
      await this.runStart({
        prompt: nextContext.prompt,
        refImage: nextContext.refImageUrl ?? void 0,
        staticGenerate: options.staticGenerate === true ? true : void 0,
        staticImagePath: options.staticImagePath,
        preserveRemoteOutput: options.preserveRemoteOutput
      });
      this.currentContext = nextContext;
      this.runningContext = nextContext;
      this.setState("running");
    } catch (error) {
      this.failOutputAndDisconnect(error);
    }
  }
  async sendTracks(tracks) {
    if (!this.rtc.snapshot.joined || !this.taskUid) {
      return;
    }
    try {
      await this.rtc.sendRoomEvent(
        createTracksRtcRoomEvent({
          userId: this.rtc.snapshot.userId ?? void 0,
          uid: this.taskUid,
          sessionUid: this.taskUid,
          tracks
        })
      );
    } catch {
    }
  }
  async stopGeneration() {
    return this.stopInternal();
  }
  async stopLocalStream() {
    if (this.disconnected) {
      return;
    }
    try {
      await this.rtc.stopVideoPublishing({
        preserveExternalTrack: !this.ownsMedia,
        preserveRemote: true
      });
    } catch {
    }
    if (!this.mediaCleaned) {
      this.mediaCleaned = true;
      try {
        this.cleanupMedia?.();
      } catch {
      }
    }
  }
  async stopInternal(options) {
    this.assertConnected();
    this.rtc.clearLocalOutboundWatch();
    this.updateDragController(false);
    const preserveRemoteDom = options?.preserveRemoteDom ?? false;
    if (preserveRemoteDom) {
      this.rtc.setPreserveRemoteDom(true);
    }
    this.rtc.configureSessionSei(null);
    if (!this.rtc.snapshot.joined) {
      this.rtc.clearRemoteVideo({ preserveDom: preserveRemoteDom });
      if (!preserveRemoteDom && this.remoteVideoContainer) {
        this.rtc.setRemoteVideoContainer(null);
      }
      this.taskUid = null;
      this.runningContext = null;
      if (!options?.suppressStateChange) {
        this.setState("idle");
      }
      if (preserveRemoteDom) {
        this.rtc.setPreserveRemoteDom(false);
      }
      return;
    }
    try {
      await this.rtc.sendRoomEvent(
        createStopRtcRoomEvent({
          userId: this.rtc.snapshot.userId ?? void 0,
          sessionUid: this.taskUid ?? void 0
        })
      );
    } finally {
      this.rtc.clearRemoteVideo({ preserveDom: preserveRemoteDom });
      if (!preserveRemoteDom && this.remoteVideoContainer) {
        this.rtc.setRemoteVideoContainer(null);
      }
      this.taskUid = null;
      this.runningContext = null;
      if (!options?.suppressStateChange) {
        this.setState("idle");
      }
      if (preserveRemoteDom) {
        this.rtc.setPreserveRemoteDom(false);
      }
    }
  }
  async disconnect() {
    if (this.disconnected) {
      return;
    }
    this.disconnected = true;
    await this.safeDisconnect({ reason: "client" });
  }
  getSessionUid() {
    return this.sessionUid;
  }
  /** Keep change_condition size pinned to the first start event. */
  resolveChangeConditionSize() {
    if (!this.firstStartEventSize) {
      return [
        this.media.streamSetting.width,
        this.media.streamSetting.height
      ];
    }
    return [this.firstStartEventSize[0], this.firstStartEventSize[1]];
  }
  async runStart(options) {
    if (!this.rtc.snapshot.joined) {
      return;
    }
    const preserveRemoteOutput = options.preserveRemoteOutput ?? false;
    if (preserveRemoteOutput) {
      this.rtc.setPreserveRemoteDom(true);
    }
    const startPrompt = options.prompt ?? this.currentContext.prompt;
    try {
      if (!preserveRemoteOutput) {
        this.rtc.setRemoteVideoContainer(null);
        this.rtc.clearRemoteVideo();
      }
      const size = [
        this.media.streamSetting.width,
        this.media.streamSetting.height
      ];
      if (!this.firstStartEventSize) {
        this.firstStartEventSize = [size[0], size[1]];
      }
      const taskUid = createTaskUid();
      this.taskUid = taskUid;
      this.rtc.configureSessionSei(taskUid);
      if (this.remoteVideoContainer) {
        this.rtc.setRemoteVideoContainer(this.remoteVideoContainer);
      }
      const startRoomEvent = createStartRtcRoomEvent({
        userId: this.rtc.snapshot.userId ?? void 0,
        uid: taskUid,
        sessionUid: taskUid,
        model: DEFAULT_REALTIME_START_EVENT_MODEL,
        size,
        prompt: startPrompt,
        refImagePath: options.refImage,
        // Never reuse prior start — caller must pass `static_*` each time.
        staticGenerate: options.staticGenerate === true ? true : void 0,
        staticImagePath: options.staticImagePath,
        mirror: this.shouldMirrorCameraInput
      });
      await this.measureTiming(
        "\u53D1\u9001\u5F00\u59CB\u751F\u6210\u4E8B\u4EF6",
        () => this.rtc.sendRoomEvent(startRoomEvent),
        {
          prompt: startRoomEvent.params.prompt,
          size: startRoomEvent.params.size,
          hasRefImage: Boolean(startRoomEvent.params.ref_image_path)
        }
      );
      const isMobileUploadInput = (this.media.kind === "video" || this.media.kind === "image") && isLikelyMobileRuntime();
      this.rtc.armLocalOutboundWatch({
        minZeroSamples: isMobileUploadInput ? 5 : 3,
        minStallMs: isMobileUploadInput ? 12e3 : 6e3,
        startGraceMs: isMobileUploadInput ? 12e3 : 6e3,
        resumeGraceMs: isMobileUploadInput ? 8e3 : 5e3,
        onStalled: (info) => {
          this.failOverloaded(`local_outbound_${info.reason}`);
        }
      });
      await this.measureTiming(
        "\u5237\u65B0\u8FDC\u7AEF\u89C6\u9891\u7ED1\u5B9A",
        () => this.rtc.refreshRemoteVideoBinding({ force: !preserveRemoteOutput })
      );
      this.updateDragController(true);
      this.scheduleNotifyRemoteStream();
    } catch (error) {
      this.rtc.configureSessionSei(null);
      this.rtc.clearRemoteFirstOutputWatch();
      this.rtc.clearLocalOutboundWatch();
      this.failOutputAndDisconnect(error);
    } finally {
      if (preserveRemoteOutput) {
        this.rtc.setPreserveRemoteDom(false);
      }
    }
  }
  async runChangeCondition(options) {
    if (!this.rtc.snapshot.joined) {
      return;
    }
    const size = this.resolveChangeConditionSize();
    const changeConditionRoomEvent = createChangeConditionRtcRoomEvent({
      userId: this.rtc.snapshot.userId ?? void 0,
      sessionUid: this.taskUid ?? void 0,
      model: DEFAULT_REALTIME_START_EVENT_MODEL,
      size,
      prompt: options.prompt ?? this.currentContext.prompt,
      refImagePath: options.refImage,
      staticGenerate: options.staticGenerate === true ? true : void 0,
      staticImagePath: options.staticImagePath
    });
    await this.measureTiming(
      "\u53D1\u9001\u5207\u6362\u6761\u4EF6\u4E8B\u4EF6",
      () => this.rtc.sendRoomEvent(changeConditionRoomEvent),
      {
        prompt: changeConditionRoomEvent.params.prompt,
        size: changeConditionRoomEvent.params.size,
        hasRefImage: Boolean(changeConditionRoomEvent.params.ref_image_path)
      }
    );
  }
  isDragEnabled() {
    return (this.dragSetting?.enabled ?? DEFAULT_REALTIME_RENDER_SETTING.dragEnabled) && Boolean(this.remoteElement && !this.hiddenRemoteElement);
  }
  updateDragController(active) {
    const dragHost = this.remoteViewHost?.dragHost;
    if (!dragHost || !active || !this.taskUid || !this.isDragEnabled()) {
      this.dragController?.setEnabled(false);
      return;
    }
    const targetSize = [
      this.media.streamSetting.width,
      this.media.streamSetting.height
    ];
    if (!this.dragController) {
      this.dragController = createDragTrackController(dragHost, {
        targetSize,
        fitMode: this.dragTrackFitMode,
        mirrored: false,
        enabled: true,
        onTracks: (tracks) => {
          void this.sendTracks(tracks);
        },
        onStrokeStart: this.dragSetting?.onStart,
        onStrokeEnd: this.dragSetting?.onEnd
      });
      return;
    }
    this.dragController.setTargetSize(targetSize);
    this.dragController.setFitMode(this.dragTrackFitMode);
    this.dragController.setMirrored(false);
    this.dragController.setEnabled(true);
  }
  scheduleNotifyRemoteStream() {
    if (!this.onRemoteStream) {
      return;
    }
    this.clearRemoteStreamNotifyTimer();
    if (this.notifyRemoteStreamOnce()) {
      return;
    }
    let attempts = 0;
    this.remoteStreamNotifyTimer = setInterval(() => {
      attempts += 1;
      if (this.notifyRemoteStreamOnce() || attempts >= 60) {
        this.clearRemoteStreamNotifyTimer();
      }
    }, 500);
  }
  notifyRemoteStreamOnce() {
    const videoRoot = this.remoteVideoContainer;
    if (!this.onRemoteStream || !videoRoot) {
      return false;
    }
    const video = videoRoot instanceof HTMLVideoElement ? videoRoot : videoRoot.querySelector("video");
    if (!(video instanceof HTMLVideoElement) || !(video.srcObject instanceof MediaStream)) {
      return false;
    }
    if (this.lastNotifiedRemoteStream === video.srcObject) {
      return true;
    }
    this.lastNotifiedRemoteStream = video.srcObject;
    this.onRemoteStream(video.srcObject);
    return true;
  }
  clearRemoteStreamNotifyTimer() {
    if (this.remoteStreamNotifyTimer !== null) {
      clearInterval(this.remoteStreamNotifyTimer);
      this.remoteStreamNotifyTimer = null;
    }
  }
  emitDisconnect(reason) {
    if (!this.sessionEstablished || this.disconnectNotified) {
      return;
    }
    this.disconnectNotified = true;
    try {
      this.onDisconnect?.(reason);
    } catch {
    }
  }
  async safeDisconnect(options) {
    const reason = options?.reason ?? this.pendingDisconnectReason;
    this.pendingDisconnectReason = reason;
    this.disconnected = true;
    this.rtc.clearRemoteFirstOutputWatch();
    this.rtc.clearLocalOutboundWatch();
    this.clearRemoteStreamNotifyTimer();
    this.lastNotifiedRemoteStream = null;
    const activeSessionUid = this.sessionUid;
    this.sessionUid = null;
    this.client.beginTeardown();
    const generationActive = !!this.taskUid && this.rtc.snapshot.joined;
    try {
      if (generationActive) {
        await this.stopInternal({ suppressStateChange: true });
      } else {
        this.updateDragController(false);
        this.rtc.clearRemoteVideo();
        if (this.remoteVideoContainer) {
          this.rtc.setRemoteVideoContainer(null);
        }
        this.taskUid = null;
      }
    } catch {
    }
    try {
      if (this.rtc.snapshot.joined) {
        await this.rtc.stopVideoPublishing({ preserveExternalTrack: !this.ownsMedia });
      }
    } catch {
    }
    try {
      await this.rtc.leave({ preserveExternalTrack: !this.ownsMedia });
    } catch {
    }
    if (activeSessionUid) {
      try {
        await this.client.closeSession(activeSessionUid);
      } catch {
      }
    }
    this.client.endTeardown();
    this.taskUid = null;
    this.dragController?.destroy();
    this.dragController = null;
    this.renderCleanup.splice(0).forEach((cleanup) => cleanup());
    if (!this.mediaCleaned) {
      this.mediaCleaned = true;
      try {
        this.cleanupMedia?.();
      } catch {
      }
    }
    if (this.hiddenRemoteElement) {
      this.hiddenRemoteElement.remove();
      this.hiddenRemoteElement = null;
    }
    this.runningContext = null;
    this.setState("disconnected");
    this.emitDisconnect(reason);
  }
};

// src/realtime/client.ts
function getFirstLiveAudioTrack(stream) {
  return stream.getAudioTracks().find((track) => track.readyState === "live");
}
function createRealtimeClient(clientOptions) {
  return {
    connectCamera: async (connectOptions) => {
      const streamSetting = resolveCameraRealtimeStreamSetting(connectOptions);
      const stream = new MediaStream();
      const withAudio = connectOptions.audio?.publish !== false;
      const preparedOptions = withPreparedRealtimeMedia({
        ...connectOptions,
        stream: streamSetting
      }, {
        kind: "camera",
        stream,
        // Replaced with the actual settings returned by startVideoCapture during bootstrap.
        sourceSetting: streamSetting,
        internalCamera: {
          facingMode: connectOptions.facingMode,
          withAudio,
          // Camera defaults to the front-facing device when facingMode is omitted.
          mirrorInput: connectOptions.facingMode !== "environment"
        },
        owned: true
      });
      try {
        return await RealtimeSessionImpl.connect(stream, preparedOptions, clientOptions);
      } catch (error) {
        throw notifyError(
          error,
          connectOptions.onError ?? clientOptions.onError,
          "Failed to connect RTC camera"
        );
      }
    },
    connectMedia: async (source, connectOptions) => {
      let mediaStream = null;
      try {
        const kind = isImageMediaFile(source) ? "image" : "video";
        mediaStream = await createMediaFileStream(source, {
          playbackRate: connectOptions.playback?.playbackRate ?? DEFAULT_REALTIME_PLAYBACK_SETTING.playbackRate,
          backgroundColor: connectOptions.render?.backgroundColor
        });
        const prepared = mediaStream;
        const preparedOptions = withPreparedRealtimeMedia(connectOptions, {
          kind,
          stream: prepared.previewStream,
          publishTrack: prepared.videoTrack,
          publishAudioTrack: connectOptions.audio?.publish !== false ? prepared.audioTrack : void 0,
          sourceSetting: {
            width: prepared.sourceWidth,
            height: prepared.sourceHeight,
            fps: prepared.fps
          },
          owned: true,
          cleanup: () => prepared.destroy()
        });
        return await RealtimeSessionImpl.connect(prepared.previewStream, preparedOptions, clientOptions);
      } catch (error) {
        mediaStream?.destroy();
        throw notifyError(
          error,
          connectOptions.onError ?? clientOptions.onError,
          "Failed to connect media"
        );
      }
    },
    connect: async (stream, connectOptions) => {
      const publishTrack = stream.getVideoTracks()[0];
      const sourceSetting = publishTrack ? await readMediaStreamSourceSetting(publishTrack) : void 0;
      const preparedOptions = withPreparedRealtimeMedia(connectOptions, {
        kind: "stream",
        stream,
        publishTrack,
        publishAudioTrack: connectOptions.audio?.publish !== false ? getFirstLiveAudioTrack(stream) : void 0,
        sourceSetting,
        owned: false
      });
      return RealtimeSessionImpl.connect(stream, preparedOptions, clientOptions);
    }
  };
}

// src/client/create-client.ts
function resolveClientOptions(options) {
  return {
    ...options,
    baseUrl: options.baseUrl?.trim() || XMAX_OPEN_API_PRODUCTION_BASE_URL
  };
}
function createXmaxClient(options) {
  const resolved = resolveClientOptions(options);
  const httpClient = new XmaxOpenClient({
    apiKey: resolved.apiKey,
    authToken: resolved.authToken,
    baseUrl: resolved.baseUrl,
    onError: resolved.onError
  });
  return {
    files: createFileClient(httpClient),
    realtime: createRealtimeClient(resolved)
  };
}

// src/realtime/models.ts
var models = {
  /**
   * @brief 选择一个实时生成模型。
   * @param name 模型的公开名称，例如 `x2.0`。
   * @returns 包含原始模型名称的 RealtimeModel。
   */
  realtime(name) {
    return { name };
  }
};

// src/drag/drag-video-sync.ts
var DRAG_SYNCED_ATTR = "data-xmax-drag-synced";
function toContentRect2(rect) {
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height
  };
}
function isMediaInsetInContainer2(mediaRect, containerRect) {
  if (!mediaRect.width || !mediaRect.height || !containerRect.width || !containerRect.height) {
    return false;
  }
  const widthRatio = mediaRect.width / containerRect.width;
  const heightRatio = mediaRect.height / containerRect.height;
  return widthRatio < 0.98 || heightRatio < 0.98;
}
function intersectContentRects(a, b) {
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.left + a.width, b.left + b.width);
  const bottom = Math.min(a.top + a.height, b.top + b.height);
  return {
    left,
    top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top)
  };
}
function readMediaIntrinsicSize(media) {
  const video = media;
  if ("videoWidth" in video && video.videoWidth > 0 && video.videoHeight > 0) {
    return [video.videoWidth, video.videoHeight];
  }
  if (media.width > 0 && media.height > 0) {
    return [media.width, media.height];
  }
  return null;
}
function resolveMediaObjectFit(media, fallback) {
  if (typeof getComputedStyle !== "function") {
    return fallback;
  }
  const fit = getComputedStyle(media).objectFit;
  if (fit === "contain" || fit === "cover" || fit === "fill") {
    return fit;
  }
  return fallback;
}
function resolveRemoteDragLayout(input) {
  const { wrapperRect, mediaRect, media, targetSize, fitMode } = input;
  if (!wrapperRect.width || !wrapperRect.height || !mediaRect.width || !mediaRect.height) {
    return null;
  }
  const wrapper = toContentRect2(wrapperRect);
  if (fitMode === "contain") {
    const overlay2 = toContentRect2(mediaRect);
    const hitRect = intersectContentRects(overlay2, wrapper);
    const drawable2 = hitRect.width > 0 && hitRect.height > 0 ? hitRect : wrapper;
    return { overlay: drawable2, mapping: overlay2, hitRect: drawable2, source: "media" };
  }
  if (isMediaInsetInContainer2(mediaRect, wrapperRect)) {
    const overlay2 = toContentRect2(mediaRect);
    return { overlay: overlay2, mapping: overlay2, hitRect: overlay2, source: "media" };
  }
  const intrinsic = media ? readMediaIntrinsicSize(media) : null;
  const frameSize = intrinsic ?? targetSize;
  const objectFit = media ? resolveMediaObjectFit(media, fitMode) : fitMode;
  if (objectFit === "fill") {
    const overlay2 = toContentRect2(mediaRect);
    return { overlay: overlay2, mapping: overlay2, hitRect: wrapper, source: "intrinsic" };
  }
  const mapping = getFitContentRect(mediaRect, frameSize, objectFit);
  const overlay = intersectContentRects(mapping, wrapper);
  const drawable = overlay.width > 0 && overlay.height > 0 ? overlay : wrapper;
  return {
    overlay: drawable,
    mapping,
    hitRect: wrapper,
    source: intrinsic ? "intrinsic" : "fit"
  };
}
function resetDragSurfaceFullBleed(dragSurface) {
  dragSurface.style.inset = "0";
  dragSurface.style.left = "";
  dragSurface.style.top = "";
  dragSurface.style.right = "";
  dragSurface.style.bottom = "";
  dragSurface.style.width = "";
  dragSurface.style.height = "";
  dragSurface.removeAttribute(DRAG_SYNCED_ATTR);
}
function applyDragSurfaceOverlayStyles(dragSurface, overlay, wrapperRect) {
  const nextLeft = `${overlay.left - wrapperRect.left}px`;
  const nextTop = `${overlay.top - wrapperRect.top}px`;
  const nextWidth = `${overlay.width}px`;
  const nextHeight = `${overlay.height}px`;
  if (dragSurface.hasAttribute(DRAG_SYNCED_ATTR) && dragSurface.style.inset === "auto" && dragSurface.style.left === nextLeft && dragSurface.style.top === nextTop && dragSurface.style.width === nextWidth && dragSurface.style.height === nextHeight) {
    return false;
  }
  dragSurface.style.inset = "auto";
  dragSurface.style.left = nextLeft;
  dragSurface.style.top = nextTop;
  dragSurface.style.width = nextWidth;
  dragSurface.style.height = nextHeight;
  dragSurface.style.right = "";
  dragSurface.style.bottom = "";
  dragSurface.setAttribute(DRAG_SYNCED_ATTR, "");
  return true;
}
function syncDragSurfaceToVideo(dragSurface, targetSize, fitMode) {
  const wrapper = dragSurface.parentElement;
  if (!wrapper) {
    resetDragSurfaceFullBleed(dragSurface);
    return false;
  }
  const layout = resolveRemoteDragLayoutFromSurface(dragSurface, targetSize, fitMode);
  if (!layout || !layout.overlay.width || !layout.overlay.height) {
    resetDragSurfaceFullBleed(dragSurface);
    return false;
  }
  const wrapperRect = wrapper.getBoundingClientRect();
  const { overlay } = layout;
  return applyDragSurfaceOverlayStyles(dragSurface, overlay, wrapperRect);
}
function resolveRemoteDragLayoutFromSurface(dragSurface, targetSize, fitMode) {
  const wrapper = dragSurface.parentElement;
  if (!wrapper) {
    return null;
  }
  const videoHost = wrapper.querySelector("[data-xmax-remote-video]");
  if (!videoHost) {
    return null;
  }
  const media = videoHost.querySelector("video, canvas");
  if (!media) {
    return null;
  }
  return resolveRemoteDragLayout({
    wrapperRect: wrapper.getBoundingClientRect(),
    mediaRect: media.getBoundingClientRect(),
    media,
    targetSize,
    fitMode
  });
}
function observeDragSurfaceVideoSync(dragSurface, options) {
  const wrapper = dragSurface.parentElement;
  if (!wrapper) {
    return () => {
    };
  }
  const mediaListeners = /* @__PURE__ */ new Map();
  let rafId = null;
  let observedVideoHost = null;
  const bindMediaListeners = (media) => {
    if (mediaListeners.has(media)) {
      return;
    }
    const rerender = () => scheduleApply();
    const bindings = [];
    const add = (type) => {
      media.addEventListener(type, rerender);
      bindings.push(() => media.removeEventListener(type, rerender));
    };
    add("loadedmetadata");
    add("loadeddata");
    add("resize");
    mediaListeners.set(media, bindings);
  };
  const apply = () => {
    const changed = syncDragSurfaceToVideo(dragSurface, options.getTargetSize(), options.getFitMode());
    if (changed) {
      options.onSync?.();
    }
    const videoHost2 = wrapper.querySelector("[data-xmax-remote-video]");
    const media = videoHost2?.querySelector("video, canvas");
    if (media) {
      bindMediaListeners(media);
    }
  };
  const scheduleApply = () => {
    if (rafId !== null) {
      return;
    }
    rafId = requestAnimationFrame(() => {
      rafId = null;
      apply();
    });
  };
  const bindVideoHostObserver = (videoHostObserver) => {
    const host = wrapper.querySelector("[data-xmax-remote-video]");
    if (!host || host === observedVideoHost || !videoHostObserver) {
      return;
    }
    videoHostObserver.disconnect();
    observedVideoHost = host;
    videoHostObserver.observe(host, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["style", "class", "width", "height"]
    });
  };
  apply();
  const resizeObserver = typeof ResizeObserver !== "undefined" ? new ResizeObserver(() => scheduleApply()) : null;
  resizeObserver?.observe(wrapper);
  const videoHost = wrapper.querySelector("[data-xmax-remote-video]");
  if (videoHost) {
    resizeObserver?.observe(videoHost);
  }
  const observeMedia = () => {
    const host = wrapper.querySelector("[data-xmax-remote-video]");
    const media = host?.querySelector("video, canvas");
    if (media) {
      resizeObserver?.observe(media);
      bindMediaListeners(media);
    }
  };
  observeMedia();
  const videoHostMutationObserver = typeof MutationObserver !== "undefined" ? new MutationObserver(() => {
    observeMedia();
    scheduleApply();
  }) : null;
  bindVideoHostObserver(videoHostMutationObserver);
  const wrapperMutationObserver = typeof MutationObserver !== "undefined" ? new MutationObserver(() => {
    bindVideoHostObserver(videoHostMutationObserver);
    observeMedia();
    scheduleApply();
  }) : null;
  wrapperMutationObserver?.observe(wrapper, {
    childList: true,
    subtree: true
  });
  const onWindowChange = () => scheduleApply();
  window.addEventListener("resize", onWindowChange);
  window.addEventListener("scroll", onWindowChange, true);
  return () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    resizeObserver?.disconnect();
    wrapperMutationObserver?.disconnect();
    videoHostMutationObserver?.disconnect();
    for (const unbind of Array.from(mediaListeners.values())) {
      unbind.forEach((dispose) => dispose());
    }
    mediaListeners.clear();
    window.removeEventListener("resize", onWindowChange);
    window.removeEventListener("scroll", onWindowChange, true);
    resetDragSurfaceFullBleed(dragSurface);
  };
}

export { ACTIVE_STATUS, DEFAULT_CAMERA_REALTIME_SETTINGS, DEFAULT_REALTIME_STREAM_CONTENT_HINT, DEFAULT_REALTIME_STREAM_MAX_KBPS, PREVIEW_CONTAIN_ATTR, PREVIEW_COVER_ATTR, PREVIEW_OUTPUT_LAYOUT_ATTR, PREVIEW_UPLOAD_FIT_ATTR, PREVIEW_UPLOAD_LAYOUT_ATTR, REMOTE_FIRST_OUTPUT_TIMEOUT_MS, RtcManager, XMAX_OPEN_API_BASE_URLS, XMAX_OPEN_API_PRODUCTION_BASE_URL, XmaxOpenClient, applyUploadPreviewMediaLayout, classifyCameraAccessError, clearPrefetchedRemoteFile, createChangeConditionRtcRoomEvent, createDragTrackController, createImageFileStream, createMediaFileStream, createRemoteViewHost, createStartRtcRoomEvent, createStopRtcRoomEvent, createTaskUid, createTracksRtcRoomEvent, createXmaxClient, downloadRemoteFile, getCameraEnvironmentIssue, isCameraAccessError, isHeicImageFile, isImageMediaFile, isRemoteFilePrefetched, isVideoMediaFile, mapTargetPointToCanvas, mapViewportPointToCoordinateSpace, models, normalizeHeicImageFile, observeDragSurfaceVideoSync, observeUploadPreviewMediaLayout, prefetchRemoteFile, resolveDefaultCameraRealtimeSetting, resolveRefImageUrl, syncDragSurfaceToVideo };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map