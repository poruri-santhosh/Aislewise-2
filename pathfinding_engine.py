import heapq
from typing import List, Tuple, Dict, Optional

# Grid Coordinates: (row, col)
Point = Tuple[int, int]

class AStarPathfinder:
    def __init__(self, grid: List[List[int]]):
        """
        0 = Walkable aisle
        1 = Shelf / Obstacle
        """
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])

    def heuristic(self, a: Point, b: Point) -> int:
        # Manhattan distance for grid movements
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def get_neighbors(self, node: Point) -> List[Point]:
        r, c = node
        # Up, Down, Left, Right movements
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        neighbors = []

        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                if self.grid[nr][nc] == 0:  # Walkable
                    neighbors.append((nr, nc))

        return neighbors

    def find_path(self, start: Point, goal: Point) -> Optional[List[Point]]:
        """Computes shortest path between two points using A* algorithm"""
        if self.grid[start[0]][start[1]] == 1 or self.grid[goal[0]][goal[1]] == 1:
            print(f"Error: Start {start} or Goal {goal} is on an obstacle!")
            return None

        # Priority Queue stores: (f_score, current_node)
        open_set = []
        heapq.heappush(open_set, (0, start))

        came_from: Dict[Point, Point] = {}

        # Cost from start to current node
        g_score: Dict[Point, float] = {start: 0}
        
        # Estimated total cost from start to goal through current node
        f_score: Dict[Point, float] = {start: self.heuristic(start, goal)}

        while open_set:
            _, current = heapq.heappop(open_set)

            # Reached destination
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()
                return path

            for neighbor in self.get_neighbors(current):
                tentative_g = g_score[current] + 1  # Cost of 1 step

                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self.heuristic(neighbor, goal)
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, neighbor))

        return None  # No valid path found


class StoreRouteOptimizer:
    """Solves multi-item shopping route: Start -> Item A -> Item B -> Checkout"""
    def __init__(self, pathfinder: AStarPathfinder):
        self.pathfinder = pathfinder

    def generate_full_shopping_route(self, start: Point, items: List[Point], checkout: Point) -> List[Point]:
        current_location = start
        remaining_items = items.copy()
        complete_path = []

        print(f"Planning route from entrance {start} through {len(items)} items to checkout {checkout}...")

        while remaining_items:
            # Nearest-Neighbor heuristic: find the item closest to current position
            closest_item = None
            shortest_subpath = None

            for item in remaining_items:
                path = self.pathfinder.find_path(current_location, item)
                if path and (shortest_subpath is None or len(path) < len(shortest_subpath)):
                    shortest_subpath = path
                    closest_item = item

            if not shortest_subpath:
                print(f"Warning: Cannot reach remaining items {remaining_items}")
                break

            # Append route (avoid repeating current node)
            if not complete_path:
                complete_path.extend(shortest_subpath)
            else:
                complete_path.extend(shortest_subpath[1:])

            current_location = closest_item
            remaining_items.remove(closest_item)

        # Final stretch: Last item to Checkout
        final_leg = self.pathfinder.find_path(current_location, checkout)
        if final_leg:
            complete_path.extend(final_leg[1:])

        return complete_path


# -------------------------------------------------------------
# Test Simulation: Visualizing the Store Floorplan
# -------------------------------------------------------------
if __name__ == "__main__":
    # 0 = Aisle Pathway, 1 = Shelves / Freezers (Obstacles)
    store_map = [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],  # Aisle 1 (Shelves)
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Cross aisle
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],  # Aisle 2 (Shelves)
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],  # Cross aisle
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],  # Aisle 3 (Shelves)
        [0, 1, 1, 0, 1, 1, 0, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]   # Checkout hallway
    ]

    pathfinder = AStarPathfinder(store_map)
    optimizer = StoreRouteOptimizer(pathfinder)

    entrance = (0, 0)
    shopping_items = [
        (4, 3),  # Item 1: Milk (Aisle 2 walk area)
        (7, 6),  # Item 2: Oats (Aisle 3 walk area)
        (1, 6)   # Item 3: Coffee (Aisle 1 walk area)
    ]
    checkout_counter = (9, 9)

    full_route = optimizer.generate_full_shopping_route(entrance, shopping_items, checkout_counter)

    print("\n--- Route Calculated Successfully! ---")
    print(f"Total Waypoint Steps: {len(full_route)}")
    print(f"Waypoints: {full_route}")

    # Render ASCII Visual Map
    visual_map = [["#" if cell == 1 else "." for cell in row] for row in store_map]
    
    # Mark Route path
    for r, c in full_route:
        visual_map[r][c] = "*"

    # Mark Start, Items, End
    visual_map[entrance[0]][entrance[1]] = "S"
    for idx, (ir, ic) in enumerate(shopping_items):
        visual_map[ir][ic] = f"I"
    visual_map[checkout_counter[0]][checkout_counter[1]] = "E"

    print("\nStore Map Visual:")
    print("S = Entrance, E = Checkout, I = Item, * = Calculated Route, # = Shelves, . = Empty Aisle")
    print("-" * 35)
    for row in visual_map:
        print(" ".join(row))
    print("-" * 35)