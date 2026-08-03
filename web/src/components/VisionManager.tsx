import {
  useState,
  useEffect,
  useCallback,
  useRef,
  useImperativeHandle,
  forwardRef,
  useMemo,
} from "react";
import { useTranslation } from "react-i18next";
import VisionEditModal from "./VisionEditModal";
import TaskEditModal, {
  type TaskEditModalCloseContext,
  type TaskEditModalSaveResult,
} from "./TaskEditModal";
import TaskTimelogsModal from "./TaskTimelogsModal";
import DraggableTaskList from "./DraggableTaskList";
import TaskManagementWrapper from "./TaskManagementWrapper";
import ErrorDisplay from "./ErrorDisplay";
import LoadingSpinner from "./LoadingSpinner";
import EmptyState from "./EmptyState";
import ActionButton, { EditButton, ActionButtonGroup } from "./ActionButton";
import ExpandableCard from "./ExpandableCard";
import AreaBadge from "./AreaBadge";
import { Icon } from "./icons";
import type { Vision, TaskWithSubtasks } from "@/services/api";
import { visionsApi } from "@/services/api";
import { formatDuration, formatDate } from "@/utils/datetime";
import { logger } from "@/utils/core";
import { useVisionManager } from "@/features/visions/controller/useVisionManager";
import { useVisionUIState } from "@/features/visions/controller/useVisionUIState";
import { useAreas } from "@/hooks/queries/useAreas";
import { useToast } from "@/contexts/ToastContext";
import ConfirmDialog from "./ConfirmDialog";
import type { UUID } from "@/types/primitive";
import type {
  TaskMutationResultPayload,
  TaskUpdateSummary,
} from "@/hooks/useTaskManagement";
import { createModalSessionId } from "@/utils/session";

export interface VisionManagerHandle {
  openCreateVision: () => void;
}

interface VisionManagerProps {
  statusFilter?: string;
  areaFilter?: UUID | null;
}

/**
 * VisionManager - Component for managing visions and their tasks
 */
const VisionManager = forwardRef<VisionManagerHandle, VisionManagerProps>(
  ({ statusFilter = "active", areaFilter }, ref) => {
    const { t } = useTranslation();

    // Use custom hook for vision management
    const {
      visions,
      loading,
      error,
      visionTasks,
      visionTasksLoading,
      expandedVisions,
      expandedTasksInVision,
      habitTaskAssociations,

      habitAssociationsLoaded: _habitAssociationsLoaded,
      deletingVision,
      harvestingVision,
      deletingTaskInfo,
      loadVisions,
      loadVisionTasks,
      requestDeleteVision,
      confirmDeleteVision,
      cancelDeleteVision,

      requestHarvestVision: _requestHarvestVision,
      confirmHarvestVision,
      cancelHarvestVision,

      requestDeleteTask: _requestDeleteTask,
      confirmDeleteTask,
      cancelDeleteTask,

      updateTaskStatus: _updateTaskStatus,
      toggleVisionExpansion,
      toggleTaskExpansion,
      applyTaskAttributesUpdate,
    } = useVisionManager(statusFilter);

    const filteredVisions = useMemo(() => {
      if (areaFilter === undefined) {
        return visions;
      }
      if (areaFilter === null) {
        return visions.filter((vision) => !vision.area_id);
      }
      return visions.filter(
        (vision) => vision.area_id === areaFilter,
      );
    }, [areaFilter, visions]);

    // UI state management for scroll position
    const { saveScrollPosition, restoreScrollPosition } = useVisionUIState();
    const scrollTimeoutRef = useRef<number | null>(null);

    // Modal state
    const [showVisionModal, setShowVisionModal] = useState(false);
    const [editingVision, setEditingVision] = useState<Vision | null>(null);
    const [showTimeRecordsModal, setShowTimeRecordsModal] = useState(false);
    const [viewingTimeRecordsTask, setViewingTimeRecordsTask] =
      useState<TaskWithSubtasks | null>(null);

    // Task management state for creating tasks
    const [showTaskEditModal, setShowTaskEditModal] = useState(false);
    const [taskModalSessionId, setTaskModalSessionId] = useState<string | null>(
      null,
    );
    const [rootTaskVisionId, setRootTaskVisionId] = useState<UUID | null>(null);
    const [taskCreationMode, setTaskCreationMode] = useState<"single" | "bulk">(
      "single",
    );

    // Reference data (areas map) with caching/TTL
    const { areaMap } = useAreas();

    // Toast notifications
    const toast = useToast();

    // 扁平化任务树的辅助函数
    const getFlattenedTasks = useCallback((tasks: TaskWithSubtasks[]) => {
      const result: TaskWithSubtasks[] = [];
      const flatten = (taskList: TaskWithSubtasks[]) => {
        taskList.forEach((task) => {
          result.push(task);
          if (task.subtasks?.length) {
            flatten(task.subtasks);
          }
        });
      };
      flatten(tasks);
      return result;
    }, []);

    const handleTaskAttributesUpdate = useCallback(
      (taskUpdate: TaskUpdateSummary) => {
        applyTaskAttributesUpdate(taskUpdate);
      },
      [applyTaskAttributesUpdate],
    );

    const handleTaskStructureChange = useCallback(
      async (
        payload: TaskMutationResultPayload & { previousVisionId: UUID | null },
      ) => {
        if (!payload) {
          return;
        }

        const candidateVisionIds = new Set<UUID>();

        if (payload.previousVisionId) {
          candidateVisionIds.add(payload.previousVisionId);
        }

        const nextVisionId = payload.updatedTask?.vision_id ?? null;
        if (nextVisionId) {
          candidateVisionIds.add(nextVisionId);
        }

        if (payload.visionIdHint) {
          candidateVisionIds.add(payload.visionIdHint);
        }

        const idsToReload = Array.from(candidateVisionIds);

        if (idsToReload.length === 0) {
          return;
        }

        await Promise.all(
          idsToReload.map((visionId) => loadVisionTasks(visionId, true)),
        );
      },
      [loadVisionTasks],
    );

    // Handle scroll position saving
    useEffect(() => {
      const handleScroll = () => {
        // Debounce scroll events to avoid excessive localStorage writes
        if (scrollTimeoutRef.current) {
          clearTimeout(scrollTimeoutRef.current);
        }

        scrollTimeoutRef.current = window.setTimeout(() => {
          saveScrollPosition(window.scrollY);
        }, 100);
      };

      window.addEventListener("scroll", handleScroll);

      return () => {
        window.removeEventListener("scroll", handleScroll);
        if (scrollTimeoutRef.current) {
          clearTimeout(scrollTimeoutRef.current);
        }
      };
    }, [saveScrollPosition]);

    // Vision handlers
    const handleCreateVision = useCallback(() => {
      setEditingVision(null);
      setShowVisionModal(true);
    }, []);

    const handleEditVision = useCallback((vision: Vision) => {
      setEditingVision(vision);
      setShowVisionModal(true);
    }, []);

    const handleVisionModalClose = useCallback(() => {
      setShowVisionModal(false);
      setEditingVision(null);
    }, []);

    const handleVisionSave = useCallback(
      async (result?: { updatedVision?: Vision }) => {
        setShowVisionModal(false);
        setEditingVision(null);

        if (result?.updatedVision) {
          await loadVisions();
          // 恢复滚动位置，避免页面跳转到顶部
          setTimeout(() => {
            restoreScrollPosition();
          }, 100);
        }
      },
      [loadVisions, restoreScrollPosition],
    );

    const handleDeleteVision = useCallback(
      async (vision: Vision) => {
        try {
          await requestDeleteVision(vision);
        } catch (error) {
          logger.error("Failed to delete vision:", error);
        }
      },
      [requestDeleteVision],
    );

    // Recompute effort and derived experience for one vision.
    const handleRecomputeVisionEfforts = useCallback(
      async (vision: Vision) => {
        try {
          // The backend also syncs derived vision experience after effort recompute.
          await visionsApi.recomputeEfforts(vision.id);

          // Reload visions so updated effort-derived experience is visible.
          await loadVisions();

          // Reload tasks too when this vision is already expanded.
          if (expandedVisions.has(vision.id)) {
            await loadVisionTasks(vision.id, true);
          }

          // 恢复滚动位置，避免页面跳转到顶部
          setTimeout(() => {
            restoreScrollPosition();
          }, 100);

          toast.showSuccess(
            t("visions.messages.recomputeSuccess"),
            `${t("tagManager.entityTypes.vision")}"${vision.name}"${t("visions.messages.recomputeSuccess")}`,
          );
        } catch (error) {
          logger.error(
            `Failed to recompute efforts for vision ${vision.id}:`,
            error,
          );

          toast.showError(
            t("visions.messages.recomputeFailed"),
            `${t("visions.messages.recomputeFailed")}"${vision.name}"${t("common.operationFailed")}`,
          );
        }
      },
      [
        loadVisions,
        loadVisionTasks,
        expandedVisions,
        toast,
        restoreScrollPosition,
        t,
      ],
    );

    const openTaskCreationModal = useCallback(
      async (vision: Vision, mode: "single" | "bulk") => {
        setRootTaskVisionId(vision.id);
        setTaskCreationMode(mode);
        setTaskModalSessionId(createModalSessionId());

        try {
          await loadVisionTasks(vision.id, true);
        } catch (err) {
          logger.warn(
            `Failed to pre-load tasks for vision ${vision.id} before opening TaskEditModal`,
            err,
          );
        }

        setShowTaskEditModal(true);
      },
      [loadVisionTasks],
    );

    const handleCreateRootTask = useCallback(
      async (vision: Vision) => {
        await openTaskCreationModal(vision, "single");
      },
      [openTaskCreationModal],
    );

    const handleBulkCreateTasks = useCallback(
      async (vision: Vision) => {
        await openTaskCreationModal(vision, "bulk");
      },
      [openTaskCreationModal],
    );

    const handleTaskEditModalClose = useCallback(
      (context?: TaskEditModalCloseContext) => {
        if (
          taskModalSessionId &&
          context?.sessionId &&
          context.sessionId !== taskModalSessionId
        ) {
          return;
        }

        setShowTaskEditModal(false);
        setRootTaskVisionId(null);
        setTaskCreationMode("single");
        setTaskModalSessionId(null);
      },
      [taskModalSessionId],
    );

    const handleTaskSave = useCallback(
      async (result?: TaskEditModalSaveResult) => {
        if (
          taskModalSessionId &&
          result?.sessionId &&
          result.sessionId !== taskModalSessionId
        ) {
          return;
        }

        setShowTaskEditModal(false);
        setRootTaskVisionId(null);
        setTaskCreationMode("single");
        setTaskModalSessionId(null);

        // 如果任务被创建或结构发生变化，刷新任务列表
        if (
          (result?.updatedTask || result?.structureChanged) &&
          rootTaskVisionId
        ) {
          await loadVisionTasks(rootTaskVisionId, true);
        }
      },
      [loadVisionTasks, rootTaskVisionId, taskModalSessionId],
    );

    // Time records handlers with debouncing
    const [clickedVisionId, setClickedVisionId] = useState<UUID | null>(null);

    const startViewTimeRecords = useCallback(
      (task: TaskWithSubtasks, visionId?: UUID) => {
        // 防止重复点击同一愿景的时间记录按钮
        if (visionId && clickedVisionId === visionId) return;

        if (visionId) {
          setClickedVisionId(visionId);
          // 延迟重置状态，防止快速连续点击
          setTimeout(() => setClickedVisionId(null), 300);
        }

        setViewingTimeRecordsTask(task);
        setShowTimeRecordsModal(true);
      },
      [clickedVisionId],
    );

    const handleTimeRecordsModalClose = useCallback(() => {
      setShowTimeRecordsModal(false);
      setViewingTimeRecordsTask(null);
    }, []);

    // Expose methods to parent component
    useImperativeHandle(ref, () => ({
      openCreateVision: handleCreateVision,
    }));

    if (loading) {
      return <LoadingSpinner message={t("common.loading")} />;
    }

    if (error) {
      return <ErrorDisplay error={error} />;
    }

    if (filteredVisions.length === 0) {
      return (
        <EmptyState
          icon={
            <Icon
              name="sparkles"
              size={40}
              className="text-primary"
              aria-hidden
            />
          }
          title={t("visions.emptyState.title")}
          description={t("visions.emptyState.description")}
          onAction={handleCreateVision}
        />
      );
    }

    return (
      <div className="w-full h-full">
        <div className="space-y-4 sm:space-y-6">
          {filteredVisions.map((vision) => {
            const tasks = visionTasks[vision.id] || [];
            const isExpanded = expandedVisions.has(vision.id);

            // 构建愿景标题+描述容器（占据满行）
            const titleDescriptionContainer = (
              <div className="space-y-3">
                {/* 愿景标题 + 领域标签 */}
                <div className="flex items-center space-x-3 min-w-0">
                  <h2 className="text-xl lg:text-2xl font-semibold whitespace-nowrap flex items-center gap-2">
                    <Icon
                      name="map"
                      size={20}
                      aria-hidden
                      className="text-primary"
                    />
                    {vision.name}
                  </h2>
                  <AreaBadge
                    areaId={vision.area_id || undefined}
                    areaMap={areaMap}
                  />
                </div>

                {/* 愿景描述 */}
                {vision.description && (
                  <p className="text-base lg:text-lg text-base-content/70 line-clamp-2 lg:line-clamp-3 font-normal break-words">
                    {vision.description}
                  </p>
                )}
              </div>
            );

            // 构建元数据容器
            const metadataContainer = (
              <div className="flex flex-wrap items-start justify-start gap-2 sm:gap-4 lg:gap-6 text-sm lg:text-base text-base-content/70 font-normal text-left w-full">
                <div className="flex items-center gap-1 min-w-0">
                  <span className="text-base-content/50 flex-shrink-0">
                    {t("visions.vision.createdAt")}
                  </span>
                  <span className="truncate">
                    {formatDate(vision.created_at)}
                  </span>
                </div>
                <div className="flex items-center gap-1 min-w-0">
                  <span className="text-base-content/50 flex-shrink-0">
                    {t("visions.vision.stage")}
                  </span>
                  <span className="truncate">{vision.stage}/10</span>
                </div>
                <div className="flex items-center gap-1 min-w-0">
                  <span className="text-base-content/50 flex-shrink-0">
                    {t("visions.vision.experience")}
                  </span>
                  <span className="truncate">{vision.experience_points}</span>
                </div>
                {vision.total_actual_effort &&
                  vision.total_actual_effort > 0 && (
                    <div className="flex items-center gap-1 min-w-0">
                      <span className="text-base-content/50 flex-shrink-0">
                        {t("visions.vision.totalEffort")}
                      </span>
                      <span className="truncate">
                        {formatDuration(vision.total_actual_effort)}
                      </span>
                    </div>
                  )}
              </div>
            );

            // 构建操作容器（操作按钮组 - 所有按钮直接显示，响应式尺寸）
            const actionContainer = (
              <div className="flex-shrink-0">
                <ActionButtonGroup gap="sm" align="end">
                  {/* 编辑 */}
                  <EditButton
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditVision(vision);
                    }}
                    size="sm"
                  />
                  {/* 创建根任务 */}
                  <ActionButton
                    label=""
                    iconName="plus"
                    color="success"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCreateRootTask(vision);
                    }}
                  />
                  <ActionButton
                    label=""
                    iconName="plus"
                    color="success"
                    size="sm"
                    variant="outline"
                    tooltip={t("visions.vision.actions.bulkCreateTasks")}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleBulkCreateTasks(vision);
                    }}
                  />
                  {/* 重新计算 */}
                  <ActionButton
                    label=""
                    iconName="refresh"
                    color="primary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRecomputeVisionEfforts(vision);
                    }}
                  />
                </ActionButtonGroup>
              </div>
            );

            // 构建愿景标题（标题+描述容器）
            const visionTitle = titleDescriptionContainer;

            // 构建愿景副标题（元数据+操作按钮 - 大屏幕时同行显示，元数据靠左，操作按钮靠右）
            const visionSubtitle = (
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 lg:gap-4 w-full">
                <div className="flex-shrink-0">{metadataContainer}</div>
                <div className="flex-shrink-0">{actionContainer}</div>
              </div>
            );

            // 操作按钮组已移到副标题区域，这里不再需要单独定义

            const isTaskListLoading = visionTasksLoading[vision.id] ?? false;

            return (
              <ExpandableCard
                key={vision.id}
                isExpanded={isExpanded}
                onToggleExpansion={() => toggleVisionExpansion(vision.id)}
                title={visionTitle}
                subtitle={visionSubtitle}
                subtitleAlign="between"
                className="w-full"
              >
                <div className="p-4 lg:p-6">
                  <div className="w-full space-y-4">
                    <TaskManagementWrapper
                      onTaskUpdateWithVisionId={() =>
                        loadVisionTasks(vision.id, true)
                      }
                      visionId={vision.id}
                      allVisions={visions}
                      allTasks={tasks}
                      getFlattenedTasks={getFlattenedTasks}
                      onTaskAttributesUpdate={handleTaskAttributesUpdate}
                      onTaskStructureChange={handleTaskStructureChange}
                      inheritPlanningFromParent={false}
                    >
                      {(taskManagement) => (
                        <>
                          {isTaskListLoading ? (
                            <div
                              className="space-y-3 min-h-[320px]"
                              aria-live="polite"
                            >
                              <div className="h-4 w-40 bg-base-200 rounded animate-pulse" />
                              <div className="flex flex-col gap-2">
                                {Array.from({ length: 4 }).map((_, index) => (
                                  <div
                                    key={index}
                                    className="h-16 w-full bg-base-200 rounded-lg animate-pulse"
                                  />
                                ))}
                              </div>
                            </div>
                          ) : tasks.length === 0 ? (
                            <EmptyState
                              icon={
                                <Icon
                                  name="map"
                                  size={36}
                                  className="text-secondary"
                                  aria-hidden
                                />
                              }
                              title={t("visions.vision.noTasks")}
                              description={t("visions.task.createFirstTask")}
                              actionText={t(
                                "visions.vision.actions.createRootTask",
                              )}
                              onAction={() => {
                                // 创建根任务 - 直接调用 TaskManagementWrapper 的创建功能
                                taskManagement.actions.handleAddSubtask();
                              }}
                              className="py-6 lg:py-8"
                            />
                          ) : (
                            <DraggableTaskList
                              tasks={tasks}
                              onEditTask={taskManagement.actions.handleEditTask}
                              onDeleteTask={
                                taskManagement.actions.handleDeleteTask
                              }
                              onStatusUpdate={
                                taskManagement.actions.handleStatusUpdate
                              }
                              onAddSubtask={
                                taskManagement.actions.handleAddSubtask
                              }
                              onViewTimeRecords={(task) =>
                                startViewTimeRecords(task, vision.id)
                              }
                              onCreateNote={
                                taskManagement.actions.handleOpenCreateNoteModal
                              }
                              onViewNotes={
                                taskManagement.actions.handleViewNotes
                              }
                              onCreateTimeRecord={
                                taskManagement.actions
                                  .handleOpenCreateTimelogModal
                              }
                              expandedTasks={
                                expandedTasksInVision[vision.id] || new Set()
                              }
                              onToggleExpansion={(taskId) =>
                                toggleTaskExpansion(vision.id, taskId)
                              }
                              onTasksReorder={
                                taskManagement.actions.handleTasksReorder
                              }
                              habitTaskAssociations={habitTaskAssociations}
                            />
                          )}
                        </>
                      )}
                    </TaskManagementWrapper>
                  </div>
                </div>
              </ExpandableCard>
            );
          })}
        </div>

        {/* Modals */}
        <VisionEditModal
          isOpen={showVisionModal}
          onClose={handleVisionModalClose}
          onSave={handleVisionSave}
          vision={editingVision}
          onRequestDelete={(v) => {
            // 关闭编辑态并触发外层删除流程
            handleVisionModalClose();
            if (v) {
              handleDeleteVision(v);
            }
          }}
        />

        {taskModalSessionId && (
          <TaskEditModal
            isOpen={showTaskEditModal}
            onClose={handleTaskEditModalClose}
            onSave={handleTaskSave}
            task={null}
            visionId={rootTaskVisionId || ("" as UUID)}
            parentTaskId={null}
            allTasks={
              rootTaskVisionId
                ? getFlattenedTasks(visionTasks[rootTaskVisionId] || [])
                : []
            }
            allVisions={visions}
            mode={taskCreationMode}
            visionLocked={taskCreationMode === "bulk"}
            sessionId={taskModalSessionId}
          />
        )}

        <TaskTimelogsModal
          isOpen={showTimeRecordsModal}
          onClose={handleTimeRecordsModalClose}
          task={viewingTimeRecordsTask}
        />

        {/* Confirmation Dialogs */}
        {deletingVision && (
          <ConfirmDialog
            isOpen={!!deletingVision}
            title={t("visions.modal.deleteVision")}
            message={t("visions.confirm.deleteVision", {
              name: deletingVision.name,
            })}
            confirmText={t("common.delete")}
            onConfirm={confirmDeleteVision}
            onCancel={cancelDeleteVision}
          />
        )}
        {harvestingVision && (
          <ConfirmDialog
            isOpen={!!harvestingVision}
            title={t("visions.modal.harvestVision")}
            message={t("visions.confirm.harvestVision", {
              name: harvestingVision.name,
            })}
            confirmText={t("visions.modal.harvestVision")}
            onConfirm={confirmHarvestVision}
            onCancel={cancelHarvestVision}
          />
        )}
        {deletingTaskInfo && (
          <ConfirmDialog
            isOpen={!!deletingTaskInfo}
            title={t("visions.modal.deleteTask")}
            message={t("visions.confirm.deleteTask", {
              content: deletingTaskInfo.task.content,
            })}
            confirmText={t("common.delete")}
            onConfirm={confirmDeleteTask}
            onCancel={cancelDeleteTask}
          />
        )}
      </div>
    );
  },
);

export default VisionManager;
