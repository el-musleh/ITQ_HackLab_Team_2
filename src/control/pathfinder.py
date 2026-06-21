"""AStarPathfinder — Grid-based A* pathfinding around obstacles.

Builds a traversability grid from arena bounds and obstacle positions,
then finds shortest paths using A* with 8-connected neighbours.
"""

import heapq
import math


class AStarPathfinder:
    """A* pathfinder on a uniform grid with obstacle avoidance."""

    # 8-connected neighbour offsets (dx, dy, cost)
    _NEIGHBOURS = [
        (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
        (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)),
    ]

    def __init__(self, arena_bounds, obstacle_positions=None,
                 cell_size=0.05, safety_margin=0.18):
        """Initialise the pathfinder.

        Args:
            arena_bounds: Dict with 'x_min', 'x_max', 'y_min', 'y_max' (m).
            obstacle_positions: List of dicts with 'x', 'y', 'width', 'height'.
            cell_size: Grid cell size in metres (smaller = finer).
            safety_margin: Minimum distance from obstacle edges (m).
        """
        self.arena_bounds = arena_bounds
        self.obstacle_positions = obstacle_positions or []
        self.cell_size = cell_size
        self.safety_margin = safety_margin

        self._x_min = arena_bounds['x_min']
        self._x_max = arena_bounds['x_max']
        self._y_min = arena_bounds['y_min']
        self._y_max = arena_bounds['y_max']

        self._nx = max(1, int(math.ceil((self._x_max - self._x_min) / cell_size)))
        self._ny = max(1, int(math.ceil((self._y_max - self._y_min) / cell_size)))

        # Build traversability grid: True = free, False = blocked
        self._grid = [[True] * self._ny for _ in range(self._nx)]
        self._build_grid()

    def _build_grid(self):
        """Mark cells blocked by obstacles + safety margin."""
        for obs in self.obstacle_positions:
            ox = obs['x']
            oy = obs['y']
            half_w = obs.get('width', 0) / 2 + self.safety_margin
            half_h = obs.get('height', 0) / 2 + self.safety_margin

            x_start = ox - half_w
            x_end = ox + half_w
            y_start = oy - half_h
            y_end = oy + half_h

            ci0 = max(0, int((x_start - self._x_min) / self.cell_size))
            ci1 = min(self._nx - 1, int((x_end - self._x_min) / self.cell_size))
            cj0 = max(0, int((y_start - self._y_min) / self.cell_size))
            cj1 = min(self._ny - 1, int((y_end - self._y_min) / self.cell_size))

            for ci in range(ci0, ci1 + 1):
                for cj in range(cj0, cj1 + 1):
                    self._grid[ci][cj] = False

    def _world_to_grid(self, x, y):
        """Convert world coordinates to grid indices."""
        ci = int((x - self._x_min) / self.cell_size)
        cj = int((y - self._y_min) / self.cell_size)
        ci = max(0, min(self._nx - 1, ci))
        cj = max(0, min(self._ny - 1, cj))
        return ci, cj

    def _grid_to_world(self, ci, cj):
        """Convert grid indices to world coordinates (cell centre)."""
        x = self._x_min + (ci + 0.5) * self.cell_size
        y = self._y_min + (cj + 0.5) * self.cell_size
        return x, y

    def is_traversable(self, x, y):
        """Return True if world coordinate (x, y) is in a free cell."""
        if x < self._x_min or x > self._x_max or y < self._y_min or y > self._y_max:
            return False
        ci, cj = self._world_to_grid(x, y)
        return self._grid[ci][cj]

    def mark_blocked(self, x, y, radius=0.15):
        """Mark cells within *radius* of world coordinate (x, y) as blocked."""
        x_start = x - radius
        x_end = x + radius
        y_start = y - radius
        y_end = y + radius

        ci0 = max(0, int((x_start - self._x_min) / self.cell_size))
        ci1 = min(self._nx - 1, int((x_end - self._x_min) / self.cell_size))
        cj0 = max(0, int((y_start - self._y_min) / self.cell_size))
        cj1 = min(self._ny - 1, int((y_end - self._y_min) / self.cell_size))

        for ci in range(ci0, ci1 + 1):
            for cj in range(cj0, cj1 + 1):
                wx, wy = self._grid_to_world(ci, cj)
                if math.hypot(wx - x, wy - y) <= radius:
                    self._grid[ci][cj] = False

    def find_path(self, start_xy, goal_xy):
        """Find shortest path from *start_xy* to *goal_xy*.

        Args:
            start_xy: (x, y) world coordinates.
            goal_xy: (x, y) world coordinates.

        Returns:
            List of (x, y) waypoints from start to goal, or None if no path.
        """
        sx, sy = start_xy
        gx, gy = goal_xy

        # Clamp start/goal to nearest free cell if they're blocked
        sci, scj = self._world_to_grid(sx, sy)
        gci, gcj = self._world_to_grid(gx, gy)

        if not self._grid[sci][scj]:
            sci, scj = self._nearest_free_cell(sci, scj)
            if sci is None:
                return None

        if not self._grid[gci][gcj]:
            gci, gcj = self._nearest_free_cell(gci, gcj)
            if gci is None:
                return None

        if (sci, scj) == (gci, gcj):
            wx, wy = self._grid_to_world(sci, scj)
            return [(wx, wy)]

        # A* search
        open_heap = []
        counter = 0  # tie-breaker for heapq
        heapq.heappush(open_heap, (0.0, counter, (sci, scj)))
        came_from = {}
        g_cost = {(sci, scj): 0.0}

        while open_heap:
            _, _, (ci, cj) = heapq.heappop(open_heap)

            if (ci, cj) == (gci, gcj):
                # Reconstruct path
                path = []
                cur = (gci, gcj)
                while cur is not None:
                    wx, wy = self._grid_to_world(cur[0], cur[1])
                    path.append((wx, wy))
                    cur = came_from.get(cur)
                path.reverse()
                # Replace first/last with actual start/goal for precision
                path[0] = (sx, sy)
                path[-1] = (gx, gy)
                return self._simplify_path(path)

            for dx, dy, cost in self._NEIGHBOURS:
                ni, nj = ci + dx, cj + dy
                if ni < 0 or ni >= self._nx or nj < 0 or nj >= self._ny:
                    continue
                if not self._grid[ni][nj]:
                    continue
                # Prevent diagonal cutting through obstacle corners
                if dx != 0 and dy != 0:
                    if not self._grid[ci + dx][cj] or not self._grid[ci][cj + dy]:
                        continue
                tentative = g_cost[(ci, cj)] + cost
                key = (ni, nj)
                if key not in g_cost or tentative < g_cost[key]:
                    g_cost[key] = tentative
                    f = tentative + self._heuristic(ni, nj, gci, gcj)
                    counter += 1
                    heapq.heappush(open_heap, (f, counter, key))
                    came_from[key] = (ci, cj)

        return None

    def _heuristic(self, ci, cj, gi, gj):
        """Euclidean distance heuristic."""
        dx = (ci - gi) * self.cell_size
        dy = (cj - gj) * self.cell_size
        return math.hypot(dx, dy)

    def _nearest_free_cell(self, ci, cj):
        """BFS to find the nearest traversable cell to (ci, cj)."""
        if self._grid[ci][cj]:
            return ci, cj
        from collections import deque
        queue = deque([(ci, cj, 0)])
        visited = {(ci, cj)}
        max_radius = max(self._nx, self._ny)
        while queue:
            i, j, r = queue.popleft()
            if r > max_radius:
                break
            for di, dj, _ in self._NEIGHBOURS:
                ni, nj = i + di, j + dj
                if ni < 0 or ni >= self._nx or nj < 0 or nj >= self._ny:
                    continue
                if (ni, nj) in visited:
                    continue
                visited.add((ni, nj))
                if self._grid[ni][nj]:
                    return ni, nj
                queue.append((ni, nj, r + 1))
        return None, None

    @staticmethod
    def _simplify_path(path):
        """Remove collinear waypoints (Douglas-Peucker lite)."""
        if len(path) <= 2:
            return path
        simplified = [path[0]]
        for i in range(1, len(path) - 1):
            prev = simplified[-1]
            curr = path[i]
            nxt = path[i + 1]
            # Check if curr is on the line segment prev->nxt
            dx1 = curr[0] - prev[0]
            dy1 = curr[1] - prev[1]
            dx2 = nxt[0] - prev[0]
            dy2 = nxt[1] - prev[1]
            cross = dx1 * dy2 - dy1 * dx2
            if abs(cross) > 1e-9:
                simplified.append(curr)
        simplified.append(path[-1])
        return simplified

    @staticmethod
    def get_path_length(path):
        """Return total path length in metres."""
        if not path or len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(path)):
            total += math.hypot(path[i][0] - path[i - 1][0],
                                path[i][1] - path[i - 1][1])
        return total
