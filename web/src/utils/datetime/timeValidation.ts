/**
 * Time validation utilities for timelog data
 *
 * This module provides functions to validate time entries and detect anomalies:
 * - Negative duration detection
 * - Time overlap detection
 * - Gap detection and placeholder generation
 */

import type { Timelog } from "@/services/api";
import type { UUID } from "@/types/primitive";
import { createDateBoundaries, sortTimeEntriesByTime } from "./datetime";
interface TimeValidationResult {
  isValid: boolean;
  hasNegativeDuration: boolean;
  hasOverlaps: boolean;
  overlappingEntries: number[];
}

export interface PlaceholderEntry {
  id: string; // Use string ID with prefix to distinguish from real entries
  title: string;
  start_time: string;
  end_time: string;
  area_id: UUID | null; // Will use a special "unknown" area
  location?: string | null;
  energy_level?: number | null;
  notes?: string | null;
  tags?: string[] | null;
  extra_data?: Record<string, unknown> | null;
  people?: never[]; // Placeholder entries don't have people
  isPlaceholder: true;
}

export interface ProcessedEntry
  extends Omit<
    Timelog,
    | "deleted_at"
    | "energy_level"
    | "id"
    | "linked_notes_count"
    | "location"
    | "notes"
    | "tags"
    | "task"
    | "task_id"
  > {
  id: UUID | string; // Support both real entries (number) and placeholders (string)
  deleted_at?: string | null;
  energy_level?: number | null;
  isPlaceholder?: boolean;
  linked_notes_count?: number;
  location?: string | null;
  notes?: string | null;
  tags?: Timelog["tags"] | string[] | null;
  task?: Timelog["task"];
  task_id?: UUID | null;
  validationResult?: TimeValidationResult;
}

/**
 * Check if an entry has negative duration
 */
function hasNegativeDuration(entry: Timelog): boolean {
  if (!entry.start_time || !entry.end_time) {
    return false;
  }

  const startTime = new Date(entry.start_time);
  const endTime = new Date(entry.end_time);

  // start_time === end_time (zero duration) is allowed for marker events
  return startTime.getTime() > endTime.getTime();
}

/**
 * Check if two time intervals overlap (excluding endpoint touches)
 * Returns true if intervals have actual overlap, false if they just touch at endpoints
 */
function intervalsOverlap(
  start1: Date,
  end1: Date,
  start2: Date,
  end2: Date,
): boolean {
  // Convert to timestamps for easier comparison
  const s1 = start1.getTime();
  const e1 = end1.getTime();
  const s2 = start2.getTime();
  const e2 = end2.getTime();

  // Check for actual overlap (not just touching at endpoints)
  return s1 < e2 && s2 < e1;
}

/**
 * Find all overlapping entries in a list
 * Returns array of entry indices that have overlaps
 */
function findOverlappingEntries(entries: Timelog[]): number[] {
  const overlappingIndices = new Set<number>();

  for (let i = 0; i < entries.length; i++) {
    const entry1 = entries[i];
    if (!entry1.start_time || !entry1.end_time) continue;

    const start1 = new Date(entry1.start_time);
    const end1 = new Date(entry1.end_time);

    for (let j = i + 1; j < entries.length; j++) {
      const entry2 = entries[j];
      if (!entry2.start_time || !entry2.end_time) continue;

      const start2 = new Date(entry2.start_time);
      const end2 = new Date(entry2.end_time);

      if (intervalsOverlap(start1, end1, start2, end2)) {
        overlappingIndices.add(i);
        overlappingIndices.add(j);
      }
    }
  }

  return Array.from(overlappingIndices);
}

/**
 * Validate a single time entry
 */
function validateTimeEntry(
  entry: Timelog,
  allEntries: Timelog[],
): TimeValidationResult {
  const hasNegDuration = hasNegativeDuration(entry);
  const overlappingEntries = findOverlappingEntries(allEntries);
  const entryIndex = allEntries.findIndex((e) => e.id === entry.id);
  const hasOverlaps =
    entryIndex !== -1 && overlappingEntries.includes(entryIndex);

  return {
    isValid: !hasNegDuration && !hasOverlaps,
    hasNegativeDuration: hasNegDuration,
    hasOverlaps,
    overlappingEntries,
  };
}

/**
 * Generate placeholder entries to fill gaps in a 24-hour day
 *
 * @param entries - Sorted array of actual entries for the day
 * @param selectedDate - The date being processed
 * @param unknownAreaId - ID to use for placeholder entries (will be -1 for unknown)
 */
function generatePlaceholderEntries(
  entries: Timelog[],
  selectedDate: Date,
  unknownAreaId: UUID = "-1" as UUID,
  timezone?: string,
): PlaceholderEntry[] {
  const placeholders: PlaceholderEntry[] = [];

  // Create start and end of day timestamps using shared utility
  const { startOfDay: dayStart, endOfDay: dayEnd } = createDateBoundaries(
    selectedDate,
    timezone,
  );

  // Filter and sort valid entries by start time, then end time
  const validEntries = sortTimeEntriesByTime(
    entries.filter((entry) => entry.start_time && entry.end_time),
  );

  let currentTime = dayStart;

  // Check gap before first entry
  if (validEntries.length > 0) {
    const firstEntryStart = new Date(validEntries[0].start_time!);

    // 标准化时间到分钟进行比较
    const normalizedCurrentTime = new Date(currentTime);
    normalizedCurrentTime.setSeconds(0, 0);
    const normalizedFirstEntryStart = new Date(firstEntryStart);
    normalizedFirstEntryStart.setSeconds(0, 0);

    const duration =
      normalizedFirstEntryStart.getTime() - normalizedCurrentTime.getTime();
    if (duration > 0) {
      // Only create placeholder if duration > 0
      placeholders.push({
        id: `placeholder_${currentTime.getTime()}_${firstEntryStart.getTime()}`,
        title: "未记录",
        start_time: currentTime.toISOString(),
        end_time: firstEntryStart.toISOString(),
        area_id: unknownAreaId,
        location: null,
        energy_level: null,
        notes: null,
        tags: null,
        extra_data: null,
        people: [],
        isPlaceholder: true,
      });
    }
    currentTime = new Date(validEntries[0].end_time!);
  }

  // Check gaps between entries
  for (let i = 1; i < validEntries.length; i++) {
    const prevEntryEnd = new Date(validEntries[i - 1].end_time!);
    const currentEntryStart = new Date(validEntries[i].start_time!);

    // 标准化时间到分钟进行比较
    const normalizedPrevEntryEnd = new Date(prevEntryEnd);
    normalizedPrevEntryEnd.setSeconds(0, 0);
    const normalizedCurrentEntryStart = new Date(currentEntryStart);
    normalizedCurrentEntryStart.setSeconds(0, 0);

    const duration =
      normalizedCurrentEntryStart.getTime() - normalizedPrevEntryEnd.getTime();
    if (duration > 0) {
      // Only create placeholder if duration > 0
      placeholders.push({
        id: `placeholder_${prevEntryEnd.getTime()}_${currentEntryStart.getTime()}`,
        title: "未记录",
        start_time: prevEntryEnd.toISOString(),
        end_time: currentEntryStart.toISOString(),
        area_id: unknownAreaId,
        location: null,
        energy_level: null,
        notes: null,
        tags: null,
        extra_data: null,
        people: [],
        isPlaceholder: true,
      });
    }

    currentTime = new Date(validEntries[i].end_time!);
  }

  // Check gap after last entry
  if (validEntries.length > 0) {
    // 标准化时间到分钟进行比较
    const normalizedCurrentTime = new Date(currentTime);
    normalizedCurrentTime.setSeconds(0, 0);
    const normalizedDayEnd = new Date(dayEnd);
    normalizedDayEnd.setSeconds(0, 0);

    const duration =
      normalizedDayEnd.getTime() - normalizedCurrentTime.getTime();
    const minDuration = 1 * 60 * 1000; // 1分钟的最小占位时长

    if (duration > minDuration) {
      // Only create placeholder if duration > 5 minutes
      placeholders.push({
        id: `placeholder_${currentTime.getTime()}_${dayEnd.getTime()}`,
        title: "未记录",
        start_time: currentTime.toISOString(),
        end_time: dayEnd.toISOString(),
        area_id: unknownAreaId,
        location: null,
        energy_level: null,
        notes: null,
        tags: null,
        extra_data: null,
        people: [],
        isPlaceholder: true,
      });
    }
  }

  // If no entries exist, create one big placeholder for the entire day
  if (validEntries.length === 0) {
    placeholders.push({
      id: `placeholder_${dayStart.getTime()}_${dayEnd.getTime()}`,
      title: "未记录",
      start_time: dayStart.toISOString(),
      end_time: dayEnd.toISOString(),
      area_id: unknownAreaId,
      location: null,
      energy_level: null,
      notes: null,
      tags: null,
      extra_data: null,
      people: [],
      isPlaceholder: true,
    });
  }

  return placeholders;
}

/**
 * Process entries by adding validation results and placeholders
 * This is the main function to be called by components
 */
export function processTimeEntries(
  entries: Timelog[],
  selectedDate: Date,
  timezone?: string,
): ProcessedEntry[] {
  const processedEntries: ProcessedEntry[] = [];

  // Add validation results to actual entries
  entries.forEach((entry) => {
    const validationResult = validateTimeEntry(entry, entries);
    processedEntries.push({
      ...entry,
      validationResult,
      isPlaceholder: false,
    });
  });

  // Generate and add placeholder entries
  const placeholders = generatePlaceholderEntries(
    entries,
    selectedDate,
    "-1" as UUID,
    timezone,
  );
  placeholders.forEach((placeholder) => {
    // Convert PlaceholderEntry to ProcessedEntry by adding missing properties
    const processedPlaceholder: ProcessedEntry = {
      ...placeholder,
      tracking_method: "placeholder",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    processedEntries.push(processedPlaceholder);
  });

  // Sort all entries by start time, then end time for stable ordering
  sortTimeEntriesByTime(processedEntries);

  return processedEntries;
}
