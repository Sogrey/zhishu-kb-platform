/** 密级常量：L3 秘密 / L4 机密起叠加动态水印（C-010）。 */
export const WATERMARK_MIN_LEVEL = 3;

export function needsWatermark(level?: number | null): boolean {
  return (level ?? 0) >= WATERMARK_MIN_LEVEL;
}

export function maxClassification(
  levels: Array<number | null | undefined>,
): number {
  let m = 0;
  for (const lv of levels) {
    const n = lv ?? 0;
    if (n > m) m = n;
  }
  return m;
}
