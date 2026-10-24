// Planner tour viết lại bằng C++ (cùng thuật toán với src/hexudon/tour.py), chạy nhiều luồng.
//
// Đầu vào (stdin, các số cách nhau bởi khoảng trắng):
//   HEXPLAN 1
//   W H  terrain[W*H]  fuel_limit
//   ndays steps[ndays]
//   nspots (pos brand stocks)*
//   nagents (kind pos fuel)*
//   day  ntraffic (pos status)*  nbrands brand*
//   steps alpha seed workers until ncheck check_time*
//   positions noise max_remove segment alns escort  w_variant_segment w_segment w_random w_reverse w_swap w_worst
// until và check_time là giây epoch (như time.time() của Python).
// Đầu ra: mỗi kế hoạch là dòng "PLAN <tag> <seed> <số xe>" rồi mỗi xe một dòng "<số lệnh> lệnh...";
// tag là chỉ số mốc (0, 1, ...) hoặc F cho kế hoạch cuối; kết thúc bằng dòng "DONE".

#include <algorithm>
#include <atomic>
#include <bitset>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <numeric>
#include <optional>
#include <queue>
#include <random>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

using namespace std;

constexpr int INF = 100000000;
constexpr int MAXS = 256;  // số điểm udon / số loại tối đa
using Bits = bitset<MAXS>;
const double VARIANTS[3][2] = {{1.0, 0.001}, {1.0, 1.0}, {0.001, 1.0}};

double now_epoch() {
    return chrono::duration<double>(chrono::system_clock::now().time_since_epoch()).count();
}

// ---------------------------------------------------------------- bản đồ và trạng thái

struct Spot {
    int pos, brand, stocks;
};

struct Board {
    int width = 0, height = 0, fuel_limit = 0, brand_count = 0;
    double busy_threshold = 3, jammed_threshold = 4;
    vector<int> terrain, day_steps, spot_index;  // spot_index: ô -> chỉ số điểm, -1 nếu không có
    vector<Spot> spots;                          // brand đã đánh lại 0..brand_count-1

    int size() const { return width * height; }

    int neighbor(int pos, int direction) const {
        int row = pos / width, col = pos % width;
        int shift = row % 2 == 0 ? 1 : 0;
        static const int dr[6] = {-1, -1, 0, 1, 1, 0};
        int dc[6] = {shift - 1, shift, 1, shift, shift - 1, -1};
        int r = row + dr[direction], c = col + dc[direction];
        if (r < 0 || r >= height || c < 0 || c >= width) return -1;
        int target = r * width + c;
        return terrain[target] == 3 ? -1 : target;
    }

    int distance(int a, int b) const {
        auto cube = [&](int pos, int& q, int& r, int& s) {
            int row = pos / width, col = pos % width;
            q = col - (row + row % 2) / 2;
            r = row;
            s = -q - r;
        };
        int q1, r1, s1, q2, r2, s2;
        cube(a, q1, r1, s1);
        cube(b, q2, r2, s2);
        return max({abs(q1 - q2), abs(r1 - r2), abs(s1 - s2)});
    }
};

struct Agent {
    int kind, pos, fuel;
};

struct State {
    vector<Agent> agents;
    unordered_map<int, int> traffic;
    Bits brands;
    int day = 0;
    // Chỉ chế độ chọn đội hình dùng: lịch sử 2 ngày số lần xe đứng trên ô đường, điểm cộng dồn.
    vector<unordered_map<int, int>> road_history;
    int daily_sum = 0, portions = 0;
};

// ---------------------------------------------------------------- số ngẫu nhiên (giao diện như random.Random)

struct Rng {
    mt19937_64 engine;
    explicit Rng(uint64_t seed) : engine(seed) {}
    double random() { return uniform_real_distribution<double>(0.0, 1.0)(engine); }
    int randrange(int n) { return uniform_int_distribution<int>(0, n - 1)(engine); }
    int randint(int a, int b) { return uniform_int_distribution<int>(a, b)(engine); }
    template <class T> const T& choice(const vector<T>& items) { return items[randrange((int)items.size())]; }
    template <class T> vector<T> sample(vector<T> items, int k) {
        for (int i = 0; i < k; ++i) swap(items[i], items[i + randrange((int)items.size() - i)]);
        items.resize(k);
        return items;
    }
    int choices(const vector<double>& weights) {
        double total = accumulate(weights.begin(), weights.end(), 0.0), x = random() * total;
        for (size_t i = 0; i < weights.size(); ++i) {
            if (x < weights[i]) return (int)i;
            x -= weights[i];
        }
        return (int)weights.size() - 1;
    }
};

// ---------------------------------------------------------------- đường ngắn nhất

struct Tree {
    vector<int> steps, fuel, parent, pdir;
};

struct LegInfo {
    int steps, fuel;
    Bits spots;  // điểm udon đi qua kể cả đích, không gồm ô xuất phát
};

class Legs {
  public:
    Legs(const Board& board, const unordered_map<int, int>& traffic) : board(board) {
        int n = board.size();
        cost.assign(n, {0, 0});
        nbrs.assign(n, {});
        for (int p = 0; p < n; ++p) {
            int t = board.terrain[p];
            if (t == 3) continue;
            if (t == 0) cost[p] = {2, 1};
            else if (t == 2) cost[p] = {3, 2};
            else {
                auto it = traffic.find(p);
                int status = it == traffic.end() ? 0 : it->second;
                static const int road[3] = {1, 2, 4};
                cost[p] = {road[max(0, min(2, status))], 2};
            }
            for (int d = 0; d < 6; ++d) {
                int v = board.neighbor(p, d);
                if (v >= 0) nbrs[p].push_back({d, v});
            }
        }
    }

    const Tree& tree(int source, int variant) {
        int64_t key = (int64_t)source * 3 + variant;
        auto it = trees.find(key);
        if (it != trees.end()) return it->second;
        double a = VARIANTS[variant][0], b = VARIANTS[variant][1];
        int n = board.size();
        vector<double> dist(n, 1e300);
        Tree tr{vector<int>(n, 0), vector<int>(n, 0), vector<int>(n, -1), vector<int>(n, -1)};
        priority_queue<pair<double, int>, vector<pair<double, int>>, greater<>> heap;
        dist[source] = 0.0;
        heap.push({0.0, source});
        while (!heap.empty()) {
            auto [d, u] = heap.top();
            heap.pop();
            if (d > dist[u]) continue;
            auto [su, fu] = cost[u];
            double nd = d + a * su + b * fu;
            int ns = tr.steps[u] + su, nf = tr.fuel[u] + fu;
            for (auto [direction, v] : nbrs[u]) {
                if (nd < dist[v] - 1e-9) {
                    dist[v] = nd;
                    tr.steps[v] = ns;
                    tr.fuel[v] = nf;
                    tr.parent[v] = u;
                    tr.pdir[v] = direction;
                    heap.push({nd, v});
                }
            }
        }
        return trees.emplace(key, move(tr)).first->second;
    }

    const LegInfo& leg(int start, int goal, int variant) {
        int64_t key = ((int64_t)start * board.size() + goal) * 3 + variant;
        auto it = legs.find(key);
        if (it != legs.end()) return it->second;
        const Tree& tr = tree(start, variant);
        LegInfo info{0, 0, Bits()};
        if (start != goal && tr.parent[goal] == -1) {
            // Ô ở vùng tách rời: chi phí vô hạn.
            info.steps = info.fuel = INF;
        } else {
            for (int pos = goal; pos != start; pos = tr.parent[pos])
                if (board.spot_index[pos] >= 0) info.spots.set(board.spot_index[pos]);
            info.steps = tr.steps[goal];
            info.fuel = tr.fuel[goal];
        }
        return legs.emplace(key, info).first->second;
    }

    vector<int> directions(int start, int goal, int variant) {
        const Tree& tr = tree(start, variant);
        if (start != goal && tr.parent[goal] == -1) throw runtime_error("không có đường đi");
        vector<int> reverse;
        for (int pos = goal; pos != start; pos = tr.parent[pos]) reverse.push_back(tr.pdir[pos]);
        return vector<int>(reverse.rbegin(), reverse.rend());
    }

  private:
    const Board& board;
    vector<pair<int, int>> cost;
    vector<vector<pair<int, int>>> nbrs;
    unordered_map<int64_t, Tree> trees;
    unordered_map<int64_t, LegInfo> legs;
};

// ---------------------------------------------------------------- bài toán một ngày

struct Segment {
    bool wait;
    int a, b, variant;  // wait: a = số step chờ
};

struct CarRun {
    bool feasible = false;
    int steps = 0, fuel = 0, spent = 0;
    Bits visited;
    vector<Segment> segments;
    double cost = 0.0;
    int end = -1;
};

using Score = array<int64_t, 5>;  // (loại mới, loại hôm nay, suất, -nhiên liệu, -step)

struct Params {
    int positions = 3, max_remove = 4, segment = 4;
    double noise = 0.5, alns = 0.0;
    bool escort = true;
    vector<double> weights = {0.105, 0.14, 0.455, 0.12, 0.09, 0.09};
    // temperature > 0: nhận lời giải ít suất hơn với xác suất exp(-mất/T), T giảm dần về 0.
    // ktemp: luồng w dùng nhiệt độ temperature * w / (số luồng - 1). search: 0 = LNS, 1 = quần thể (PSO rời rạc).
    double temperature = 0.0;
    bool ktemp = false;
    int search = 0;
    // last_day_free: ngày cuối không chừa nhiên liệu quay về điểm hẹn (không còn ngày sau).
    bool last_day_free = false;
};
enum Operator { VARIANT_SEGMENT, SEGMENT, RANDOM, REVERSE, SWAP, WORST };

struct Hub {
    int pos, arrival, escort = -1;  // escort >= 0: xe tiếp tế hộ tống xe tuần tra này
};
using Option = vector<pair<int, Hub>>;  // (xe tiếp tế, điểm hẹn)

int types_coverage(const Board& board, const State& state, int steps, const vector<pair<int, int>>& hubs,
                   double alpha, Legs& legs, const Params& params);

vector<int> allowances(const Board& board, const State& state, int steps, double alpha) {
    int remaining = 0;
    for (size_t d = state.day; d < board.day_steps.size(); ++d) remaining += board.day_steps[d];
    if (!remaining) remaining = steps;
    double share = state.day >= (int)board.day_steps.size() - 1 ? 1.0 : min(1.0, alpha * steps / remaining);
    vector<int> result;
    for (auto& a : state.agents) result.push_back((int)(a.fuel * share));
    return result;
}

struct DayProblem {
    const Board& board;
    const State& state;
    int steps, next_steps;  // next_steps = 0: không có ngày mai
    Legs& legs;
    const Params& params;
    vector<int> patrols, allowance;
    vector<pair<int, int>> hubs;          // (ô hẹn, step xe tiếp tế tới nơi)
    unordered_map<int, int> hub_arrival;  // ô hẹn -> step tới sớm nhất
    map<int, pair<int, int>> escort;      // xe tuần tra -> (xe tiếp tế, step tới chỗ nó)
    map<int, int> anchors;                // xe tuần tra -> ô phải dừng cuối ngày
    shared_ptr<map<vector<int>, int>> coverages = make_shared<map<vector<int>, int>>();
    unordered_map<int, int> reserves;
    double alpha = 1.0;
    int limit;
    Option option;

    DayProblem(const Board& board, const State& state, int steps, vector<pair<int, int>> hubs_,
               vector<int> allowance, int next_steps, Legs& legs, const Params& params)
        : board(board), state(state), steps(steps), next_steps(next_steps), legs(legs), params(params),
          allowance(move(allowance)), hubs(move(hubs_)), limit(board.fuel_limit) {
        for (size_t i = 0; i < state.agents.size(); ++i)
            if (state.agents[i].kind == 0) patrols.push_back((int)i);
        for (auto [hub, arrival] : hubs) {
            auto it = hub_arrival.find(hub);
            hub_arrival[hub] = it == hub_arrival.end() ? arrival : min(it->second, arrival);
        }
    }

    int arrival_at(int pos) const {
        auto it = hub_arrival.find(pos);
        return it == hub_arrival.end() ? INF : it->second;
    }

    int reserve(int pos) {
        if (hubs.empty()) return 0;
        if (params.last_day_free && state.day >= (int)board.day_steps.size() - 1) return 0;
        auto it = reserves.find(pos);
        if (it != reserves.end()) return it->second;
        int best = INF;
        for (auto [hub, _] : hubs) best = min(best, legs.leg(pos, hub, 2).fuel);
        return reserves[pos] = best;
    }

    // Điểm hẹn có tổng đường đi + về ngắn nhất; goal = -1: không cần quay lại.
    tuple<int, int, const LegInfo*> refuel_hub(int pos, int goal, int variant) {
        int best_total = -1, best_hub = -1, best_arrival = 0;
        const LegInfo* best_go = nullptr;
        for (auto [hub, arrival] : hubs) {
            const LegInfo& go = legs.leg(pos, hub, variant);
            int back = goal >= 0 ? legs.leg(hub, goal, variant).steps : 0;
            int total = go.steps + back;
            if (best_go == nullptr || total < best_total) {
                best_total = total;
                best_hub = hub;
                best_arrival = arrival;
                best_go = &go;
            }
        }
        return {best_hub, best_arrival, best_go};
    }

    void mark(Bits& visited, int pos) const {
        if (board.spot_index[pos] >= 0) visited.set(board.spot_index[pos]);
    }

    CarRun run(int car, vector<int> stops, int variant) {
        auto anchor = anchors.find(car);
        if (anchor != anchors.end() && (stops.empty() || stops.back() != anchor->second))
            stops.push_back(anchor->second);
        auto esc = escort.find(car);
        if (esc != escort.end()) return escorted(car, stops, variant, esc->second.second);
        const Agent& agent = state.agents[car];
        int pos = agent.pos, t = 0, fuel = agent.fuel, T = steps;
        CarRun out;
        mark(out.visited, pos);
        bool refueled = false;
        for (int stop : stops) {
            const LegInfo* leg = &legs.leg(pos, stop, variant);
            if (!hubs.empty() && fuel < leg->fuel + reserve(stop)) {
                auto [hub, arrival, go] = refuel_hub(pos, stop, variant);
                if (fuel < go->fuel) return CarRun();
                if (hub != pos) {
                    out.segments.push_back({false, pos, hub, variant});
                    out.visited |= go->spots;
                }
                t += go->steps;
                fuel -= go->fuel;
                if (arrival > t) {
                    out.segments.push_back({true, arrival - t, 0, 0});
                    t = arrival;
                }
                fuel = limit;
                pos = hub;
                refueled = true;
                leg = &legs.leg(pos, stop, variant);
                if (fuel < leg->fuel + reserve(stop)) return CarRun();
            } else if (fuel < leg->fuel) {
                return CarRun();
            }
            out.segments.push_back({false, pos, stop, variant});
            t += leg->steps;
            fuel -= leg->fuel;
            out.visited |= leg->spots;
            pos = stop;
            if (t > T) return CarRun();
            if (t >= arrival_at(pos)) {
                // Dừng ở điểm hẹn khi xe tiếp tế đã tới: simulator đổ đầy bình.
                fuel = limit;
                refueled = true;
            }
        }
        if (!stops.empty() && arrival_at(pos) <= T) {
            fuel = limit;
            refueled = true;
        }
        if (!hubs.empty() && !stops.empty()) {
            // Xe đã di chuyển phải còn đủ nhiên liệu về điểm hẹn.
            if (fuel < reserve(pos)) {
                auto [hub, arrival, go] = refuel_hub(pos, -1, variant);
                if (fuel < go->fuel || t + go->steps > T) return CarRun();
                out.segments.push_back({false, pos, hub, variant});
                out.visited |= go->spots;
                t += go->steps;
                fuel = max(t, arrival) <= T ? limit : fuel - go->fuel;
                refueled = refueled || fuel == limit;
                pos = hub;
            }
        } else if (hubs.empty() && agent.fuel - fuel > allowance[car]) {
            return CarRun();
        }
        int spent = refueled ? limit - fuel : agent.fuel - fuel;
        double scale = !hubs.empty() ? limit : max(1, allowance[car]);
        out.feasible = true;
        out.steps = t;
        out.fuel = fuel;
        out.spent = max(0, spent);
        out.cost = (double)t / T + max(0, agent.fuel - fuel) / scale;
        out.end = pos;
        return out;
    }

    // Xe tuần tra chờ xe tiếp tế tới rồi hai xe đi cùng lệnh: không giới hạn nhiên liệu.
    CarRun escorted(int car, const vector<int>& stops, int variant, int arrival) {
        int pos = state.agents[car].pos, t = arrival;
        CarRun out;
        mark(out.visited, pos);
        if (arrival) out.segments.push_back({true, arrival, 0, 0});
        for (int stop : stops) {
            const LegInfo& leg = legs.leg(pos, stop, variant);
            out.segments.push_back({false, pos, stop, variant});
            t += leg.steps;
            out.visited |= leg.spots;
            pos = stop;
            if (t > steps) return CarRun();
        }
        out.feasible = true;
        out.steps = t;
        out.fuel = limit;
        out.cost = (double)t / steps;
        out.end = pos;
        return out;
    }

    Score score(const map<int, CarRun>& runs) const {
        int n = (int)board.spots.size();
        vector<int> counts(n, 0);
        int spent = 0, used = 0;
        for (auto& [car, run] : runs) {
            spent += run.spent;
            used += run.steps;
            for (int i = 0; i < n; ++i)
                if (run.visited[i]) ++counts[i];
        }
        Bits brands;
        int portions = 0;
        for (int i = 0; i < n; ++i)
            if (counts[i]) {
                brands.set(board.spots[i].brand);
                portions += min(counts[i], board.spots[i].stocks);
            }
        int fresh = (int)(brands & ~state.brands).count();
        return {fresh, (int64_t)brands.count(), portions, -spent, -used};
    }

    int coverage(const map<int, CarRun>& runs) {
        vector<int> key;
        for (int c : patrols) {
            key.push_back(runs.at(c).end);
            key.push_back(runs.at(c).fuel);
        }
        return coverage_from(key);
    }

    // key: (ô cuối, nhiên liệu cuối) của từng xe tuần tra theo thứ tự patrols.
    int coverage_from(const vector<int>& key) {
        if (!next_steps) return 0;
        auto it = coverages->find(key);
        if (it != coverages->end()) return it->second;
        map<int, int> escorting;  // xe tiếp tế -> ô cuối của xe được hộ tống
        for (auto& [patrol, info] : escort) {
            int index = (int)(find(patrols.begin(), patrols.end(), patrol) - patrols.begin());
            escorting[info.first] = key[2 * index];
        }
        State tomorrow;
        tomorrow.traffic = state.traffic;
        tomorrow.day = state.day + 1;
        size_t hub_index = 0, patrol_index = 0;
        vector<pair<int, int>> tomorrow_hubs;
        for (size_t car = 0; car < state.agents.size(); ++car) {
            const Agent& agent = state.agents[car];
            if (agent.kind == 0) {
                tomorrow.agents.push_back({0, key[2 * patrol_index], key[2 * patrol_index + 1]});
                ++patrol_index;
            } else {
                int pos = agent.pos;
                if (escorting.count((int)car)) pos = escorting[(int)car];
                else if (hub_index < hubs.size()) pos = hubs[hub_index++].first;
                tomorrow.agents.push_back({1, pos, 0});
                tomorrow_hubs.push_back({pos, 0});
            }
        }
        int value = types_coverage(board, tomorrow, next_steps, tomorrow_hubs, alpha, legs, params);
        (*coverages)[key] = value;
        return value;
    }
};

// ---------------------------------------------------------------- dựng tuyến

using Clock = chrono::steady_clock;
double seconds_now() { return chrono::duration<double>(Clock::now().time_since_epoch()).count(); }
constexpr double NO_DEADLINE = 1e300;

struct Insertion {
    double delta;
    vector<int> trial;
    CarRun run;
};

// Phương án chèn rẻ nhất cho từng điểm vào tuyến của một xe (chỉ số điểm -> phương án).
map<int, Insertion> car_insertions(DayProblem& problem, int car, const vector<int>& route, int variant,
                                   const CarRun& current) {
    Legs& legs = problem.legs;
    int T = problem.steps, positions = problem.params.positions;
    vector<int> seq = {problem.state.agents[car].pos};
    seq.insert(seq.end(), route.begin(), route.end());
    map<int, Insertion> options;
    for (size_t index = 0; index < problem.board.spots.size(); ++index) {
        if (current.visited[index]) continue;
        int spot = problem.board.spots[index].pos;
        vector<pair<int, int>> quick;
        for (size_t k = 0; k < seq.size(); ++k) {
            int a = seq[k];
            int extra = legs.leg(a, spot, variant).steps;
            if (k + 1 < seq.size()) {
                int b = seq[k + 1];
                extra += legs.leg(spot, b, variant).steps - legs.leg(a, b, variant).steps;
            }
            if (current.steps + extra <= T) quick.push_back({extra, (int)k});
        }
        sort(quick.begin(), quick.end());
        optional<Insertion> best;
        for (size_t q = 0; q < quick.size() && (int)q < positions; ++q) {
            int k = quick[q].second;
            vector<int> trial(route.begin(), route.begin() + k);
            trial.push_back(spot);
            trial.insert(trial.end(), route.begin() + k, route.end());
            CarRun run = problem.run(car, trial, variant);
            // Giữ đúng phép so của bản Python: chi phí tuyệt đối so với mức tăng đã lưu (so mức tăng với
            // mức tăng đo trên 200 bản đồ không tốt hơn).
            if (run.feasible && (!best || run.cost < best->delta))
                best = Insertion{run.cost - current.cost, move(trial), move(run)};
        }
        if (best) options.emplace((int)index, move(*best));
    }
    return options;
}

struct Solution {
    Score score;
    map<int, vector<int>> routes;
    map<int, int> variants;
    map<int, CarRun> runs;
};

void insert_greedy(DayProblem& problem, map<int, vector<int>>& routes, map<int, int>& variants,
                   map<int, CarRun>& runs, Rng* rng, double noise, double deadline, bool types_only) {
    const Board& board = problem.board;
    int n = (int)board.spots.size();
    map<int, map<int, Insertion>> cache;
    while (deadline >= NO_DEADLINE || seconds_now() < deadline) {
        vector<int> counts(n, 0);
        Bits today;
        for (auto& [car, run] : runs)
            for (int i = 0; i < n; ++i)
                if (run.visited[i]) ++counts[i];
        for (int i = 0; i < n; ++i)
            if (counts[i]) today.set(board.spots[i].brand);
        bool found = false;
        array<int, 3> best_gain{};
        double best_delta = 0;
        int best_car = -1, best_spot = -1;
        for (int car : problem.patrols) {
            auto cached = cache.find(car);
            if (cached == cache.end())
                cached = cache.emplace(car, car_insertions(problem, car, routes[car], variants[car], runs[car])).first;
            for (auto& [spot, option] : cached->second) {
                const Spot& info = board.spots[spot];
                array<int, 3> gain = {!problem.state.brands[info.brand] && !today[info.brand], !today[info.brand],
                                      counts[spot] < info.stocks};
                if (!(gain[0] || gain[1] || gain[2]) || (types_only && !gain[1])) continue;
                double delta = option.delta;
                if (rng && noise) delta *= 1 + noise * rng->random();
                if (!found || gain > best_gain || (gain == best_gain && -delta > -best_delta)) {
                    found = true;
                    best_gain = gain;
                    best_delta = delta;
                    best_car = car;
                    best_spot = spot;
                }
            }
        }
        if (!found) return;
        Insertion& chosen = cache[best_car][best_spot];
        routes[best_car] = chosen.trial;
        runs[best_car] = chosen.run;
        cache.erase(best_car);
    }
}

optional<Solution> construct(DayProblem& problem, int variant, double deadline = NO_DEADLINE, bool types_only = false,
                             Rng* rng = nullptr, double noise = 0.0) {
    Solution s;
    for (int c : problem.patrols) {
        s.routes[c] = {};
        s.variants[c] = variant;
        s.runs[c] = problem.run(c, {}, variant);
        if (!s.runs[c].feasible) return nullopt;
    }
    insert_greedy(problem, s.routes, s.variants, s.runs, rng, noise, deadline, types_only);
    s.score = problem.score(s.runs);
    return s;
}

int types_coverage(const Board& board, const State& state, int steps, const vector<pair<int, int>>& hubs,
                   double alpha, Legs& legs, const Params& params) {
    DayProblem problem(board, state, steps, hubs, allowances(board, state, steps, alpha), 0, legs, params);
    int best = 0;
    vector<int> variants = hubs.empty() ? vector<int>{0, 2} : vector<int>{0};
    for (int variant : variants) {
        auto result = construct(problem, variant, NO_DEADLINE, true);
        if (result) best = max(best, (int)result->score[1]);
        if (best == board.brand_count) break;
    }
    return best;
}

// ---------------------------------------------------------------- mốc gửi kế hoạch tạm

struct Checkpoint {
    mutex lock;
    atomic<int> requested{-1};
    vector<int> answered;                    // mốc mới nhất từng luồng đã trả lời
    vector<vector<vector<int>>> snapshots;   // kế hoạch tạm của từng luồng
};

vector<vector<int>> commands(DayProblem& problem, const map<int, CarRun>& runs, const Option& supply_routes);

struct Worker {
    int index;
    Checkpoint* checkpoint;
    double temperature = 0.0;
    int answered = -1;

    void emit(DayProblem& problem, const map<int, CarRun>& runs) {
        if (!checkpoint) return;
        int request = checkpoint->requested.load();
        if (request <= answered) return;
        answered = request;
        auto actions = commands(problem, runs, problem.option);
        lock_guard<mutex> guard(checkpoint->lock);
        checkpoint->snapshots[index] = move(actions);
        checkpoint->answered[index] = request;
    }
};

// Ứng viên: (lời giải, phương án điểm hẹn, bài toán). Bài toán giữ bằng shared_ptr để dùng lại.
struct Candidate {
    Solution solution;
    Option option;
    shared_ptr<DayProblem> problem;
};

Candidate cover_types(vector<Candidate>& candidates, double deadline, Rng& rng, const vector<int>& variants,
                      Candidate best, Worker& worker) {
    size_t attempt = 0;
    while (seconds_now() < deadline) {
        Candidate& cand = candidates[attempt % candidates.size()];
        int variant = variants[(attempt / candidates.size()) % variants.size()];
        // Lượt đầu mỗi (phương án, kiểu đường) dựng không nhiễu.
        double noise = attempt < candidates.size() * variants.size() ? 0.0 : 1.0 + rng.random();
        ++attempt;
        auto skeleton = construct(*cand.problem, variant, deadline, true, &rng, noise);
        if (!skeleton || skeleton->score[1] < best.solution.score[1]) continue;
        insert_greedy(*cand.problem, skeleton->routes, skeleton->variants, skeleton->runs, nullptr, 0.0, deadline,
                      false);
        skeleton->score = cand.problem->score(skeleton->runs);
        if (skeleton->score > best.solution.score) best = Candidate{*skeleton, cand.option, cand.problem};
        if (best.solution.score[1] == cand.problem->board.brand_count) break;
        // Trả lời mốc nộp nhanh bằng lời giải tốt nhất hiện có (ngày ngắn có thể ở đây khá lâu).
        worker.emit(*best.problem, best.solution.runs);
    }
    return best;
}

// ---------------------------------------------------------------- phá và dựng lại

vector<pair<int, int>> removal_savings(DayProblem& problem, int car, const vector<int>& route, int variant) {
    Legs& legs = problem.legs;
    vector<int> seq = {problem.state.agents[car].pos};
    seq.insert(seq.end(), route.begin(), route.end());
    vector<pair<int, int>> savings;
    for (size_t i = 1; i < seq.size(); ++i) {
        int saved = legs.leg(seq[i - 1], seq[i], variant).steps;
        if (i + 1 < seq.size())
            saved += legs.leg(seq[i], seq[i + 1], variant).steps - legs.leg(seq[i - 1], seq[i + 1], variant).steps;
        savings.push_back({saved, (int)i - 1});
    }
    return savings;
}

bool extended_move(DayProblem& problem, map<int, vector<int>>& routes, map<int, int>& variants, Rng& rng, int kind) {
    vector<int> cars;
    for (int c : problem.patrols)
        if (!routes[c].empty()) cars.push_back(c);
    if (cars.empty()) return false;
    if (kind == REVERSE) {
        vector<int>& route = routes[rng.choice(cars)];
        if (route.size() < 3) return false;
        int i = rng.randrange((int)route.size() - 1);
        int j = rng.randint(i + 2, min((int)route.size(), i + 8));
        reverse(route.begin() + i, route.begin() + j);
    } else if (kind == SWAP) {
        if (cars.size() < 2) return false;
        auto pair_ = rng.sample(cars, 2);
        vector<int>& a = routes[pair_[0]];
        vector<int>& b = routes[pair_[1]];
        int i = rng.randrange((int)a.size()), j = rng.randrange((int)b.size());
        if (find(b.begin(), b.end(), a[i]) != b.end() || find(a.begin(), a.end(), b[j]) != a.end()) return false;
        swap(a[i], b[j]);
    } else {
        int car = rng.choice(cars);
        auto savings = removal_savings(problem, car, routes[car], variants[car]);
        sort(savings.rbegin(), savings.rend());
        int count = rng.randint(1, min(3, (int)savings.size()));
        vector<pair<int, int>> chosen(savings.begin(), savings.begin() + count);
        sort(chosen.begin(), chosen.end(), [](auto& x, auto& y) { return x.second > y.second; });
        for (auto& [_, index] : chosen) routes[car].erase(routes[car].begin() + index);
    }
    return true;
}

bool destroy(DayProblem& problem, map<int, vector<int>>& routes, map<int, int>& variants, Rng& rng, int op) {
    if (op == REVERSE || op == SWAP || op == WORST) return extended_move(problem, routes, variants, rng, op);
    if (op == VARIANT_SEGMENT) variants[rng.choice(problem.patrols)] = rng.randrange(3);
    vector<pair<int, int>> stops;
    for (auto& [c, r] : routes)
        for (int i = 0; i < (int)r.size(); ++i) stops.push_back({c, i});
    if (!stops.empty()) {
        if (op == VARIANT_SEGMENT || op == SEGMENT) {
            int car = rng.choice(problem.patrols);
            vector<int>& route = routes[car];
            if (!route.empty()) {
                int i = rng.randrange((int)route.size());
                int j = rng.randint(i + 1, min((int)route.size(), i + problem.params.segment));
                route.erase(route.begin() + i, route.begin() + j);
            }
        } else {
            int count = rng.randint(1, min(problem.params.max_remove, (int)stops.size()));
            auto chosen = rng.sample(stops, count);
            sort(chosen.begin(), chosen.end(), [](auto& x, auto& y) { return x.second > y.second; });
            for (auto& [c, i] : chosen) routes[c].erase(routes[c].begin() + i);
        }
    }
    return true;
}

atomic<long long> improve_rounds{0};  // thống kê: tổng số vòng phá và dựng lại (in ra stderr)

// Phá lời giải `base` bằng toán tử op rồi chèn lại có nhiễu; nullopt nếu không áp được hoặc không khả thi.
optional<Solution> perturb(DayProblem& problem, const Solution& base, int op, double deadline, Rng& rng) {
    auto routes = base.routes;
    auto variants = base.variants;
    if (!destroy(problem, routes, variants, rng, op)) return nullopt;
    bool extended = op == REVERSE || op == SWAP || op == WORST;
    map<int, CarRun> runs;
    for (int c : problem.patrols) {
        CarRun run = problem.run(c, routes[c], variants[c]);
        if (!run.feasible) {
            if (extended) return nullopt;
            routes[c].clear();
            run = problem.run(c, {}, variants[c]);
            if (!run.feasible) return nullopt;
        }
        runs[c] = move(run);
    }
    insert_greedy(problem, routes, variants, runs, &rng, problem.params.noise, deadline, false);
    Score score = problem.score(runs);
    return Solution{score, move(routes), move(variants), move(runs)};
}

// Quần thể (PSO rời rạc): mỗi hạt kéo tuyến một xe từ lời giải tốt nhất của nó hoặc của cả quần thể
// ("vận tốc"), rồi phá và dựng lại ("nhiễu"); hạt luôn di chuyển, giữ lời giải tốt nhất.
Solution improve_population(DayProblem& problem, Solution solution, double deadline, Rng& rng, Worker& worker) {
    worker.emit(problem, solution.runs);
    const int size = 6;
    vector<Solution> particles(size, solution), personal(size, solution);
    const vector<double>& weights = problem.params.weights;
    for (int step = 0; seconds_now() < deadline && !problem.patrols.empty(); ++step) {
        int j = step % size;
        Solution moved = particles[j];
        double r = rng.random();
        const Solution* guide = r < 0.4 ? &solution : (r < 0.7 ? &personal[j] : nullptr);
        if (guide) {
            int car = rng.choice(problem.patrols);
            moved.routes[car] = guide->routes.at(car);
            moved.variants[car] = guide->variants.at(car);
        }
        auto next = perturb(problem, moved, rng.choices(weights), deadline, rng);
        if (!next) continue;
        ++improve_rounds;
        particles[j] = *next;
        if (next->score >= personal[j].score) personal[j] = *next;
        if (next->score >= solution.score) solution = *next;
        worker.emit(problem, solution.runs);
    }
    return solution;
}

Solution improve(DayProblem& problem, Solution solution, double deadline, Rng& rng, Worker& worker) {
    if (problem.params.search == 1) return improve_population(problem, solution, deadline, rng, worker);
    worker.emit(problem, solution.runs);
    vector<double> weights = problem.params.weights;
    vector<double> gained(weights.size(), 0.0);
    vector<int> used(weights.size(), 0);
    double rate = problem.params.alns, start = seconds_now(), t0 = worker.temperature;
    int rounds = 0;
    Solution current = solution;  // lời giải đang xét; với nhiệt độ > 0 có thể kém lời giải tốt nhất
    while (seconds_now() < deadline && !problem.patrols.empty()) {
        int op = rng.choices(weights);
        auto next = perturb(problem, current, op, deadline, rng);
        if (!next) continue;
        ++used[op];
        bool accept = next->score >= current.score;
        if (accept) gained[op] += next->score > current.score ? 5.0 : 1.0;
        if (!accept && t0 > 0 && next->score[0] == current.score[0] && next->score[1] == current.score[1]) {
            // Không bao giờ nhận lời giải mất loại; nửa suất phạt thêm cho phần nhiên liệu/step kém hơn.
            double temp = t0 * max(0.0, 1.0 - (seconds_now() - start) / max(1e-9, deadline - start));
            double drop = (double)(current.score[2] - next->score[2]) + 0.5;
            accept = temp > 0 && rng.random() < exp(-drop / temp);
        }
        if (accept) {
            current = move(*next);
            if (current.score > solution.score) solution = current;
        }
        worker.emit(problem, solution.runs);
        ++rounds;
        ++improve_rounds;
        if (rate > 0 && rounds % 50 == 0) {
            for (size_t i = 0; i < weights.size(); ++i) {
                if (used[i]) weights[i] = max(0.02, (1 - rate) * weights[i] + rate * gained[i] / used[i]);
                gained[i] = 0.0;
                used[i] = 0;
            }
        }
    }
    return solution;
}

vector<vector<int>> commands(DayProblem& problem, const map<int, CarRun>& runs, const Option& supply_routes) {
    Legs& legs = problem.legs;
    int steps = problem.steps;
    vector<vector<int>> actions(problem.state.agents.size());
    for (auto& [car, run] : runs) {
        int used = 0;
        for (const Segment& seg : run.segments) {
            if (seg.wait) {
                actions[car].push_back(-seg.a);
                used += seg.a;
            } else {
                auto dirs = legs.directions(seg.a, seg.b, seg.variant);
                actions[car].insert(actions[car].end(), dirs.begin(), dirs.end());
                used += legs.leg(seg.a, seg.b, seg.variant).steps;
            }
        }
        if (used < steps) actions[car].push_back(-(steps - used));
    }
    for (auto& [car, hub] : supply_routes) {
        int pos = problem.state.agents[car].pos;
        if (hub.pos != pos) {
            auto dirs = legs.directions(pos, hub.pos, 0);
            actions[car].insert(actions[car].end(), dirs.begin(), dirs.end());
        }
        if (hub.escort >= 0) {
            // Hộ tống: lặp lại đúng các lệnh của xe tuần tra sau lượt chờ đầu.
            const auto& follow = actions[hub.escort];
            actions[car].insert(actions[car].end(), follow.begin() + (hub.arrival ? 1 : 0), follow.end());
        } else if (hub.arrival < steps) {
            actions[car].push_back(-(steps - hub.arrival));
        }
    }
    return actions;
}

// ---------------------------------------------------------------- điểm hẹn, ô neo, hộ tống

vector<pair<int, int>> hub_candidates(const Board& board, const State& state, int car, Legs& legs, int steps,
                                      int count = 4) {
    vector<int> spots, patrols;
    for (auto& s : board.spots) spots.push_back(s.pos);
    for (auto& a : state.agents)
        if (a.kind == 0) patrols.push_back(a.pos);
    int pos = state.agents[car].pos;
    auto sum_to = [&](int p, const vector<int>& targets) {
        int total = 0;
        for (int q : targets) total += board.distance(p, q);
        return total;
    };
    vector<int> central = spots, near = spots;
    stable_sort(central.begin(), central.end(), [&](int a, int b) { return sum_to(a, spots) < sum_to(b, spots); });
    stable_sort(near.begin(), near.end(), [&](int a, int b) { return sum_to(a, patrols) < sum_to(b, patrols); });
    vector<int> options = {pos};
    auto add = [&](int p) {
        if (find(options.begin(), options.end(), p) == options.end()) options.push_back(p);
    };
    // Xe tuần tra gần cạn nhiên liệu chỉ được cứu khi xe tiếp tế tự chạy tới chỗ nó.
    for (auto& a : state.agents)
        if (a.kind == 0 && a.fuel < board.fuel_limit / 4) add(a.pos);
    for (int i = 0; i < count && i < (int)central.size(); ++i) add(central[i]);
    for (int i = 0; i < count && i < (int)near.size(); ++i) add(near[i]);
    vector<pair<int, int>> result;
    for (int hub : options) {
        int arrival = hub != pos ? legs.leg(pos, hub, 0).steps : 0;
        if (arrival <= steps) result.push_back({hub, arrival});
    }
    return result;
}

int fuel_free_types(const Board& board, const State& state, int steps, Legs& legs, const Params& params) {
    State relaxed = state;
    for (auto& a : relaxed.agents) a.fuel = a.kind == 0 ? 1000000000 : 0;
    DayProblem problem(board, relaxed, steps, {}, vector<int>(relaxed.agents.size(), 1000000000), 0, legs, params);
    auto result = construct(problem, 0, NO_DEADLINE, true);
    return result ? (int)result->score[1] : 0;
}

map<int, int> spread_anchors(DayProblem& problem, const map<int, vector<pair<int, CarRun>>>& reach, double radius) {
    const Board& board = problem.board;
    Bits covered;
    map<int, int> anchors;
    map<int, Bits> near;
    vector<int> order = problem.patrols;
    stable_sort(order.begin(), order.end(), [&](int a, int b) { return reach.at(a).size() < reach.at(b).size(); });
    for (int car : order) {
        bool found = false;
        pair<int, int> best_gain;
        int best_spot = -1;
        for (auto& [spot, run] : reach.at(car)) {
            if (!near.count(spot)) {
                Bits brands;
                for (auto& s : board.spots)
                    if (problem.legs.leg(spot, s.pos, 0).steps <= radius) brands.set(s.brand);
                near[spot] = brands;
            }
            pair<int, int> gain = {(int)(near[spot] & ~covered).count(), -run.steps};
            if (!found || gain > best_gain) {
                found = true;
                best_gain = gain;
                best_spot = spot;
            }
        }
        anchors[car] = best_spot;
        covered |= near[best_spot];
    }
    return anchors;
}

// Ô dừng cuối ngày của từng xe để ngày mai phủ đủ loại, đi ít step nhất; nullopt nếu có xe không tới được ô nào.
optional<pair<map<int, int>, int>> find_anchors(DayProblem& problem, const map<int, CarRun>& runs, double deadline,
                                                 Rng& rng, const function<void()>& tick) {
    vector<int> cells;
    for (auto& s : problem.board.spots) cells.push_back(s.pos);
    for (auto& [hub, _] : problem.hubs)
        if (problem.board.spot_index[hub] < 0 && find(cells.begin(), cells.end(), hub) == cells.end())
            cells.push_back(hub);
    map<int, vector<pair<int, CarRun>>> reach;
    map<int, map<int, int>> where;  // xe -> ô -> vị trí trong reach
    for (int car : problem.patrols) {
        for (int spot : cells) {
            CarRun run = problem.run(car, {spot}, 0);
            if (run.feasible) {
                where[car][spot] = (int)reach[car].size();
                reach[car].push_back({spot, move(run)});
            }
        }
        if (reach[car].empty()) return nullopt;
    }
    auto random_cell = [&](int car) { return reach[car][rng.randrange((int)reach[car].size())].first; };
    auto key = [&](const map<int, int>& anchors) {
        vector<int> ends;
        int used = 0;
        for (int c : problem.patrols) {
            const CarRun& run = reach[c][where[c][anchors.at(c)]].second;
            ends.push_back(anchors.at(c));
            ends.push_back(run.fuel);
            used += run.steps;
        }
        return pair<int, int>{problem.coverage_from(ends), -used};
    };
    vector<map<int, int>> starts(1);
    for (int c : problem.patrols) {
        int end = runs.at(c).end;
        starts[0][c] = where[c].count(end) ? end : random_cell(c);
    }
    for (double share : {0.35, 0.5, 0.7}) {
        if (seconds_now() >= deadline) break;
        starts.push_back(spread_anchors(problem, reach, share * (problem.next_steps ? problem.next_steps : problem.steps)));
    }
    vector<pair<pair<int, int>, map<int, int>>> scored;
    for (auto& a : starts) scored.push_back({key(a), a});
    stable_sort(scored.begin(), scored.end(), [](auto& x, auto& y) { return x.first > y.first; });
    auto best = scored[0].first;
    auto best_anchors = scored[0].second;
    auto current = best_anchors;
    auto current_key = best;
    int stale = 0;
    while (seconds_now() < deadline && best.first < problem.board.brand_count) {
        tick();
        if (stale >= 40) {
            // Kẹt: quay về một bộ khởi đầu khác rồi xáo trộn một xe.
            current = scored[rng.randrange((int)scored.size())].second;
            int car = rng.choice(problem.patrols);
            current[car] = random_cell(car);
            current_key = key(current);
            stale = 0;
        }
        auto trial = current;
        int moves = rng.randint(1, min(2, (int)problem.patrols.size()));
        for (int car : rng.sample(problem.patrols, moves)) trial[car] = random_cell(car);
        auto score = key(trial);
        if (score >= current_key) {
            stale = score > current_key ? 0 : stale + 1;
            current = trial;
            current_key = score;
            if (score > best) {
                best = score;
                best_anchors = trial;
            }
        } else {
            ++stale;
        }
    }
    return pair<map<int, int>, int>{best_anchors, best.first};
}

// ---------------------------------------------------------------- lập tuyến một ngày

vector<vector<int>> plan_tour(const Board& board, const State& state, int steps, double seconds, double alpha,
                              int seed, const Params& params, Worker& worker) {
    double started = seconds_now(), deadline = started + max(0.0, seconds);
    double first_deadline = started + max(seconds, 0.5);
    Rng rng((uint64_t)(seed + 7919LL * state.day));
    Legs legs(board, state.traffic);
    vector<int> supplies;
    for (size_t i = 0; i < state.agents.size(); ++i)
        if (state.agents[i].kind == 1) supplies.push_back((int)i);
    vector<int> allowance = allowances(board, state, steps, alpha);
    int following = state.day + 1 < (int)board.day_steps.size() ? board.day_steps[state.day + 1] : 0;
    int brand_count = board.brand_count;
    vector<int> patrols;
    for (size_t i = 0; i < state.agents.size(); ++i)
        if (state.agents[i].kind == 0) patrols.push_back((int)i);

    vector<Option> options = {{}};
    for (int car : supplies) {
        auto cands = hub_candidates(board, state, car, legs, steps);
        vector<Option> next;
        for (auto& o : options)
            for (auto [hub, arrival] : cands) {
                if (next.size() >= 12) break;
                Option extended = o;
                extended.push_back({car, Hub{hub, arrival}});
                next.push_back(extended);
            }
        options = next;
    }
    // Đội không có tiếp tế phải tiết kiệm nhiên liệu nên thử cả ba kiểu đường khi dựng.
    vector<int> variants = supplies.empty() ? vector<int>{0, 1, 2} : vector<int>{0};
    auto make = [&](const Option& option) {
        vector<pair<int, int>> hubs;
        for (auto& [car, hub] : option)
            if (hub.escort < 0) hubs.push_back({hub.pos, hub.arrival});
        auto problem = make_shared<DayProblem>(board, state, steps, hubs, allowance, following, legs, params);
        problem->option = option;
        for (auto& [car, hub] : option)
            if (hub.escort >= 0) problem->escort[hub.escort] = {car, hub.arrival};
        return problem;
    };

    optional<Candidate> best;
    vector<Candidate> candidates;
    for (auto& option : options) {
        auto problem = make(option);
        bool added = false;
        for (int variant : variants) {
            if (best && seconds_now() >= started + seconds * 0.4) break;
            auto result = construct(*problem, variant, best ? deadline : first_deadline);
            if (!result) continue;
            if (!added) {
                candidates.push_back({*result, option, problem});
                added = true;
            }
            if (!best || result->score > best->solution.score) best = Candidate{*result, option, problem};
        }
    }
    if (!best) return {};
    worker.emit(*best->problem, best->solution.runs);
    if (best->solution.score[1] < brand_count && !patrols.empty()) {
        // Ngày ngắn: phủ đủ loại là bài toán chặt, chèn tham lam một lượt dễ thiếu một loại.
        double cover_until = seconds_now() + max(0.0, deadline - seconds_now()) * 0.4;
        best = cover_types(candidates, cover_until, rng, supplies.empty() ? vector<int>{0, 2} : variants, *best,
                           worker);
    }
    // Một bình đầy đi tối đa 2 step mỗi nhiên liệu, nên 2 × bình < số step nghĩa là không đủ cả ngày.
    if (params.escort && !supplies.empty() && 2 * board.fuel_limit < steps && best->solution.score[1] < brand_count &&
        !patrols.empty() && fuel_free_types(board, state, steps, legs, params) > best->solution.score[1]) {
        double escort_until = seconds_now() + max(0.0, deadline - seconds_now()) * 0.3;
        vector<pair<int, Option>> escorts;
        for (int car : supplies) {
            int pos = state.agents[car].pos;
            for (int patrol : patrols) {
                int target = state.agents[patrol].pos;
                int arrival = pos != target ? legs.leg(pos, target, 0).steps : 0;
                if (arrival < steps) {
                    Option o;
                    int total = 0;
                    for (int c : supplies) {
                        if (c == car) {
                            o.push_back({c, Hub{target, arrival, patrol}});
                            total += arrival;
                        } else {
                            o.push_back({c, Hub{state.agents[c].pos, 0}});
                        }
                    }
                    escorts.push_back({total, o});
                }
            }
        }
        stable_sort(escorts.begin(), escorts.end(), [](auto& x, auto& y) { return x.first < y.first; });
        vector<Candidate> tried;
        for (auto& [_, option] : escorts) {
            if (seconds_now() >= escort_until) break;
            auto problem = make(option);
            auto result = construct(*problem, 0, escort_until);
            if (result) tried.push_back({*result, option, problem});
        }
        if (!tried.empty()) {
            Candidate rescue = *max_element(tried.begin(), tried.end(), [](auto& x, auto& y) {
                return x.solution.score < y.solution.score;
            });
            if (rescue.solution.score[1] < brand_count)
                rescue = cover_types(tried, escort_until, rng, {0}, rescue, worker);
            if (make_pair(rescue.solution.score[0], rescue.solution.score[1]) >
                make_pair(best->solution.score[0], best->solution.score[1]))
                best = rescue;
        }
    }
    Solution solution = best->solution;
    Option option = best->option;
    auto problem = best->problem;
    problem->alpha = alpha;
    problem->option = option;
    auto remaining = [&]() { return max(0.0, deadline - seconds_now()); };
    if (following && !problem->patrols.empty()) {
        // Ngày mai thiếu loại từ vị trí cuối ngày thì tìm ô neo rồi lập lại tuyến dừng ở ô neo.
        solution = improve(*problem, solution, seconds_now() + remaining() * 0.3, rng, worker);
        int covered = problem->coverage(solution.runs);
        if (covered < brand_count) {
            double share = following < steps ? 0.4 : 0.25;
            auto found = find_anchors(*problem, solution.runs, seconds_now() + remaining() * share, rng,
                                      [&]() { worker.emit(*problem, solution.runs); });
            if (found && found->second > covered) {
                auto anchored = make_shared<DayProblem>(board, state, steps, problem->hubs, allowance, following, legs,
                                                        params);
                anchored->coverages = problem->coverages;
                anchored->option = option;
                anchored->escort = problem->escort;
                anchored->anchors = found->first;
                anchored->alpha = alpha;
                optional<Solution> trial;
                for (int variant : variants) {
                    auto result = construct(*anchored, variant, deadline);
                    if (result && (!trial || result->score > trial->score)) trial = result;
                }
                if (trial) {
                    *trial = improve(*anchored, *trial, seconds_now() + remaining() * 0.5, rng, worker);
                    auto old_key = make_tuple(solution.score[0], solution.score[1], (int64_t)covered);
                    auto new_key = make_tuple(trial->score[0], trial->score[1], (int64_t)anchored->coverage(trial->runs));
                    if (new_key > old_key) {
                        problem = anchored;
                        solution = *trial;
                    }
                }
            }
        }
    }
    solution = improve(*problem, solution, deadline, rng, worker);
    return commands(*problem, solution.runs, option);
}

// ---------------------------------------------------------------- đọc đầu vào, chạy nhiều luồng

bool simulate_day(const Board& board, State& state, const vector<vector<int>>& actions, int steps);

// Khóa so kế hoạch như tour.plan_key: (hợp lệ, U, loại hôm nay, loại ngày mai ước lượng, suất hôm nay).
struct PlanKey {
    int valid = 0, u = 0, d = 0, cov = -1, q = 0;
};

// Chấm các kế hoạch bằng simulator C++; với objective 1 (lookahead) ước lượng thêm số loại ngày mai
// cho nhóm có (U, loại hôm nay) cao nhất, dựng chỉ nhắm loại từ trạng thái cuối ngày như next_coverage.
vector<PlanKey> plan_keys(const Board& board, const State& state, int steps, const vector<vector<vector<int>>>& plans,
                          int objective, const Params& params) {
    vector<PlanKey> keys(plans.size());
    vector<State> afters(plans.size());
    for (size_t i = 0; i < plans.size(); ++i) {
        afters[i] = state;
        if (!simulate_day(board, afters[i], plans[i], steps)) continue;
        keys[i] = {1, (int)afters[i].brands.count(), afters[i].daily_sum - state.daily_sum, -1,
                   afters[i].portions - state.portions};
    }
    if (objective != 1) return keys;
    pair<int, int> top{-1, -1};
    for (auto& k : keys)
        if (k.valid) top = max(top, {k.u, k.d});
    for (size_t i = 0; i < plans.size(); ++i) {
        if (!keys[i].valid || make_pair(keys[i].u, keys[i].d) != top) continue;
        const State& after = afters[i];
        if (after.day >= (int)board.day_steps.size()) {
            keys[i].cov = 0;
            continue;
        }
        vector<pair<int, int>> hubs;
        for (auto& a : after.agents)
            if (a.kind == 1) hubs.push_back({a.pos, 0});
        Legs legs(board, after.traffic);
        keys[i].cov = types_coverage(board, after, board.day_steps[after.day], hubs, 1.0, legs, params);
    }
    return keys;
}

void print_plan(const string& tag, int seed, const vector<vector<int>>& actions, const PlanKey& key) {
    string out = "PLAN " + tag + " " + to_string(seed) + " " + to_string(actions.size()) + " " +
                 to_string(key.valid) + " " + to_string(key.u) + " " + to_string(key.d) + " " + to_string(key.cov) +
                 " " + to_string(key.q) + "\n";
    for (auto& car : actions) {
        out += to_string(car.size());
        for (int c : car) out += " " + to_string(c);
        out += "\n";
    }
    fwrite(out.data(), 1, out.size(), stdout);
    fflush(stdout);
}

bool read_board(Board& board, map<int, int>& brand_ids) {
    cin >> board.width >> board.height;
    board.terrain.resize(board.size());
    for (int& t : board.terrain) cin >> t;
    cin >> board.fuel_limit;
    int ndays;
    cin >> ndays;
    board.day_steps.resize(ndays);
    for (int& s : board.day_steps) cin >> s;
    int nspots;
    cin >> nspots;
    if (nspots > MAXS) {
        fprintf(stderr, "quá nhiều điểm udon\n");
        return false;
    }
    board.spot_index.assign(board.size(), -1);
    for (int i = 0; i < nspots; ++i) {
        Spot s;
        cin >> s.pos >> s.brand >> s.stocks;
        if (!brand_ids.count(s.brand)) brand_ids[s.brand] = (int)brand_ids.size();
        s.brand = brand_ids[s.brand];
        board.spot_index[s.pos] = i;
        board.spots.push_back(s);
    }
    board.brand_count = (int)brand_ids.size();
    return true;
}

Params read_params() {
    Params params;
    int escort;
    cin >> params.positions >> params.noise >> params.max_remove >> params.segment >> params.alns >> escort;
    params.escort = escort != 0;
    for (double& w : params.weights) cin >> w;
    int ktemp;
    int last_day_free;
    cin >> params.temperature >> ktemp >> params.search >> last_day_free;
    params.last_day_free = last_day_free != 0;
    params.ktemp = ktemp != 0;
    return params;
}

int select_main();
int sim_main();

int main() {
    ios::sync_with_stdio(false);
    string magic;
    int version;
    cin >> magic >> version;
    if (magic == "HEXSELECT" && version == 1) return select_main();
    if (magic == "HEXSIM" && version == 1) return sim_main();
    if (magic != "HEXPLAN" || version != 1) {
        fprintf(stderr, "sai định dạng đầu vào\n");
        return 2;
    }
    Board board;
    map<int, int> brand_ids;
    if (!read_board(board, brand_ids)) return 2;
    State state;
    int nagents;
    cin >> nagents;
    state.agents.resize(nagents);
    for (auto& a : state.agents) cin >> a.kind >> a.pos >> a.fuel;
    int ntraffic;
    cin >> state.day >> ntraffic;
    for (int i = 0; i < ntraffic; ++i) {
        int pos, status;
        cin >> pos >> status;
        state.traffic[pos] = status;
    }
    int nbrands;
    cin >> nbrands;
    for (int i = 0; i < nbrands; ++i) {
        int brand;
        cin >> brand;
        if (brand_ids.count(brand)) state.brands.set(brand_ids[brand]);
    }
    int steps, seed, workers, ncheck;
    double alpha, until;
    cin >> steps >> alpha >> seed >> workers >> until >> ncheck;
    vector<double> checks(ncheck);
    for (double& c : checks) cin >> c;
    Params params = read_params();
    // Cách chọn (0 score, 1 lookahead) và lịch sử ô đường 2 ngày để simulator tính mặt đường ngày mai.
    int objective, nhistory;
    cin >> objective >> nhistory;
    for (int h = 0; h < nhistory; ++h) {
        int count;
        cin >> count;
        unordered_map<int, int> history;
        for (int i = 0; i < count; ++i) {
            int pos, value;
            cin >> pos >> value;
            history[pos] = value;
        }
        state.road_history.push_back(history);
    }
    cin >> board.busy_threshold >> board.jammed_threshold;
    if (!cin) {
        fprintf(stderr, "thiếu dữ liệu đầu vào\n");
        return 2;
    }
    auto emit_all = [&](const string& tag, const vector<int>& seeds, const vector<vector<vector<int>>>& plans) {
        auto keys = plan_keys(board, state, steps, plans, objective, params);
        for (size_t i = 0; i < plans.size(); ++i) print_plan(tag, seeds[i], plans[i], keys[i]);
    };

    Checkpoint checkpoint;
    checkpoint.answered.assign(workers, -1);
    checkpoint.snapshots.assign(workers, {});
    vector<vector<vector<int>>> finals(workers);
    vector<atomic<bool>> done(workers);
    for (auto& d : done) d = false;
    vector<thread> threads;
    // Ngân sách tính theo đồng hồ đơn điệu từ lúc bắt đầu, quy đổi từ mốc epoch.
    double budget = until - now_epoch();
    for (int w = 0; w < workers; ++w) {
        threads.emplace_back([&, w]() {
            Worker worker{w, &checkpoint};
            worker.temperature = params.ktemp ? params.temperature * w / max(1, workers - 1) : params.temperature;
            try {
                finals[w] = plan_tour(board, state, steps, budget, alpha, seed + w, params, worker);
            } catch (const exception& error) {
                fprintf(stderr, "luồng %d lỗi: %s\n", w, error.what());
            }
            done[w] = true;
        });
    }
    for (size_t k = 0; k < checks.size(); ++k) {
        double wait = checks[k] - now_epoch();
        if (wait > 0) this_thread::sleep_for(chrono::duration<double>(wait));
        checkpoint.requested = (int)k;
        // Chờ các luồng còn chạy trả lời mốc này, tối đa 0,2 giây.
        double limit = now_epoch() + 0.2;
        while (now_epoch() < limit) {
            bool all = true;
            {
                lock_guard<mutex> guard(checkpoint.lock);
                for (int w = 0; w < workers; ++w)
                    if (!done[w] && checkpoint.answered[w] < (int)k) all = false;
            }
            if (all) break;
            this_thread::sleep_for(chrono::milliseconds(5));
        }
        vector<int> seeds;
        vector<vector<vector<int>>> plans;
        {
            lock_guard<mutex> guard(checkpoint.lock);
            for (int w = 0; w < workers; ++w) {
                if (done[w] && !finals[w].empty()) plans.push_back(finals[w]);
                else if (checkpoint.answered[w] == (int)k) plans.push_back(checkpoint.snapshots[w]);
                else continue;
                seeds.push_back(seed + w);
            }
        }
        emit_all(to_string(k), seeds, plans);
    }
    // Kế hoạch cuối: chờ tới hạn cộng 0,25 giây; luồng chưa xong bị bỏ.
    double limit = until + 0.25;
    while (now_epoch() < limit) {
        bool all = true;
        for (int w = 0; w < workers; ++w) all = all && done[w];
        if (all) break;
        this_thread::sleep_for(chrono::milliseconds(5));
    }
    vector<int> final_seeds;
    vector<vector<vector<int>>> final_plans;
    for (int w = 0; w < workers; ++w)
        if (done[w] && !finals[w].empty()) {
            final_seeds.push_back(seed + w);
            final_plans.push_back(finals[w]);
        }
    emit_all("F", final_seeds, final_plans);
    fprintf(stderr, "STAT rounds %lld\n", improve_rounds.load());
    fputs("DONE\n", stdout);
    fflush(stdout);
    bool all = true;
    for (int w = 0; w < workers; ++w) all = all && done[w];
    if (all) {
        for (auto& t : threads) t.join();
        return 0;
    }
    _Exit(0);  // còn luồng chạy quá hạn: thoát ngay, không chờ
}

// ---------------------------------------------------------------- chọn đội hình: mô phỏng cả trận

// Một ngày của một đội, đúng như src/hexudon/simulator.py (kiểm tra lệnh, đi từng step, đổ xăng
// khi cùng ô xe tiếp tế, đếm ô đường, thu hàng, giao thông hôm sau từ 2 ngày gần nhất). false: lỗi.
bool simulate_day(const Board& board, State& state, const vector<vector<int>>& actions, int steps) {
    int n = (int)state.agents.size();
    if ((int)actions.size() != n) return false;
    auto cost = [&](int pos) {
        int t = board.terrain[pos];
        if (t == 0) return pair<int, int>{2, 1};
        if (t == 2) return pair<int, int>{3, 2};
        auto it = state.traffic.find(pos);
        static const int road[3] = {1, 2, 4};
        return pair<int, int>{road[it == state.traffic.end() ? 0 : it->second], 2};
    };
    for (int car = 0; car < n; ++car) {
        int pos = state.agents[car].pos, total = 0;
        for (int command : actions[car]) {
            if (command > 5) return false;
            if (command < 0) {
                total -= command;
            } else {
                int target = board.neighbor(pos, command);
                if (target < 0) return false;
                total += cost(pos).first;
                pos = target;
            }
            if (total > steps) return false;
        }
        if (total != steps) return false;
    }
    vector<int> stocks(board.spots.size()), pointer(n, 0), remaining(n, 0), destination(n, -1), fuel_cost(n, 0);
    for (size_t i = 0; i < board.spots.size(); ++i) stocks[i] = board.spots[i].stocks;
    vector<Bits> visited(n);
    vector<bool> arrived(n, false);
    Bits today;
    unordered_map<int, int> roads;
    for (int tick = 0; tick < steps; ++tick) {
        for (int car = 0; car < n; ++car) {
            Agent& agent = state.agents[car];
            if (remaining[car] == 0) {
                int command = actions[car][pointer[car]++];
                if (command < 0) {
                    remaining[car] = -command;
                    destination[car] = -1;
                    fuel_cost[car] = 0;
                } else {
                    auto [duration, fuel] = cost(agent.pos);
                    if (agent.kind == 0 && agent.fuel < fuel) return false;
                    remaining[car] = duration;
                    destination[car] = board.neighbor(agent.pos, command);
                    fuel_cost[car] = agent.kind == 0 ? fuel : 0;
                }
            }
        }
        for (int car = 0; car < n; ++car) {
            Agent& agent = state.agents[car];
            if (--remaining[car] == 0 && destination[car] >= 0) {
                agent.pos = destination[car];
                agent.fuel -= fuel_cost[car];
                arrived[car] = true;
            }
        }
        vector<int> supply;
        for (auto& a : state.agents)
            if (a.kind == 1) supply.push_back(a.pos);
        for (int car = 0; car < n; ++car) {
            Agent& agent = state.agents[car];
            int pos = agent.pos;
            if (agent.kind == 0 && find(supply.begin(), supply.end(), pos) != supply.end()) agent.fuel = board.fuel_limit;
            if (board.terrain[pos] == 1 && (destination[car] < 0 || arrived[car])) ++roads[pos];
            int index = board.spot_index[pos];
            if (agent.kind == 0 && index >= 0 && !visited[car][index]) {
                visited[car].set(index);
                if (stocks[index] > 0) {
                    --stocks[index];
                    today.set(board.spots[index].brand);
                    state.brands.set(board.spots[index].brand);
                    ++state.portions;
                }
            }
        }
    }
    ++state.day;
    state.daily_sum += (int)today.count();
    state.road_history.push_back(roads);
    if (state.road_history.size() > 2) state.road_history.erase(state.road_history.begin());
    unordered_map<int, int> total;
    for (auto& history : state.road_history)
        for (auto [pos, count] : history) total[pos] += count;
    state.traffic.clear();
    for (auto [pos, count] : total) {
        int status = count >= board.jammed_threshold ? 2 : count >= board.busy_threshold ? 1 : 0;
        if (status) state.traffic[pos] = status;
    }
    return true;
}

struct Trial {
    int candidate, seed;
    array<int, 3> score{};
    bool complete = false;
};

// Một trận trọn vẹn của một đội hình với planner tour (day_seconds mỗi ngày, cùng seed cho mọi đội hình).
Trial evaluate(const Board& board, const vector<int>& starts, const vector<int>& kinds, int candidate, int seed,
               double day_seconds, const Params& params, double until) {
    Trial trial{candidate, seed};
    State state;
    for (size_t i = 0; i < kinds.size(); ++i)
        state.agents.push_back({kinds[i], starts[i], kinds[i] == 0 ? board.fuel_limit : 0});
    for (int steps : board.day_steps) {
        if (now_epoch() > until) return trial;
        Worker worker{0, nullptr};
        auto actions = plan_tour(board, state, steps, day_seconds, 1.0, seed, params, worker);
        if (actions.empty()) actions.assign(state.agents.size(), {-steps});
        if (!simulate_day(board, state, actions, steps)) return trial;
    }
    trial.score = {(int)state.brands.count(), state.daily_sum, state.portions};
    trial.complete = true;
    return trial;
}

// Đầu vào sau "HEXSELECT 1": bản đồ như HEXPLAN, rồi busy jammed, nagents start*, ncand kinds*,
// threads until day_seconds, rồi dòng tham số như HEXPLAN. Loại dần: vòng đầu mỗi đội hình một trận,
// sau mỗi vòng giữ nửa tốt nhất theo (U thấp nhất, D thấp nhất, Q trung bình); mọi đội hình trong
// một vòng dùng cùng seed để so cặp. In "RESULT ứng_viên seed U D Q đủ_trận", "BEST ứng_viên", "DONE".
int select_main() {
    Board board;
    map<int, int> brand_ids;
    if (!read_board(board, brand_ids)) return 2;
    int nagents, ncand, threads;
    cin >> board.busy_threshold >> board.jammed_threshold >> nagents;
    vector<int> starts(nagents);
    for (int& p : starts) cin >> p;
    cin >> ncand;
    vector<vector<int>> candidates(ncand, vector<int>(nagents));
    for (auto& kinds : candidates)
        for (int& k : kinds) cin >> k;
    double until, day_seconds;
    cin >> threads >> until >> day_seconds;
    Params params = read_params();
    if (!cin || ncand == 0) {
        fprintf(stderr, "thiếu dữ liệu đầu vào\n");
        return 2;
    }
    vector<vector<Trial>> trials(ncand);
    auto key = [&](int c) {
        // (đủ trận, U thấp nhất, D thấp nhất, Q trung bình): đội hình chưa có trận đủ đứng cuối.
        double u = 1e9, d = 1e9, q = 0;
        int count = 0;
        for (auto& t : trials[c])
            if (t.complete) {
                u = min(u, (double)t.score[0]);
                d = min(d, (double)t.score[1]);
                q += t.score[2];
                ++count;
            }
        return count ? make_tuple(1, u, d, q / count) : make_tuple(0, 0.0, 0.0, 0.0);
    };
    vector<int> alive(ncand);
    iota(alive.begin(), alive.end(), 0);
    mutex lock;
    for (int round = 0; now_epoch() < until - 0.05; ++round) {
        int per = round == 0 ? 1 : max(1, threads / (int)alive.size());
        vector<pair<int, int>> tasks;
        for (int s = 0; s < per; ++s)
            for (int c : alive) tasks.push_back({c, round * 1000 + s});
        atomic<size_t> next{0};
        vector<thread> pool;
        for (int w = 0; w < threads; ++w) {
            pool.emplace_back([&]() {
                for (size_t i = next++; i < tasks.size() && now_epoch() < until; i = next++) {
                    Trial t = evaluate(board, starts, candidates[tasks[i].first], tasks[i].first, tasks[i].second,
                                       day_seconds, params, until);
                    lock_guard<mutex> guard(lock);
                    trials[t.candidate].push_back(t);
                    printf("RESULT %d %d %d %d %d %d\n", t.candidate, t.seed, t.score[0], t.score[1], t.score[2],
                           (int)t.complete);
                    fflush(stdout);
                }
            });
        }
        for (auto& t : pool) t.join();
        stable_sort(alive.begin(), alive.end(), [&](int a, int b) { return key(a) > key(b); });
        if (alive.size() > 2) alive.resize(max<size_t>(2, (alive.size() + 1) / 2));
    }
    printf("BEST %d\nDONE\n", alive[0]);
    fflush(stdout);
    return 0;
}

// Kiểm tra simulator: "HEXSIM 1", bản đồ như HEXPLAN, busy jammed, trạng thái (nagents (kind pos fuel)*,
// day ntraffic (pos status)* nbrands brand* daily_sum portions nhistory (n (pos count)*)*), steps, lệnh
// từng xe (n lệnh*). In "OK pos fuel ... | U D Q | traffic" hoặc "INVALID".
int sim_main() {
    Board board;
    map<int, int> brand_ids;
    if (!read_board(board, brand_ids)) return 2;
    State state;
    int nagents, ntraffic, nbrands, nhistory, steps;
    cin >> board.busy_threshold >> board.jammed_threshold >> nagents;
    state.agents.resize(nagents);
    for (auto& a : state.agents) cin >> a.kind >> a.pos >> a.fuel;
    cin >> state.day >> ntraffic;
    for (int i = 0; i < ntraffic; ++i) {
        int pos, status;
        cin >> pos >> status;
        state.traffic[pos] = status;
    }
    cin >> nbrands;
    for (int i = 0; i < nbrands; ++i) {
        int brand;
        cin >> brand;
        state.brands.set(brand_ids[brand]);
    }
    cin >> state.daily_sum >> state.portions >> nhistory;
    for (int h = 0; h < nhistory; ++h) {
        int count;
        cin >> count;
        unordered_map<int, int> history;
        for (int i = 0; i < count; ++i) {
            int pos, value;
            cin >> pos >> value;
            history[pos] = value;
        }
        state.road_history.push_back(history);
    }
    cin >> steps;
    vector<vector<int>> actions(nagents);
    for (auto& car : actions) {
        int count;
        cin >> count;
        car.resize(count);
        for (int& c : car) cin >> c;
    }
    if (!simulate_day(board, state, actions, steps)) {
        puts("INVALID");
        return 0;
    }
    printf("OK");
    for (auto& a : state.agents) printf(" %d %d", a.pos, a.fuel);
    printf(" | %d %d %d |", (int)state.brands.count(), state.daily_sum, state.portions);
    vector<pair<int, int>> traffic(state.traffic.begin(), state.traffic.end());
    sort(traffic.begin(), traffic.end());
    for (auto [pos, status] : traffic) printf(" %d:%d", pos, status);
    puts("");
    return 0;
}
