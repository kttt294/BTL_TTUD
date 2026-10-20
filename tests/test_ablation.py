"""Kiểm tra đối chứng bỏ thành phần không vô tình đổi bộ điều khiển nền."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ablation_planner import plan_day as measured_plan
from hexudon.planner import plan_day
from hexudon.model import Board, State


class AblationTests(unittest.TestCase):
    def test_coordinated_copy_matches_original_without_timeout(self):
        board=Board([[0]*8 for _ in range(8)],
                    [dict(pos=p,brand=i%3,stocks=2) for i,p in enumerate((19,20,27,28))],
                    [9,10,17,18],[20],20)
        for strategy in ('greedy','lookahead'):
            state=State.initial(board,[0,0,0,1])
            original=plan_day(board,state,20,strategy,1000)
            measured=measured_plan(board,state,20,strategy)
            self.assertEqual(original.actions,measured.actions)
            self.assertFalse(measured.fallback)

    def test_coordination_avoids_competing_for_same_daily_stock(self):
        from benchmark_ablation import play
        board=Board([[0]*8 for _ in range(8)],
                    [dict(pos=p,brand=i,stocks=1) for i,p in enumerate((18,19,20,26,29,34,37,42,43,44))],
                    [27,28,35,36],[6,6],24)
        independent=play(board,[0]*4,False)
        shared=play(board,[0]*4)
        self.assertEqual(independent['score'],(9,15,15))
        self.assertEqual(shared['score'],(10,20,20))
        self.assertEqual(shared['fallback'],0)


if __name__=='__main__':
    unittest.main()
