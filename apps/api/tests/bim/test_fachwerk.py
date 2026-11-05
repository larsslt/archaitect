"""Fachwerk planner: random walls must never lose beams, cross openings or leave plain fields bare."""
import random

import pytest

from archaitect.bim import fachwerk

PATTERNS = ["k_brace", "st_andrew", "man", "foot_head", "diamond", "none"]


def _wall(rng, L):
    ops, u = [], rng.uniform(0.4, 1.5)
    while u < L - 0.8:
        w = rng.choice([0.9, 1.0, 1.3, 1.4, 2.0])
        if u + w > L - 0.4:
            break
        door = rng.random() < 0.15
        zb = 0.0 if door else rng.choice([0.8, 0.9, 1.0])
        ops.append((u, u + w, zb, 2.2 if door else zb + rng.choice([1.2, 1.3, 1.4]), door))
        u += w + rng.uniform(0.3, 2.5)
    return ops


@pytest.mark.parametrize("pattern", PATTERNS)
def test_random_walls_are_valid(pattern):
    rng = random.Random(7)
    for _ in range(150):
        L = rng.uniform(3.0, 16.0)
        zlo, zhi = 0.76, 2.6
        ops = _wall(rng, L)
        polys, posts, bays = fachwerk.plan_wall(L, zlo, zhi, ops, rng.choice([1.0, 1.2, 1.4]), 0.14, pattern)
        assert fachwerk.validate(L, zlo, zhi, ops, polys, bays, pattern) == [], (L, ops)
        # every opening sits between two posts
        for o in ops:
            assert any(abs(p[1] - o[0]) < 0.03 for p in posts) and any(abs(p[0] - o[1]) < 0.03 for p in posts), o


def test_no_bay_wider_than_spacing_limit():
    polys, posts, bays = fachwerk.plan_wall(12.0, 0.0, 2.6, [], 1.2, 0.14, "k_brace")
    assert max(b - a for a, b, _ in bays) <= 1.2 * 1.25 + 0.01
