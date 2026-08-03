import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import ActionButton, { CreateNewButton } from "@/components/ActionButton";
import ConfirmDialog from "@/components/ConfirmDialog";
import { FormField, TextInput } from "@/components/forms";
import LoadingSpinner from "@/components/LoadingSpinner";
import AssetSelect from "@/components/selects/AssetSelect";
import { useToast } from "@/contexts/ToastContext";
import ModalBase from "@/layouts/ModalBase";
import Surface from "@/layouts/Surface";
import {
  financeApi,
  type FinanceRateSnapshot,
  type FinanceRateSnapshotCreate,
  type FinanceRateSnapshotUpdate,
  type FinanceAsset,
} from "@/services/api/finance";
import {
  addFinanceRateSnapshotToListCache,
  invalidateAllFinanceSnapshots,
  invalidateFinanceAssets,
  invalidateFinanceRateSnapshots,
  removeFinanceRateSnapshotCache,
  removeFinanceRateSnapshotFromListCache,
  setFinanceRateSnapshotCache,
  setFinanceRateSnapshotInListCache,
} from "@/services/api/cacheInvalidation/finance";
import { financeKeys } from "@/services/api/queryKeys";
import type { UUID } from "@/types/primitive";
import { formatDateTime } from "@/utils/datetime";

import {
  SnapshotActionButtons,
  SnapshotNavigator,
  SnapshotSelectorToolbar,
} from "./SnapshotChrome";
import { FinanceAmountText, FinanceAssetSymbol } from "./AmountText";
import {
  isoToDateTimeLocal,
  localDateTimeToIso,
  nowDateTimeLocal,
  formatAmountForAsset,
  rateSnapshotLabel,
  type RateRowState,
  type RateSnapshotFormMode,
} from "./utils";
import { financeTextClass } from "./styles";
import { useFinanceAssetSource } from "./useFinanceAssetSource";

export function RateSnapshotsWorkspace() {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { assets, createAsset } = useFinanceAssetSource();
  const [selectedRateSnapshotId, setSelectedRateSnapshotId] = useState<UUID | null>(null);
  const [rateFormVisible, setRateFormVisible] = useState(false);
  const [rateFormMode, setRateFormMode] = useState<RateSnapshotFormMode>("create");
  const [pendingDeleteRateSnapshot, setPendingDeleteRateSnapshot] =
    useState<FinanceRateSnapshot | null>(null);
  const [deletedRateSnapshotIds, setDeletedRateSnapshotIds] = useState<Set<UUID>>(
    () => new Set(),
  );
  const [capturedAt, setCapturedAt] = useState(nowDateTimeLocal());
  const [source, setSource] = useState("manual");
  const [note, setNote] = useState("");
  const [rateRows, setRateRows] = useState<RateRowState[]>([
    { baseAmount: "1", baseCurrency: "BTC", quoteAmount: "", quoteCurrency: "USDT" },
  ]);
  const rateSnapshotFormId = "finance-rate-snapshot-form";

  const rateSnapshotsQuery = useQuery({
    queryKey: financeKeys.rateSnapshots(),
    queryFn: () => financeApi.listRateSnapshots(),
  });

  const createRateSnapshotMutation = useMutation({
    mutationFn: (payload: FinanceRateSnapshotCreate) => financeApi.createRateSnapshot(payload),
    onSuccess: async (rateSnapshot) => {
      toast.showSuccess(t("finance.messages.rateSnapshotCreated"));
      setRateRows([
        { baseAmount: "1", baseCurrency: "BTC", quoteAmount: "", quoteCurrency: "USDT" },
      ]);
      setNote("");
      setSelectedRateSnapshotId(rateSnapshot.id);
      setRateFormVisible(false);
      setRateFormMode("create");
      setFinanceRateSnapshotCache(queryClient, rateSnapshot);
      addFinanceRateSnapshotToListCache(queryClient, rateSnapshot);
      await invalidateFinanceRateSnapshots(queryClient);
    },
    onError: (error) => {
      toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
    },
  });

  const updateRateSnapshotMutation = useMutation({
    mutationFn: ({
      rateSnapshotId,
      payload,
    }: {
      rateSnapshotId: UUID;
      payload: FinanceRateSnapshotUpdate;
    }) => financeApi.updateRateSnapshot(rateSnapshotId, payload),
    onSuccess: async (rateSnapshot) => {
      toast.showSuccess(t("finance.messages.rateSnapshotUpdated"));
      setSelectedRateSnapshotId(rateSnapshot.id);
      setRateFormVisible(false);
      setRateFormMode("create");
      setFinanceRateSnapshotCache(queryClient, rateSnapshot);
      setFinanceRateSnapshotInListCache(queryClient, rateSnapshot);
      await Promise.all([
        invalidateFinanceRateSnapshots(queryClient),
        invalidateAllFinanceSnapshots(queryClient),
      ]);
    },
    onError: (error) => {
      toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
    },
  });

  const deleteRateSnapshotMutation = useMutation({
    mutationFn: (rateSnapshotId: UUID) => financeApi.deleteRateSnapshot(rateSnapshotId),
    onMutate: async (rateSnapshotId) => {
      const deletedIndex = snapshots.findIndex((snapshot) => snapshot.id === rateSnapshotId);
      const nextSnapshot = snapshots[deletedIndex + 1] ?? snapshots[deletedIndex - 1] ?? null;
      await queryClient.cancelQueries({
        queryKey: financeKeys.rateSnapshot(rateSnapshotId),
        exact: true,
      });
      setDeletedRateSnapshotIds((existing) => new Set(existing).add(rateSnapshotId));
      if (currentSnapshot?.id === rateSnapshotId) {
        setSelectedRateSnapshotId(nextSnapshot?.id ?? null);
      }
      removeFinanceRateSnapshotFromListCache(queryClient, rateSnapshotId);
      removeFinanceRateSnapshotCache(queryClient, rateSnapshotId);
      return { previousSelectedRateSnapshotId: selectedRateSnapshotId };
    },
    onSuccess: async () => {
      toast.showSuccess(t("finance.messages.rateSnapshotDeleted"));
      setPendingDeleteRateSnapshot(null);
      setRateFormVisible(false);
      setRateFormMode("create");
      await Promise.all([
        invalidateFinanceRateSnapshots(queryClient),
        invalidateAllFinanceSnapshots(queryClient),
      ]);
    },
    onError: async (error, rateSnapshotId, context) => {
      setDeletedRateSnapshotIds((existing) => {
        const next = new Set(existing);
        next.delete(rateSnapshotId);
        return next;
      });
      setSelectedRateSnapshotId(context?.previousSelectedRateSnapshotId ?? null);
      await invalidateFinanceRateSnapshots(queryClient);
      toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
    },
  });

  const submitRateSnapshot = (event: React.FormEvent) => {
    event.preventDefault();
    const entries = rateRows
      .map((row) => {
        const baseAmountValue = row.baseAmount.trim();
        const quoteAmountValue = row.quoteAmount.trim();
        const baseAmount = Number(baseAmountValue);
        const quoteAmount = Number(quoteAmountValue);
        const baseCurrency = row.baseCurrency.trim().toUpperCase();
        const quoteCurrency = row.quoteCurrency.trim().toUpperCase();
        return {
          base_currency: baseCurrency,
          quote_currency: quoteCurrency,
          rate:
            Number.isFinite(baseAmount) && baseAmount > 0 && Number.isFinite(quoteAmount)
              ? baseAmount === 1
                ? quoteAmountValue
                : String(quoteAmount / baseAmount)
              : "",
          source: source.trim() || "manual",
        };
      })
      .filter((entry) => entry.base_currency || entry.quote_currency || entry.rate);
    if (!entries.length) {
      toast.showWarning(t("finance.messages.rateSnapshotRatesRequired"));
      return;
    }
    if (
      entries.some((entry) => {
        const numericRate = Number(entry.rate);
        return (
          !entry.base_currency ||
          !entry.quote_currency ||
          entry.base_currency === entry.quote_currency ||
          !Number.isFinite(numericRate) ||
          numericRate <= 0
        );
      })
    ) {
      toast.showWarning(t("finance.messages.rateSnapshotRatesRequired"));
      return;
    }
    const payload = {
      captured_at: localDateTimeToIso(capturedAt),
      source: source.trim() || "manual",
      note: note.trim() || null,
      entries,
    };
    if (rateFormMode === "edit" && currentSnapshot) {
      updateRateSnapshotMutation.mutate({
        rateSnapshotId: currentSnapshot.id,
        payload,
      });
      return;
    }
    createRateSnapshotMutation.mutate(payload);
  };

  const rawSnapshots = rateSnapshotsQuery.data?.items ?? [];
  const snapshots = rawSnapshots.filter((snapshot) => !deletedRateSnapshotIds.has(snapshot.id));
  const currentSnapshot =
    snapshots.find((snapshot) => snapshot.id === selectedRateSnapshotId) ?? snapshots[0] ?? null;
  const currentPosition = currentSnapshot
    ? snapshots.findIndex((snapshot) => snapshot.id === currentSnapshot.id) + 1
    : 0;
  const hasPrevious = currentPosition > 1;
  const hasNext = currentPosition > 0 && currentPosition < snapshots.length;
  const snapshotOptions = snapshots.map((snapshot) => ({
    value: snapshot.id,
    label: rateSnapshotLabel(snapshot),
  }));

  const selectRateSnapshot = (snapshotId: UUID) => {
    setSelectedRateSnapshotId(snapshotId);
    setRateFormVisible(false);
    setRateFormMode("create");
  };

  const resetRateSnapshotForm = () => {
    setCapturedAt(nowDateTimeLocal());
    setSource("manual");
    setNote("");
    setRateRows([
      { baseAmount: "1", baseCurrency: "BTC", quoteAmount: "", quoteCurrency: "USDT" },
    ]);
  };

  const openCreateRateSnapshotForm = () => {
    resetRateSnapshotForm();
    setRateFormMode("create");
    setRateFormVisible(true);
  };

  const openEditRateSnapshotForm = () => {
    if (!currentSnapshot) return;
    setCapturedAt(isoToDateTimeLocal(currentSnapshot.captured_at));
    setSource(currentSnapshot.source || "manual");
    setNote(currentSnapshot.note ?? "");
    setRateRows(
      (currentSnapshot.entries ?? []).map((entry) => ({
        baseAmount: "1",
        baseCurrency: entry.base_currency,
        quoteAmount: formatAmountForAsset(entry.rate, entry.quote_currency, assets),
        quoteCurrency: entry.quote_currency,
      })),
    );
    setRateFormMode("edit");
    setRateFormVisible(true);
  };

  const openCopyRateSnapshotForm = () => {
    if (!currentSnapshot) return;
    setCapturedAt(nowDateTimeLocal());
    setSource(currentSnapshot.source || "manual");
    setNote(currentSnapshot.note ?? "");
    setRateRows(
      (currentSnapshot.entries ?? []).map((entry) => ({
        baseAmount: "1",
        baseCurrency: entry.base_currency,
        quoteAmount: formatAmountForAsset(entry.rate, entry.quote_currency, assets),
        quoteCurrency: entry.quote_currency,
      })),
    );
    setRateFormMode("copy");
    setRateFormVisible(true);
  };

  const closeRateSnapshotForm = () => {
    setRateFormVisible(false);
    setRateFormMode("create");
  };

  const moveRateSnapshot = (direction: -1 | 1) => {
    if (!currentSnapshot) return;
    const index = snapshots.findIndex((snapshot) => snapshot.id === currentSnapshot.id);
    const next = snapshots[index + direction];
    if (next) {
      selectRateSnapshot(next.id);
    }
  };

  return (
    <div className="space-y-6">
      <SnapshotSelectorToolbar
        description={t("finance.rates.tabDescription")}
        selectValue={currentSnapshot?.id ?? null}
        selectOptions={snapshotOptions}
        selectPlaceholder={t("finance.rates.selectSnapshot")}
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        createLabel={t("finance.snapshot.new")}
        onSelect={selectRateSnapshot}
        onPrevious={() => moveRateSnapshot(-1)}
        onNext={() => moveRateSnapshot(1)}
        onCreate={openCreateRateSnapshotForm}
      />

      <Surface as="section" padding="md" radius="xl" border="subtle" elevation="subtle">
        {rateFormVisible ? (
          <>
            <SnapshotNavigator
              title={
                rateFormMode === "edit"
                  ? t("finance.rates.editSnapshot")
                  : rateFormMode === "copy"
                    ? t("finance.rates.copySnapshot")
                  : t("finance.rates.createSnapshot")
              }
            />
            <div
              className={`mt-4 flex gap-2 ${
                rateFormMode === "create" ? "justify-end" : "justify-center"
              }`}
            >
              <ActionButton
                label={t("common.cancel")}
                iconName="x-mark"
                onClick={closeRateSnapshotForm}
                size="sm"
                variant="ghost"
                disabled={
                  createRateSnapshotMutation.isPending || updateRateSnapshotMutation.isPending
                }
              />
              <ActionButton
                type="submit"
                form={rateSnapshotFormId}
                label={
                  createRateSnapshotMutation.isPending || updateRateSnapshotMutation.isPending
                    ? t("common.saving")
                    : t("common.save")
                }
                iconName="check"
                color="primary"
                variant="solid"
                disabled={
                  createRateSnapshotMutation.isPending || updateRateSnapshotMutation.isPending
                }
              />
            </div>
            <form id={rateSnapshotFormId} className="mt-4 space-y-4" onSubmit={submitRateSnapshot}>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <FormField label={t("finance.rates.capturedAt")}>
                  <TextInput
                    type="datetime-local"
                    value={capturedAt}
                    onChange={(event) => setCapturedAt(event.target.value)}
                  />
                </FormField>
                <FormField label={t("finance.rates.source")}>
                  <TextInput value={source} onChange={(event) => setSource(event.target.value)} />
                </FormField>
                <FormField label={t("finance.rates.note")}>
                  <TextInput value={note} onChange={(event) => setNote(event.target.value)} />
                </FormField>
              </div>

              <div className="rounded-lg border border-base-200">
                <div
                  className={`grid grid-cols-[minmax(5rem,0.7fr)_minmax(7rem,1fr)_auto_minmax(5rem,0.7fr)_minmax(7rem,1fr)_auto] gap-2 border-b border-base-200 px-3 py-2 ${financeTextClass.tableHeader}`}
                >
                  <span>{t("finance.rates.baseAmount")}</span>
                  <span>{t("finance.rates.baseAsset")}</span>
                  <span />
                  <span>{t("finance.rates.quoteAmount")}</span>
                  <span>{t("finance.rates.quoteAsset")}</span>
                  <span />
                </div>
                <div className="space-y-2 p-3">
                  {rateRows.map((row, index) => (
                    <div
                      key={index}
                      className="grid grid-cols-[minmax(5rem,0.7fr)_minmax(7rem,1fr)_auto_minmax(5rem,0.7fr)_minmax(7rem,1fr)_auto] items-center gap-2 rounded-md transition-colors hover:bg-primary/10 focus-within:bg-primary/10"
                    >
                      <TextInput
                        size="sm"
                        inputMode="decimal"
                        value={row.baseAmount}
                        onChange={(event) =>
                          setRateRows((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, baseAmount: event.target.value }
                                : item,
                            ),
                          )
                        }
                      />
                      <AssetSelect
                        assets={assets}
                        value={row.baseCurrency}
                        onChange={(assetCode) =>
                          setRateRows((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, baseCurrency: assetCode } : item,
                            ),
                          )
                        }
                        onCreateAsset={createAsset}
                        disabled={
                          createRateSnapshotMutation.isPending ||
                          updateRateSnapshotMutation.isPending
                        }
                      />
                      <span className={`text-center ${financeTextClass.placeholder}`}>=</span>
                      <TextInput
                        size="sm"
                        inputMode="decimal"
                        value={row.quoteAmount}
                        onChange={(event) =>
                          setRateRows((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, quoteAmount: event.target.value }
                                : item,
                            ),
                          )
                        }
                      />
                      <AssetSelect
                        assets={assets}
                        value={row.quoteCurrency}
                        onChange={(assetCode) =>
                          setRateRows((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, quoteCurrency: assetCode } : item,
                            ),
                          )
                        }
                        onCreateAsset={createAsset}
                        disabled={
                          createRateSnapshotMutation.isPending ||
                          updateRateSnapshotMutation.isPending
                        }
                      />
                      <ActionButton
                        type="button"
                        label=""
                        iconName="trash"
                        iconOnly
                        size="sm"
                        variant="ghost"
                        color="error"
                        ariaLabel={t("common.delete")}
                        disabled={rateRows.length === 1}
                        onClick={() =>
                          setRateRows((current) =>
                            current.filter((_, itemIndex) => itemIndex !== index),
                          )
                        }
                      />
                    </div>
                  ))}
                  <ActionButton
                    type="button"
                    label={t("finance.rates.addRate")}
                    iconName="plus"
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      setRateRows((current) =>
                        current.concat({
                          baseAmount: "1",
                          baseCurrency: "",
                          quoteAmount: "",
                          quoteCurrency: "",
                        }),
                      )
                    }
                  />
                </div>
              </div>
            </form>
          </>
        ) : rateSnapshotsQuery.isLoading ? (
          <LoadingSpinner />
        ) : currentSnapshot ? (
          <>
            <SnapshotNavigator
              title={rateSnapshotLabel(currentSnapshot)}
              rightSlot={
                <SnapshotActionButtons
                  editLabel={t("common.edit")}
                  copyLabel={t("common.copy")}
                  deleteLabel={t("common.delete")}
                  disabled={deleteRateSnapshotMutation.isPending}
                  deleteDisabled={deleteRateSnapshotMutation.isPending}
                  onEdit={openEditRateSnapshotForm}
                  onCopy={openCopyRateSnapshotForm}
                  onDelete={() => setPendingDeleteRateSnapshot(currentSnapshot)}
                />
              }
            />
            <div className="grid grid-cols-1 gap-3 rounded-lg border border-base-200 bg-base-200/30 p-3 sm:grid-cols-3">
              <div>
                <p className={financeTextClass.fieldLabel}>
                  {t("finance.rates.capturedAt")}
                </p>
                <p className={`mt-1 ${financeTextClass.rowTitle}`}>
                  {formatDateTime(currentSnapshot.captured_at)}
                </p>
              </div>
              <div>
                <p className={financeTextClass.fieldLabel}>
                  {t("finance.rates.source")}
                </p>
                <p className={`mt-1 ${financeTextClass.rowTitle}`}>
                  {currentSnapshot.source || "-"}
                </p>
              </div>
              <div>
                <p className={financeTextClass.fieldLabel}>
                  {t("finance.rates.note")}
                </p>
                <p className={`mt-1 whitespace-pre-wrap ${financeTextClass.bodyMuted}`}>
                  {currentSnapshot.note || "-"}
                </p>
              </div>
            </div>
            <div className="overflow-x-auto rounded-lg border border-base-200">
              <table className="table table-sm">
                <thead className={financeTextClass.tableHeader}>
                  <tr>
                    <th className="text-right">{t("finance.rates.baseAmount")}</th>
                    <th>{t("finance.rates.baseAsset")}</th>
                    <th className="text-center">{t("finance.rates.rate")}</th>
                    <th className="text-right">{t("finance.rates.quoteAmount")}</th>
                    <th>{t("finance.rates.quoteAsset")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(currentSnapshot.entries ?? []).map((entry) => (
                    <tr
                      key={entry.id}
                      className="transition-colors hover:bg-primary/10 focus-within:bg-primary/10"
                    >
                      <RateEntryEquationCells entry={entry} assets={assets} />
                    </tr>
                  ))}
                  {!(currentSnapshot.entries ?? []).length ? (
                    <tr>
                      <td colSpan={5} className={`text-center ${financeTextClass.placeholder}`}>
                        -
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div
            className={`rounded-lg border border-dashed border-base-300 p-6 text-center ${financeTextClass.helperText}`}
          >
            {t("finance.rates.empty")}
            <div className="mt-4 flex justify-center">
              <CreateNewButton
                label={t("finance.snapshot.new")}
                onClick={openCreateRateSnapshotForm}
                size="sm"
                color="primary"
                variant="solid"
              />
            </div>
          </div>
        )}
      </Surface>

      <ConfirmDialog
        isOpen={Boolean(pendingDeleteRateSnapshot)}
        title={t("finance.rates.deleteTitle")}
        message={t("finance.rates.deleteMessage", {
          name: pendingDeleteRateSnapshot ? rateSnapshotLabel(pendingDeleteRateSnapshot) : "",
        })}
        confirmText={t("finance.rates.deleteConfirm")}
        onCancel={() => setPendingDeleteRateSnapshot(null)}
        onConfirm={() => {
          if (pendingDeleteRateSnapshot) {
            deleteRateSnapshotMutation.mutate(pendingDeleteRateSnapshot.id);
          }
        }}
        loading={deleteRateSnapshotMutation.isPending}
      />
    </div>
  );
}

export function FinanceAssetManagerModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { assets } = useFinanceAssetSource();
  const [assetCode, setAssetCode] = useState("");
  const [assetName, setAssetName] = useState("");
  const [assetDecimalPlaces, setAssetDecimalPlaces] = useState("2");
  const [editingAssetId, setEditingAssetId] = useState<UUID | null>(null);
  const [editingAssetCode, setEditingAssetCode] = useState("");
  const [editingAssetName, setEditingAssetName] = useState("");
  const [editingAssetDecimalPlaces, setEditingAssetDecimalPlaces] = useState("2");

  const updateAssetMutation = useMutation({
    mutationFn: ({
      assetId,
      code,
      name,
      decimalPlaces,
    }: {
      assetId: UUID;
      code: string;
      name: string | null;
      decimalPlaces: number;
    }) => financeApi.updateAsset(assetId, { code, name, decimal_places: decimalPlaces }),
    onSuccess: async () => {
      toast.showSuccess(t("finance.messages.assetUpdated"));
      setEditingAssetId(null);
      await invalidateFinanceAssets(queryClient);
    },
    onError: (error) => {
      toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
    },
  });

  const deleteAssetMutation = useMutation({
    mutationFn: (assetId: UUID) => financeApi.deleteAsset(assetId),
    onSuccess: async () => {
      toast.showSuccess(t("finance.messages.assetDeleted"));
      await invalidateFinanceAssets(queryClient);
    },
    onError: (error) => {
      toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
    },
  });

  const submitAsset = (event: React.FormEvent) => {
    event.preventDefault();
    const code = assetCode.trim().toUpperCase();
    if (!code) return;
    financeApi
      .createAsset({
        code,
        name: assetName.trim() || null,
        decimal_places: parseDecimalPlaces(assetDecimalPlaces),
      })
      .then(async () => {
        await invalidateFinanceAssets(queryClient);
        toast.showSuccess(t("finance.messages.assetCreated"));
        setAssetCode("");
        setAssetName("");
        setAssetDecimalPlaces("2");
      })
      .catch((error) => {
        toast.showError(t("common.error"), error instanceof Error ? error.message : String(error));
      });
  };

  return (
    <ModalBase
      isOpen={isOpen}
      onClose={onClose}
      title={t("finance.assets.title")}
      size="lg"
      bodyOverflow="auto"
    >
      <div className="space-y-4">
        <p className={financeTextClass.helperText}>{t("finance.assets.description")}</p>
        <form
          className="grid grid-cols-1 gap-2 sm:grid-cols-[8rem_minmax(0,1fr)_8rem_auto]"
          onSubmit={submitAsset}
        >
          <TextInput
            size="sm"
            value={assetCode}
            onChange={(event) => setAssetCode(event.target.value.toUpperCase())}
            placeholder={t("finance.assets.code")}
          />
          <TextInput
            size="sm"
            value={assetName}
            onChange={(event) => setAssetName(event.target.value)}
            placeholder={t("finance.assets.name")}
          />
          <TextInput
            type="number"
            min={0}
            max={8}
            step={1}
            size="sm"
            value={assetDecimalPlaces}
            onChange={(event) => setAssetDecimalPlaces(event.target.value)}
            placeholder={t("finance.assets.decimalPlaces")}
          />
          <ActionButton
            type="submit"
            label={t("finance.assets.addAsset")}
            iconName="plus"
            size="sm"
            color="primary"
            variant="outline"
            disabled={!assetCode.trim()}
          />
        </form>
        <div className="max-h-[520px] overflow-y-auto pr-1">
          <table className="table table-sm">
            <thead className={financeTextClass.tableHeader}>
              <tr>
                <th>{t("finance.assets.code")}</th>
                <th>{t("finance.assets.name")}</th>
                <th>{t("finance.assets.decimalPlaces")}</th>
                <th className="w-24 text-right">{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => {
                const editing = editingAssetId === asset.id;
                return (
                  <tr key={asset.id}>
                    <td>
                      {editing ? (
                        <TextInput
                          size="sm"
                          value={editingAssetCode}
                          onChange={(event) => setEditingAssetCode(event.target.value.toUpperCase())}
                        />
                      ) : (
                        <FinanceAssetSymbol symbol={asset.code} />
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <TextInput
                          size="sm"
                          value={editingAssetName}
                          onChange={(event) => setEditingAssetName(event.target.value)}
                        />
                      ) : (
                        asset.name || "-"
                      )}
                    </td>
                    <td>
                      {editing ? (
                        <TextInput
                          type="number"
                          min={0}
                          max={8}
                          step={1}
                          size="sm"
                          value={editingAssetDecimalPlaces}
                          onChange={(event) => setEditingAssetDecimalPlaces(event.target.value)}
                        />
                      ) : (
                        asset.decimal_places
                      )}
                    </td>
                    <td>
                      <div className="flex justify-end gap-1">
                        {editing ? (
                          <>
                            <ActionButton
                              label=""
                              iconName="check"
                              iconOnly
                              size="sm"
                              variant="ghost"
                              ariaLabel={t("common.save")}
                              disabled={!editingAssetCode.trim() || updateAssetMutation.isPending}
                              onClick={() =>
                                updateAssetMutation.mutate({
                                  assetId: asset.id,
                                  code: editingAssetCode.trim().toUpperCase(),
                                  name: editingAssetName.trim() || null,
                                  decimalPlaces: parseDecimalPlaces(editingAssetDecimalPlaces),
                                })
                              }
                            />
                            <ActionButton
                              label=""
                              iconName="x-mark"
                              iconOnly
                              size="sm"
                              variant="ghost"
                              ariaLabel={t("common.cancel")}
                              onClick={() => setEditingAssetId(null)}
                            />
                          </>
                        ) : (
                          <>
                            <ActionButton
                              label=""
                              iconName="edit"
                              iconOnly
                              size="sm"
                              variant="ghost"
                              ariaLabel={t("common.edit")}
                              onClick={() => {
                                setEditingAssetId(asset.id);
                                setEditingAssetCode(asset.code);
                                setEditingAssetName(asset.name ?? "");
                                setEditingAssetDecimalPlaces(String(asset.decimal_places));
                              }}
                            />
                            <ActionButton
                              label=""
                              iconName="trash"
                              iconOnly
                              size="sm"
                              variant="ghost"
                              color="error"
                              ariaLabel={t("common.delete")}
                              disabled={asset.is_default || deleteAssetMutation.isPending}
                              onClick={() => deleteAssetMutation.mutate(asset.id)}
                            />
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </ModalBase>
  );
}

function parseDecimalPlaces(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed)) {
    return 2;
  }
  return Math.min(8, Math.max(0, parsed));
}

function RateEntryEquationCells({
  entry,
  assets,
}: {
  entry: NonNullable<FinanceRateSnapshot["entries"]>[number];
  assets: FinanceAsset[];
}) {
  return (
    <>
      <td className="text-right">
        <FinanceAmountText
          amount={formatAmountForAsset("1", entry.base_currency, assets)}
          currencyCode={entry.base_currency}
          showCurrency={false}
        />
      </td>
      <td>
        <FinanceAssetSymbol symbol={entry.base_currency} />
      </td>
      <td className={`text-center ${financeTextClass.placeholder}`}>=</td>
      <td className="text-right">
        <FinanceAmountText
          amount={formatAmountForAsset(entry.rate, entry.quote_currency, assets)}
          currencyCode={entry.quote_currency}
          showCurrency={false}
        />
      </td>
      <td>
        <FinanceAssetSymbol symbol={entry.quote_currency} />
      </td>
    </>
  );
}
