"""Kiểm tra mạng thật sự điều khiển đích và kế hoạch không đổi sang heuristic."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'/'rl'))

try:
    import torch
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'Kiểm thử RL tùy chọn cần PyTorch.')
class PolicyTests(unittest.TestCase):
    def test_wait_is_policy_decision(self):
        from rl_policy import TargetPolicy, play
        from hexudon.model import Board
        model = TargetPolicy()
        for parameter in model.parameters():
            parameter.data.zero_()
        # Đặc trưng 15 đánh dấu hành động chờ; trọng số ép mạng chọn chờ.
        model.encoder[0].weight.data[0,15] = 1
        model.encoder[2].weight.data[0,0] = 1
        model.actor.weight.data[0,0] = 10
        board = Board([[0,0,0],[0,0,0]], [dict(pos=2,brand=0,stocks=1)], [0], [4,4], 10)
        result,_ = play(board,model)
        self.assertEqual(result['actions'],[[[-4]],[[-4]]])
        self.assertEqual(result['score'],(0,0,0))
        self.assertEqual(result['fallback_calls'],0)

    def test_prefix_is_contiguous_and_fuel_carries(self):
        from rl_policy import play
        from hexudon.model import Board
        board = Board([[0,0,0,0,0],[0,0,0,0,0]],
                      [dict(pos=4,brand=0,stocks=1)],[0],[3,3,3,3],4)
        result,_ = play(board,mode='nearest')
        self.assertEqual(result['score'][0],1)
        self.assertEqual(result['fallback_calls'],0)


if __name__=='__main__':
    unittest.main()
