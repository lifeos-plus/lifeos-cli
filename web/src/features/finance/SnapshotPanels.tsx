import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import ActionButton from "@/components/ActionButton";
import { FormField, TextArea, TextInput } from "@/components/forms";
import AssetSelect from "@/components/selects/AssetSelect";
import EnumSelect from "@/components/selects/EnumSelect";
import { useToast } from "@/contexts/ToastContext";
import { useSystemTimezone } from "@/hooks/useSystemTimezone";
import type {
  FinanceAsset,
  FinanceRateSnapshot,
  FinanceSnapshot,
  FinanceSnapshotEntryCreate,
  FinanceTree,
} from "@/services/api/finance";
import type { UUID } from "@/types/primitive";

import { FinanceAmountListText, FinanceAmountText, FinanceAssetSymbol } from "./AmountText";
import { financeTextClass } from "./styles";
import {
  dateToEndIso,
  dateToStartIso,
  assetDecimalPlaces,
  flattenTree,
  formatAmountForAsset,
  formatNumberForAsset,
  isoToDateInput,
  isoToDateTimeLocal,
  localDateTimeToIso,
  nowDateTimeLocal,
  rateSnapshotLabel,
  todayDate,
  type PresetConfig,
  type SnapshotAmountState,
  type SnapshotFormMode,
  type TreeNodeWithChildren,
} from "./utils";

const SNAPSHOT_TREE_ROW_HOVER_CLASS =
  "transition-colors hover:bg-primary/10 focus-within:bg-primary/10";

export function SnapshotFormPanel({
  tree,
  preset,
  assets,
  onCreateAsset,
  treeOptions,
  selectedTreeId,
  onSelectTree,
  treeNodes,
  rateSnapshots,
  submitting,
  mode,
  initialSnapshot,
  onSubmit,
  onCancel,
}: {
  tree: FinanceTree;
  preset: PresetConfig;
  assets: FinanceAsset[];
  onCreateAsset: (code: string) => Promise<FinanceAsset>;
  treeOptions: FinanceTree[];
  selectedTreeId: UUID | null;
  onSelectTree: (treeId: UUID) => void;
  treeNodes: TreeNodeWithChildren[];
  rateSnapshots: FinanceRateSnapshot[];
  submitting: boolean;
  mode: SnapshotFormMode;
  initialSnapshot?: FinanceSnapshot | null;
  onSubmit: (payload: {
    title?: string | null;
    snapshot_ts?: string | null;
    period_start?: string | null;
    period_end?: string | null;
    primary_currency?: string | null;
    rate_snapshot_id?: UUID | null;
    note?: string | null;
    entries: FinanceSnapshotEntryCreate[];
  }) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const timezonePreference = useSystemTimezone();
  const activeTimezone = timezonePreference.timezone;
  const initialToday = todayDate(activeTimezone);
  const [snapshotTs, setSnapshotTs] = useState(() =>
    nowDateTimeLocal(activeTimezone),
  );
  const [periodStart, setPeriodStart] = useState(
    initialToday.slice(0, 8) + "01",
  );
  const [periodEnd, setPeriodEnd] = useState(initialToday);
  const [title, setTitle] = useState("");
  const [amounts, setAmounts] = useState<SnapshotAmountState>({});
  const [snapshotNote, setSnapshotNote] = useState("");
  const [selectedRateSnapshotId, setSelectedRateSnapshotId] = useState<UUID | "">("");
  const [settlementCurrency, setSettlementCurrency] = useState(tree.primary_currency);
  const flatNodes = useMemo(
    () => flattenTree(treeNodes),
    [treeNodes],
  );
  const requiredSettlementCurrencies = useMemo(
    () => getRequiredHoldingRateCurrencies(amounts, settlementCurrency),
    [amounts, settlementCurrency],
  );
  const selectedRateSnapshot = useMemo(
    () => rateSnapshots.find((snapshot) => snapshot.id === selectedRateSnapshotId) ?? null,
    [rateSnapshots, selectedRateSnapshotId],
  );
  const conversionRates = useMemo(
    () => buildConversionRateMap(selectedRateSnapshot, settlementCurrency),
    [selectedRateSnapshot, settlementCurrency],
  );
  const rateInfoByCurrency = useMemo(
    () => buildRateInfoFromRateSnapshot(selectedRateSnapshot, settlementCurrency),
    [selectedRateSnapshot, settlementCurrency],
  );
  const aggregatedAmounts = useMemo(
    () =>
      buildAggregatedSnapshotAmounts(
        treeNodes,
        amounts,
        settlementCurrency,
        conversionRates,
        assets,
      ),
    [amounts, assets, conversionRates, settlementCurrency, treeNodes],
  );
  const nativeAggregatedAmounts = useMemo(
    () => buildNativeSnapshotAmounts(treeNodes, amounts, tree.primary_currency, assets),
    [amounts, assets, tree.primary_currency, treeNodes],
  );
  const nativeSummaryRows = useMemo(
    () => buildNativeCurrencySummaryRows(treeNodes, amounts, tree.primary_currency, assets),
    [amounts, assets, tree.primary_currency, treeNodes],
  );
  const missingRateCurrencies = requiredSettlementCurrencies.filter(
    (currency) => !conversionRates[currency],
  );
  const hasCompleteRateSnapshot =
    Boolean(selectedRateSnapshotId) && missingRateCurrencies.length === 0;

  useEffect(() => {
    if (!initialSnapshot || mode === "create") {
      const currentDate = todayDate(activeTimezone);
      setSnapshotTs(nowDateTimeLocal(activeTimezone));
      setPeriodStart(currentDate.slice(0, 8) + "01");
      setPeriodEnd(currentDate);
      setTitle("");
      setAmounts({});
      setSnapshotNote("");
      setSelectedRateSnapshotId("");
      setSettlementCurrency(tree.primary_currency);
      return;
    }

    setSnapshotTs(
      mode === "copy"
        ? nowDateTimeLocal(activeTimezone)
        : isoToDateTimeLocal(initialSnapshot.snapshot_ts, activeTimezone),
    );
    setPeriodStart(isoToDateInput(initialSnapshot.period_start, activeTimezone));
    setPeriodEnd(isoToDateInput(initialSnapshot.period_end, activeTimezone));
    setTitle(initialSnapshot.title ?? "");
    setSnapshotNote(initialSnapshot.note ?? "");
    setSelectedRateSnapshotId(initialSnapshot.rate_snapshot_id ?? "");
    setSettlementCurrency(initialSnapshot.primary_currency || tree.primary_currency);
    const nextAmounts: SnapshotAmountState = {};
    (initialSnapshot.entries ?? [])
      .filter((entry) => !entry.is_auto_generated)
      .forEach((entry) => {
        nextAmounts[entry.node_id] = [
          ...(nextAmounts[entry.node_id] ?? []),
          {
            id: entry.id,
            currencyCode: entry.currency_code,
            amount: formatAmountForAsset(entry.amount, entry.currency_code, assets),
            note: entry.note ?? "",
          },
        ];
      });
    setAmounts(nextAmounts);
  }, [activeTimezone, assets, initialSnapshot, mode, tree.primary_currency]);

  useEffect(() => {
    if (mode === "create") {
      setSettlementCurrency(tree.primary_currency);
    }
  }, [mode, tree.primary_currency]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (timezonePreference.loading) return;
    let hasHoldingWithoutAsset = false;
    const entryNodes = flatNodes.filter(
      (node) => !node.children.length || (amounts[node.id] ?? []).length > 0,
    );
    const entries = entryNodes.reduce<FinanceSnapshotEntryCreate[]>((acc, node) => {
      (amounts[node.id] ?? []).forEach((holding) => {
        const amount = holding.amount.trim();
        if (!amount) {
          return;
        }
        const currencyCode = normalizeHoldingCurrency(holding.currencyCode);
        if (!currencyCode) {
          hasHoldingWithoutAsset = true;
          return;
        }
        acc.push({
          node_id: node.id,
          amount: amount.replace(",", "."),
          currency_code: currencyCode,
          note: holding.note.trim() || null,
        });
      });
      return acc;
    }, []);

    if (hasHoldingWithoutAsset) {
      toast.showWarning(t("finance.messages.holdingAssetRequired"));
      return;
    }
    if (!entries.length) {
      toast.showWarning(t("finance.messages.noEntries"));
      return;
    }
    const snapshotTimestamp =
      preset.timeMode === "instant"
        ? localDateTimeToIso(snapshotTs, activeTimezone)
        : null;
    const periodStartTimestamp =
      preset.timeMode === "period"
        ? dateToStartIso(periodStart, activeTimezone)
        : null;
    const periodEndTimestamp =
      preset.timeMode === "period"
        ? dateToEndIso(periodEnd, activeTimezone)
        : null;
    if (
      (preset.timeMode === "instant" && !snapshotTimestamp) ||
      (preset.timeMode === "period" &&
        (!periodStartTimestamp || !periodEndTimestamp))
    ) {
      toast.showWarning(t("finance.messages.invalidDateTime"));
      return;
    }
    onSubmit({
      title: title.trim() || null,
      snapshot_ts: snapshotTimestamp,
      period_start: periodStartTimestamp,
      period_end: periodEndTimestamp,
      primary_currency: settlementCurrency,
      rate_snapshot_id: selectedRateSnapshotId || null,
      note: snapshotNote || null,
      entries,
    });
    if (mode !== "edit") {
      setTitle("");
      setAmounts({});
      setSnapshotNote("");
      setSelectedRateSnapshotId("");
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div
        className={
          mode !== "create"
            ? "grid grid-cols-1 items-center gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]"
            : "flex flex-wrap items-center justify-between gap-3"
        }
      >
        <TextInput
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder={t("finance.snapshot.titlePlaceholder")}
          aria-label={t("finance.snapshot.title")}
          className={`max-w-xl ${financeTextClass.moduleTitle}`}
        />
        <div className={`flex gap-2 ${mode !== "create" ? "justify-center" : "justify-end"}`}>
          <ActionButton
            type="button"
            label={t("common.cancel")}
            iconName="x-mark"
            onClick={onCancel}
            size="sm"
            variant="ghost"
            disabled={submitting}
          />
          <ActionButton
            type="submit"
            label={submitting ? t("common.saving") : t("common.save")}
            color="primary"
            variant="solid"
            iconName="check"
            disabled={
              submitting || timezonePreference.loading || !flatNodes.length
            }
          />
        </div>
        {mode !== "create" ? <span className="hidden lg:block" aria-hidden="true" /> : null}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <InlineFinanceField label={t("finance.tree.selectTree")}>
          <select
            className="select select-bordered select-sm w-full"
            value={selectedTreeId ?? tree.id}
            onChange={(event) => {
              if (event.target.value) {
                onSelectTree(event.target.value as UUID);
              }
            }}
            disabled={mode === "edit" || submitting}
          >
            {treeOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.name}
                {option.is_default ? ` · ${t("finance.tree.default")}` : ""}
                {` · ${option.primary_currency}`}
              </option>
            ))}
          </select>
        </InlineFinanceField>

        {preset.timeMode === "instant" ? (
          <InlineFinanceField label={t("finance.snapshot.snapshotTime")}>
            <TextInput
              type="datetime-local"
              value={snapshotTs}
              onChange={(event) => setSnapshotTs(event.target.value)}
              disabled={mode === "edit" || submitting}
            />
          </InlineFinanceField>
        ) : (
          <>
            <InlineFinanceField label={t("finance.snapshot.periodStart")}>
              <TextInput
                type="date"
                value={periodStart}
                onChange={(event) => setPeriodStart(event.target.value)}
                disabled={mode === "edit" || submitting}
              />
            </InlineFinanceField>
            <InlineFinanceField label={t("finance.snapshot.periodEnd")}>
              <TextInput
                type="date"
                value={periodEnd}
                onChange={(event) => setPeriodEnd(event.target.value)}
                disabled={mode === "edit" || submitting}
              />
            </InlineFinanceField>
          </>
        )}

        <InlineFinanceField label={t("finance.snapshot.settlementCurrency")}>
          <AssetSelect
            assets={assets}
            value={settlementCurrency}
            onChange={setSettlementCurrency}
            onCreateAsset={onCreateAsset}
            disabled={submitting}
          />
        </InlineFinanceField>

        <RateSnapshotSelectPanel
          rateSnapshots={rateSnapshots}
          selectedRateSnapshotId={selectedRateSnapshotId}
          onSelectRateSnapshot={setSelectedRateSnapshotId}
          timezone={activeTimezone}
        />
      </div>

      <div className="space-y-3">
        <AssetSummaryPanel
          rows={nativeSummaryRows}
          primaryCurrency={settlementCurrency}
          assets={assets}
          rateSnapshotLabelText={
            selectedRateSnapshot
              ? rateSnapshotLabel(selectedRateSnapshot, activeTimezone)
              : t("finance.rates.noRateSnapshot")
          }
          rateInfoByCurrency={rateInfoByCurrency}
          rateSnapshotTooltip={
            selectedRateSnapshot
              ? rateSnapshotTooltip(selectedRateSnapshot, assets, activeTimezone)
              : ""
          }
          showConversions
        />

        <SnapshotEntryTreeTable
          treeNodes={treeNodes}
          amounts={amounts}
          aggregatedAmounts={hasCompleteRateSnapshot ? aggregatedAmounts : {}}
          nativeAggregatedAmounts={nativeAggregatedAmounts}
          primaryCurrency={settlementCurrency}
          conversionRates={conversionRates}
          assets={assets}
          onCreateAsset={onCreateAsset}
          hasRateSnapshot={hasCompleteRateSnapshot}
          submitting={submitting}
          onAddHolding={(node) =>
            setAmounts((prev) => addExtraHoldingToNode(prev, node, settlementCurrency, assets))
          }
          onChangeHolding={(nodeId, holdingId, patch) =>
            setAmounts((prev) => updateHoldingInNode(prev, nodeId, holdingId, patch))
          }
          onRemoveHolding={(nodeId, holdingId) =>
            setAmounts((prev) => removeHoldingFromNode(prev, nodeId, holdingId))
          }
        />
      </div>

      <FormField label={t("finance.snapshot.snapshotNote")}>
        <TextArea
          value={snapshotNote}
          onChange={(event) => setSnapshotNote(event.target.value)}
          resize="y"
        />
      </FormField>
    </form>
  );
}

function InlineFinanceField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid items-center gap-2 sm:grid-cols-[8rem_minmax(0,1fr)]">
      <span className={financeTextClass.inlineLabel}>{label}</span>
      <div className="min-w-0">{children}</div>
    </label>
  );
}

function RateSnapshotSelectPanel({
  rateSnapshots,
  selectedRateSnapshotId,
  onSelectRateSnapshot,
  timezone,
}: {
  rateSnapshots: FinanceRateSnapshot[];
  selectedRateSnapshotId: UUID | "";
  onSelectRateSnapshot: (rateSnapshotId: UUID | "") => void;
  timezone: string;
}) {
  const { t } = useTranslation();
  const options = [
    { value: "", label: t("finance.rates.noRateSnapshot") },
    ...rateSnapshots.map((snapshot) => ({
      value: snapshot.id,
      label: rateSnapshotLabel(snapshot, timezone),
    })),
  ];

  return (
    <InlineFinanceField label={t("finance.rates.title")}>
      <div className="flex flex-wrap items-center gap-3">
        <EnumSelect
          value={selectedRateSnapshotId || undefined}
          onChange={(value) => onSelectRateSnapshot((value as UUID | undefined) ?? "")}
          options={options}
          placeholder={t("finance.rates.selectSnapshot")}
          showLabel={false}
          includeEmptyOption
          size="sm"
          className="min-w-[14rem]"
        />
      </div>
    </InlineFinanceField>
  );
}

function SnapshotEntryTreeTable({
  treeNodes,
  amounts,
  aggregatedAmounts,
  nativeAggregatedAmounts,
  primaryCurrency,
  conversionRates,
  assets,
  onCreateAsset,
  hasRateSnapshot,
  submitting,
  onAddHolding,
  onChangeHolding,
  onRemoveHolding,
}: {
  treeNodes: TreeNodeWithChildren[];
  amounts: SnapshotAmountState;
  aggregatedAmounts: Record<UUID, string>;
  nativeAggregatedAmounts: Record<UUID, string>;
  primaryCurrency: string;
  conversionRates: Record<string, number>;
  assets: FinanceAsset[];
  onCreateAsset: (code: string) => Promise<FinanceAsset>;
  hasRateSnapshot: boolean;
  submitting: boolean;
  onAddHolding: (node: TreeNodeWithChildren) => void;
  onChangeHolding: (
    nodeId: UUID,
    holdingId: string,
    patch: { currencyCode?: string; amount?: string; note?: string },
  ) => void;
  onRemoveHolding: (nodeId: UUID, holdingId: string) => void;
}) {
  const { t } = useTranslation();
  const [expandedIds, setExpandedIds] = useState<Set<UUID>>(new Set());

  useEffect(() => {
    const initial = new Set<UUID>();
    includeFinanceNodeIds(treeNodes, initial);
    setExpandedIds(initial);
  }, [treeNodes]);

  const toggleNode = (nodeId: UUID) => {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const renderRows = (nodes: TreeNodeWithChildren[], depth: number): React.ReactNode[] =>
    nodes.flatMap((node) => {
      const hasChildren = node.children.length > 0;
      const isExpanded = expandedIds.has(node.id);
      const holdings = amounts[node.id] ?? [];
      const defaultCurrency = normalizeHoldingCurrency(node.currency_code || primaryCurrency);
      const defaultHolding = holdings.find(
        (holding) => normalizeHoldingCurrency(holding.currencyCode) === defaultCurrency,
      );
      const extraHoldings = holdings.filter((holding) => holding.id !== defaultHolding?.id);
      const nativeAggregatedAmount = nativeAggregatedAmounts[node.id] ?? "";
      const aggregatedAmount = aggregatedAmounts[node.id] ?? "";
      const defaultAmount = defaultHolding?.amount ?? "";
      const defaultConvertedAmount = hasRateSnapshot
        ? convertSnapshotAmount(
            defaultAmount,
            defaultCurrency,
            primaryCurrency,
            conversionRates,
            assets,
          )
        : "";
      const displayConvertedAmount = hasChildren ? aggregatedAmount : defaultConvertedAmount;
      const defaultAmountNegative = isNegativeAmount(defaultAmount);

      const rows: React.ReactNode[] = [
        <tr
          key={node.id}
          className={[
            "border-base-200",
            SNAPSHOT_TREE_ROW_HOVER_CLASS,
            hasChildren ? "border-l-4 border-l-base-content/30 bg-base-200/60" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <td className="align-top">
            <div
              className="flex items-start gap-3"
              style={{ paddingLeft: `${depth * 1.25}rem` }}
            >
              {hasChildren ? (
                <ActionButton
                  label=""
                  iconName={isExpanded ? "chevron-down" : "chevron-right"}
                  iconOnly
                  size="xs"
                  variant="ghost"
                  shape="circle"
                  className="mt-1 h-6 w-6 p-0"
                  ariaLabel={isExpanded ? t("common.collapse") : t("common.expand")}
                  ariaExpanded={isExpanded}
                  onClick={() => toggleNode(node.id)}
                />
              ) : (
                <span className="mt-1 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center text-base-content/30">
                  •
                </span>
              )}
              <div className="min-w-0 flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
                <p className={`truncate ${financeTextClass.rowTitle}`}>{node.name}</p>
              </div>
            </div>
          </td>
          <td className="align-top text-center">
            <span className="inline-flex min-h-[2.25rem] items-center">
              {hasChildren ? (
                <span className={financeTextClass.placeholder}>-</span>
              ) : (
                <FinanceAssetSymbol symbol={defaultCurrency} />
              )}
            </span>
          </td>
          <td className="align-top">
            {hasChildren ? (
              <div className="flex min-w-[12rem] items-start gap-2">
                <div
                  className={`min-h-[2.25rem] flex-1 rounded-md border border-dashed border-base-200 px-3 py-2 ${financeTextClass.helperText}`}
                >
                  <FinanceAmountListText value={nativeAggregatedAmount} />
                </div>
                <ActionButton
                  label=""
                  iconName="plus"
                  iconOnly
                  size="xs"
                  variant="ghost"
                  ariaLabel={t("finance.snapshot.addHolding")}
                  disabled={submitting}
                  onClick={() => {
                    onAddHolding(node);
                    setExpandedIds((current) => new Set(current).add(node.id));
                  }}
                />
              </div>
            ) : (
              <div className="flex min-w-[12rem] items-start gap-2">
                <TextInput
                  type="text"
                  inputMode="decimal"
                  pattern={amountInputPattern(assetDecimalPlaces(assets, defaultCurrency))}
                  size="sm"
                  className={defaultAmountNegative ? "text-warning" : "text-base-content"}
                  value={defaultAmount}
                  onChange={(event) =>
                    onChangeHolding(node.id, defaultHolding?.id ?? "", {
                      currencyCode: defaultCurrency,
                      amount: event.target.value,
                    })
                  }
                  placeholder={t("finance.snapshot.balancePlaceholder")}
                  disabled={submitting}
                />
                <ActionButton
                  label=""
                  iconName="plus"
                  iconOnly
                  size="xs"
                  variant="ghost"
                  ariaLabel={t("finance.snapshot.addHolding")}
                  disabled={submitting}
                  onClick={() => {
                    onAddHolding(node);
                    setExpandedIds((current) => new Set(current).add(node.id));
                  }}
                />
              </div>
            )}
          </td>
          <td className="align-top">
            {displayConvertedAmount ? (
              <span className="inline-flex min-h-[2.25rem] items-center rounded-md border border-dashed border-base-200 px-3 text-sm">
                <FinanceAmountText
                  amount={displayConvertedAmount}
                  currencyCode={primaryCurrency}
                  showCurrency={false}
                />
              </span>
            ) : (
              <span className={`inline-flex min-h-[2.25rem] items-center rounded-md border border-dashed border-base-200 px-3 text-sm ${financeTextClass.placeholder}`}>
                -
              </span>
            )}
          </td>
          <td className="align-top">
            {hasChildren ? (
              <span className={`inline-flex min-h-[2.25rem] items-center ${financeTextClass.placeholder}`}>
                -
              </span>
            ) : (
              <TextInput
                type="text"
                size="sm"
                value={defaultHolding?.note ?? ""}
                onChange={(event) =>
                  onChangeHolding(node.id, defaultHolding?.id ?? "", {
                    currencyCode: defaultCurrency,
                    note: event.target.value,
                  })
                }
                placeholder={t("finance.snapshot.notePlaceholder")}
                disabled={submitting}
              />
            )}
          </td>
        </tr>,
      ];

      if (isExpanded) {
        (hasChildren ? holdings : extraHoldings).forEach((holding) => {
          const holdingCurrency = normalizeHoldingCurrency(holding.currencyCode);
          const holdingPrecisionCurrency = holdingCurrency || primaryCurrency;
          const convertedHoldingAmount = hasRateSnapshot
            ? holdingCurrency
              ? convertSnapshotAmount(
                  holding.amount,
                  holdingCurrency,
                  primaryCurrency,
                  conversionRates,
                  assets,
                )
              : ""
            : "";
          const amountNegative = isNegativeAmount(holding.amount);
          rows.push(
            <tr
              key={`${node.id}:${holding.id}`}
              className={`border-base-200 border-l-4 border-l-transparent bg-base-100 ${SNAPSHOT_TREE_ROW_HOVER_CLASS}`}
            >
              <td className="align-top">
                <div
                  className="flex items-start gap-3"
                  style={{ paddingLeft: `${(depth + 1) * 1.25}rem` }}
                />
              </td>
              <td className="align-top">
                <AssetSelect
                  assets={assets}
                  value={holdingCurrency}
                  onChange={(currencyCode) =>
                    onChangeHolding(node.id, holding.id, { currencyCode })
                  }
                  onCreateAsset={onCreateAsset}
                  disabled={submitting}
                  size="sm"
                  className="min-w-[8rem]"
                />
              </td>
              <td className="align-top">
                <div className="flex min-w-[12rem] items-start gap-2">
                  <TextInput
                    type="text"
                    inputMode="decimal"
                    pattern={amountInputPattern(
                      assetDecimalPlaces(assets, holdingPrecisionCurrency),
                    )}
                    size="sm"
                    className={amountNegative ? "text-warning" : "text-base-content"}
                    value={holding.amount}
                    onChange={(event) =>
                      onChangeHolding(node.id, holding.id, { amount: event.target.value })
                    }
                    placeholder={t("finance.snapshot.balancePlaceholder")}
                    disabled={submitting}
                  />
                  <ActionButton
                    label=""
                    iconName="trash"
                    iconOnly
                    size="xs"
                    variant="ghost"
                    color="error"
                    ariaLabel={t("finance.snapshot.removeHolding")}
                    disabled={submitting}
                    onClick={() => onRemoveHolding(node.id, holding.id)}
                  />
                </div>
              </td>
              <td className="align-top">
                {convertedHoldingAmount ? (
                  <span className="inline-flex min-h-[2.25rem] items-center rounded-md border border-dashed border-base-200 px-3 text-sm">
                    <FinanceAmountText
                      amount={convertedHoldingAmount}
                      currencyCode={primaryCurrency}
                      showCurrency={false}
                    />
                  </span>
                ) : (
                  <span className={`inline-flex min-h-[2.25rem] items-center rounded-md border border-dashed border-base-200 px-3 text-sm ${financeTextClass.placeholder}`}>
                    -
                  </span>
                )}
              </td>
              <td className="align-top">
                <TextInput
                  type="text"
                  size="sm"
                  value={holding.note}
                  onChange={(event) =>
                    onChangeHolding(node.id, holding.id, { note: event.target.value })
                  }
                  placeholder={t("finance.snapshot.notePlaceholder")}
                  disabled={submitting}
                />
              </td>
            </tr>,
          );
        });
      }

      if (hasChildren && isExpanded) {
        rows.push(...renderRows(node.children, depth + 1));
      }

      return rows;
    });

  return (
    <div className="rounded-lg border border-base-200">
      <div
        className={`border-b border-base-200 bg-base-200/40 px-4 py-2 ${financeTextClass.sectionTitle}`}
      >
        {t("finance.snapshot.tableTitle")}
      </div>
      {treeNodes.length ? (
        <div className="overflow-x-auto p-3 pb-4">
          <table className="min-w-full text-sm">
            <thead className={`text-left ${financeTextClass.tableHeader}`}>
              <tr>
                <th className="w-[40%] min-w-[12rem] px-4 py-2">
                  {t("finance.snapshot.node")}
                </th>
                <th className="w-20 px-4 py-2 text-center">
                  {t("finance.snapshot.asset")}
                </th>
                <th className="min-w-[10rem] px-4 py-2">
                  {t("finance.snapshot.originalAmount")}
                </th>
                <th className="min-w-[10rem] px-4 py-2">
                  {t("finance.metrics.convertTo", { currency: primaryCurrency })}
                </th>
                <th className="min-w-[10rem] px-4 py-2">
                  {t("finance.snapshot.note")}
                </th>
              </tr>
            </thead>
            <tbody>{renderRows(treeNodes, 0)}</tbody>
          </table>
        </div>
      ) : (
        <div className={`px-4 py-8 text-center ${financeTextClass.helperText}`}>
          {t("finance.snapshot.noEntryNodes")}
        </div>
      )}
    </div>
  );
}

type AssetSummaryRow = {
  currency: string;
  amount: string;
  numericAmount: number;
};

type RateInfo = {
  baseCurrency: string;
  quoteCurrency: string;
  rate: string;
  sourcePairs: string[];
  path: string[];
};

function AssetSummaryPanel({
  rows,
  primaryCurrency,
  assets,
  rateSnapshotLabelText,
  rateSnapshotTooltip,
  rateInfoByCurrency,
  showConversions,
}: {
  rows: AssetSummaryRow[];
  primaryCurrency: string;
  assets: FinanceAsset[];
  rateSnapshotLabelText: string;
  rateSnapshotTooltip?: string;
  rateInfoByCurrency: Record<string, RateInfo>;
  showConversions: boolean;
}) {
  const { t } = useTranslation();
  const summaryRows = rows.length
    ? rows
    : [
        {
          currency: primaryCurrency.toUpperCase(),
          amount: formatNumberForAsset(0, primaryCurrency, assets),
          numericAmount: 0,
        },
      ];
  const convertedRows = summaryRows.map((row) => {
    const rateInfo =
      row.currency === primaryCurrency.toUpperCase()
        ? {
            baseCurrency: row.currency,
            quoteCurrency: primaryCurrency.toUpperCase(),
            rate: "1",
            sourcePairs: [],
            path: [row.currency],
          }
        : rateInfoByCurrency[row.currency];
    const rate = rateInfo ? Number(rateInfo.rate) : Number.NaN;
    const convertedValue =
      showConversions && Number.isFinite(rate) ? row.numericAmount * rate : null;
    return {
      ...row,
      rateInfo,
      convertedValue,
      convertedAmount:
        convertedValue === null
          ? ""
          : formatNumberForAsset(convertedValue, primaryCurrency, assets),
    };
  });
  const canShowTotal = convertedRows.every((row) => row.convertedValue !== null);
  const totalValue = canShowTotal
    ? convertedRows.reduce((sum, row) => sum + (row.convertedValue ?? 0), 0)
    : null;
  const rowsWithShare = convertedRows.map((row) => ({
    ...row,
    share:
      totalValue !== null && totalValue !== 0 && row.convertedValue !== null
        ? formatSharePercentage(row.convertedValue / totalValue)
        : "",
  }));

  return (
    <div className="rounded-lg border border-base-300 bg-base-100">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-base-200 px-3 py-2">
        <h4 className={financeTextClass.sectionTitle}>
          {t("finance.metrics.assetSummary")}
        </h4>
        <span className={`text-right ${financeTextClass.bodyMuted}`} title={rateSnapshotTooltip}>
          {t("finance.rates.tabTitle")}
          <span className="ml-2 text-base-content">{rateSnapshotLabelText}</span>
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="table table-sm">
          <thead className={financeTextClass.tableHeader}>
            <tr>
              <th>{t("finance.snapshot.currency")}</th>
              <th className="text-right">{t("finance.snapshot.amount")}</th>
              <th className="text-right">{t("finance.rates.rate")}</th>
              <th className="text-right">
                {t("finance.metrics.convertTo", { currency: primaryCurrency })}
              </th>
              <th className="text-right">{t("finance.metrics.share")}</th>
            </tr>
          </thead>
          <tbody>
            {rowsWithShare.map((row) => (
              <tr
                key={row.currency}
                className="transition-colors hover:bg-primary/10 focus-within:bg-primary/10"
              >
                <td>
                  <FinanceAssetSymbol symbol={row.currency} />
                </td>
                <td className="text-right">
                  <FinanceAmountText
                    amount={row.amount}
                    currencyCode={row.currency}
                    value={row.numericAmount}
                    showCurrency={false}
                  />
                </td>
                <td className="text-right">
                  {row.rateInfo ? (
                    <span title={rateInfoTooltip(row.rateInfo, assets)}>
                      <FinanceAmountText
                        amount={formatAmountForAsset(
                          row.rateInfo.rate,
                          row.rateInfo.quoteCurrency,
                          assets,
                        )}
                        currencyCode={row.rateInfo.quoteCurrency}
                        value={Number(row.rateInfo.rate)}
                        showCurrency={false}
                      />
                    </span>
                  ) : (
                    <span className={financeTextClass.placeholder}>-</span>
                  )}
                </td>
                <td className="text-right">
                  {row.convertedAmount ? (
                    <FinanceAmountText
                      amount={row.convertedAmount}
                      currencyCode={primaryCurrency}
                      value={row.convertedValue}
                      showCurrency={false}
                    />
                  ) : (
                    <span className={financeTextClass.placeholder}>-</span>
                  )}
                </td>
                <td className="text-right tabular-nums">
                  {row.share || <span className={financeTextClass.placeholder}>-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-end gap-3 border-t border-base-200 px-3 py-2">
        <span className={financeTextClass.inlineLabel}>
          {t("finance.metrics.totalValue")}
        </span>
        <span className="font-semibold">
          {totalValue === null ? (
            <span className={financeTextClass.placeholder}>-</span>
          ) : (
            <FinanceAmountText
              amount={formatNumberForAsset(totalValue, primaryCurrency, assets)}
              currencyCode={primaryCurrency}
              value={totalValue}
            />
          )}
        </span>
      </div>
    </div>
  );
}

export function SnapshotDetail({
  snapshot,
  assets,
  treeNodes,
  rateSnapshots,
}: {
  snapshot: FinanceSnapshot;
  assets: FinanceAsset[];
  treeNodes: TreeNodeWithChildren[];
  rateSnapshots: FinanceRateSnapshot[];
}) {
  const { t } = useTranslation();
  const activeTimezone = useSystemTimezone().timezone;
  const usesConvertedAggregation = getSummaryAggregationMode(snapshot.summary) === "converted";
  const displayTree = useMemo(
    () =>
      buildSnapshotDisplayTree(
        treeNodes,
        snapshot.entries ?? [],
        usesConvertedAggregation,
        snapshot.primary_currency,
        assets,
      ),
    [assets, snapshot.entries, snapshot.primary_currency, treeNodes, usesConvertedAggregation],
  );
  const amountsByCurrency = useMemo(
    () =>
      buildSummaryRowsFromAmountsByCurrency(
        getSummaryAmountsByCurrency(snapshot.summary),
        snapshot.primary_currency,
        assets,
      ),
    [assets, snapshot.primary_currency, snapshot.summary],
  );
  const rateInfoByCurrency = useMemo(
    () => getExchangeRateInfoByCurrency(snapshot.exchange_rates),
    [snapshot.exchange_rates],
  );

  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const expandableIds = new Set<string>();
    collectExpandableSnapshotNodeIds(displayTree, expandableIds);
    setExpandedIds(expandableIds);
  }, [displayTree]);

  const toggleNode = (nodeId: string) => {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const visibleNodes = useMemo(
    () => flattenVisibleSnapshotNodes(displayTree, expandedIds),
    [displayTree, expandedIds],
  );
  const snapshotNote = snapshot.note?.trim() ?? "";
  const rateSnapshot = rateSnapshots.find((item) => item.id === snapshot.rate_snapshot_id) ?? null;

  return (
    <div className="space-y-4">
      <AssetSummaryPanel
        rows={amountsByCurrency}
        primaryCurrency={snapshot.primary_currency}
        assets={assets}
        rateSnapshotLabelText={
          rateSnapshot
            ? rateSnapshotLabel(rateSnapshot, activeTimezone)
            : t("finance.rates.noRateSnapshot")
        }
        rateSnapshotTooltip={
          rateSnapshot
            ? rateSnapshotTooltip(rateSnapshot, assets, activeTimezone)
            : ""
        }
        rateInfoByCurrency={rateInfoByCurrency}
        showConversions
      />

      <div className="rounded-lg border border-base-300">
        <div className="border-b border-base-200 px-3 py-2">
          <h4 className={financeTextClass.sectionTitle}>
            {t("finance.metrics.details")}
          </h4>
        </div>
        <div className="overflow-x-auto">
          <table className="table table-sm">
            <thead className={financeTextClass.tableHeader}>
              <tr>
                <th className="w-[40%] min-w-[12rem] px-4 py-2">
                  {t("finance.snapshot.node")}
                </th>
                <th className="w-20 px-4 py-2 text-center">
                  {t("finance.snapshot.asset")}
                </th>
                <th className="min-w-[10rem] px-4 py-2">
                  {t("finance.snapshot.originalAmount")}
                </th>
                <th className="min-w-[10rem] px-4 py-2">
                  {t("finance.metrics.convertTo", { currency: snapshot.primary_currency })}
                </th>
                <th className="min-w-[12rem]">{t("finance.snapshot.note")}</th>
              </tr>
            </thead>
            <tbody className={financeTextClass.tableBody}>
              {visibleNodes.map((node) => {
                const hasChildren = node.children.length > 0;
                const isExpanded = expandedIds.has(node.id);
                const hasNodeLabel = node.name.trim().length > 0;
                const isAggregateRow = hasChildren || node.isAutoGenerated;

                return (
                  <tr
                    key={node.id}
                    className={[
                      "border-base-200",
                      SNAPSHOT_TREE_ROW_HOVER_CLASS,
                      isAggregateRow
                        ? "border-l-4 border-l-base-content/30 bg-base-200/60"
                        : "border-l-4 border-l-transparent",
                    ].join(" ")}
                  >
                    <td className="align-top">
                      <div
                        className="flex items-start gap-2"
                        style={{ paddingLeft: `${Math.min(node.depth, 6) * 1.5}rem` }}
                      >
                        {hasChildren ? (
                          <ActionButton
                            label=""
                            iconName={isExpanded ? "chevron-down" : "chevron-right"}
                            iconOnly
                            size="xs"
                            variant="ghost"
                            color="neutral"
                            ariaLabel={isExpanded ? t("common.collapse") : t("common.expand")}
                            ariaExpanded={isExpanded}
                            onClick={() => toggleNode(node.id)}
                          />
                        ) : hasNodeLabel ? (
                          <span className="mt-1 inline-flex h-5 w-5 flex-shrink-0 items-center justify-center text-base-content/30">
                            •
                          </span>
                        ) : (
                          <span className="inline-flex h-5 w-5 flex-shrink-0" />
                        )}
                        <div className="min-w-0 space-y-1">
                          {hasNodeLabel ? (
                            <span className={financeTextClass.rowTitle}>{node.name}</span>
                          ) : null}
                        </div>
                      </div>
                    </td>
                    <td className="align-top text-center">
                      {node.currencyCode ? (
                        <FinanceAssetSymbol symbol={node.currencyCode} />
                      ) : (
                        <span className={financeTextClass.placeholder}>-</span>
                      )}
                    </td>
                    <td className="align-top">
                      {node.currencyCode ? (
                        <FinanceAmountText
                          amount={node.amount}
                          currencyCode={node.currencyCode}
                          showCurrency={false}
                        />
                      ) : (
                        <FinanceAmountListText value={node.amount} />
                      )}
                    </td>
                    <td className="align-top">
                      {usesConvertedAggregation && node.amountConverted ? (
                        <FinanceAmountText
                          amount={formatAmountForAsset(
                            node.amountConverted,
                            snapshot.primary_currency,
                            assets,
                          )}
                          currencyCode={snapshot.primary_currency}
                          value={parseDisplayAmount(node.amountConverted)}
                          showCurrency={false}
                        />
                      ) : (
                        <span className={financeTextClass.placeholder}>-</span>
                      )}
                    </td>
                    <td className="align-top">
                      {node.note ? (
                        <span className={`block min-h-[2.25rem] ${financeTextClass.bodyMuted}`}>
                          {node.note}
                        </span>
                      ) : (
                        <span className={financeTextClass.placeholder}>-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!visibleNodes.length ? (
                <tr>
                  <td colSpan={5} className={`text-center py-6 ${financeTextClass.helperText}`}>
                    {t("finance.history.noSelection")}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      {snapshotNote ? (
        <div className={`rounded-lg border border-dashed border-base-200 p-3 ${financeTextClass.bodyMuted}`}>
          <p className={financeTextClass.rowTitle}>{t("finance.snapshot.note")}</p>
          <p className="mt-1 whitespace-pre-wrap">{snapshotNote}</p>
        </div>
      ) : null}
    </div>
  );
}

type SnapshotEntry = NonNullable<FinanceSnapshot["entries"]>[number];

type SnapshotDisplayNode = {
  id: string;
  name: string;
  depth: number;
  amount: string;
  amountConverted: string;
  currencyCode: string;
  note: string | null;
  isAutoGenerated: boolean;
  children: SnapshotDisplayNode[];
};

function buildSnapshotDisplayTree(
  treeNodes: TreeNodeWithChildren[],
  entries: SnapshotEntry[],
  useConvertedRollups: boolean,
  primaryCurrency: string,
  assets: FinanceAsset[],
): SnapshotDisplayNode[] {
  const manualEntriesByNodeId = new Map<UUID, SnapshotEntry[]>();
  const rollupEntriesByNodeId = new Map<UUID, SnapshotEntry[]>();
  entries.forEach((entry) => {
    const target = entry.is_auto_generated ? rollupEntriesByNodeId : manualEntriesByNodeId;
    target.set(entry.node_id, [...(target.get(entry.node_id) ?? []), entry]);
  });
  const usedEntryIds = new Set<string>();

  const buildNodes = (nodes: TreeNodeWithChildren[], depth: number): SnapshotDisplayNode[] =>
    nodes
      .map((node) => {
        const childNodes = buildNodes(node.children, depth + 1);
        const manualEntries = manualEntriesByNodeId.get(node.id) ?? [];
        const rollupEntries = rollupEntriesByNodeId.get(node.id) ?? [];
        const inlineSingleHolding = !childNodes.length && manualEntries.length === 1;
        const sortedManualEntries = [...manualEntries].sort((left, right) =>
          left.currency_code.localeCompare(right.currency_code),
        );
        const sortedRollupEntries = [...rollupEntries].sort((left, right) =>
          left.currency_code.localeCompare(right.currency_code),
        );
        const holdingChildren = sortedManualEntries
          .filter(() => !inlineSingleHolding)
          .map((entry) => {
            usedEntryIds.add(entry.id);
            return {
              id: `${node.id}:${entry.id}`,
              name: "",
              depth: depth + 1,
              amount: entry.amount,
              amountConverted: entry.amount_converted,
              currencyCode: entry.currency_code,
              note: entry.note ?? null,
              isAutoGenerated: false,
              children: [],
            } satisfies SnapshotDisplayNode;
          });
        if (inlineSingleHolding) {
          usedEntryIds.add(manualEntries[0].id);
        }
        const children = [...holdingChildren, ...childNodes];
        if (!rollupEntries.length && !manualEntries.length && !children.length) {
          return null;
        }
        rollupEntries.forEach((entry) => usedEntryIds.add(entry.id));
        const inlineEntry = inlineSingleHolding ? manualEntries[0] : null;
        const amountConverted = useConvertedRollups
          ? (rollupEntries[0]?.amount_converted ??
            inlineEntry?.amount_converted ??
            sumSnapshotNodeAmounts(children, primaryCurrency, assets))
          : "";
        const amount = useConvertedRollups
          ? formatAmountForAsset(amountConverted, primaryCurrency, assets)
          : (sortedRollupEntries.length ? sortedRollupEntries : inlineEntry ? [inlineEntry] : [])
              .map((entry) => `${entry.amount} ${entry.currency_code}`)
              .join(", ");
        const currencyCode = useConvertedRollups
          ? primaryCurrency
          : rollupEntries.length === 1 || inlineEntry
            ? (rollupEntries[0] ?? inlineEntry)?.currency_code ?? ""
            : "";
        return {
          id: node.id,
          name: node.name,
          depth,
          amount,
          amountConverted,
          currencyCode,
          note: inlineEntry?.note ?? null,
          isAutoGenerated: rollupEntries.length > 0,
          children,
        } satisfies SnapshotDisplayNode;
      })
      .filter(Boolean) as SnapshotDisplayNode[];

  const roots = buildNodes(treeNodes, 0);
  const orphanEntries = entries
    .filter((entry) => !usedEntryIds.has(entry.id))
    .map(
      (entry) =>
        ({
          id: entry.id,
          name: entry.node_name ?? entry.node_id,
          depth: 0,
          amount: entry.amount,
          amountConverted: entry.amount_converted,
          currencyCode: entry.currency_code,
          note: entry.note ?? null,
          isAutoGenerated: entry.is_auto_generated,
          children: [],
        }) satisfies SnapshotDisplayNode,
    );
  return roots.concat(orphanEntries);
}

function getSummaryAmountsByCurrency(
  summary?: Record<string, unknown> | null,
): Record<string, { net_amount: string }> {
  const rawAmounts = summary?.amounts_by_currency;
  if (!rawAmounts || typeof rawAmounts !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(rawAmounts as Record<string, Record<string, unknown>>).map(
      ([currency, totals]) => [
        currency,
        {
          net_amount: String(totals.net_amount ?? "0"),
        },
      ],
    ),
  );
}

function buildSummaryRowsFromAmountsByCurrency(
  amountsByCurrency: Record<string, { net_amount: string }>,
  fallbackCurrency: string,
  assets: FinanceAsset[],
): AssetSummaryRow[] {
  const rows = Object.entries(amountsByCurrency).map(([currency, totals]) => {
    const normalizedCurrency = currency.toUpperCase();
    const numericAmount = parseDisplayAmount(totals.net_amount);
    return {
      currency: normalizedCurrency,
      amount: formatAmountForAsset(totals.net_amount, normalizedCurrency, assets),
      numericAmount: Number.isFinite(numericAmount) ? numericAmount : 0,
    };
  });
  if (rows.length) {
    return rows.sort((left, right) => left.currency.localeCompare(right.currency));
  }
  return [
    {
      currency: fallbackCurrency.toUpperCase(),
      amount: formatNumberForAsset(0, fallbackCurrency, assets),
      numericAmount: 0,
    },
  ];
}

function getSummaryAggregationMode(summary?: Record<string, unknown> | null): string {
  const mode = summary?.aggregation_mode;
  return typeof mode === "string" ? mode : "native_by_currency";
}

function buildRateInfoFromRateSnapshot(
  rateSnapshot: FinanceRateSnapshot | null,
  primaryCurrency: string,
): Record<string, RateInfo> {
  const primary = primaryCurrency.toUpperCase();
  const result: Record<string, RateInfo> = {
    [primary]: {
      baseCurrency: primary,
      quoteCurrency: primary,
      rate: "1",
      sourcePairs: [],
      path: [primary],
    },
  };
  (rateSnapshot?.entries ?? []).forEach((entry) => {
    const baseCurrency = entry.base_currency.toUpperCase();
    const quoteCurrency = entry.quote_currency.toUpperCase();
    const rate = Number(entry.rate);
    if (!Number.isFinite(rate) || rate <= 0) {
      return;
    }
    if (quoteCurrency === primary) {
      result[baseCurrency] = {
        baseCurrency,
        quoteCurrency,
        rate: entry.rate,
        sourcePairs: [`${baseCurrency}/${quoteCurrency}`],
        path: [baseCurrency, quoteCurrency],
      };
    }
    if (baseCurrency === primary) {
      result[quoteCurrency] = {
        baseCurrency: quoteCurrency,
        quoteCurrency: primary,
        rate: String(1 / rate),
        sourcePairs: [`${baseCurrency}/${quoteCurrency}`],
        path: [quoteCurrency, baseCurrency],
      };
    }
  });
  return result;
}

function getExchangeRateInfoByCurrency(
  exchangeRates?: Record<string, unknown> | null,
): Record<string, RateInfo> {
  const rates = exchangeRates?.rates;
  if (!rates || typeof rates !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(rates as Record<string, Record<string, unknown>>).map(
      ([currency, value]) => [
        currency.toUpperCase(),
        {
          baseCurrency: String(value.base_currency ?? currency).toUpperCase(),
          quoteCurrency: String(value.quote_currency ?? "").toUpperCase(),
          rate: String(value.rate ?? ""),
          sourcePairs: Array.isArray(value.source_pairs)
            ? value.source_pairs.map((pair) => String(pair))
            : [],
          path: Array.isArray(value.path) ? value.path.map((item) => String(item)) : [],
        } satisfies RateInfo,
      ],
    ),
  );
}

function rateInfoTooltip(rateInfo: RateInfo, assets: FinanceAsset[]): string {
  const primaryLine = `1 ${rateInfo.baseCurrency} = ${formatAmountForAsset(
    rateInfo.rate,
    rateInfo.quoteCurrency,
    assets,
  )} ${
    rateInfo.quoteCurrency
  }`;
  const sourceLines = rateInfo.sourcePairs.map((pair) => pair.replace("/", " = "));
  const pathLine = rateInfo.path.length ? rateInfo.path.join(" -> ") : "";
  return [primaryLine, ...sourceLines, pathLine].filter(Boolean).join("\n");
}

function formatSharePercentage(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function rateSnapshotTooltip(
  snapshot: FinanceRateSnapshot,
  assets: FinanceAsset[],
  timezone: string,
): string {
  const lines = (snapshot.entries ?? []).map((entry) => {
    const baseAmount = formatAmountForAsset("1", entry.base_currency, assets);
    const quoteAmount = formatAmountForAsset(entry.rate, entry.quote_currency, assets);
    return `${baseAmount} ${entry.base_currency} = ${quoteAmount} ${entry.quote_currency}`;
  });
  return lines.length
    ? lines.join("\n")
    : rateSnapshotLabel(snapshot, timezone);
}

function includeFinanceNodeIds(nodes: TreeNodeWithChildren[], target: Set<UUID>) {
  nodes.forEach((node) => {
    target.add(node.id);
    if (node.children.length) {
      includeFinanceNodeIds(node.children, target);
    }
  });
}

function createHoldingId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `holding-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function normalizeHoldingCurrency(currency: string): string {
  return currency.trim().toUpperCase();
}

function nextExtraHoldingCurrency(
  existingCurrencies: string[],
  defaultCurrency: string,
  assets: FinanceAsset[],
): string {
  const used = new Set(existingCurrencies.map(normalizeHoldingCurrency));
  const normalizedDefault = normalizeHoldingCurrency(defaultCurrency);
  const available = assets
    .map((asset) => asset.code)
    .find((assetCode) => {
      const normalized = normalizeHoldingCurrency(assetCode);
      return normalized !== normalizedDefault && !used.has(normalized);
    });
  return available ?? "";
}

function addExtraHoldingToNode(
  current: SnapshotAmountState,
  node: TreeNodeWithChildren,
  primaryCurrency: string,
  assets: FinanceAsset[],
): SnapshotAmountState {
  const existing = current[node.id] ?? [];
  const currencyCode = nextExtraHoldingCurrency(
    existing.map((holding) => holding.currencyCode),
    node.currency_code || primaryCurrency,
    assets,
  );
  return {
    ...current,
    [node.id]: [
      ...existing,
      {
        id: createHoldingId(),
        currencyCode,
        amount: "",
        note: "",
      },
    ],
  };
}

function updateHoldingInNode(
  current: SnapshotAmountState,
  nodeId: UUID,
  holdingId: string,
  patch: { currencyCode?: string; amount?: string; note?: string },
): SnapshotAmountState {
  if (!holdingId) {
    const created = {
      id: createHoldingId(),
      currencyCode: normalizeHoldingCurrency(patch.currencyCode ?? ""),
      amount: patch.amount ?? "",
      note: patch.note ?? "",
    };
    return {
      ...current,
      [nodeId]: [...(current[nodeId] ?? []), created],
    };
  }
  return {
    ...current,
    [nodeId]: (current[nodeId] ?? []).map((holding) =>
      holding.id === holdingId
        ? {
            ...holding,
            ...patch,
            currencyCode:
              patch.currencyCode !== undefined
                ? normalizeHoldingCurrency(patch.currencyCode)
                : holding.currencyCode,
          }
        : holding,
    ),
  };
}

function removeHoldingFromNode(
  current: SnapshotAmountState,
  nodeId: UUID,
  holdingId: string,
): SnapshotAmountState {
  const remaining = (current[nodeId] ?? []).filter((holding) => holding.id !== holdingId);
  if (remaining.length) {
    return { ...current, [nodeId]: remaining };
  }
  const next = { ...current };
  delete next[nodeId];
  return next;
}

function getRequiredHoldingRateCurrencies(
  amounts: SnapshotAmountState,
  settlementCurrency: string,
): string[] {
  const settlement = normalizeHoldingCurrency(settlementCurrency);
  const currencies = new Set<string>();
  Object.values(amounts).forEach((holdings) => {
    holdings.forEach((holding) => {
      const amount = holding.amount.trim();
      const currency = normalizeHoldingCurrency(holding.currencyCode);
      if (amount && currency && currency !== settlement) {
        currencies.add(currency);
      }
    });
  });
  return Array.from(currencies).sort((left, right) => left.localeCompare(right));
}

function buildAggregatedSnapshotAmounts(
  nodes: TreeNodeWithChildren[],
  amounts: SnapshotAmountState,
  primaryCurrency: string,
  conversionRates: Record<string, number>,
  assets: FinanceAsset[],
): Record<UUID, string> {
  const result: Record<UUID, string> = {};

  const visit = (node: TreeNodeWithChildren): string => {
    const convertedAmounts = (amounts[node.id] ?? [])
      .map((holding) =>
        convertSnapshotAmount(
          holding.amount,
          holding.currencyCode || node.currency_code || primaryCurrency,
          primaryCurrency,
          conversionRates,
          assets,
        ),
      )
      .filter(Boolean);
    if (node.children.length) {
      convertedAmounts.push(...node.children.map(visit));
    }
    const total = sumAmountStrings(convertedAmounts, primaryCurrency, assets);
    if (total) {
      result[node.id] = total;
    }
    return total;
  };

  nodes.forEach(visit);
  return result;
}

function buildNativeSnapshotAmounts(
  nodes: TreeNodeWithChildren[],
  amounts: SnapshotAmountState,
  primaryCurrency: string,
  assets: FinanceAsset[],
): Record<UUID, string> {
  const result: Record<UUID, string> = {};

  const visit = (node: TreeNodeWithChildren): Map<string, number> => {
    const totals = new Map<string, number>();
    (amounts[node.id] ?? []).forEach((holding) => {
      const amount = holding.amount.trim() ?? "";
      const parsed = parseDisplayAmount(amount);
      if (!amount || !Number.isFinite(parsed)) {
        return;
      }
      const currency = normalizeHoldingCurrency(
        holding.currencyCode || node.currency_code || primaryCurrency,
      );
      totals.set(currency, (totals.get(currency) ?? 0) + parsed);
    });
    if (node.children.length) {
      node.children.forEach((child) => {
        visit(child).forEach((value, currency) => {
          totals.set(currency, (totals.get(currency) ?? 0) + value);
        });
      });
    }
    if (totals.size) {
      result[node.id] = Array.from(totals.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([currency, value]) => `${formatNumberForAsset(value, currency, assets)} ${currency}`)
        .join(", ");
    }
    return totals;
  };

  nodes.forEach(visit);
  return result;
}

function buildNativeCurrencySummaryRows(
  nodes: TreeNodeWithChildren[],
  amounts: SnapshotAmountState,
  primaryCurrency: string,
  assets: FinanceAsset[],
): AssetSummaryRow[] {
  const totals = new Map<string, number>();
  const visit = (node: TreeNodeWithChildren) => {
    (amounts[node.id] ?? []).forEach((holding) => {
      const amount = holding.amount.trim() ?? "";
      const parsed = parseDisplayAmount(amount);
      if (!amount || !Number.isFinite(parsed)) {
        return;
      }
      const currency = normalizeHoldingCurrency(
        holding.currencyCode || node.currency_code || primaryCurrency,
      );
      totals.set(currency, (totals.get(currency) ?? 0) + parsed);
    });
    node.children.forEach(visit);
  };
  nodes.forEach(visit);
  return Array.from(totals.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([currency, value]) => ({
      currency,
      amount: formatNumberForAsset(value, currency, assets),
      numericAmount: value,
    }));
}

function buildConversionRateMap(
  rateSnapshot: FinanceRateSnapshot | null,
  primaryCurrency: string,
): Record<string, number> {
  const normalizedPrimary = primaryCurrency.toUpperCase();
  const result: Record<string, number> = { [normalizedPrimary]: 1 };
  (rateSnapshot?.entries ?? []).forEach((entry) => {
    const baseCurrency = entry.base_currency.toUpperCase();
    const quoteCurrency = entry.quote_currency.toUpperCase();
    const rate = Number(entry.rate);
    if (!Number.isFinite(rate) || rate <= 0) {
      return;
    }
    if (quoteCurrency === normalizedPrimary) {
      result[baseCurrency] = rate;
    }
    if (baseCurrency === normalizedPrimary) {
      result[quoteCurrency] = 1 / rate;
    }
  });
  return result;
}

function convertSnapshotAmount(
  amount: string,
  currencyCode: string,
  primaryCurrency: string,
  conversionRates: Record<string, number>,
  assets: FinanceAsset[],
): string {
  const trimmed = amount.trim();
  if (!trimmed) {
    return "";
  }
  const parsed = parseDisplayAmount(trimmed);
  if (!Number.isFinite(parsed)) {
    return "";
  }
  const currency = currencyCode.toUpperCase();
  const primary = primaryCurrency.toUpperCase();
  const rate = currency === primary ? 1 : conversionRates[currency];
  if (!Number.isFinite(rate)) {
    return "";
  }
  return formatNumberForAsset(parsed * rate, primary, assets);
}

function sumAmountStrings(
  values: string[],
  currencyCode?: string,
  assets: FinanceAsset[] = [],
): string {
  let hasValue = false;
  const total = values.reduce((acc, value) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return acc;
    }
    const parsed = parseDisplayAmount(trimmed);
    if (!Number.isFinite(parsed)) {
      return acc;
    }
    hasValue = true;
    return acc + parsed;
  }, 0);
  if (!hasValue) {
    return "";
  }
  return currencyCode ? formatNumberForAsset(total, currencyCode, assets) : total.toString();
}

function sumSnapshotNodeAmounts(
  nodes: SnapshotDisplayNode[],
  primaryCurrency: string,
  assets: FinanceAsset[],
): string {
  return sumAmountStrings(
    nodes.map((node) => node.amountConverted),
    primaryCurrency,
    assets,
  );
}

function isNegativeAmount(value: string | null | undefined): boolean {
  const numeric = parseDisplayAmount(value ?? "");
  return Number.isFinite(numeric) && numeric < 0;
}

function parseDisplayAmount(value: string): number {
  return Number(value.replace(",", "."));
}

function amountInputPattern(decimalPlaces: number): string {
  if (decimalPlaces <= 0) {
    return "-?[0-9]*";
  }
  return `-?[0-9]*[.,]?[0-9]{0,${decimalPlaces}}`;
}

function collectExpandableSnapshotNodeIds(
  nodes: SnapshotDisplayNode[],
  target: Set<string>,
) {
  nodes.forEach((node) => {
    if (node.children.length) {
      target.add(node.id);
      collectExpandableSnapshotNodeIds(node.children, target);
    }
  });
}

function flattenVisibleSnapshotNodes(
  nodes: SnapshotDisplayNode[],
  expandedIds: Set<string>,
): SnapshotDisplayNode[] {
  const result: SnapshotDisplayNode[] = [];
  const walk = (items: SnapshotDisplayNode[]) => {
    items.forEach((node) => {
      result.push(node);
      if (node.children.length && expandedIds.has(node.id)) {
        walk(node.children);
      }
    });
  };
  walk(nodes);
  return result;
}
