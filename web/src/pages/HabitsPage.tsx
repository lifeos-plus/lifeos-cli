import { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { useHabitManager } from "@/features/habits/controller/useHabitManager";
import type { Habit, HabitAction } from "@/services/api/habits";
import EmptyState from "@/components/EmptyState";
import ErrorDisplay from "@/components/ErrorDisplay";
import LoadingSpinner from "@/components/LoadingSpinner";
import { HabitFormModal } from "@/components/habits/HabitFormModal";
import { HabitActionList } from "@/components/habits/HabitActionList";
import { usePageHeader } from "@/contexts/PageHeaderContext";
import PageLayout from "@/layouts/PageLayout";
import ActionButton, { CreateNewButton } from "@/components/ActionButton";
import StatusBadge from "@/components/StatusBadge";
import EnumSelect from "@/components/selects/EnumSelect";
import ExpandableCard from "@/components/ExpandableCard";
import ConfirmDialog from "@/components/ConfirmDialog";
import { useCalendarAdapter } from "@/hooks/useCalendarAdapter";
import { useHabitActions } from "@/hooks/queries/useHabitActions";
import { useHabitStats } from "@/hooks/queries/useHabitStats";
import { HABIT_STATUS_FILTER_OPTIONS } from "@/utils/constants";
import type { UUID } from "@/types/primitive";
import type { CalendarAdapter, CalendarSystem } from "@/utils/calendar";
import { Icon } from "@/components/icons";
import { addDays, formatDate } from "@/utils/datetime";
function HabitItem({
  habit,
  isExpanded,
  onToggleExpansion,
  onEdit,
  onCopy,
  onStatusUpdate,
  calendarAdapter,
  calendarSystem,
  t,
}: {
  habit: Habit;
  isExpanded: boolean;
  onToggleExpansion: () => void;
  onEdit: (habit: Habit) => void;
  onCopy: (habit: Habit) => void;
  onStatusUpdate: (
    habitId: UUID,
    action: HabitAction,
    newStatus: string,
  ) => void;
  calendarAdapter: CalendarAdapter;
  calendarSystem: CalendarSystem;
  t: TFunction;
}) {
  const parseHabitDate = (value: string) => {
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      const [year, month, day] = value.split("-").map(Number);
      return new Date(year, month - 1, day);
    }
    return new Date(value);
  };

  const habitStartDate = parseHabitDate(habit.start_date);
  const habitEndDate = addDays(habitStartDate, habit.duration_days - 1);
  const today = new Date();
  const initialCenterDate =
    today < habitStartDate
      ? habitStartDate
      : today > habitEndDate
        ? habitEndDate
        : today;

  const [actionCenterDate, setActionCenterDate] = useState<Date>(
    () => initialCenterDate,
  );

  useEffect(() => {
    const refreshedStart = parseHabitDate(habit.start_date);
    const refreshedEnd = addDays(refreshedStart, habit.duration_days - 1);
    const current = new Date();
    const clamped =
      current < refreshedStart
        ? refreshedStart
        : current > refreshedEnd
          ? refreshedEnd
          : current;
    setActionCenterDate(clamped);
  }, [habit.id, habit.start_date, habit.duration_days]);
  const { actions, query: actionsQuery } = useHabitActions(habit.id, {
    enabled: isExpanded,
    centerDate: actionCenterDate,
    windowSize: 100,
  });
  const { stats } = useHabitStats(habit.id, { enabled: isExpanded });

  const effectiveStats = isExpanded ? (stats ?? habit.stats) : habit.stats;
  const completionRate = effectiveStats
    ? effectiveStats.total_actions > 0
      ? (effectiveStats.completed_actions / effectiveStats.total_actions) * 100
      : 0
    : 0;

  // 构建习惯标题+描述容器（占据满行）
  const titleDescriptionContainer = (
    <div className="space-y-3">
      {/* 习惯标题 + 状态标签 */}
      <div className="flex items-center space-x-3 min-w-0">
        <h2 className="text-xl lg:text-2xl font-semibold whitespace-nowrap flex items-center gap-2">
          <Icon name="repeat" size={20} aria-hidden className="text-primary" />
          {habit.title}
        </h2>
        <StatusBadge status={habit.status} type="habit" />
      </div>

      {/* 习惯描述 */}
      {habit.description && (
        <p className="text-base lg:text-lg text-base-content/70 line-clamp-2 lg:line-clamp-3 font-normal break-words">
          {habit.description}
        </p>
      )}
    </div>
  );

  // 构建元数据容器
  const metadataContainer = (
    <div className="flex flex-wrap items-start justify-start gap-2 sm:gap-4 lg:gap-6 text-sm lg:text-base text-base-content/70 font-normal text-left w-full">
      <div className="flex items-center gap-1 min-w-0">
        <span className="text-base-content/50 flex-shrink-0">
          {t("habits.habit.startDate")}
        </span>
        <span className="truncate">{formatDate(habit.start_date)}</span>
      </div>
      <div className="flex items-center gap-1 min-w-0">
        <span className="text-base-content/50 flex-shrink-0">
          {t("habits.habit.duration")}
        </span>
        <span className="truncate">{habit.duration_days} 天</span>
      </div>
      <div className="flex items-center gap-1 min-w-0">
        <span className="text-base-content/50 flex-shrink-0">
          {t("habits.habit.status")}
        </span>
        <span className="truncate">{habit.status}</span>
      </div>
      {effectiveStats && (
        <>
          <div className="flex items-center gap-1 min-w-0">
            <span className="text-base-content/50 flex-shrink-0">
              {t("habits.stats.totalActions")}
            </span>
            <span className="truncate">{effectiveStats.total_actions}</span>
          </div>
          <div className="flex items-center gap-1 min-w-0">
            <span className="text-base-content/50 flex-shrink-0">
              {t("habits.stats.completionRate")}
            </span>
            <span className="truncate">{completionRate.toFixed(1)}%</span>
          </div>
        </>
      )}
    </div>
  );

  // 构建操作容器（操作按钮组）
  const actionContainer = (
    <div className="flex-shrink-0">
      <div className="flex items-center gap-2">
        <ActionButton
          label={t("common.edit")}
          iconName="edit"
          color="primary"
          size="sm"
          iconOnly
          onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
            e.stopPropagation();
            onEdit(habit);
          }}
        />
        <ActionButton
          label={t("common.copy")}
          iconName="clipboard"
          color="neutral"
          size="sm"
          iconOnly
          onClick={(e: React.MouseEvent<HTMLButtonElement>) => {
            e.stopPropagation();
            onCopy(habit);
          }}
        />
      </div>
    </div>
  );

  // 构建习惯标题（标题+描述容器）
  const habitTitle = titleDescriptionContainer;

  // 构建习惯副标题（元数据+操作按钮）
  const habitSubtitle = (
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 lg:gap-4 w-full">
      <div className="flex-shrink-0">{metadataContainer}</div>
      <div className="flex-shrink-0">{actionContainer}</div>
    </div>
  );

  return (
    <ExpandableCard
      isExpanded={isExpanded}
      onToggleExpansion={onToggleExpansion}
      title={habitTitle}
      subtitle={habitSubtitle}
      subtitleAlign="between"
      className="w-full"
    >
      <div className="p-4 lg:p-6">
        <div className="w-full space-y-4">
          {/* 详细统计信息 */}
          {effectiveStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-base-200 rounded-lg">
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">
                  {effectiveStats.total_actions}
                </div>
                <div className="text-sm text-base-content/70">
                  {t("habits.stats.totalActions")}
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-success">
                  {completionRate.toFixed(1)}%
                </div>
                <div className="text-sm text-base-content/70">
                  {t("habits.stats.completionRate")}
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-info">
                  {effectiveStats.current_streak}
                </div>
                <div className="text-sm text-base-content/70">
                  {t("habits.stats.currentStreak")}
                </div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-warning">
                  {effectiveStats.longest_streak}
                </div>
                <div className="text-sm text-base-content/70">
                  {t("habits.stats.longestStreak")}
                </div>
              </div>
            </div>
          )}

          {/* 习惯动作列表 */}
          {isExpanded && (
            <HabitActionList
              habitId={habit.id}
              habitTitle={habit.title}
              actions={actions || []}
              durationDays={habit.duration_days}
              startDate={habit.start_date}
              cadenceFrequency={habit.cadence_frequency}
              calendarAdapter={calendarAdapter}
              calendarSystem={calendarSystem}
              centerDate={actionCenterDate}
              onCenterDateChange={setActionCenterDate}
              onStatusUpdate={(habitId, action, newStatus) =>
                onStatusUpdate(habitId, action, newStatus)
              }
              onNotesChanged={() => {
                void actionsQuery.refetch();
              }}
            />
          )}
        </div>
      </div>
    </ExpandableCard>
  );
}

function HabitsPage() {
  const { t } = useTranslation();
  const { setHeader } = usePageHeader();
  const { adapter: calendarAdapter, calendarSystem } = useCalendarAdapter();

  // State
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [showFormModal, setShowFormModal] = useState(false);
  const [editingHabit, setEditingHabit] = useState<Habit | null>(null);
  const [prefillHabit, setPrefillHabit] = useState<{
    title: string;
    description?: string | null;
    duration_days: number;
    task_id?: UUID | null;
  } | null>(null);

  // Data
  const {
    habits,
    isLoading,
    error,
    updateActionStatus,
    createHabit,
    updateHabit,
    expandedHabits,
    toggleHabitExpansion,
    deletingHabit,
    requestDeleteHabit,
    confirmDeleteHabit,
    cancelDeleteHabit,
  } = useHabitManager({
    statusFilter: statusFilter,
  });

  useEffect(() => {
    setHeader({
      actions: (
        <div className="flex items-center gap-3">
          {/* Status filter group */}
          <div className="flex items-center gap-2">
            <EnumSelect
              value={statusFilter}
              onChange={(value) => setStatusFilter(value as string)}
              options={HABIT_STATUS_FILTER_OPTIONS}
              id="habit-status-filter"
              showLabel={false}
              autoWidth={false}
            />
          </div>

          {/* Action buttons group */}
          <div className="flex items-center gap-2">
            <CreateNewButton
              label={t("common.create_new")}
              onClick={() => {
                setEditingHabit(null);
                setPrefillHabit(null);
                setShowFormModal(true);
              }}
            />
          </div>
        </div>
      ),
    });
    return () => setHeader({ actions: undefined });
  }, [setHeader, t, statusFilter]);

  // Handlers

  const handleEditHabit = useCallback((habit: Habit) => {
    setPrefillHabit(null);
    setEditingHabit(habit);
    setShowFormModal(true);
  }, []);

  const handleCopyHabit = useCallback((habit: Habit) => {
    setEditingHabit(null);
    setPrefillHabit({
      title: habit.title,
      description: habit.description ?? null,
      duration_days: habit.duration_days,
      task_id: habit.task_id ?? null,
    });
    setShowFormModal(true);
  }, []);

  const handleStatusUpdate = useCallback(
    async (habitId: UUID, action: HabitAction, newStatus: string) => {
      updateActionStatus(habitId, action, newStatus);
    },
    [updateActionStatus],
  );

  const handleCloseForm = useCallback(() => {
    setShowFormModal(false);
    setEditingHabit(null);
    setPrefillHabit(null);
  }, []);

  return (
    <PageLayout>
      {isLoading ? (
        <LoadingSpinner />
      ) : error ? (
        <ErrorDisplay error={t("habits.errors.loadFailed")} />
      ) : (
        <>
          {habits.length === 0 ? (
            <EmptyState
              icon={
                <Icon
                  name="sparkles"
                  size={36}
                  className="text-primary"
                  aria-hidden
                />
              }
              title={t("habits.emptyState.title")}
              description={t("habits.emptyState.description")}
              actionText={t("common.create_new")}
              onAction={() => {
                setEditingHabit(null);
                setPrefillHabit(null);
                setShowFormModal(true);
              }}
            />
          ) : (
            <div className="space-y-4">
              {habits.map((habit) => (
                <HabitItem
                  key={habit.id}
                  habit={habit}
                  isExpanded={expandedHabits.has(habit.id)}
                  onToggleExpansion={() => toggleHabitExpansion(habit.id)}
                  onEdit={handleEditHabit}
                  onCopy={handleCopyHabit}
                  onStatusUpdate={handleStatusUpdate}
                  calendarAdapter={calendarAdapter}
                  calendarSystem={calendarSystem}
                  t={t}
                />
              ))}
            </div>
          )}

          <HabitFormModal
            open={showFormModal}
            onClose={handleCloseForm}
            habitToEdit={editingHabit}
            prefillHabit={prefillHabit}
            onCreateHabit={createHabit}
            onUpdateHabit={updateHabit}
            onRequestDelete={requestDeleteHabit}
          />
          {deletingHabit && (
            <ConfirmDialog
              isOpen={!!deletingHabit}
              title={t("habits.confirmDelete.title")}
              message={t("habits.confirmDelete.message", {
                name: deletingHabit.title,
              })}
              confirmText={t("common.delete")}
              onConfirm={confirmDeleteHabit}
              onCancel={cancelDeleteHabit}
            />
          )}
        </>
      )}
    </PageLayout>
  );
}

export default HabitsPage;
