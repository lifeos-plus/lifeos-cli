import { useTranslation } from "react-i18next";

import ActionButton, { CreateNewButton } from "@/components/ActionButton";
import EnumSelect from "@/components/selects/EnumSelect";
import type { UUID } from "@/types/primitive";
import Surface from "@/layouts/Surface";

import { financeTextClass } from "./styles";

export function SnapshotSelectorToolbar({
  selectValue,
  selectOptions,
  selectPlaceholder,
  hasPrevious,
  hasNext,
  description,
  createLabel,
  createDisabled,
  onSelect,
  onPrevious,
  onNext,
  onCreate,
}: {
  selectValue?: UUID | null;
  selectOptions: { value: UUID; label: string }[];
  selectPlaceholder: string;
  hasPrevious: boolean;
  hasNext: boolean;
  description?: string;
  createLabel: string;
  createDisabled?: boolean;
  onSelect: (snapshotId: UUID) => void;
  onPrevious: () => void;
  onNext: () => void;
  onCreate: () => void;
}) {
  const { t } = useTranslation();

  return (
    <Surface as="section" padding="md" elevation="moderate">
      <div className="grid grid-cols-1 items-center gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        {description ? (
          <p className={`min-w-0 ${financeTextClass.bodyMuted}`}>{description}</p>
        ) : (
          <span aria-hidden="true" />
        )}

        <div className="flex min-w-0 items-center justify-center gap-1 whitespace-nowrap sm:gap-2">
          <ActionButton
            label=""
            iconName="chevron-left"
            iconOnly
            ariaLabel={t("finance.snapshot.previous")}
            size="sm"
            variant="ghost"
            shape="circle"
            onClick={onPrevious}
            disabled={!selectOptions.length || !hasPrevious}
          />

          <EnumSelect
            value={selectValue ?? undefined}
            onChange={(value) => {
              if (value) onSelect(String(value) as UUID);
            }}
            options={selectOptions}
            placeholder={selectPlaceholder}
            showLabel={false}
            size="sm"
            className="w-auto min-w-[12rem] sm:min-w-[16rem] max-w-full"
            autoWidth
            disabled={!selectOptions.length}
          />

          <ActionButton
            label=""
            iconName="chevron-right"
            iconOnly
            ariaLabel={t("finance.snapshot.next")}
            size="sm"
            variant="ghost"
            shape="circle"
            onClick={onNext}
            disabled={!selectOptions.length || !hasNext}
          />
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <CreateNewButton
            label={createLabel}
            onClick={onCreate}
            size="sm"
            color="primary"
            variant="solid"
            disabled={createDisabled}
            ariaLabel={createLabel}
          />
        </div>
      </div>
    </Surface>
  );
}

export function SnapshotActionButtons({
  editLabel,
  copyLabel,
  deleteLabel,
  disabled,
  deleteDisabled,
  onEdit,
  onCopy,
  onDelete,
}: {
  editLabel: string;
  copyLabel?: string;
  deleteLabel: string;
  disabled?: boolean;
  deleteDisabled?: boolean;
  onEdit: () => void;
  onCopy?: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="flex justify-end gap-2">
      <ActionButton
        label={editLabel}
        iconName="edit"
        onClick={onEdit}
        size="sm"
        variant="ghost"
        ariaLabel={editLabel}
        disabled={disabled}
      />
      {copyLabel && onCopy ? (
        <ActionButton
          label={copyLabel}
          iconName="clipboard"
          onClick={onCopy}
          size="sm"
          variant="ghost"
          ariaLabel={copyLabel}
          disabled={disabled}
        />
      ) : null}
      <ActionButton
        label={deleteLabel}
        iconName="trash"
        onClick={onDelete}
        size="sm"
        variant="ghost"
        color="error"
        ariaLabel={deleteLabel}
        disabled={deleteDisabled ?? disabled}
      />
    </div>
  );
}

export function SnapshotNavigator({
  title,
  rightSlot,
}: {
  title: React.ReactNode;
  rightSlot?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex flex-grow flex-wrap items-center gap-3">
        <div>
          {typeof title === "string" ? (
            <p className={financeTextClass.moduleTitle}>{title}</p>
          ) : (
            title
          )}
        </div>
      </div>
      {rightSlot ? (
        <div className={`text-right ${financeTextClass.bodyMuted}`}>{rightSlot}</div>
      ) : null}
    </header>
  );
}
