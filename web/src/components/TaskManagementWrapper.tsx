import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import TaskEditModal from "./TaskEditModal";
import TaskTimelogsModal from "./TaskTimelogsModal";
import TaskTimelogQuickAddModal from "./TaskTimelogQuickAddModal";
import TaskNotesModal from "./TaskNotesModal";
import CreateNoteModal from "./CreateNoteModal";
import ConfirmDialog from "./ConfirmDialog";
import {
  useTaskManagement,
  type TaskManagementConfig,
} from "@/hooks/useTaskManagement";
import type { TaskWithSubtasks, Vision } from "@/services/api";
import { deriveNoteAssociationDefaults } from "@/utils/notes";

interface TaskManagementWrapperProps extends TaskManagementConfig {
  children: (
    taskManagement: ReturnType<typeof useTaskManagement>,
  ) => React.ReactNode;
  allVisions?: Vision[];
  allTasks?: TaskWithSubtasks[];
  getFlattenedTasks?: (tasks: TaskWithSubtasks[]) => TaskWithSubtasks[];
  /** 规划页与愿景页可区分子任务是否继承规划周期 */
  inheritPlanningFromParent?: boolean;
}

/**
 * TaskManagementWrapper - 任务管理包装器组件
 *
 * 提供统一的任务管理能力，包括：
 * 1. 任务编辑、删除、状态更新
 * 2. 添加子任务、查看时间记录
 * 3. 任务重排序
 * 4. 相关的模态框和对话框
 *
 * 使用方式：
 * <TaskManagementWrapper onTaskUpdate={handleUpdate} allVisions={visions}>
 *   {(taskManagement) => (
 *     <YourComponent
 *       onEditTask={taskManagement.actions.handleEditTask}
 *       onDeleteTask={taskManagement.actions.handleDeleteTask}
 *       // ... 其他 props
 *     />
 *   )}
 * </TaskManagementWrapper>
 */
const TaskManagementWrapper: React.FC<TaskManagementWrapperProps> = ({
  children,
  allVisions = [],
  allTasks = [],
  getFlattenedTasks,
  inheritPlanningFromParent = true,
  ...config
}) => {
  const { t } = useTranslation();
  // 扁平化任务列表，用于 useTaskManagement 中的任务查找（确保嵌套任务可被找到）
  const flattenedTasks = useMemo(() => {
    if (getFlattenedTasks) {
      return getFlattenedTasks(allTasks);
    }

    const result: TaskWithSubtasks[] = [];
    const flatten = (tasks: TaskWithSubtasks[]) => {
      tasks.forEach((task) => {
        result.push(task);
        if (task.subtasks?.length) {
          flatten(task.subtasks);
        }
      });
    };

    flatten(allTasks);
    return result;
  }, [allTasks, getFlattenedTasks]);

  const taskManagement = useTaskManagement({
    ...config,
    allVisions,
    allTasks: flattenedTasks,
    getFlattenedTasks,
  });

  const createNoteDefaults = useMemo(() => {
    if (!taskManagement.creatingNoteForTask) return null;
    return deriveNoteAssociationDefaults({
      task: taskManagement.creatingNoteForTask,
      people: taskManagement.creatingNoteForTask.people,
    });
  }, [taskManagement.creatingNoteForTask]);

  return (
    <>
      {children(taskManagement)}

      {/* 任务编辑模态框 */}
      {taskManagement.isEditModalOpen && taskManagement.editModalSessionId && (
        <TaskEditModal
          isOpen={taskManagement.isEditModalOpen}
          onClose={taskManagement.actions.closeEditModal}
          onSave={taskManagement.actions.handleTaskSave}
          onRequestDelete={taskManagement.actions.handleDeleteTask}
          task={taskManagement.editingTask}
          visionId={
            taskManagement.editingTask?.vision_id ||
            (taskManagement.creatingSubtask && taskManagement.parentTaskId
              ? allTasks.find((t) => t.id === taskManagement.parentTaskId)
                  ?.vision_id
              : undefined) ||
            allTasks[0]?.vision_id ||
            config.visionId ||
            ""
          }
          parentTaskId={
            taskManagement.creatingSubtask
              ? taskManagement.parentTaskId
              : taskManagement.editingTask?.parent_task_id
          }
          allTasks={flattenedTasks}
          allVisions={allVisions}
          inheritPlanningFromParent={inheritPlanningFromParent}
          sessionId={taskManagement.editModalSessionId}
        />
      )}

      {/* 删除确认对话框 */}
      {taskManagement.isDeleteConfirmOpen && taskManagement.deletingTask && (
        <ConfirmDialog
          isOpen={taskManagement.isDeleteConfirmOpen}
          title="确认删除任务"
          message={`确定要删除任务 "${taskManagement.deletingTask.content}" 吗？此操作不可撤销。`}
          confirmText="删除"
          cancelText={t("common.cancel")}
          onConfirm={taskManagement.actions.confirmDeleteTask}
          onCancel={taskManagement.actions.closeDeleteConfirm}
        />
      )}

      {/* 时间记录查看模态框 */}
      {taskManagement.isTimeRecordsModalOpen &&
        taskManagement.viewingTimeRecords && (
          <TaskTimelogsModal
            isOpen={taskManagement.isTimeRecordsModalOpen}
            onClose={taskManagement.actions.closeTimeRecordsModal}
            task={taskManagement.viewingTimeRecords}
          />
        )}

      {/* 任务笔记查看模态框 */}
      {taskManagement.isNotesModalOpen && taskManagement.viewingNotes && (
        <TaskNotesModal
          isOpen={taskManagement.isNotesModalOpen}
          onClose={taskManagement.actions.closeNotesModal}
          task={taskManagement.viewingNotes}
        />
      )}

      {/* 创建笔记模态框 */}
      {taskManagement.isCreateNoteModalOpen && (
        <CreateNoteModal
          isOpen={taskManagement.isCreateNoteModalOpen}
          onClose={taskManagement.actions.closeCreateNoteModal}
          preSelectedTaskId={
            createNoteDefaults?.preSelectedTaskId ??
            taskManagement.creatingNoteForTask?.id
          }
          preSelectedTaskTitle={
            createNoteDefaults?.preSelectedTaskTitle ??
            taskManagement.creatingNoteForTask?.content
          }
          preSelectedPersonIds={
            createNoteDefaults?.preSelectedPersonIds ??
            taskManagement.creatingNoteForTask?.people?.map((p) => p.id)
          }
          lockTaskSelection={createNoteDefaults?.lockTaskSelection ?? false}
          lockPersonSelection={createNoteDefaults?.lockPersonSelection ?? false}
          onNoteCreated={taskManagement.actions.handleNoteCreated}
        />
      )}

      {taskManagement.isCreateTimelogModalOpen && (
        <TaskTimelogQuickAddModal
          isOpen={taskManagement.isCreateTimelogModalOpen}
          onClose={taskManagement.actions.closeCreateTimelogModal}
          task={taskManagement.creatingTimelogForTask}
          onTimelogCreated={taskManagement.actions.handleTimelogCreated}
        />
      )}
    </>
  );
};

export default TaskManagementWrapper;
