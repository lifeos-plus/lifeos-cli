import type {
  FinanceAsset,
  FinanceRateSnapshot,
  FinanceSnapshot,
  FinanceTreeNode,
} from "@/services/api/finance";
import type { UUID } from "@/types/primitive";
import {
  dateStringToISO,
  formatDate,
  formatDateInTimezone,
  formatDateTime,
  localDateTimeLocalToUtcIso,
  utcToLocalDateTimeLocal,
} from "@/utils/datetime";

export type PresetConfig = {
  report: "balance" | "cashflow";
  titleKey: string;
  descriptionKey: string;
  timeMode: "instant" | "period";
};

export type FinanceTab = PresetConfig["report"] | "rates" | "trees";
export type FinanceToolbarTab = FinanceTab | "assets";

export const DEFAULT_FINANCE_TAB: FinanceTab = "trees";

export const FINANCE_TOOLBAR_ORDER = [
  "assets",
  "trees",
  "rates",
  "balance",
  "cashflow",
] as const satisfies readonly FinanceToolbarTab[];

export type TreeNodeWithChildren = FinanceTreeNode & {
  children: TreeNodeWithChildren[];
};

type SnapshotHoldingState = {
  id: string;
  currencyCode: string;
  amount: string;
  note: string;
};

export type SnapshotAmountState = Record<UUID, SnapshotHoldingState[]>;

export type SnapshotFormMode = "create" | "edit" | "copy";

export type RateSnapshotFormMode = "create" | "edit" | "copy";

export type RateRowState = {
  baseAmount: string;
  baseCurrency: string;
  quoteAmount: string;
  quoteCurrency: string;
};

export type FinanceNodeFormState =
  | { mode: "create"; parentId?: UUID | null }
  | { mode: "edit"; node: TreeNodeWithChildren };

export const todayDate = (timezone: string) =>
  formatDateInTimezone(new Date(), timezone);

export const nowDateTimeLocal = (timezone: string) =>
  utcToLocalDateTimeLocal(new Date().toISOString(), timezone);

export const localDateTimeToIso = (value: string, timezone: string) => {
  if (!value) return null;
  return localDateTimeLocalToUtcIso(value, timezone) || null;
};

export const isoToDateTimeLocal = (
  value: string | null | undefined,
  timezone: string,
) =>
  value
    ? utcToLocalDateTimeLocal(value, timezone)
    : nowDateTimeLocal(timezone);

export const isoToDateInput = (
  value: string | null | undefined,
  timezone: string,
) => (value ? formatDate(value, timezone) : todayDate(timezone));

export const dateToStartIso = (value: string, timezone: string) => {
  if (!value) return null;
  return dateStringToISO(value, timezone, false) || null;
};

export const dateToEndIso = (value: string, timezone: string) => {
  if (!value) return null;
  return dateStringToISO(value, timezone, true) || null;
};

export const assetDecimalPlaces = (assets: FinanceAsset[], currency = "") => {
  const normalized = currency.toUpperCase();
  const places = assets.find((asset) => asset.code === normalized)?.decimal_places ?? 2;
  return Math.min(8, Math.max(0, places));
};

export const formatNumberForAsset = (
  value: number,
  currency: string,
  assets: FinanceAsset[] = [],
) =>
  value.toLocaleString(undefined, {
    useGrouping: false,
    minimumFractionDigits: 0,
    maximumFractionDigits: assetDecimalPlaces(assets, currency),
  });

export const formatAmountForAsset = (
  value: string,
  currency: string,
  assets: FinanceAsset[] = [],
) => {
  if (!value.trim()) {
    return value;
  }
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return value;
  }
  return formatNumberForAsset(numeric, currency, assets);
};

export const buildTree = (nodes: FinanceTreeNode[]): TreeNodeWithChildren[] => {
  const sorted = [...nodes].sort((a, b) => {
    if (a.path !== b.path) return a.path.localeCompare(b.path);
    return a.display_order - b.display_order;
  });
  const map = new Map<UUID, TreeNodeWithChildren>();
  sorted.forEach((node) => {
    map.set(node.id, { ...node, children: [] });
  });
  const roots: TreeNodeWithChildren[] = [];
  sorted.forEach((node) => {
    const current = map.get(node.id);
    if (!current) return;
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)?.children.push(current);
      return;
    }
    roots.push(current);
  });
  return roots;
};

export const flattenTree = (nodes: TreeNodeWithChildren[]): TreeNodeWithChildren[] => {
  const result: TreeNodeWithChildren[] = [];
  const walk = (items: TreeNodeWithChildren[]) => {
    items.forEach((item) => {
      result.push(item);
      walk(item.children);
    });
  };
  walk(nodes);
  return result;
};

export function snapshotLabel(snapshot: FinanceSnapshot, timezone: string) {
  const title = snapshot.title?.trim();
  if (title) {
    return title;
  }
  if (snapshot.period_start && snapshot.period_end) {
    return `${formatDate(snapshot.period_start, timezone)} - ${formatDate(snapshot.period_end, timezone)}`;
  }
  if (snapshot.snapshot_ts) {
    return formatDateTime(snapshot.snapshot_ts, timezone);
  }
  return snapshot.created_at;
}

export function rateSnapshotLabel(
  snapshot: FinanceRateSnapshot,
  timezone: string,
) {
  return formatDateTime(snapshot.captured_at, timezone);
}
