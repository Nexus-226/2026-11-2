import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ["VITE_", "AMAP_JS_SECURITY_CODE"]);
  const target = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  const securityCode = env.AMAP_JS_SECURITY_CODE?.trim();

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": target,
        "/health": target,
        ...(securityCode && {
          "^/_AMapService/(v3/log/init|v4/map/styles)([?]|$)": {
            target: "https://restapi.amap.com",
            changeOrigin: true,
            rewrite(path: string) {
              const url = new URL(path, "https://restapi.amap.com");
              url.searchParams.set("jscode", securityCode);
              return url.pathname.slice("/_AMapService".length) + url.search;
            },
          },
        }),
      },
    },
  };
});
