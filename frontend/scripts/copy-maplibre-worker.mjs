// Copia o worker do MapLibre para public/vendor, de onde o navegador o carrega.
// O MapLibre 6 localiza o worker por import.meta.url, o que o empacotador do Next não resolve.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const source = join(dirname(require.resolve("maplibre-gl/package.json")), "dist", "maplibre-gl-worker.mjs");
const targetDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "vendor");

mkdirSync(targetDir, { recursive: true });
copyFileSync(source, join(targetDir, "maplibre-gl-worker.mjs"));
console.log("worker do MapLibre copiado para public/vendor/");
