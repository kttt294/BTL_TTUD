"""Mô hình dữ liệu và các phép toán trên bản đồ lục giác."""

from dataclasses import dataclass, field


@dataclass
class Board:
    cells: list[list[int]]
    spots: list[dict]
    starts: list[int]
    day_steps: list[int]
    fuel_limit: int
    busy_threshold: float = 3
    jammed_threshold: float = 4

    @classmethod
    def from_dict(cls, data, starts=None):
        positions = starts if starts is not None else data.get("agents")
        if not positions:
            raise ValueError("Cần cung cấp vị trí xuất phát qua agents hoặc --starts.")
        cells = data["map"]["cells"]
        height, width = data["map"]["height"], data["map"]["width"]
        if len(cells) != height or any(len(row) != width for row in cells):
            raise ValueError("Kích thước cells không khớp cấu hình bản đồ.")
        if any(type(cell) is not int or cell not in range(4) for row in cells for cell in row):
            raise ValueError("Mã địa hình phải là số nguyên từ 0 đến 3.")
        board = cls(cells, data["spots"], positions, data["daySteps"], data["fuelLimits"],
                    data.get("busyThreshold", 3), data.get("jammedThreshold", 4))
        if not board.day_steps or any(type(t) is not int or t <= 0 for t in board.day_steps):
            raise ValueError("Quỹ bước mỗi ngày phải là số nguyên dương.")
        if type(board.fuel_limit) is not int or board.fuel_limit <= 0:
            raise ValueError("Giới hạn nhiên liệu phải là số nguyên dương.")
        if any(type(p) is not int or not 0 <= p < width * height or board.terrain(p) != 0
               for p in positions):
            raise ValueError("Vị trí xuất phát phải là ô đồng bằng trong bản đồ.")
        spot_positions = set()
        for spot in board.spots:
            p = spot["pos"]
            if (type(p) is not int or not 0 <= p < width * height or board.terrain(p) != 0
                    or p in spot_positions or type(spot["stocks"]) is not int
                    or not 1 <= spot["stocks"] <= len(positions)):
                raise ValueError("Điểm udon phải có vị trí riêng trên đồng bằng và kho hợp lệ.")
            spot_positions.add(p)
        if any(p in spot_positions for p in positions):
            raise ValueError("Vị trí xuất phát không được trùng điểm udon.")
        if not 0 <= board.busy_threshold <= board.jammed_threshold:
            raise ValueError("Ngưỡng giao thông không hợp lệ.")
        return board

    @property
    def width(self):
        return len(self.cells[0])

    @property
    def height(self):
        return len(self.cells)

    def terrain(self, pos):
        row, col = divmod(pos, self.width)
        return self.cells[row][col]

    def neighbor(self, pos, direction):
        row, col = divmod(pos, self.width)
        shift = 1 if row % 2 == 0 else 0
        offsets = [(-1, shift - 1), (-1, shift), (0, 1),
                   (1, shift), (1, shift - 1), (0, -1)]
        dr, dc = offsets[direction]
        r, c = row + dr, col + dc
        if 0 <= r < self.height and 0 <= c < self.width:
            target = r * self.width + c
            if self.terrain(target) != 3:
                return target
        return None

    def neighbors(self, pos):
        return [(direction, target) for direction in range(6)
                if (target := self.neighbor(pos, direction)) is not None]

    def distance(self, start, goal):
        def cube(pos):
            row, col = divmod(pos, self.width)
            q = col - (row + row % 2) // 2
            return q, row, -q - row
        return max(abs(a - b) for a, b in zip(cube(start), cube(goal)))

    def cost(self, pos, traffic):
        terrain = self.terrain(pos)
        if terrain == 0:
            return 2, 1
        if terrain == 2:
            return 3, 2
        if terrain == 1:
            return (1, 2, 4)[traffic.get(pos, 0)], 2
        raise ValueError("Xe không thể đứng trên ao.")


@dataclass
class Agent:
    kind: int
    pos: int
    fuel: int


@dataclass
class State:
    agents: list[Agent]
    traffic: dict[int, int] = field(default_factory=dict)
    brands: set[int] = field(default_factory=set)
    daily_sum: int = 0
    portions: int = 0
    road_history: list[dict[int, int]] = field(default_factory=list)
    day: int = 0

    @classmethod
    def initial(cls, board, kinds):
        if len(kinds) != len(board.starts) or any(type(k) is not int or k not in (0, 1) for k in kinds):
            raise ValueError("Mỗi xe phải có một loại 0 hoặc 1.")
        return cls([Agent(kind, pos, board.fuel_limit if kind == 0 else 0)
                    for kind, pos in zip(kinds, board.starts)])

    def score(self):
        return len(self.brands), self.daily_sum, self.portions
