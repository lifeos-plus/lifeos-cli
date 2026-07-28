import { describe, expect, it } from "vitest";

import { buildBucketBoundaries } from "@/features/insights/periodBuckets";
import {
  GregorianCalendarAdapter,
  MayanCalendarAdapter,
} from "@/utils/calendar";

describe("periodBuckets", () => {
  const mondayFirstAdapter = new GregorianCalendarAdapter(1);

  it("keeps the leading cross-month week complete in month week stats", () => {
    const buckets = buildBucketBoundaries(
      "week",
      "2026-05-01",
      "2026-05-31",
      mondayFirstAdapter,
    );

    expect(buckets[0]).toEqual({
      start: "2026-04-27",
      end: "2026-05-03",
    });
    expect(buckets).not.toContainEqual({
      start: "2026-05-01",
      end: "2026-05-03",
    });
  });

  it("keeps the trailing cross-month week complete in month week stats", () => {
    const buckets = buildBucketBoundaries(
      "week",
      "2026-07-01",
      "2026-07-31",
      mondayFirstAdapter,
    );

    expect(buckets.at(-1)).toEqual({
      start: "2026-07-27",
      end: "2026-08-02",
    });
  });

  it("keeps cross-year weeks complete in year week stats", () => {
    const buckets = buildBucketBoundaries(
      "week",
      "2026-01-01",
      "2026-12-31",
      mondayFirstAdapter,
    );

    expect(buckets[0]).toEqual({
      start: "2025-12-29",
      end: "2026-01-04",
    });
    expect(buckets.at(-1)).toEqual({
      start: "2026-12-28",
      end: "2027-01-03",
    });
  });

  it("keeps Mayan year boundaries aligned around Day Out of Time", () => {
    const buckets = buildBucketBoundaries(
      "week",
      "2026-07-20",
      "2026-07-28",
      new MayanCalendarAdapter(),
    );

    expect(buckets).toEqual([
      {
        start: "2026-07-18",
        end: "2026-07-24",
      },
      {
        start: "2026-07-25",
        end: "2026-07-25",
      },
      {
        start: "2026-07-26",
        end: "2026-08-01",
      },
    ]);
  });

  it("includes Day Out of Time as a Mayan month bucket", () => {
    const buckets = buildBucketBoundaries(
      "month",
      "2026-06-27",
      "2026-07-26",
      new MayanCalendarAdapter(),
    );

    expect(buckets).toEqual([
      {
        start: "2026-06-27",
        end: "2026-07-24",
      },
      {
        start: "2026-07-25",
        end: "2026-07-25",
      },
      {
        start: "2026-07-26",
        end: "2026-08-22",
      },
    ]);
  });
});
