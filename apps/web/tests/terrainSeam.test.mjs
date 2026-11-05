import {test} from 'node:test';
import assert from 'node:assert/strict';
import {terrainHeight, seamHeight} from '../app/entwurf/terrainSeam.ts';

const positions = [0, 0, 0, 2, 0, 2, 0, 2, 4];
const indices = [0, 1, 2];
test('interpolates the actual triangular surface and rejects outside points', () => {
  assert.equal(terrainHeight(positions, indices, 0.5, 0.5), 1.5);
  assert.equal(terrainHeight(positions, indices, 1, 1), 3);
  assert.equal(terrainHeight(positions, indices, 2, 2), null);
});
test('transforms a rotated and elevated placement correctly', () => {
  assert.ok(Math.abs(seamHeight(positions, indices, 9.5, 20.5, {x: 10, y: 20, rotation_deg: 90}, 7) - 8.5) < 1e-9);
});
