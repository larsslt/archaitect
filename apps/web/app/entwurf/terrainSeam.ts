/** Sample the rendered triangulation, in house coordinates, rather than inventing terrain heights. */
export function terrainHeight(positions: number[], indices: number[], x: number, y: number): number | null {
  for (let i = 0; i + 2 < indices.length; i += 3) {
    const a = indices[i] * 3, b = indices[i + 1] * 3, c = indices[i + 2] * 3;
    const ax = positions[a], ay = positions[a + 1], bx = positions[b], by = positions[b + 1], cx = positions[c], cy = positions[c + 1];
    if (x < Math.min(ax, bx, cx) - 1e-7 || x > Math.max(ax, bx, cx) + 1e-7 || y < Math.min(ay, by, cy) - 1e-7 || y > Math.max(ay, by, cy) + 1e-7) continue;
    const d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy);
    if (Math.abs(d) < 1e-12) continue;
    const u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d;
    const v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d;
    const w = 1 - u - v;
    if (u >= -1e-7 && v >= -1e-7 && w >= -1e-7) return u * positions[a + 2] + v * positions[b + 2] + w * positions[c + 2];
  }
  return null;
}

export function seamHeight(positions: number[], indices: number[], x: number, y: number, placement: {x: number; y: number; rotation_deg: number}, base: number): number | null {
  const a = placement.rotation_deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
  const dx = x - placement.x, dy = y - placement.y;
  const z = terrainHeight(positions, indices, c * dx + s * dy, -s * dx + c * dy);
  return z === null ? null : z + base;
}
