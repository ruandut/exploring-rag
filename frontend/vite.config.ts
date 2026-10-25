import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, lazyPlugins } from "vite-plus";

// https://viteplus.dev/config/
export default defineConfig({
  fmt: { ignorePatterns: ["src/routeTree.gen.ts"] },
  lint: {
    plugins: ["react", "typescript", "oxc"],
    // Generated (routeTree) and shadcn-vendored files are not ours to lint.
    ignorePatterns: ["src/routeTree.gen.ts", "src/components/ui/**", "src/hooks/use-mobile.ts"],
    rules: {
      "react/rules-of-hooks": "error",
      // TanStack file routes export `Route` next to their components by design.
      "react/only-export-components": "off",
      "vite-plus/prefer-vite-plus-imports": "error",
    },
    options: { typeAware: true, typeCheck: true },
    jsPlugins: [{ name: "vite-plus", specifier: "vite-plus/oxlint-plugin" }],
  },
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5173,
    // The System Design page imports ../specs/*.md (outside this package) at build time.
    fs: { allow: [".."] },
    // Dev proxy: the browser talks to one origin; Vite forwards API + websocket traffic to Django.
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  plugins: lazyPlugins(() => [
    // Must come before react(): generates src/routeTree.gen.ts from src/routes/.
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ]),
});
