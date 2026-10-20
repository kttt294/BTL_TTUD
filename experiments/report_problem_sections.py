"""Nội dung dẫn nhập đề bài và bảng đối chiếu cho các chương đầu báo cáo."""


def intro(section, para, table, figure):
    section('1.1. Bối cảnh và nhiệm vụ của đội chơi', 2)
    para('HEXUDON là bài toán điều khiển một đội xe đi thu thập udon, một loại mì được '
         'dùng như mặt hàng trong trò chơi. Người chơi không điều khiển xe từng bước trên '
         'giao diện, mà viết chương trình nhận dữ liệu bản đồ rồi xuất kế hoạch di chuyển. '
         'Bản đồ gồm các ô lục giác với đường bộ, đồng bằng, núi và ao; các điểm bán udon '
         'nằm trên một số ô đồng bằng. Mỗi điểm thuộc một chuỗi cửa hàng, tương ứng với '
         'một loại udon. Nhiều điểm có thể bán cùng một loại [1].')
    figure('btc_map.png', 'Hình X1. Bản đồ lục giác và chỉ số ô, trích đề BTC [1, tr. 1].', 16)
    para('Trong hình, ô xanh lá là đồng bằng, ô nâu là núi, ô xanh dương là ao và ô xám '
         'là đường. Số trong hình bên phải là chỉ số vị trí, không phải chi phí đi lại. '
         'Một ô có nhiều nhất sáu ô kề; hai hàng liên tiếp được xếp lệch nhau nên không '
         'thể áp dụng trực tiếp bốn hướng của lưới vuông. Với bản đồ rộng w ô, chương trình '
         'đánh số vị trí theo công thức pos = row×w + col, bắt đầu từ 0.')
    para('Đề BTC quy định chiều rộng và chiều cao bản đồ từ 8 đến 32 ô, mỗi đội có từ '
         '3 đến 8 tác nhân và một trận kéo dài tối đa 10 ngày [1]. Vị trí xuất phát được '
         'cấp sẵn; đội chọn vai trò cho từng xe trước trận và vai trò được giữ đến cuối. '
         'Mỗi ngày có quỹ thời gian tính bằng step. Xe tuần tra phải cân đối nhiên liệu '
         'để đi thu hàng, còn xe tiếp tế có thể giúp xe tuần tra tiếp tục hoạt động. '
         'Bài toán khó ở việc phối hợp nhiều quyết định: đi đến đâu, theo tuyến nào, '
         'dành nhiên liệu cho ngày sau ra sao và nên dùng bao nhiêu xe để tiếp tế.')
    para('Đội chơi được ưu tiên theo số loại udon khác nhau thu được trong cả trận, rồi '
         'đến tổng số loại tính theo từng ngày, cuối cùng mới đến tổng số suất. Vì vậy, '
         'đi thật xa hoặc lấy thật nhiều suất của một loại chưa chắc tạo điểm tốt hơn '
         'một tuyến ngắn nhưng ghé được loại còn thiếu. Báo cáo dùng bối cảnh này để '
         'nghiên cứu thuật toán, còn phần thực nghiệm hiện chỉ đánh giá một đội.')
    table('Bảng T1. Từ yêu cầu ứng dụng đến nội dung thuật toán được nghiên cứu',
          ['Quyết định cần giải', 'Phương pháp trong bài', 'Cách đánh giá'],
          [['Tìm tuyến đủ step và nhiên liệu', 'DFS, BFS, Greedy Best-First, Dijkstra, A*', 'Tính hợp lệ, chi phí tuyến, nhãn, thời gian'],
           ['Chọn thứ tự ghé điểm', 'Greedy và Lookahead hai điểm', 'Bộ điểm (U,D,Q) theo từng cặp input'],
           ['Chọn vai trò xe trước trận', 'Sàng lọc và mô phỏng giới hạn thời gian', 'So đội hình chọn với đội hình cố định'],
           ['Biết heuristic còn cách tối ưu bao xa', 'DP chính xác trên phiên bản thu nhỏ', 'Số bài khớp tối ưu và độ thiếu hụt có điều kiện'],
           ['Ứng dụng trong hệ thống có học máy', 'RL chọn đích, A* tạo tuyến, Greedy làm nền', 'Điểm BTC và phạm vi đóng góp đã kiểm chứng']],
          [4.8, 5.8, 5.4], 10.5)


def problem_model(section, para, table, figure):
    section('2. Mô tả đề bài và mô hình tối ưu')
    section('2.1. Bản đồ, điểm bán và hai loại xe', 2)
    figure('btc_agents.png', 'Hình X2. Vai trò xe tuần tra và xe tiếp tế, trích đề BTC [1, tr. 4].', 15)
    table('Bảng T2. Những khác biệt ảnh hưởng tới cách phối hợp hai loại xe',
          ['Đặc điểm', 'Xe tuần tra', 'Xe tiếp tế'],
          [['Thu thập udon', 'Có; là xe trực tiếp tạo điểm', 'Không'],
           ['Nhiên liệu khi di chuyển', 'Tiêu hao theo ô nguồn', 'Không tiêu hao nhiên liệu'],
           ['Thời gian khi di chuyển', 'Phải trả đủ step theo địa hình', 'Vẫn phải trả đủ step theo địa hình'],
           ['Tiếp nhiên liệu', 'Được nạp đầy khi cùng ô với xe tiếp tế cùng đội', 'Nạp đầy cho xe tuần tra cùng đội tại cùng ô'],
           ['Lựa chọn đầu trận', 'Mã vai trò 0 trong chương trình', 'Mã vai trò 1 trong chương trình']],
          [4.2, 5.9, 5.9], 10.5)
    para('Một xe tiếp tế làm giảm số xe trực tiếp đi lấy udon nhưng có thể kéo dài khả năng '
         'hoạt động của các xe tuần tra. Do đó, chọn toàn tuần tra hay dành một xe để tiếp '
         'tế là một quyết định tối ưu cần được đánh giá theo bản đồ. Các xe được phép đứng '
         'cùng một ô; bài toán không áp dụng ràng buộc tránh va chạm giữa các tuyến như '
         'một số bài tìm đường đa tác tử khác [1].')
    figure('btc_spots.png', 'Hình X3. Điểm bán và các loại udon theo chuỗi, trích đề BTC [1, tr. 3].', 15)
    para('Hình minh họa có hai cửa hàng cùng thuộc chuỗi A. Xe ghé cả hai có thể lấy hai '
         'suất nhưng chỉ bổ sung một loại udon nếu trước đó chưa thu loại A. Mỗi xe tuần '
         'tra chỉ lấy tối đa một suất tại mỗi điểm trong một ngày, còn tổng số suất xe '
         'có thể mang không bị giới hạn. Tồn kho mỗi điểm là kho riêng cho từng đội và '
         'được bổ sung đầu ngày. Khi nhiều xe cùng đội ghé một điểm, chúng vẫn phải chia '
         'nhau số suất còn lại, vì vậy lập tuyến độc lập có thể làm kế hoạch dự kiến '
         'nhiều hàng hơn thực tế [1].')
    section('2.2. Thời gian, nhiên liệu và tiến trình một ngày', 2)
    para('Step là đơn vị thời gian của trò chơi, khác số giây chương trình được phép tính '
         'toán. Mỗi xe có cùng quỹ step của ngày và hoạt động đồng thời với các xe khác; '
         'không cộng thời lượng của tất cả xe thành một quỹ chung. Một lệnh di chuyển '
         'sang ô kề có thể tốn nhiều step và có chi phí nhiên liệu riêng. Các chi phí '
         'được tính theo ô xe rời đi, không theo ô xe sắp đến.')
    table('Bảng 1. Chi phí rời ô nguồn', ['Ô nguồn', 'Step di chuyển', 'Nhiên liệu tuần tra'],
          [['Đồng bằng', 2, 1], ['Núi', 3, 2], ['Đường thông thoáng', 1, 2],
           ['Đường đông đúc', 2, 2], ['Đường ùn tắc', 4, 2], ['Ao', 'Không được đi vào', 'Không áp dụng']],
          [6, 5, 5], 11)
    para('Chẳng hạn, xe đang ở đồng bằng cần hai step và một đơn vị nhiên liệu để sang '
         'ô kề. Nếu ngày chỉ còn một step, xe phải chờ; việc xuất một hướng di chuyển '
         'trong tình huống này làm câu trả lời không hợp lệ. Nhiên liệu của xe tuần tra '
         'không tự đầy lại khi chuyển ngày, mà được kế thừa từ cuối ngày trước. Xe chỉ '
         'được nạp đầy khi gặp xe tiếp tế cùng đội theo timeline của trò chơi.')
    para('Trước trận, chương trình nhận bản đồ và chọn vai trò xe. Ở đầu mỗi ngày, '
         'chương trình đọc vị trí, nhiên liệu và trạng thái đường hiện tại, sau đó lập '
         'một kế hoạch cho từng xe trong giới hạn giây được cấp. Máy chủ thực thi các '
         'kế hoạch theo step, cập nhật việc tiếp tế và thu hàng, rồi cung cấp trạng thái '
         'ngày tiếp theo. Vị trí và nhiên liệu được kế thừa, kho được bổ sung, còn '
         'trạng thái đường được tính lại. Vì vậy, chương trình phải lập lại kế hoạch '
         'từ trạng thái thực thay vì lặp nguyên đường đi của ngày đầu [1], [4].')
    section('2.3. Dữ liệu đầu vào và ví dụ kế hoạch đầu ra', 2)
    table('Bảng T3. Dữ liệu chương trình cần đọc và thời điểm sử dụng',
          ['Thông tin', 'Dữ liệu hoặc tên trường', 'Ý nghĩa'],
          [['Bản đồ', 'map.height, map.width, map.cells', 'Địa hình và kích thước được giữ trong trận'],
           ['Điểm bán', 'spots: pos, brand, stocks', 'Vị trí, loại udon và kho mỗi ngày'],
           ['Vị trí xuất phát', 'agents hoặc dữ liệu vị trí được cung cấp', 'Xác định vị trí các xe, không tự đổi vị trí'],
           ['Quỹ tài nguyên', 'daySteps, fuelLimits', 'Step mỗi ngày và sức chứa nhiên liệu'],
           ['Ngưỡng giao thông', 'busyThreshold, jammedThreshold', 'Phân loại lưu lượng trên ô đường'],
           ['Trạng thái đầu ngày', 'Vị trí, nhiên liệu, traffics từ trạng thái API', 'Thay đổi sau thực thi; không có sẵn cho mọi ngày trong input cấu hình']],
          [3.5, 6, 6.5], 10.5)
    para('Đầu ra trước trận là danh sách vai trò xe. Đầu ra mỗi ngày là một mảng gồm '
         'các mảng lệnh, giữ đúng thứ tự xe trong input. Mã 0–5 chỉ hướng di chuyển '
         'sang ô kề; số âm −k chỉ chờ k step. Mã hướng không cho biết thời lượng lệnh: '
         'thời lượng vẫn phải tra địa hình và trạng thái đường của ô nguồn. Bảng mã '
         'hướng cụ thể nằm trong phụ lục A.')
    para('Ví dụ minh họa, giả sử một ngày có tám step, ba xe có vai trò [0,0,1] và các '
         'lệnh đi đều rời ô đồng bằng. Khi các ô đích hợp lệ và xe tuần tra còn đủ '
         'nhiên liệu, một output hợp lệ về cấu trúc và thời lượng là '
         '[[2,3,-4],[5,-6],[-8]]. Xe thứ nhất đi hai lần hết bốn step rồi chờ bốn step; '
         'xe thứ hai đi một lần hết hai step rồi chờ sáu step; xe tiếp tế đứng chờ '
         'tám step. Cả ba cùng kết thúc ở step thứ tám, dù số phần tử mảng khác nhau. '
         'Ví dụ này không phải lời giải dùng chung cho mọi bản đồ; ô đích, nhiên liệu '
         'và lịch gặp vẫn phải được kiểm tra trước khi nộp.')
    section('2.4. Cách tính điểm và trạng thái đường', 2)
    para('Nhóm ký hiệu chất lượng bằng bộ (U,D,Q): U là số loại udon khác nhau trong '
         'cả trận, D là tổng số loại của từng ngày, còn Q là tổng số suất. Máy chấm '
         'so từ trái sang phải. Ví dụ, nếu ngày đầu đội lấy ba suất thuộc {A,A,B} và '
         'ngày hai lấy hai suất thuộc {B,C}, đội có U=3, D=2+2=4 và Q=5, tức (3,4,5).')
    table('Bảng T4. Ví dụ so sánh bộ điểm theo thứ tự ưu tiên',
          ['Phương án', 'Bộ điểm (U,D,Q)', 'Kết quả khi so với A=(3,4,5)'],
          [['A', '(3,4,5)', 'Mốc minh họa'], ['B', '(2,8,20)', 'Kém A vì U nhỏ hơn, dù D và Q lớn hơn'],
           ['C', '(3,5,4)', 'Tốt hơn A vì bằng U và D lớn hơn'],
           ['D', '(3,4,6)', 'Tốt hơn A vì bằng U, D và Q lớn hơn']], [3, 4.5, 8.5], 11)
    para('Đề BTC còn dùng thời gian phản hồi lũy kế để phân định khi ba thành phần '
         'thu thập bằng nhau, rồi mới tới quy tắc hòa cuối cùng [1]. Báo cáo tập trung '
         'so bộ điểm thu thập và ghi chi phí tính toán riêng; thời gian chạy offline '
         'không được xem như thời gian phản hồi chính thức của máy chủ.')
    para('Đường có ba trạng thái: thông thoáng, đông đúc và ùn tắc. Trạng thái giữ '
         'nguyên trong ngày nhưng thay đổi giữa các ngày dựa trên lưu lượng trước đó. '
         'Theo đề, ngày 1 thông thoáng; ngày 2 dùng lịch sử ngày 1, còn những ngày '
         'sau dùng hai ngày trước. Trong trận nhiều đội, xe của các đội đều góp vào '
         'lưu lượng, nên chương trình không thể suy chính xác mọi ngày tương lai chỉ '
         'từ cấu hình ban đầu. Trong các thí nghiệm một đội của báo cáo, giao thông '
         'được cập nhật từ lịch sử xe đội mình; nó vẫn có thể đông hoặc tắc [1], [4].')
    section('2.5. Chuyển đề bài thành mô hình đồ thị có tài nguyên', 2)
    para('Nhóm biểu diễn bản đồ bằng đồ thị G=(V,E). Mỗi ô không phải ao là một đỉnh; '
         'hai ô kề đi được tạo cạnh có hướng. Mỗi đỉnh có tối đa sáu cạnh đi ra, nên '
         'E=O(V). Trọng số thời gian và nhiên liệu của cạnh phụ thuộc ô nguồn; do đó, '
         'hai cạnh ngược chiều giữa cùng cặp ô có thể có trọng số khác nhau. Chương '
         'trình tính láng giềng khi cần thay vì lưu một ma trận kề đầy đủ.')
    para('Một tuyến khả thi phải thỏa tổng step không vượt thời gian còn lại và tổng '
         'nhiên liệu không vượt mức xe đang có. Tìm đường một chặng chưa xét tiếp tế '
         'giữa đường; lớp lập kế hoạch chịu trách nhiệm nối các chặng trước và sau '
         'lần gặp xe tiếp tế. Trạng thái toàn trận còn cần vị trí và vai trò xe, '
         'những loại đã thu, điểm số và lịch sử đường. Từ mô hình này, chương tiếp '
         'theo mới xem xét cách tìm đường nhanh và đúng tài nguyên.')


def search_table(table):
    table('Bảng T5. So sánh mục tiêu và cấu trúc của năm thuật toán tìm đường',
          ['Thuật toán', 'Thứ tự mở rộng', 'Bảo đảm khi tìm đủ', 'Vai trò trong bài'],
          [['DFS', 'Ngăn xếp; duyệt sâu', 'Không tối ưu chi phí tuyến', 'Đối chứng duyệt cơ bản'],
           ['BFS', 'Hàng đợi; số cạnh tăng dần', 'Ít cạnh nhất trong các tuyến khả thi', 'Tách số lần đi khỏi chi phí step'],
           ['Dijkstra', 'Heap theo g: step đã dùng', 'Ít step nhất dưới giới hạn nhiên liệu', 'Mốc đối chiếu chất lượng cho A*'],
           ['Greedy Best-First', 'Heap theo h: khoảng cách còn lại', 'Không tối ưu step', 'Đo lợi ích và rủi ro của định hướng hình học'],
           ['A*', 'Heap theo g+h', 'Ít step nhất khi h khả chấp và giữ nhãn đúng', 'Bộ tìm đường của các heuristic toàn trận']],
          [3, 4.3, 4.7, 4], 10.5)


def planning_table(table):
    table('Bảng T6. Khác biệt giữa hai heuristic và bộ đối chứng chính xác',
          ['Đặc điểm', 'Greedy', 'Lookahead', 'DP bài nhỏ'],
          [['Phạm vi quyết định', 'Chọn một đích kế tiếp', 'Xét cặp đích rồi chọn chặng đầu', 'Tối ưu chuỗi lệnh của cả trận thu nhỏ'],
           ['Số ứng viên', 'Tối đa sáu đích mỗi lượt', 'Sáu đích đầu, tối đa ba đích sau', 'Mọi chuyển tiếp hợp lệ trong miền hỗ trợ'],
           ['Ưu điểm', 'Ít truy vấn phụ, dễ hoàn tất dưới hạn ngắn', 'Thấy lợi ích của hai điểm liền nhau', 'Có nghiệm tối ưu để đo chất lượng'],
           ['Đánh đổi', 'Không thấy lợi ích xa hơn', 'Tăng chi phí tìm kiếm; chưa nhìn hết nhiều ngày', 'Không gian trạng thái tăng theo hàm mũ'],
           ['Có bảo đảm tối ưu toàn trận?', 'Không', 'Không', 'Có, chỉ trong phiên bản thu nhỏ đã đặc tả']],
          [3.5, 4, 4.3, 4.2], 10.5)


def rl_table(table):
    table('Bảng T7. Phân biệt huấn luyện ở nhánh gốc với lượt đánh giá hiện tại',
          ['Khía cạnh', 'Nhánh huấn luyện gốc', 'Thực nghiệm trong báo cáo'],
          [['Trọng số mạng', 'Được cập nhật từ các episode', 'Giữ cố định checkpoint episode_256.pt'],
           ['Vai trò critic', 'Ước lượng giá trị để hỗ trợ cập nhật', 'Không có bước cập nhật tham số'],
           ['Đầu ra chính sách', 'Phân phối lựa chọn mục tiêu', 'Chọn xác định rồi tạo tuyến bằng A*'],
           ['Nguồn đánh giá cuối', 'Phần thưởng và chỉ số huấn luyện', 'Điểm và tính hợp lệ do máy chủ BTC trả'],
           ['Kết luận cho phép', 'Cần log để đánh giá hội tụ', 'Chỉ đánh giá checkpoint và cấu hình đã chạy']],
          [3.7, 6.1, 6.2], 10.5)
