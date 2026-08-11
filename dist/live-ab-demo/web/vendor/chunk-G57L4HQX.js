// src/i18n/en-US.ts
var enUS = {
  "errors.apiKeyEmpty": "apiKey cannot be empty",
  "errors.baseUrlEmpty": "baseUrl is required \u2014 pass XMAX_OPEN_API_PRODUCTION_BASE_URL for production",
  "errors.modelEmpty": "model cannot be empty",
  "errors.invalidJson": "Response is not valid JSON",
  "errors.invalidPayload": "Response payload is invalid",
  "errors.requestFailed": "Request failed",
  "errors.requestRetry": "Request failed. Please try again later.",
  "errors.requestTimeout": "Request timeout",
  "errors.invalidFile": "Upload failed. Please select the file again and try again.",
  "errors.invalidFileType": "Upload failed. This file type is not supported.",
  "errors.sessionJoinInfoIncomplete": "session does not contain complete RTC join info",
  "errors.sessionUidMissing": "session does not contain sessionUid",
  "errors.refImageMissing": "missing reference image",
  "errors.imageCheckMissingUrl": "image check response missing url",
  "errors.imageCheckUnsafe": "image did not pass safety check",
  "errors.captureStreamUnsupported": "captureStream is not supported in this browser",
  "errors.videoTrackMissing": "failed to create video track from file",
  "errors.imageTrackMissing": "failed to create video track from image file",
  "errors.imageLoadFailed": "failed to load image \u2014 try again after selecting the file",
  "errors.invalidMediaFileType": "unsupported media file type: {type}",
  "errors.videoPlaybackFailed": "failed to start video playback \u2014 try again after selecting the file",
  "errors.rtcNotJoined": "Please join the RTC room first",
  "errors.rtcNotJoinedForMessaging": "Please join the RTC room before sending events",
  "errors.systemOverloaded": "Network connection failed. Please try again.",
  "rtc.alreadyInRoom": "RTC is already in the target room. Skip duplicate join.",
  "rtc.joiningRoom": "Joining RTC room",
  "rtc.joinSuccess": "RTC joinRoom succeeded",
  "rtc.roomUsers": "Current room users: {users}",
  "rtc.localVideoAlreadyPublished": "Local video is already published",
  "rtc.localVideoPublished": "Local video capture started and stream published",
  "rtc.externalVideoPublished": "External video stream published",
  "rtc.localVideoStopped": "Local video publishing stopped",
  "rtc.leaveRoomError": "Error occurred during RTC leaveRoom",
  "rtc.engineDestroyed": "RTC engine destroyed",
  "rtc.roomEventSent": "RTC event sent",
  "rtc.remotePlayerRefreshed": "Remote video player refreshed: {userId}",
  "rtc.remotePlayerRefreshFailed": "Failed to refresh remote video player",
  "rtc.userJoined": "User joined RTC room: {userId}",
  "rtc.userLeft": "User left RTC room: {userId}",
  "rtc.connectionStateChanged": "RTC connection state changed",
  "rtc.userPublished": "User published stream: {userId}",
  "rtc.userUnpublished": "User unpublished stream: {userId}",
  "rtc.seiReceived": "Remote SEI received: {userId}",
  "rtc.error": "RTC error: {code}",
  "rtc.captureSizeSet": "Local video capture size set: {width} x {height}",
  "rtc.encoderPreferenceSet": "Video encoder preference set to H.264",
  "rtc.encoderPreferenceFailed": "Failed to set video encoder preference",
  "rtc.remoteWaitSei": "Remote video is waiting for SEI gate: {userId}",
  "rtc.remoteContainerNotReady": "Remote video container is not ready. Skip binding.",
  "rtc.remotePlayerBound": "Remote video player bound: {userId}",
  "rtc.remoteOutputStalled": "Remote output stalled for 15s; attempting to recover generation",
  "rtc.sendSeiFailed": "Failed to send SEI. The browser or encoder config may not support it.",
  "rtc.seiUnsupported": "H.264 is not supported. SEI gate will be disabled and output will not be blocked.",
  "rtc.seiGateFallback": "SEI gate timed out \u2014 showing remote output",
  "rtc.getCodecsFailed": "Failed to get supported codecs. SEI gate will be disabled and output will not be blocked."
};

// src/i18n/zh-CN.ts
var zhCN = {
  "errors.apiKeyEmpty": "apiKey \u4E0D\u80FD\u4E3A\u7A7A",
  "errors.baseUrlEmpty": "baseUrl \u4E3A\u5FC5\u586B\u9879 \u2014 \u751F\u4EA7\u73AF\u5883\u8BF7\u4F20\u5165 XMAX_OPEN_API_PRODUCTION_BASE_URL",
  "errors.modelEmpty": "model \u4E0D\u80FD\u4E3A\u7A7A",
  "errors.invalidJson": "\u54CD\u5E94\u4E0D\u662F\u6709\u6548\u7684 JSON",
  "errors.invalidPayload": "\u54CD\u5E94\u6570\u636E\u683C\u5F0F\u4E0D\u6B63\u786E",
  "errors.requestFailed": "\u8BF7\u6C42\u5931\u8D25",
  "errors.requestRetry": "\u8BF7\u6C42\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5",
  "errors.requestTimeout": "\u8BF7\u6C42\u8D85\u65F6",
  "errors.invalidFile": "\u4E0A\u4F20\u5931\u8D25\uFF1A\u6587\u4EF6\u65E0\u6548\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9\u540E\u518D\u8BD5",
  "errors.invalidFileType": "\u4E0A\u4F20\u5931\u8D25\uFF1A\u6587\u4EF6\u683C\u5F0F\u4E0D\u652F\u6301\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9",
  "errors.sessionJoinInfoIncomplete": "session \u7F3A\u5C11\u5B8C\u6574\u7684 RTC \u8FDB\u623F\u4FE1\u606F",
  "errors.sessionUidMissing": "session \u7F3A\u5C11 sessionUid",
  "errors.refImageMissing": "\u7F3A\u5C11\u53C2\u8003\u56FE",
  "errors.imageCheckMissingUrl": "\u56FE\u7247\u68C0\u67E5\u54CD\u5E94\u7F3A\u5C11 url",
  "errors.imageCheckUnsafe": "\u56FE\u7247\u672A\u901A\u8FC7\u5B89\u5168\u68C0\u67E5",
  "errors.captureStreamUnsupported": "\u5F53\u524D\u6D4F\u89C8\u5668\u4E0D\u652F\u6301 captureStream",
  "errors.videoTrackMissing": "\u672A\u80FD\u4ECE\u89C6\u9891\u6587\u4EF6\u521B\u5EFA video track",
  "errors.imageTrackMissing": "\u672A\u80FD\u4ECE\u56FE\u7247\u6587\u4EF6\u521B\u5EFA video track",
  "errors.imageLoadFailed": "\u56FE\u7247\u65E0\u6CD5\u52A0\u8F7D\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9\u6587\u4EF6\u540E\u518D\u8BD5",
  "errors.invalidMediaFileType": "\u4E0D\u652F\u6301\u7684\u5A92\u4F53\u6587\u4EF6\u7C7B\u578B\uFF1A{type}",
  "errors.videoPlaybackFailed": "\u89C6\u9891\u65E0\u6CD5\u5F00\u59CB\u64AD\u653E\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9\u6587\u4EF6\u540E\u518D\u8BD5",
  "errors.rtcNotJoined": "\u8BF7\u5148\u6210\u529F\u52A0\u5165 RTC \u623F\u95F4",
  "errors.rtcNotJoinedForMessaging": "\u8BF7\u5148\u6210\u529F\u52A0\u5165 RTC \u623F\u95F4\u540E\u518D\u53D1\u9001\u4E8B\u4EF6",
  "errors.systemOverloaded": "\u7F51\u7EDC\u8FDE\u63A5\u5931\u8D25\uFF0C\u8BF7\u91CD\u8BD5",
  "rtc.alreadyInRoom": "RTC \u5DF2\u5728\u76EE\u6807\u623F\u95F4\u4E2D\uFF0C\u8DF3\u8FC7\u91CD\u590D\u8FDB\u623F",
  "rtc.joiningRoom": "\u51C6\u5907\u52A0\u5165 RTC \u623F\u95F4",
  "rtc.joinSuccess": "RTC joinRoom \u6210\u529F",
  "rtc.roomUsers": "\u5F53\u524D\u623F\u95F4\u7528\u6237: {users}",
  "rtc.localVideoAlreadyPublished": "\u672C\u5730\u89C6\u9891\u5DF2\u5904\u4E8E\u53D1\u5E03\u72B6\u6001",
  "rtc.localVideoPublished": "\u5DF2\u5F00\u542F\u672C\u5730\u89C6\u9891\u91C7\u96C6\u5E76\u53D1\u5E03\u89C6\u9891\u6D41",
  "rtc.externalVideoPublished": "\u5DF2\u53D1\u5E03\u81EA\u5B9A\u4E49\u89C6\u9891\u6D41",
  "rtc.localVideoStopped": "\u5DF2\u505C\u6B62\u672C\u5730\u89C6\u9891\u53D1\u5E03",
  "rtc.leaveRoomError": "RTC leaveRoom \u8FC7\u7A0B\u4E2D\u51FA\u73B0\u5F02\u5E38",
  "rtc.engineDestroyed": "RTC \u5F15\u64CE\u5DF2\u9500\u6BC1",
  "rtc.roomEventSent": "\u5DF2\u53D1\u9001 RTC \u4E8B\u4EF6",
  "rtc.remotePlayerRefreshed": "\u5DF2\u5237\u65B0\u8FDC\u7AEF\u89C6\u9891\u64AD\u653E\u5668: {userId}",
  "rtc.remotePlayerRefreshFailed": "\u5237\u65B0\u8FDC\u7AEF\u89C6\u9891\u64AD\u653E\u5668\u5931\u8D25",
  "rtc.userJoined": "\u7528\u6237\u52A0\u5165 RTC \u623F\u95F4: {userId}",
  "rtc.userLeft": "\u7528\u6237\u79BB\u5F00 RTC \u623F\u95F4: {userId}",
  "rtc.connectionStateChanged": "RTC \u8FDE\u63A5\u72B6\u6001\u53D8\u5316",
  "rtc.userPublished": "\u7528\u6237\u53D1\u5E03\u6D41: {userId}",
  "rtc.userUnpublished": "\u7528\u6237\u53D6\u6D88\u53D1\u5E03\u6D41: {userId}",
  "rtc.seiReceived": "\u6536\u5230\u8FDC\u7AEF SEI: {userId}",
  "rtc.error": "RTC \u9519\u8BEF: {code}",
  "rtc.captureSizeSet": "\u5DF2\u8BBE\u7F6E\u672C\u5730\u89C6\u9891\u91C7\u96C6\u5C3A\u5BF8: {width} x {height}",
  "rtc.encoderPreferenceSet": "\u5DF2\u8BBE\u7F6E\u89C6\u9891\u7F16\u7801\u504F\u597D\u4E3A H.264",
  "rtc.encoderPreferenceFailed": "\u8BBE\u7F6E\u89C6\u9891\u7F16\u7801\u504F\u597D\u5931\u8D25",
  "rtc.remoteWaitSei": "\u8FDC\u7AEF\u89C6\u9891\u7B49\u5F85 SEI \u653E\u884C: {userId}",
  "rtc.remoteContainerNotReady": "\u8FDC\u7AEF\u89C6\u9891\u5BB9\u5668\u672A\u5C31\u7EEA\uFF0C\u8DF3\u8FC7\u7ED1\u5B9A",
  "rtc.remotePlayerBound": "\u5DF2\u7ED1\u5B9A\u8FDC\u7AEF\u89C6\u9891\u64AD\u653E\u5668: {userId}",
  "rtc.remoteOutputStalled": "\u8FDC\u7AEF\u8F93\u51FA\u8D85\u8FC7 15 \u79D2\u65E0\u65B0\u5E27\uFF0C\u5C1D\u8BD5\u6062\u590D\u751F\u6210\u4EFB\u52A1",
  "rtc.sendSeiFailed": "\u53D1\u9001 SEI \u5931\u8D25\uFF0C\u5F53\u524D\u6D4F\u89C8\u5668\u6216\u7F16\u7801\u914D\u7F6E\u53EF\u80FD\u4E0D\u652F\u6301\u8BE5\u80FD\u529B",
  "rtc.seiUnsupported": "\u5F53\u524D\u73AF\u5883\u4E0D\u652F\u6301 H.264\uFF0CSEI gate \u5C06\u4E0D\u4F1A\u751F\u6548\uFF0Coutput \u5C06\u4E0D\u518D\u88AB\u62E6\u622A",
  "rtc.seiGateFallback": "SEI \u95E8\u63A7\u8D85\u65F6\uFF0C\u5DF2\u663E\u793A\u8FDC\u7AEF\u8F93\u51FA",
  "rtc.getCodecsFailed": "\u83B7\u53D6\u6D4F\u89C8\u5668\u7F16\u89E3\u7801\u652F\u6301\u5931\u8D25\uFF0CSEI gate \u5C06\u4E0D\u4F1A\u751F\u6548\uFF0Coutput \u5C06\u4E0D\u518D\u88AB\u62E6\u622A"
};

// src/i18n/api-error-codes.ts
var SYSTEM_OVERLOADED = {
  "zh-CN": "\u5F53\u524D\u4F7F\u7528\u4EBA\u6570\u8FC7\u591A\uFF0C\u8BF7\u7A0D\u540E\u518D\u8BD5",
  "en-US": "The system is currently overloaded. Please retry after some time."
};
var CONNECTION_FAILED = {
  "zh-CN": "\u8FDE\u63A5\u670D\u52A1\u5668\u5931\u8D25\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5",
  "en-US": "Failed to connect to the server. Please try again later."
};
var API_ERROR_MESSAGES = {
  "46001": { "zh-CN": "X-Api-Key \u4E0D\u80FD\u4E3A\u7A7A", "en-US": "X-Api-Key cannot be empty" },
  "46002": { "zh-CN": "\u65E0\u6548\u7684\u7528\u6237 API Key", "en-US": "Invalid user API Key" },
  "46003": { "zh-CN": "model \u4E0D\u80FD\u4E3A\u7A7A", "en-US": "model cannot be empty" },
  "46004": { "zh-CN": "sessionUid \u4E0D\u80FD\u4E3A\u7A7A", "en-US": "sessionUid cannot be empty" },
  "46005": { "zh-CN": "\u6A21\u578B\u7C7B\u578B\u4E0D\u5B58\u5728", "en-US": "Model type does not exist" },
  "46006": SYSTEM_OVERLOADED,
  "46007": SYSTEM_OVERLOADED,
  "46008": SYSTEM_OVERLOADED,
  "46009": CONNECTION_FAILED,
  "46010": CONNECTION_FAILED,
  "46012": { "zh-CN": "\u4F1A\u8BDD\u4E0D\u5B58\u5728", "en-US": "Session does not exist" },
  "46013": { "zh-CN": "\u4F1A\u8BDD\u4E0D\u5C5E\u4E8E\u5F53\u524D\u7528\u6237", "en-US": "Session does not belong to the current user" },
  "46014": { "zh-CN": "\u4F1A\u8BDD\u5DF2\u5173\u95ED", "en-US": "Session has been closed" },
  "46015": { "zh-CN": "\u4F1A\u8BDD\u5DF2\u8D85\u65F6", "en-US": "Session has timed out" },
  "46018": { "zh-CN": "\u4E34\u65F6 API Key \u5DF2\u8FC7\u671F", "en-US": "Temporary API Key has expired" },
  "46019": {
    "zh-CN": "\u4E34\u65F6 API Key \u5DF2\u8FBE\u5230\u79EF\u5206\u4E0A\u9650",
    "en-US": "Temporary API Key has reached its points limit"
  },
  "46021": {
    "zh-CN": "\u4E34\u65F6 API Key \u4E0D\u5141\u8BB8\u518D\u521B\u5EFA\u4E34\u65F6 API Key",
    "en-US": "A temporary API Key cannot create another temporary API Key"
  }
};
function resolveApiErrorMessage(code, locale) {
  if (code === null || code === void 0) return void 0;
  const entry = API_ERROR_MESSAGES[String(code)];
  if (!entry) return void 0;
  return entry[locale] ?? entry["en-US"];
}

// src/i18n/index.ts
function formatTemplate(template, params) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, rawKey) => {
    const value = params[rawKey];
    return value === null || value === void 0 ? "" : String(value);
  });
}
function getDefaultMessages(locale) {
  return locale === "zh-CN" ? zhCN : enUS;
}
function createSDKI18n(input) {
  const locale = input?.locale ?? "en-US";
  if (typeof input?.t === "function") {
    return { locale, t: input.t };
  }
  const base = getDefaultMessages(locale);
  const merged = { ...base, ...input?.messages ?? {} };
  return {
    locale,
    t: (key, params) => {
      const template = merged[key] ?? key;
      return formatTemplate(template, params);
    }
  };
}

// src/rtc/media/publish-fps.ts
var MOBILE_PUBLISH_MAX_WIDTH_PX = 768;
var RTC_PUBLISH_FPS_WEB = 30;
var RTC_PUBLISH_FPS_MOBILE = 24;
function isMobilePublishEnvironment() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(`(max-width: ${MOBILE_PUBLISH_MAX_WIDTH_PX}px)`).matches;
}
function resolveRtcPublishFps(options = {}) {
  if (typeof options.fps === "number" && Number.isFinite(options.fps) && options.fps > 0) {
    return options.fps;
  }
  const mobile = options.mobile ?? isMobilePublishEnvironment();
  return mobile ? RTC_PUBLISH_FPS_MOBILE : RTC_PUBLISH_FPS_WEB;
}
function resolveRtcPublishFrameIntervalS(options) {
  return 1 / resolveRtcPublishFps(options);
}
var RTC_PUBLISH_FRAME_INTERVAL_S = 1 / RTC_PUBLISH_FPS_WEB;
var RTC_PUBLISH_FRAME_INTERVAL_MS = 1e3 / RTC_PUBLISH_FPS_WEB;
var MEDIA_TIME_EPSILON_S = 1e-3;
var MEDIA_TIME_LOOP_JUMP_S = 0.05;

// src/rtc/media/reference-video-size.ts
var PREVIEW_CONTAINER_ASPECT_RATIO = 16 / 9;
function resolvePreviewAspectRatio(size) {
  return `${size[0]} / ${size[1]}`;
}
var DEFAULT_SESSION_TARGET_SIZE = [1472, 832];
var UPLOAD_SIZE_ALIGN = 32;
var MIN_UPLOAD_VIDEO_PIXELS = 6e5;
var MAX_UPLOAD_VIDEO_PIXELS = 128e4;
function alignToSizeMultiple(value) {
  return Math.max(UPLOAD_SIZE_ALIGN, Math.round(value / UPLOAD_SIZE_ALIGN) * UPLOAD_SIZE_ALIGN);
}
function alignUpToSizeMultiple(value) {
  return Math.max(UPLOAD_SIZE_ALIGN, Math.ceil(value / UPLOAD_SIZE_ALIGN) * UPLOAD_SIZE_ALIGN);
}
function alignDownToSizeMultiple(value) {
  return Math.max(UPLOAD_SIZE_ALIGN, Math.floor(value / UPLOAD_SIZE_ALIGN) * UPLOAD_SIZE_ALIGN);
}
function makeEven(value) {
  const rounded = Math.max(2, Math.round(value));
  return rounded % 2 === 0 ? rounded : rounded - 1;
}
function resolveUploadPublishSize(sourceWidth, sourceHeight) {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    return DEFAULT_SESSION_TARGET_SIZE;
  }
  return [makeEven(sourceWidth), makeEven(sourceHeight)];
}
function resolveAdaptiveRtcVideoSize(sourceWidth, sourceHeight, baseSize = DEFAULT_SESSION_TARGET_SIZE) {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    return baseSize;
  }
  const [baseWidth, baseHeight] = baseSize;
  const sourceAspectRatio = sourceHeight / sourceWidth;
  const baseAspectRatio = baseHeight / baseWidth;
  if (sourceAspectRatio >= baseAspectRatio) {
    return [baseWidth, baseHeight];
  }
  const adaptiveHeight = Math.max(
    UPLOAD_SIZE_ALIGN,
    Math.round(baseWidth * sourceAspectRatio)
  );
  return [baseWidth, makeEven(adaptiveHeight)];
}
function resolveUploadVideoSize(sourceWidth, sourceHeight) {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    return DEFAULT_SESSION_TARGET_SIZE;
  }
  const sourcePixels = sourceWidth * sourceHeight;
  let size;
  if (sourcePixels < MIN_UPLOAD_VIDEO_PIXELS) {
    const scale = Math.sqrt(MIN_UPLOAD_VIDEO_PIXELS / sourcePixels);
    size = [
      alignUpToSizeMultiple(sourceWidth * scale),
      alignUpToSizeMultiple(sourceHeight * scale)
    ];
  } else if (sourcePixels > MAX_UPLOAD_VIDEO_PIXELS) {
    const scale = Math.sqrt(MAX_UPLOAD_VIDEO_PIXELS / sourcePixels);
    size = [
      alignDownToSizeMultiple(sourceWidth * scale),
      alignDownToSizeMultiple(sourceHeight * scale)
    ];
  } else {
    size = [
      alignToSizeMultiple(sourceWidth),
      alignToSizeMultiple(sourceHeight)
    ];
  }
  const alignedPixels = size[0] * size[1];
  if (alignedPixels <= MIN_UPLOAD_VIDEO_PIXELS) {
    const scale = Math.sqrt(MIN_UPLOAD_VIDEO_PIXELS / sourcePixels);
    return [
      alignUpToSizeMultiple(sourceWidth * scale),
      alignUpToSizeMultiple(sourceHeight * scale)
    ];
  }
  if (alignedPixels >= MAX_UPLOAD_VIDEO_PIXELS) {
    const scale = Math.sqrt(MAX_UPLOAD_VIDEO_PIXELS / sourcePixels);
    const constrained = [
      alignDownToSizeMultiple(sourceWidth * scale),
      alignDownToSizeMultiple(sourceHeight * scale)
    ];
    if (constrained[0] * constrained[1] >= MAX_UPLOAD_VIDEO_PIXELS) {
      if (constrained[0] >= constrained[1]) {
        constrained[0] = Math.max(UPLOAD_SIZE_ALIGN, constrained[0] - UPLOAD_SIZE_ALIGN);
      } else {
        constrained[1] = Math.max(UPLOAD_SIZE_ALIGN, constrained[1] - UPLOAD_SIZE_ALIGN);
      }
    }
    return constrained;
  }
  return size;
}
function resolveSessionTargetSize(input) {
  if (input.overrideSize) {
    return input.overrideSize;
  }
  if (input.localVideoSize?.width && input.localVideoSize?.height) {
    return [input.localVideoSize.width, input.localVideoSize.height];
  }
  return DEFAULT_SESSION_TARGET_SIZE;
}

// src/rtc/canvas/canvas-frame-draw.ts
function drawSourceCover(ctx, source, outputWidth, outputHeight, sourceWidth, sourceHeight, backgroundColor = "#000000") {
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.clearRect(0, 0, outputWidth, outputHeight);
  ctx.fillStyle = "#000000";
  if (backgroundColor.trim()) {
    ctx.fillStyle = backgroundColor;
  }
  ctx.fillRect(0, 0, outputWidth, outputHeight);
  const scale = Math.max(outputWidth / sourceWidth, outputHeight / sourceHeight);
  const width = sourceWidth * scale;
  const height = sourceHeight * scale;
  const x = (outputWidth - width) / 2;
  const y = (outputHeight - height) / 2;
  ctx.drawImage(source, 0, 0, sourceWidth, sourceHeight, x, y, width, height);
}
function createCanvasPosterUrl(canvas, options = {}) {
  if (typeof canvas.toBlob !== "function") {
    return Promise.resolve(null);
  }
  const type = options.type ?? "image/png";
  return new Promise((resolve) => {
    try {
      canvas.toBlob((blob) => {
        if (!blob) {
          resolve(null);
          return;
        }
        try {
          resolve(URL.createObjectURL(blob));
        } catch {
          resolve(null);
        }
      }, type, options.quality);
    } catch {
      resolve(null);
    }
  });
}

// src/rtc/render/capture-host.ts
var captureHostRoot = null;
var ANDROID_HOST_STYLE = "position:fixed;left:0;top:0;width:1px;height:1px;overflow:hidden;opacity:1;pointer-events:none;z-index:2147483647;";
var ANDROID_VIDEO_STYLE = "position:absolute;left:0;top:0;width:16px;height:16px;opacity:1;pointer-events:none;object-fit:cover;";
var ANDROID_CANVAS_STYLE = "position:absolute;left:0;top:0;width:1px;height:1px;opacity:1;pointer-events:none;";
var DESKTOP_HOST_STYLE = "position:fixed;left:0;top:0;width:0;height:0;overflow:hidden;pointer-events:none;z-index:-1;";
var DESKTOP_VIDEO_STYLE = "position:fixed;left:-10000px;top:0;width:640px;height:480px;opacity:1;pointer-events:none;z-index:-1;";
function isAndroidCaptureRuntime() {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}
function getCaptureHost() {
  if (!captureHostRoot) {
    captureHostRoot = document.createElement("div");
    captureHostRoot.setAttribute("data-xmax-capture-host", "true");
    captureHostRoot.style.cssText = isAndroidCaptureRuntime() ? ANDROID_HOST_STYLE : DESKTOP_HOST_STYLE;
    document.body.appendChild(captureHostRoot);
  }
  return captureHostRoot;
}
function mountCaptureVideo(videoEl) {
  const android = isAndroidCaptureRuntime();
  videoEl.setAttribute("playsinline", "true");
  videoEl.setAttribute("webkit-playsinline", "true");
  if (android) {
    videoEl.setAttribute("x5-playsinline", "true");
    videoEl.setAttribute("x5-video-player-type", "h5");
    videoEl.setAttribute("x5-video-player-fullscreen", "false");
    videoEl.setAttribute("muted", "");
    videoEl.setAttribute("preload", "auto");
  }
  videoEl.style.cssText = android ? ANDROID_VIDEO_STYLE : DESKTOP_VIDEO_STYLE;
  getCaptureHost().appendChild(videoEl);
}
function mountCaptureCanvas(canvasEl) {
  if (!isAndroidCaptureRuntime()) {
    return;
  }
  canvasEl.style.cssText = ANDROID_CANVAS_STYLE;
  getCaptureHost().appendChild(canvasEl);
}

// src/rtc/media/video-frame-rate.ts
var COMMON_VIDEO_FPS = [24, 25, 30, 48, 50, 60];
function median(values) {
  if (values.length === 0) {
    return 30;
  }
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[mid - 1] + sorted[mid]) / 2;
  }
  return sorted[mid];
}
function snapToCommonVideoFps(fps) {
  if (!Number.isFinite(fps) || fps <= 0) {
    return 30;
  }
  const clamped = Math.max(1, Math.min(120, fps));
  let best = 30;
  let bestDiff = Infinity;
  for (const candidate of COMMON_VIDEO_FPS) {
    const diff = Math.abs(clamped - candidate);
    if (diff < bestDiff || diff === bestDiff && candidate < best) {
      bestDiff = diff;
      best = candidate;
    }
  }
  return best;
}
function snapToCommonVideoFpsConservative(fps) {
  if (!Number.isFinite(fps) || fps <= 0) {
    return 30;
  }
  const snapped = snapToCommonVideoFps(fps);
  if (snapped <= fps + 0.5) {
    return snapped;
  }
  const lowerCandidates = COMMON_VIDEO_FPS.filter((candidate) => candidate < snapped);
  if (lowerCandidates.length > 0) {
    return lowerCandidates[lowerCandidates.length - 1];
  }
  return snapped;
}
async function estimateVideoFrameRate(videoEl, options = {}) {
  const timeoutMs = options.timeoutMs ?? 3e3;
  const sampleDurationMs = options.sampleDurationMs ?? 900;
  const fallbackFps = options.fallbackFps ?? 30;
  const video = videoEl;
  if (!video.requestVideoFrameCallback) {
    return fallbackFps;
  }
  return new Promise((resolve) => {
    let settled = false;
    let startWallMs = 0;
    let startPresented = 0;
    const deltas = [];
    let lastMediaTime = -1;
    const finish = (rawFps) => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      resolve(snapToCommonVideoFpsConservative(rawFps));
    };
    const timer = setTimeout(() => {
      if (startWallMs > 0) {
        finish(fallbackFps);
        return;
      }
      if (deltas.length > 0) {
        finish(median(deltas.map((delta) => 1 / delta)));
        return;
      }
      finish(fallbackFps);
    }, timeoutMs);
    const schedule = () => {
      if (settled) {
        return;
      }
      video.requestVideoFrameCallback((now, metadata) => {
        if (lastMediaTime >= 0) {
          const delta = metadata.mediaTime - lastMediaTime;
          if (delta > 1e-3 && delta < 0.5) {
            deltas.push(delta);
          }
        }
        lastMediaTime = metadata.mediaTime;
        if (startWallMs === 0) {
          startWallMs = now;
          startPresented = metadata.presentedFrames;
          schedule();
          return;
        }
        const elapsedMs = now - startWallMs;
        if (elapsedMs >= sampleDurationMs) {
          const frameCount = metadata.presentedFrames - startPresented;
          if (frameCount > 0) {
            finish(frameCount / (elapsedMs / 1e3));
            return;
          }
        }
        schedule();
      });
    };
    schedule();
  });
}
function resolveTrackFrameRate(track, fallback) {
  const settings = track.getSettings?.();
  if (typeof settings?.frameRate === "number" && settings.frameRate > 0) {
    return snapToCommonVideoFpsConservative(settings.frameRate);
  }
  return snapToCommonVideoFpsConservative(fallback);
}
function resolvePlaybackDrivenEncoderFps(track, fallback = 24) {
  return resolveTrackFrameRate(track, fallback);
}

// src/rtc/media/video-file-stream.ts
var STALL_CATCHUP_MS = 1500;
var MEDIA_READY_TIMEOUT_MS = 8e3;
var RVFC_STALL_FALLBACK_MS = 400;
function isAndroidRuntime() {
  return typeof navigator !== "undefined" && /Android/i.test(navigator.userAgent);
}
function isAppleMobileRuntime() {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
}
function shouldSampleAtMediaTime(lastMediaTimeS, mediaTimeS, frameIntervalS) {
  if (!Number.isFinite(mediaTimeS) || mediaTimeS < 0) {
    return false;
  }
  if (lastMediaTimeS < 0) {
    return true;
  }
  if (mediaTimeS + MEDIA_TIME_LOOP_JUMP_S < lastMediaTimeS) {
    return true;
  }
  const minIntervalS = Math.max(0, frameIntervalS - MEDIA_TIME_EPSILON_S);
  return mediaTimeS - lastMediaTimeS >= minIntervalS;
}
async function applyPublishTrackConstraints(track, width, height) {
  if (typeof track.applyConstraints !== "function") {
    return;
  }
  try {
    await track.applyConstraints({
      width: { ideal: width, max: width },
      height: { ideal: height, max: height }
    });
  } catch {
  }
}
async function createVideoFileStream(fileOrUrl, options = {}) {
  const i18n = options.i18n ?? createSDKI18n();
  const mobile = isAndroidRuntime() || isAppleMobileRuntime() || (options.mobile ?? isMobilePublishEnvironment());
  const isUrl = typeof fileOrUrl === "string";
  const url = isUrl ? fileOrUrl : URL.createObjectURL(fileOrUrl);
  const videoEl = document.createElement("video");
  videoEl.muted = options.muted ?? true;
  videoEl.playsInline = true;
  if (isUrl) {
    videoEl.crossOrigin = "anonymous";
  }
  videoEl.src = url;
  videoEl.loop = true;
  videoEl.autoplay = true;
  mountCaptureVideo(videoEl);
  try {
    videoEl.load();
    await waitForEvent(videoEl, "loadedmetadata", MEDIA_READY_TIMEOUT_MS);
    if (!isAndroidRuntime()) {
      await waitForCanPlay(videoEl, MEDIA_READY_TIMEOUT_MS);
    }
  } catch (error) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw error;
  }
  if (typeof options.playbackRate === "number") {
    videoEl.playbackRate = options.playbackRate;
  }
  await startVideoPlayback(videoEl, i18n);
  const sourceWidth = videoEl.videoWidth || 0;
  const sourceHeight = videoEl.videoHeight || 0;
  if (!sourceWidth || !sourceHeight) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.videoTrackMissing"));
  }
  const measuredFps = typeof options.fps === "number" && options.fps > 0 ? options.fps : mobile ? resolveRtcPublishFps({ mobile: true }) : await estimateVideoFrameRate(videoEl);
  const [outputWidth, outputHeight] = options.targetSize ?? resolveUploadVideoSize(sourceWidth, sourceHeight);
  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const ctx = canvas.getContext("2d", { alpha: false });
  if (!ctx) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.captureStreamUnsupported"));
  }
  const captureStreamFn = canvas.captureStream ?? canvas.mozCaptureStream;
  if (!captureStreamFn) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.captureStreamUnsupported"));
  }
  mountCaptureCanvas(canvas);
  const streamFps = resolveRtcPublishFps({ mobile, fps: options.fps });
  const previewStream = captureStreamFn.call(canvas, streamFps);
  const videoTrack = previewStream.getVideoTracks()[0];
  const webAudioCleanupRef = { current: null };
  const shouldCaptureUploadAudio = !mobile;
  let audioTrack;
  if (shouldCaptureUploadAudio) {
    audioTrack = await resolveUploadAudioTrack(videoEl, webAudioCleanupRef);
    if (audioTrack && previewStream.getAudioTracks().length === 0) {
      const attachedAudioTrack = typeof audioTrack.clone === "function" ? audioTrack.clone() : audioTrack;
      previewStream.addTrack(attachedAudioTrack);
      audioTrack = attachedAudioTrack;
    }
  }
  if (!videoTrack) {
    if (!isUrl) URL.revokeObjectURL(url);
    throw new Error(i18n.t("errors.videoTrackMissing"));
  }
  const frameIntervalS = resolveRtcPublishFrameIntervalS({ mobile, fps: streamFps });
  const publishFps = resolvePlaybackDrivenEncoderFps(videoTrack, measuredFps);
  await applyPublishTrackConstraints(videoTrack, outputWidth, outputHeight);
  let destroyed = false;
  let lastAdvanceAt = Date.now();
  let lastDrawMediaTimeS = -1;
  let lastSampleWallMs = 0;
  let videoFrameCallbackId = null;
  let rafId = null;
  let rvfcStallTimer = null;
  let usingRvfc = false;
  const drawFrame = () => {
    if (destroyed) {
      return;
    }
    try {
      drawSourceCover(ctx, videoEl, outputWidth, outputHeight, sourceWidth, sourceHeight, options.backgroundColor);
    } catch {
    }
  };
  const onPlaybackSample = (mediaTimeS) => {
    if (destroyed || !shouldSampleAtMediaTime(lastDrawMediaTimeS, mediaTimeS, frameIntervalS)) {
      return;
    }
    lastDrawMediaTimeS = mediaTimeS;
    lastAdvanceAt = Date.now();
    lastSampleWallMs = performance.now();
    drawFrame();
  };
  const scheduleRafWatch = () => {
    if (destroyed || rafId !== null) {
      return;
    }
    const tick = () => {
      rafId = null;
      if (destroyed) return;
      if (!usingRvfc || performance.now() - lastSampleWallMs >= RVFC_STALL_FALLBACK_MS) {
        onPlaybackSample(videoEl.currentTime);
      }
      rafId = window.requestAnimationFrame(tick);
    };
    rafId = window.requestAnimationFrame(tick);
  };
  const scheduleRvfcWatch = () => {
    if (destroyed) return;
    const video = videoEl;
    if (!video.requestVideoFrameCallback) return;
    usingRvfc = true;
    videoFrameCallbackId = video.requestVideoFrameCallback((_now, metadata) => {
      videoFrameCallbackId = null;
      onPlaybackSample(metadata.mediaTime);
      if (rvfcStallTimer !== null) clearTimeout(rvfcStallTimer);
      scheduleRvfcWatch();
      rvfcStallTimer = setTimeout(() => {
        usingRvfc = false;
        scheduleRafWatch();
      }, RVFC_STALL_FALLBACK_MS);
    });
  };
  const schedulePlaybackWatch = () => {
    scheduleRafWatch();
    if (!mobile) scheduleRvfcWatch();
  };
  drawFrame();
  schedulePlaybackWatch();
  const ensurePlaying = () => {
    if (destroyed) {
      return;
    }
    if (videoEl.ended && videoEl.loop) {
      videoEl.currentTime = 0;
      lastDrawMediaTimeS = -1;
    }
    if (videoEl.paused) {
      void videoEl.play().catch(() => void 0);
    }
  };
  videoEl.addEventListener("pause", ensurePlaying);
  videoEl.addEventListener("ended", ensurePlaying);
  videoEl.addEventListener("stalled", ensurePlaying);
  videoEl.addEventListener("waiting", ensurePlaying);
  const healthIntervalMs = options.healthIntervalMs ?? 3e3;
  let healthTimer = null;
  if (options.onHealthReport) {
    const reportHealth = options.onHealthReport;
    healthTimer = setInterval(() => {
      ensurePlaying();
      const now = Date.now();
      const currentTime = videoEl.currentTime;
      const duration = videoEl.duration;
      const nearEnd = duration > 0 && currentTime >= duration - 0.2;
      const stalled = !videoEl.paused && !videoEl.ended && !nearEnd && now - lastAdvanceAt >= healthIntervalMs;
      if (stalled && now - lastAdvanceAt >= STALL_CATCHUP_MS) {
        void videoEl.play().catch(() => void 0);
      }
      reportHealth({
        currentTime,
        duration,
        paused: videoEl.paused,
        ended: videoEl.ended,
        readyState: videoEl.readyState,
        trackReadyState: videoTrack.readyState,
        trackMuted: videoTrack.muted,
        stalled,
        timeSinceAdvanceMs: now - lastAdvanceAt
      });
    }, healthIntervalMs);
  }
  const cancelPlaybackWatch = () => {
    const video = videoEl;
    if (rvfcStallTimer !== null) clearTimeout(rvfcStallTimer);
    if (videoFrameCallbackId !== null) {
      video.cancelVideoFrameCallback?.(videoFrameCallbackId);
      videoFrameCallbackId = null;
    }
    if (rafId !== null) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
  };
  const destroy = () => {
    destroyed = true;
    videoEl.removeEventListener("pause", ensurePlaying);
    videoEl.removeEventListener("ended", ensurePlaying);
    videoEl.removeEventListener("stalled", ensurePlaying);
    videoEl.removeEventListener("waiting", ensurePlaying);
    cancelPlaybackWatch();
    if (healthTimer !== null) {
      clearInterval(healthTimer);
      healthTimer = null;
    }
    try {
      videoEl.pause();
    } catch {
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
      webAudioCleanupRef.current?.();
      webAudioCleanupRef.current = null;
    } catch {
    }
    try {
      videoEl.remove();
    } catch {
    }
    try {
      canvas.remove();
    } catch {
    }
    try {
      videoEl.src = "";
      videoEl.load();
    } catch {
    }
    if (!isUrl) URL.revokeObjectURL(url);
  };
  return {
    url,
    previewStream,
    videoEl,
    videoTrack,
    audioTrack,
    fps: publishFps,
    width: outputWidth,
    height: outputHeight,
    sourceWidth,
    sourceHeight,
    destroy
  };
}
async function resolveUploadAudioTrack(videoEl, webAudioCleanupRef) {
  let audioTrack = getFirstLiveAudioTrack(getVideoElementStream(videoEl));
  if (audioTrack) {
    return audioTrack;
  }
  ensureSilentButUnmuted(videoEl);
  audioTrack = getFirstLiveAudioTrack(getVideoElementStream(videoEl));
  if (audioTrack) {
    return audioTrack;
  }
  const webAudio = await createAudioTrackViaWebAudio(videoEl);
  if (webAudio) {
    webAudioCleanupRef.current = webAudio.cleanup;
    return webAudio.track;
  }
  return void 0;
}
async function createAudioTrackViaWebAudio(videoEl) {
  const AudioContextCtor = globalThis.AudioContext ?? globalThis.window?.webkitAudioContext;
  if (!AudioContextCtor) {
    return null;
  }
  let audioContext = null;
  let source = null;
  let destination = null;
  try {
    audioContext = new AudioContextCtor();
    source = audioContext.createMediaElementSource(videoEl);
    destination = audioContext.createMediaStreamDestination();
    source.connect(destination);
    if (audioContext.state === "suspended") {
      await audioContext.resume();
    }
    const track = getFirstLiveAudioTrack(destination.stream);
    if (!track) {
      source.disconnect();
      destination.disconnect();
      await audioContext.close();
      return null;
    }
    const cleanup = () => {
      try {
        source?.disconnect();
      } catch {
      }
      try {
        destination?.disconnect();
      } catch {
      }
      try {
        if (track.readyState !== "ended") {
          track.stop();
        }
      } catch {
      }
      try {
        if (audioContext && audioContext.state !== "closed") {
          void audioContext.close();
        }
      } catch {
      }
    };
    return { track, cleanup };
  } catch {
    try {
      source?.disconnect();
    } catch {
    }
    try {
      destination?.disconnect();
    } catch {
    }
    try {
      if (audioContext && audioContext.state !== "closed") {
        await audioContext.close();
      }
    } catch {
    }
    return null;
  }
}
function getVideoElementStream(videoEl) {
  const captureVideoEl = videoEl;
  const capture = captureVideoEl.captureStream ?? captureVideoEl.mozCaptureStream;
  if (!capture) {
    return null;
  }
  try {
    return capture.call(captureVideoEl);
  } catch {
    return null;
  }
}
function getFirstLiveAudioTrack(stream) {
  return stream?.getAudioTracks().find((track) => track.readyState === "live");
}
function ensureSilentButUnmuted(videoEl) {
  videoEl.muted = false;
  videoEl.volume = 0;
}
function waitForEvent(el, eventName, timeoutMs) {
  return new Promise((resolve, reject) => {
    const onOk = () => {
      cleanup();
      resolve();
    };
    const onErr = (e) => {
      cleanup();
      const mediaEl = el;
      const code = mediaEl.error ? mediaEl.error.code : "unknown";
      const message = mediaEl.error ? mediaEl.error.message : "no message";
      const src = mediaEl.src || "unknown src";
      reject(new Error(`failed to load video metadata: ${String(eventName)} (code: ${code}, message: ${message}, src: ${src})`));
    };
    const onTimeout = () => {
      cleanup();
      reject(new Error(`timed out waiting for video ${String(eventName)}`));
    };
    const cleanup = () => {
      clearTimeout(timeoutId);
      el.removeEventListener(eventName, onOk);
      el.removeEventListener("error", onErr);
    };
    const timeoutId = setTimeout(onTimeout, timeoutMs);
    el.addEventListener(eventName, onOk, { once: true });
    el.addEventListener("error", onErr, { once: true });
  });
}
function waitForCanPlay(videoEl, timeoutMs) {
  if (videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const onReady = () => {
      cleanup();
      resolve();
    };
    const onTimeout = () => {
      cleanup();
      reject(new Error("timed out waiting for video canplay"));
    };
    const cleanup = () => {
      clearTimeout(timeoutId);
      videoEl.removeEventListener("canplay", onReady);
      videoEl.removeEventListener("loadeddata", onReady);
    };
    const timeoutId = setTimeout(onTimeout, timeoutMs);
    videoEl.addEventListener("canplay", onReady, { once: true });
    videoEl.addEventListener("loadeddata", onReady, { once: true });
  });
}
async function startVideoPlayback(videoEl, i18n) {
  try {
    const playResult = videoEl.play();
    if (playResult && typeof playResult.then === "function") {
      await playResult;
    }
  } catch {
    throw new Error(i18n.t("errors.videoPlaybackFailed"));
  }
  try {
    await waitForPlaying(videoEl, MEDIA_READY_TIMEOUT_MS);
  } catch {
    throw new Error(i18n.t("errors.videoPlaybackFailed"));
  }
  if (videoEl.paused || videoEl.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
    throw new Error(i18n.t("errors.videoPlaybackFailed"));
  }
}
function waitForPlaying(videoEl, timeoutMs) {
  if (!videoEl.paused && videoEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const onPlaying = () => {
      cleanup();
      resolve();
    };
    const onErr = () => {
      cleanup();
      reject(new Error("video playback failed"));
    };
    const onTimeout = () => {
      cleanup();
      reject(new Error("timed out waiting for video playback"));
    };
    const cleanup = () => {
      clearTimeout(timeoutId);
      videoEl.removeEventListener("playing", onPlaying);
      videoEl.removeEventListener("error", onErr);
    };
    const timeoutId = setTimeout(onTimeout, timeoutMs);
    videoEl.addEventListener("playing", onPlaying, { once: true });
    videoEl.addEventListener("error", onErr, { once: true });
  });
}

export { API_ERROR_MESSAGES, DEFAULT_SESSION_TARGET_SIZE, MAX_UPLOAD_VIDEO_PIXELS, MEDIA_TIME_EPSILON_S, MEDIA_TIME_LOOP_JUMP_S, MIN_UPLOAD_VIDEO_PIXELS, MOBILE_PUBLISH_MAX_WIDTH_PX, PREVIEW_CONTAINER_ASPECT_RATIO, RTC_PUBLISH_FPS_MOBILE, RTC_PUBLISH_FPS_WEB, RTC_PUBLISH_FRAME_INTERVAL_MS, RTC_PUBLISH_FRAME_INTERVAL_S, createCanvasPosterUrl, createSDKI18n, createVideoFileStream, drawSourceCover, getDefaultMessages, isMobilePublishEnvironment, resolveAdaptiveRtcVideoSize, resolveApiErrorMessage, resolvePlaybackDrivenEncoderFps, resolvePreviewAspectRatio, resolveRtcPublishFps, resolveRtcPublishFrameIntervalS, resolveSessionTargetSize, resolveUploadPublishSize, resolveUploadVideoSize, shouldSampleAtMediaTime };
//# sourceMappingURL=chunk-G57L4HQX.js.map
//# sourceMappingURL=chunk-G57L4HQX.js.map