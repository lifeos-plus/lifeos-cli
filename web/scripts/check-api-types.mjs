import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";

const generatedSchema = new URL(
  "../src/services/api/generated/schema.ts",
  import.meta.url,
);

const before = await readFile(generatedSchema, "utf8");
const result = spawnSync("npm", ["run", "api:generate"], {
  cwd: new URL("..", import.meta.url),
  stdio: "inherit",
});

if (result.status !== 0) process.exit(result.status ?? 1);

const after = await readFile(generatedSchema, "utf8");
if (before !== after) {
  console.error(
    "Generated API contracts were stale. Run `npm run api:generate` and commit the updated schema.ts.",
  );
  process.exit(1);
}
