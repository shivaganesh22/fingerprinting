/**
 * Client-side instrumentation hooks for browser fingerprinting detection.
 * Designed to be non-intrusive, native-looking, robust, and low-overhead.
 */
(() => {
    // Avoid double injection
    if (window.__fpstudy_installed) {
        return;
    }
    window.__fpstudy_installed = true;

    const MAX_EVENTS = window.__fpstudy_max_events || 5000;
    let eventCount = 0;
    let truncated = false;
    const eventQueue = [];

    // Helper: hash string for inline scripts
    function simpleHash(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = (hash << 5) - hash + char;
            hash |= 0;
        }
        return Math.abs(hash).toString(16);
    }

    // Helper: make wrapped functions look native
    const nativeToString = Function.prototype.toString;
    const wrappedFns = new WeakSet();
    const fnNames = new WeakMap();

    function wrapNative(origFn, newFn, name) {
        wrappedFns.add(newFn);
        fnNames.set(newFn, name || origFn.name || "");
        try {
            Object.defineProperty(newFn, "name", {
                value: name || origFn.name,
                configurable: true,
                writable: false,
            });
            Object.defineProperty(newFn, "length", {
                value: origFn.length,
                configurable: true,
                writable: false,
            });
        } catch (e) {}
        return newFn;
    }

    // Stealth toString override
    const customToString = function toString() {
        if (wrappedFns.has(this)) {
            const name = fnNames.get(this) || "";
            return `function ${name}() { [native code] }`;
        }
        return nativeToString.call(this);
    };
    wrappedFns.add(customToString);
    fnNames.set(customToString, "toString");
    try {
        Function.prototype.toString = customToString;
    } catch (e) {}

    // Stack trace parsing for script attribution
    function getCallingScript() {
        try {
            const stack = new Error().stack;
            if (!stack) return "unknown";
            const lines = stack.split("\n");
            const docBase = window.location.href.split("?")[0].split("#")[0];

            for (let i = 2; i < lines.length; i++) {
                const line = lines[i].trim();
                // Skip our own hook lines
                if (line.includes("hooks.js") || line.includes("__fpstudy_")) {
                    continue;
                }
                if (line.includes("eval at ")) {
                    return `eval:${simpleHash(line)}`;
                }
                if (line.includes("<anonymous>")) {
                    return `inline:${simpleHash(line)}+${window.location.href}`;
                }

                // Match standard v8 stack: at functionName (url:line:col) or at url:line:col
                const parenMatch = line.match(/\((.*?):(\d+):(\d+)\)/);
                if (parenMatch && parenMatch[1]) {
                    const rawUrl = parenMatch[1].trim();
                    const urlBase = rawUrl.split("?")[0].split("#")[0];
                    if (urlBase === docBase || urlBase.endsWith(".html") || urlBase.endsWith(".htm")) {
                        return `inline:${simpleHash(line)}+${window.location.href}`;
                    }
                    return rawUrl;
                }

                const urlMatch = line.match(/at\s+(.*?):(\d+):(\d+)/);
                if (urlMatch && urlMatch[1]) {
                    const candidate = urlMatch[1].trim();
                    if (!candidate.startsWith("new ") && !candidate.startsWith("Object.")) {
                        const candBase = candidate.split("?")[0].split("#")[0];
                        if (candBase === docBase || candBase.endsWith(".html") || candBase.endsWith(".htm")) {
                            return `inline:${simpleHash(line)}+${window.location.href}`;
                        }
                        return candidate;
                    }
                }
            }
        } catch (e) {}
        return `inline:${simpleHash(window.location.href)}+${window.location.href}`;
    }

    function getTopUrl() {
        try {
            return window.top.location.href;
        } catch (e) {
            try {
                const ancestors = window.location.ancestorOrigins;
                if (ancestors && ancestors.length) {
                    return ancestors[ancestors.length - 1];
                }
            } catch (ancestorError) {}
            return window.location.href;
        }
    }

    // Emit event
    function emitEvent(api, methodOrProp, argsSummary, returnSummary) {
        if (eventCount >= MAX_EVENTS) {
            if (!truncated) {
                truncated = true;
                window.__fpstudy_truncated = true;
            }
            return;
        }
        eventCount++;

        const callingScript = getCallingScript();
        const frameUrl = window.location.href;
        const topUrl = getTopUrl();

        const evt = {
            ts: performance.now(),
            api: api,
            method_or_property: methodOrProp,
            args_summary: argsSummary || {},
            return_summary: returnSummary || {},
            script_url: callingScript,
            frame_url: frameUrl,
            top_level_url: topUrl,
        };

        eventQueue.push(evt);

        // Immediate flush if Python binding is ready
        if (typeof window.__fpstudy_push_events === "function") {
            try {
                const chunk = eventQueue.splice(0, eventQueue.length);
                window.__fpstudy_push_events(chunk);
            } catch (e) {
                // If async flush throws, preserve in queue
                eventQueue.unshift(...chunk);
            }
        }
    }

    // Periodic drain into binding
    setInterval(() => {
        if (eventQueue.length > 0 && typeof window.__fpstudy_push_events === "function") {
            try {
                const chunk = eventQueue.splice(0, eventQueue.length);
                window.__fpstudy_push_events(chunk);
            } catch (e) {}
        }
    }, 250);

    // Provide window drain hook for Python
    window.__fpstudy_drain_events = () => {
        const remaining = eventQueue.splice(0, eventQueue.length);
        return {
            events: remaining,
            truncated: truncated,
            total_count: eventCount,
        };
    };

    // ==========================================
    // 1. CANVAS INSTRUMENTATION
    // ==========================================
    try {
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = wrapNative(
            origToDataURL,
            function toDataURL(...args) {
                emitEvent("canvas", "toDataURL", {
                    width: this.width,
                    height: this.height,
                    type: args[0] || "image/png",
                }, {});
                return origToDataURL.apply(this, args);
            },
            "toDataURL"
        );

        const origToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = wrapNative(
            origToBlob,
            function toBlob(...args) {
                emitEvent("canvas", "toBlob", {
                    width: this.width,
                    height: this.height,
                    type: args[1] || "image/png",
                }, {});
                return origToBlob.apply(this, args);
            },
            "toBlob"
        );

        const origGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = wrapNative(
            origGetContext,
            function getContext(type, ...rest) {
                emitEvent("canvas", "getContext", {
                    contextType: type,
                    width: this.width,
                    height: this.height,
                }, {});
                return origGetContext.call(this, type, ...rest);
            },
            "getContext"
        );

        const origAddEventListener = HTMLCanvasElement.prototype.addEventListener;
        HTMLCanvasElement.prototype.addEventListener = wrapNative(
            origAddEventListener,
            function addEventListener(type, listener, options) {
                emitEvent("canvas", "addEventListener", {
                    eventType: type,
                    width: this.width,
                    height: this.height,
                }, {});
                return origAddEventListener.call(this, type, listener, options);
            },
            "addEventListener"
        );

        const c2d = CanvasRenderingContext2D.prototype;

        const origFillText = c2d.fillText;
        c2d.fillText = wrapNative(
            origFillText,
            function fillText(text, x, y, maxWidth) {
                const str = String(text);
                emitEvent("canvas", "fillText", {
                    text: str.substring(0, 50),
                    text_length: str.length,
                    width: this.canvas ? this.canvas.width : null,
                    height: this.canvas ? this.canvas.height : null,
                    fillStyle: String(this.fillStyle),
                    font: this.font,
                }, {});
                return origFillText.call(this, text, x, y, maxWidth);
            },
            "fillText"
        );

        const origStrokeText = c2d.strokeText;
        c2d.strokeText = wrapNative(
            origStrokeText,
            function strokeText(text, x, y, maxWidth) {
                const str = String(text);
                emitEvent("canvas", "strokeText", {
                    text: str.substring(0, 50),
                    text_length: str.length,
                    width: this.canvas ? this.canvas.width : null,
                    height: this.canvas ? this.canvas.height : null,
                    strokeStyle: String(this.strokeStyle),
                    font: this.font,
                }, {});
                return origStrokeText.call(this, text, x, y, maxWidth);
            },
            "strokeText"
        );

        const origMeasureText = c2d.measureText;
        c2d.measureText = wrapNative(
            origMeasureText,
            function measureText(text) {
                const str = String(text);
                emitEvent("canvas", "measureText", {
                    text_length: str.length,
                    font: this.font,
                    width: this.canvas ? this.canvas.width : null,
                    height: this.canvas ? this.canvas.height : null,
                }, {});
                return origMeasureText.call(this, text);
            },
            "measureText"
        );

        const origGetImageData = c2d.getImageData;
        c2d.getImageData = wrapNative(
            origGetImageData,
            function getImageData(sx, sy, sw, sh, ...rest) {
                emitEvent("canvas", "getImageData", {
                    sx,
                    sy,
                    sw,
                    sh,
                    area: Math.abs(sw * sh),
                    width: this.canvas ? this.canvas.width : null,
                    height: this.canvas ? this.canvas.height : null,
                }, {});
                return origGetImageData.call(this, sx, sy, sw, sh, ...rest);
            },
            "getImageData"
        );

        const origFillRect = c2d.fillRect;
        c2d.fillRect = wrapNative(
            origFillRect,
            function fillRect(x, y, w, h) {
                emitEvent("canvas", "fillRect", {
                    width: w,
                    height: h,
                    fillStyle: String(this.fillStyle),
                }, {});
                return origFillRect.call(this, x, y, w, h);
            },
            "fillRect"
        );

        const origIsPointInPath = c2d.isPointInPath;
        c2d.isPointInPath = wrapNative(
            origIsPointInPath,
            function isPointInPath(...args) {
                emitEvent("canvas", "isPointInPath", {}, {});
                return origIsPointInPath.apply(this, args);
            },
            "isPointInPath"
        );

        const origSave = c2d.save;
        c2d.save = wrapNative(
            origSave,
            function save() {
                emitEvent("canvas", "save", {}, {});
                return origSave.call(this);
            },
            "save"
        );

        const origRestore = c2d.restore;
        c2d.restore = wrapNative(
            origRestore,
            function restore() {
                emitEvent("canvas", "restore", {}, {});
                return origRestore.call(this);
            },
            "restore"
        );
    } catch (e) {}

    // ==========================================
    // 2. WEBGL INSTRUMENTATION (1 & 2)
    // ==========================================
    const glContexts = [];
    if (typeof WebGLRenderingContext !== "undefined") {
        glContexts.push(WebGLRenderingContext.prototype);
    }
    if (typeof WebGL2RenderingContext !== "undefined") {
        glContexts.push(WebGL2RenderingContext.prototype);
    }

    const UNMASKED_VENDOR_WEBGL = 0x9245;
    const UNMASKED_RENDERER_WEBGL = 0x9246;

    glContexts.forEach((glProto) => {
        try {
            const origGetParameter = glProto.getParameter;
            glProto.getParameter = wrapNative(
                origGetParameter,
                function getParameter(pname) {
                    const isUnmasked =
                        pname === UNMASKED_VENDOR_WEBGL || pname === UNMASKED_RENDERER_WEBGL;
                    const res = origGetParameter.call(this, pname);
                    emitEvent("webgl", "getParameter", {
                        pname: pname,
                        is_unmasked_vendor_or_renderer: isUnmasked,
                    }, {
                        return_type: typeof res,
                        return_preview: typeof res === "string" ? res.substring(0, 50) : null,
                    });
                    return res;
                },
                "getParameter"
            );

            const origGetExtension = glProto.getExtension;
            glProto.getExtension = wrapNative(
                origGetExtension,
                function getExtension(name) {
                    const isDebugInfo = name === "WEBGL_debug_renderer_info";
                    emitEvent("webgl", "getExtension", {
                        name: name,
                        is_debug_renderer_info: isDebugInfo,
                    }, {});
                    return origGetExtension.call(this, name);
                },
                "getExtension"
            );

            const origGetSupportedExtensions = glProto.getSupportedExtensions;
            glProto.getSupportedExtensions = wrapNative(
                origGetSupportedExtensions,
                function getSupportedExtensions() {
                    const exts = origGetSupportedExtensions.call(this);
                    emitEvent("webgl", "getSupportedExtensions", {}, {
                        count: exts ? exts.length : 0,
                    });
                    return exts;
                },
                "getSupportedExtensions"
            );

            const origGetShaderPrecisionFormat = glProto.getShaderPrecisionFormat;
            glProto.getShaderPrecisionFormat = wrapNative(
                origGetShaderPrecisionFormat,
                function getShaderPrecisionFormat(shaderType, precisionType) {
                    emitEvent("webgl", "getShaderPrecisionFormat", {
                        shaderType,
                        precisionType,
                    }, {});
                    return origGetShaderPrecisionFormat.call(this, shaderType, precisionType);
                },
                "getShaderPrecisionFormat"
            );

            const origReadPixels = glProto.readPixels;
            glProto.readPixels = wrapNative(
                origReadPixels,
                function readPixels(x, y, width, height, format, type, pixels) {
                    emitEvent("webgl", "readPixels", {
                        width,
                        height,
                        format,
                        type,
                    }, {});
                    return origReadPixels.call(this, x, y, width, height, format, type, pixels);
                },
                "readPixels"
            );
        } catch (e) {}
    });

    // ==========================================
    // 3. AUDIO CONTEXT INSTRUMENTATION
    // ==========================================
    try {
        const audioContexts = [];
        if (typeof AudioContext !== "undefined") audioContexts.push(AudioContext);
        if (typeof webkitAudioContext !== "undefined") audioContexts.push(webkitAudioContext);

        audioContexts.forEach((Ctx) => {
            const origCtx = Ctx;
            const wrappedCtx = function (...args) {
                emitEvent("audio", "AudioContext", {}, {});
                return new origCtx(...args);
            };
            wrappedCtx.prototype = origCtx.prototype;
            wrapNative(origCtx, wrappedCtx, "AudioContext");
            try {
                window[Ctx.name] = wrappedCtx;
            } catch (e) {}
        });

        if (typeof OfflineAudioContext !== "undefined") {
            const origOffline = OfflineAudioContext;
            const wrappedOffline = function (...args) {
                emitEvent("audio", "OfflineAudioContext", {
                    numberOfChannels: args[0],
                    length: args[1],
                    sampleRate: args[2],
                }, {});
                return new origOffline(...args);
            };
            wrappedOffline.prototype = origOffline.prototype;
            wrapNative(origOffline, wrappedOffline, "OfflineAudioContext");
            try {
                window.OfflineAudioContext = wrappedOffline;
            } catch (e) {}

            const origStartRendering = origOffline.prototype.startRendering;
            origOffline.prototype.startRendering = wrapNative(
                origStartRendering,
                function startRendering() {
                    emitEvent("audio", "startRendering", {}, {});
                    return origStartRendering.call(this);
                },
                "startRendering"
            );
        }

        const baseCtxProto =
            typeof BaseAudioContext !== "undefined"
                ? BaseAudioContext.prototype
                : (typeof AudioContext !== "undefined" ? AudioContext.prototype : null);

        if (baseCtxProto) {
            const origCreateOscillator = baseCtxProto.createOscillator;
            baseCtxProto.createOscillator = wrapNative(
                origCreateOscillator,
                function createOscillator() {
                    emitEvent("audio", "createOscillator", {}, {});
                    return origCreateOscillator.call(this);
                },
                "createOscillator"
            );

            const origCreateDynamicsCompressor = baseCtxProto.createDynamicsCompressor;
            baseCtxProto.createDynamicsCompressor = wrapNative(
                origCreateDynamicsCompressor,
                function createDynamicsCompressor() {
                    emitEvent("audio", "createDynamicsCompressor", {}, {});
                    return origCreateDynamicsCompressor.call(this);
                },
                "createDynamicsCompressor"
            );

            const origCreateAnalyser = baseCtxProto.createAnalyser;
            baseCtxProto.createAnalyser = wrapNative(
                origCreateAnalyser,
                function createAnalyser() {
                    emitEvent("audio", "createAnalyser", {}, {});
                    return origCreateAnalyser.call(this);
                },
                "createAnalyser"
            );
        }

        if (typeof AudioBuffer !== "undefined") {
            const origGetChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = wrapNative(
                origGetChannelData,
                function getChannelData(channel) {
                    emitEvent("audio", "getChannelData", { channel }, {});
                    return origGetChannelData.call(this, channel);
                },
                "getChannelData"
            );
        }

        if (typeof AnalyserNode !== "undefined") {
            const origGetFloatFreq = AnalyserNode.prototype.getFloatFrequencyData;
            AnalyserNode.prototype.getFloatFrequencyData = wrapNative(
                origGetFloatFreq,
                function getFloatFrequencyData(array) {
                    emitEvent("audio", "analyser.getFloatFrequencyData", {}, {});
                    return origGetFloatFreq.call(this, array);
                },
                "getFloatFrequencyData"
            );
        }
    } catch (e) {}

    // ==========================================
    // 4. FONT PROBING & ENUMERATION INSTRUMENTATION
    // ==========================================
    try {
        if (typeof FontFace !== "undefined") {
            const origFontFace = FontFace;
            const wrappedFontFace = function (family, source, descriptors) {
                emitEvent("fonts", "FontFace", { family: String(family) }, {});
                return new origFontFace(family, source, descriptors);
            };
            wrappedFontFace.prototype = origFontFace.prototype;
            wrapNative(origFontFace, wrappedFontFace, "FontFace");
            try {
                window.FontFace = wrappedFontFace;
            } catch (e) {}
        }

        if (document.fonts && typeof document.fonts.check === "function") {
            const origCheck = document.fonts.check;
            document.fonts.check = wrapNative(
                origCheck,
                function check(font, text) {
                    emitEvent("fonts", "document.fonts.check", {
                        font: String(font),
                        text: text ? String(text) : null,
                    }, {});
                    return origCheck.call(document.fonts, font, text);
                },
                "check"
            );
        }

        // Element dimension getters often probed repeatedly during font enumeration
        const origOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetWidth");
        if (origOffsetWidth && origOffsetWidth.get) {
            Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
                get: wrapNative(
                    origOffsetWidth.get,
                    function offsetWidth() {
                        const styleFont = this.style ? this.style.fontFamily : "";
                        if (styleFont) {
                            emitEvent("fonts", "element.offsetWidth", { fontFamily: styleFont }, {});
                        }
                        return origOffsetWidth.get.call(this);
                    },
                    "offsetWidth"
                ),
                configurable: true,
            });
        }

        const origOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "offsetHeight");
        if (origOffsetHeight && origOffsetHeight.get) {
            Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
                get: wrapNative(
                    origOffsetHeight.get,
                    function offsetHeight() {
                        const styleFont = this.style ? this.style.fontFamily : "";
                        if (styleFont) {
                            emitEvent("fonts", "element.offsetHeight", { fontFamily: styleFont }, {});
                        }
                        return origOffsetHeight.get.call(this);
                    },
                    "offsetHeight"
                ),
                configurable: true,
            });
        }
    } catch (e) {}

    // ==========================================
    // 5. SUPPORTING SIGNALS (NAVIGATOR / SCREEN / INTL)
    // ==========================================
    try {
        const navProps = [
            "userAgent",
            "platform",
            "languages",
            "hardwareConcurrency",
            "deviceMemory",
            "plugins",
            "mimeTypes",
            "maxTouchPoints",
            "webdriver",
        ];

        navProps.forEach((prop) => {
            const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, prop);
            if (desc && desc.get) {
                Object.defineProperty(Navigator.prototype, prop, {
                    get: wrapNative(
                        desc.get,
                        function () {
                            const val = desc.get.call(this);
                            emitEvent("signals", `navigator.${prop}`, {}, {
                                val_preview: typeof val === "object" ? "[object]" : String(val),
                            });
                            return val;
                        },
                        `get ${prop}`
                    ),
                    configurable: true,
                });
            }
        });

        const screenProps = ["width", "height", "colorDepth", "pixelDepth"];
        screenProps.forEach((prop) => {
            const desc = Object.getOwnPropertyDescriptor(Screen.prototype, prop);
            if (desc && desc.get) {
                Object.defineProperty(Screen.prototype, prop, {
                    get: wrapNative(
                        desc.get,
                        function () {
                            const val = desc.get.call(this);
                            emitEvent("signals", `screen.${prop}`, {}, { value: val });
                            return val;
                        },
                        `get ${prop}`
                    ),
                    configurable: true,
                });
            }
        });

        const dprDesc = Object.getOwnPropertyDescriptor(Window.prototype, "devicePixelRatio");
        if (dprDesc && dprDesc.get) {
            Object.defineProperty(Window.prototype, "devicePixelRatio", {
                get: wrapNative(
                    dprDesc.get,
                    function () {
                        const val = dprDesc.get.call(this);
                        emitEvent("signals", "window.devicePixelRatio", {}, { value: val });
                        return val;
                    },
                    "get devicePixelRatio"
                ),
                configurable: true,
            });
        }

        if (Intl && Intl.DateTimeFormat) {
            const origResolved = Intl.DateTimeFormat.prototype.resolvedOptions;
            Intl.DateTimeFormat.prototype.resolvedOptions = wrapNative(
                origResolved,
                function resolvedOptions() {
                    const res = origResolved.call(this);
                    emitEvent("signals", "Intl.DateTimeFormat().resolvedOptions", {}, {
                        timeZone: res ? res.timeZone : null,
                    });
                    return res;
                },
                "resolvedOptions"
            );
        }

        const origTz = Date.prototype.getTimezoneOffset;
        Date.prototype.getTimezoneOffset = wrapNative(
            origTz,
            function getTimezoneOffset() {
                const res = origTz.call(this);
                emitEvent("signals", "Date.prototype.getTimezoneOffset", {}, { value: res });
                return res;
            },
            "getTimezoneOffset"
        );
    } catch (e) {}
})();
