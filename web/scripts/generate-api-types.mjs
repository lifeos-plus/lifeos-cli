import { readFile, writeFile } from "node:fs/promises";

import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import ts from "typescript";

const inputPath = new URL("../openapi.json", import.meta.url);
const outputPath = new URL("../src/services/api/generated/schema.ts", import.meta.url);
const document = JSON.parse(await readFile(inputPath, "utf8"));

const ast = await openapiTS(document, {
  defaultNonNullable: false,
  inject: `export type JsonValue =
  | string
  | number
  | boolean
  | JsonValue[]
  | { [key: string]: JsonValue }
  | null;`,
  transform(_schema, options) {
    if (options.path === "#/components/schemas/JsonValue") {
      return ts.factory.createTypeReferenceNode("JsonValue");
    }
    return undefined;
  },
});

await writeFile(outputPath, `${COMMENT_HEADER}${astToString(ast)}`, "utf8");
