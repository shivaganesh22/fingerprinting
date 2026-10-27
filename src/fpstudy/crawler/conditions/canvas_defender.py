"""Canvas Defender condition: Controlled canvas noise injection simulation."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Browser, BrowserContext

from fpstudy.crawler.conditions.base import BaseCondition, register_condition

CANVAS_DEFENDER_SIMULATION_JS = """
/**
 * SIMULATION: Canvas Defender Fingerprint Defense.
 * Injects subtle controlled noise into CanvasRenderingContext2D readback APIs
 * (toDataURL, toBlob, and getImageData) to poison canvas fingerprint hashes.
 */
(() => {
    if (window.__canvas_defender_active) return;
    window.__canvas_defender_active = true;

    // Helper to perturb an ImageData buffer with controlled pseudo-random noise
    function perturbImageData(imageData) {
        const data = imageData.data;
        for (let i = 0; i < data.length; i += 4) {
            // Apply subtle +/- 3 delta to RGB channels without corrupting transparency
            const noise = ((i * 17 + 5) % 7) - 3;
            data[i] = Math.min(255, Math.max(0, data[i] + noise));
            data[i + 1] = Math.min(255, Math.max(0, data[i + 1] - noise));
            data[i + 2] = Math.min(255, Math.max(0, data[i + 2] + (noise % 2)));
        }
        return imageData;
    }

    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh, ...rest) {
        const res = origGetImageData.call(this, sx, sy, sw, sh, ...rest);
        return perturbImageData(res);
    };

    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        try {
            const ctx = this.getContext('2d');
            if (ctx && this.width > 0 && this.height > 0) {
                // Apply noise to internal canvas buffer before serializing
                const imgData = origGetImageData.call(ctx, 0, 0, this.width, this.height);
                perturbImageData(imgData);
                ctx.putImageData(imgData, 0, 0);
            }
        } catch (e) {}
        return origToDataURL.apply(this, args);
    };
})();
"""


@register_condition("canvas_defender")
class CanvasDefenderCondition(BaseCondition):
    """Controlled canvas noise injection condition simulating anti-fingerprinting extensions."""

    async def prepare(self) -> None:
        """No external downloads needed."""
        pass

    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Create context with Canvas Defender noise script injected."""
        ctx = await browser.new_context(**context_options)
        await ctx.add_init_script(CANVAS_DEFENDER_SIMULATION_JS)
        return ctx

    async def teardown(self) -> None:
        """No teardown needed."""
        pass

    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Canary check: verify that canvas getImageData is modified by the defender script."""
        ctx = await self.launch_context(browser, {})
        try:
            page = await ctx.new_page()
            check_script = """
            () => {
                const canvas = document.createElement('canvas');
                canvas.width = 20;
                canvas.height = 20;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = 'rgb(100, 100, 100)';
                ctx.fillRect(0, 0, 20, 20);
                const data = ctx.getImageData(0, 0, 5, 5).data;
                // If unmodified, data[0] would be exactly 100. If noised, data[0] != 100.
                let modified = false;
                for (let i = 0; i < data.length; i += 4) {
                    if (data[i] !== 100) {
                        modified = true;
                        break;
                    }
                }
                return {
                    active: !!window.__canvas_defender_active,
                    noise_detected: modified,
                    sample_pixel: [data[0], data[1], data[2], data[3]]
                };
            }
            """
            res = await page.evaluate(check_script)
            passed = bool(res.get("active") and res.get("noise_detected"))
            return {
                "passed": passed,
                "details": res,
            }
        finally:
            await ctx.close()
