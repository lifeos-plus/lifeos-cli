import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sourceRoot = path.join(webRoot, "src");
const localePaths = {
  en: path.join(sourceRoot, "locales", "en", "common.json"),
  zh: path.join(sourceRoot, "locales", "zh", "common.json"),
};

function flattenKeys(value, prefix = "", keys = new Set()) {
  for (const [name, child] of Object.entries(value)) {
    const key = prefix ? `${prefix}.${name}` : name;
    if (child && typeof child === "object" && !Array.isArray(child)) {
      flattenKeys(child, key, keys);
    } else {
      keys.add(key);
    }
  }
  return keys;
}

function sourceFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(entryPath);
    return /\.(ts|tsx)$/.test(entry.name) ? [entryPath] : [];
  });
}

function literalTranslationReferences() {
  const references = [];
  const callPattern = /(?:\bt|\bi18n\.t)\(\s*["'`]([^"'`$]+)["'`]/g;

  for (const filePath of sourceFiles(sourceRoot)) {
    const source = fs.readFileSync(filePath, "utf8");
    for (const match of source.matchAll(callPattern)) {
      references.push({
        key: match[1],
        file: path.relative(webRoot, filePath),
        line: source.slice(0, match.index).split("\n").length,
      });
    }
  }
  return references;
}

const catalogs = Object.fromEntries(
  Object.entries(localePaths).map(([locale, localePath]) => [
    locale,
    flattenKeys(JSON.parse(fs.readFileSync(localePath, "utf8"))),
  ]),
);
const failures = [];

for (const [locale, keys] of Object.entries(catalogs)) {
  for (const [otherLocale, otherKeys] of Object.entries(catalogs)) {
    if (locale >= otherLocale) continue;
    for (const key of keys) {
      if (!otherKeys.has(key)) {
        failures.push(`${otherLocale} locale is missing key: ${key}`);
      }
    }
    for (const key of otherKeys) {
      if (!keys.has(key)) {
        failures.push(`${locale} locale is missing key: ${key}`);
      }
    }
  }
}

for (const reference of literalTranslationReferences()) {
  for (const [locale, keys] of Object.entries(catalogs)) {
    if (!keys.has(reference.key)) {
      failures.push(
        `${reference.file}:${reference.line} references missing ${locale} key: ${reference.key}`,
      );
    }
  }
}

if (failures.length > 0) {
  console.error("Web translation catalog validation failed:");
  for (const failure of [...new Set(failures)].sort()) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Web translation catalogs and literal references are valid.");
