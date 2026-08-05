import { memo, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import type { Schema } from "hast-util-sanitize";

interface MarkdownRendererProps {
  content: string;
  className?: string;
  isStreaming?: boolean;
}

type PropertyDefinition =
  | string
  | [string, ...Array<string | number | boolean | RegExp | null | undefined>];

const baseSchema = defaultSchema as Schema;

const extendAttributes = (
  current: PropertyDefinition[] | undefined,
  extras: PropertyDefinition[],
): PropertyDefinition[] => [...(current ?? []), ...extras];

const markdownSanitizeSchema: Schema = {
  ...baseSchema,
  attributes: {
    ...(baseSchema.attributes ?? {}),
    code: extendAttributes(
      baseSchema.attributes?.code as PropertyDefinition[] | undefined,
      ["className"],
    ),
    span: extendAttributes(
      baseSchema.attributes?.span as PropertyDefinition[] | undefined,
      ["className"],
    ),
    a: extendAttributes(
      baseSchema.attributes?.a as PropertyDefinition[] | undefined,
      ["target", "rel"],
    ),
  },
};

const BASE_PROSE_CLASSES =
  "markdown-prose prose max-w-none text-base-content prose-headings:font-semibold prose-headings:text-base-content prose-a:font-medium prose-blockquote:border-base-300/70";

const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
  className,
  isStreaming = false,
}: MarkdownRendererProps) {
  const sanitizedContent = content ?? "";

  const key = useMemo(
    () => (isStreaming ? `stream-${sanitizedContent.length}` : undefined),
    [isStreaming, sanitizedContent.length],
  );

  const combinedClassName = useMemo(() => {
    if (!className) return BASE_PROSE_CLASSES;
    return `${BASE_PROSE_CLASSES} ${className}`.trim();
  }, [className]);

  return (
    <div className={combinedClassName} data-testid="markdown-renderer">
      <ReactMarkdown
        key={key}
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, markdownSanitizeSchema]]}
      >
        {sanitizedContent}
      </ReactMarkdown>
    </div>
  );
});

export default MarkdownRenderer;
