import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";

const generatedFiles = [
  new URL("../openapi.json", import.meta.url),
  new URL("../src/services/api/generated/schema.ts", import.meta.url),
];

const before = await Promise.all(generatedFiles.map((path) => readFile(path, "utf8")));
const result = spawnSync("npm", ["run", "api:generate"], {
  cwd: new URL("..", import.meta.url),
  stdio: "inherit",
});

if (result.status !== 0) process.exit(result.status ?? 1);

const after = await Promise.all(generatedFiles.map((path) => readFile(path, "utf8")));
if (before.some((content, index) => content !== after[index])) {
  console.error("Generated API contracts were stale. Run `npm run api:generate` and commit the results.");
  process.exit(1);
}
