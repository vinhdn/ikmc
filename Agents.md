Để xây dựng một website ôn luyện thi Toán Quốc tế Kangaroo ([IKMC - International Kangaroo Math Contest](https://kangaroo-math.vn/?utm_source=gemini)) dành riêng cho học sinh lớp 2 (Level 1: Pre-Ecolier), hệ thống cần kết hợp giữa **cấu trúc chuẩn của kỳ thi quốc tế** và **trải nghiệm người dùng (UX/UI) trực quan, sinh động** phù hợp với tâm lý lứa tuổi 7–8 tuổi.

Dưới đây là bản thiết kế hoàn chỉnh từ khung chương trình, kiến trúc hệ thống, thuật toán tạo đề, cơ chế tính điểm đến bản mẫu code chạy thử nghiệm.

---

### 1. Tổng quan cấu trúc chuẩn đề thi IKMC Level 1 (Lớp 1 – 2)

* **Thời gian làm bài:** 75 phút.
* **Số lượng câu hỏi:** 24 câu trắc nghiệm (mỗi câu gồm 5 phương án chọn $A, B, C, D, E$).
* **Phân bố thang điểm:**
* **Phần A (Cơ bản):** 8 câu $\times$ 3 điểm = 24 điểm.
* **Phần B (Trung bình):** 8 câu $\times$ 4 điểm = 32 điểm.
* **Phần C (Nâng cao / Tư duy sâu):** 8 câu $\times$ 5 điểm = 40 điểm.


* **Quy tắc tính điểm chuẩn Kangaroo:**
* **Điểm xuất phát ban đầu:** $+24$ điểm (đảm bảo thí sinh không bị điểm âm).
* **Trả lời đúng:** Được cộng trọn số điểm của câu đó ($+3, +4$ hoặc $+5$).
* **Trả lời sai:** Bị trừ $\frac{1}{4}$ số điểm của câu đó ($-0.75$ điểm cho câu 3đ; $-1.0$ điểm cho câu 4đ; $-1.25$ điểm cho câu 5đ).
* **Không trả lời (bỏ trống):** $0$ điểm (không cộng, không trừ).
* **Điểm tối đa:** $24 + 24 + 32 + 40 = 120$ điểm.
* **Điểm tối thiểu:** $0$ điểm.



---

### 2. Phân loại 4 nhóm dạng bài trọng tâm lớp 2

Đề thi IKMC lớp 2 ưu tiên khả năng quan sát hình ảnh và suy luận logic hơn là tính toán số học phức tạp:

| Nhóm chuyên đề | Các dạng bài tiêu biểu | Đặc điểm nhận biết & Gợi ý hướng dẫn |
| --- | --- | --- |
| **1. Số học & Quy luật trực quan** | - Dãy số cách đều, dãy hình lặp lại.<br>

<br>- Biểu tượng thay thế chữ số (hoa quả, con vật thay số).<br>

<br>- Phép tính cộng/trừ gắn với đồ vật thực tế (kẹo, que tính, khối gỗ). | Trực quan hóa phép tính bằng hình ảnh; hướng dẫn bé tìm quy luật lặp chu kỳ ($A-B-C-A-B-C$). |
| **2. Hình học & Không gian** | - Đếm số khối lập phương bị che khuất.<br>

<br>- Ghép hình ghép tranh (Tangram/Puzzle) tìm mảnh còn thiếu.<br>

<br>- Gấp giấy đục lỗ, đối xứng qua gương.<br>

<br>- Mê cung và xác định hướng đi. | Sử dụng hình vẽ 2D/3D rõ ràng, hướng dẫn bé đếm theo tầng hoặc đánh dấu số thứ tự lên từng khối. |
| **3. Đo lường, Thời gian & Cân đĩa** | - Đọc giờ đồng hồ kim (giờ đúng, giờ rưỡi, trước/sau bao lâu).<br>

<br>- Cân thăng bằng so sánh nặng/nhẹ giữa các vật thể.<br>

<br>- Xem lịch tuần, ngày tháng, đếm bước nhảy độ dài. | Hướng dẫn bé phương pháp khử vật giống nhau ở 2 đĩa cân để so sánh trực tiếp. |
| **4. Tư duy logic & Tổ hợp** | - Xếp hàng xác định vị trí (trước, sau, giữa, thứ mấy từ trái/phải).<br>

<br>- Bài toán điền số Sudoku mini ($3 \times 3$, $4 \times 4$).<br>

<br>- Phân loại và tô màu bản đồ (hai ô cạnh nhau không trùng màu). | Vẽ sơ đồ đoạn thẳng hoặc sơ đồ hàng dọc/ngang để bé dễ hình dung thứ tự. |

---

### 3. Thiết kế cấu trúc dữ liệu (Data Schema)

Để quản lý ngân hàng câu hỏi và tạo đề linh hoạt, cấu trúc JSON cho một câu hỏi cần tối ưu hiển thị song ngữ hoặc tiếng Việt kèm hình ảnh:

```json
{
  "id": "ikmc_g2_001",
  "topic": "spatial_reasoning", // arithmetic | spatial_reasoning | measurement | logic
  "grade": 2,
  "points": 4, // 3, 4, hoặc 5 điểm
  "question": {
    "text_vi": "Bạn sóc Na muốn đi qua mê cung để nhặt quả dẻ gai. Trên đường đi Na có thể nhặt được nhiều nhất bao nhiêu quả dẻ gai nếu không được đi qua một ô quá 1 lần?",
    "text_en": "Squirrel Na wants to go through the maze to collect acorns. What is the greatest number of acorns Na can collect without visiting any square more than once?",
    "image_url": "https://example.com/images/maze_acorns.png"
  },
  "options": [
    { "key": "A", "text": "3", "image_url": null },
    { "key": "B", "text": "4", "image_url": null },
    { "key": "C", "text": "5", "image_url": null },
    { "key": "D", "text": "6", "image_url": null },
    { "key": "E", "text": "7", "image_url": null }
  ],
  "correct_answer": "D",
  "explanation": {
    "step_by_step_vi": [
      "Bước 1: Quan sát tất cả các nhánh đường đi từ điểm bắt đầu đến lối ra.",
      "Bước 2: Tìm đường đi rẽ qua các ô có chứa quả dẻ gai nhiều nhất.",
      "Bước 3: Đếm tổng số quả trên lộ trình dài nhất hợp lệ: 6 quả."
    ],
    "key_takeaway_vi": "Khi đi qua mê cung, hãy thử đếm lần lượt các ngã rẽ và tránh các đường cụt."
  }
}

```

---

### 4. Thuật toán tạo đề & Logic chấm điểm chuẩn IKMC

#### A. Thuật toán tạo đề (Exam Generator)

Đề thi chuẩn 24 câu được tạo bằng cách bốc ngẫu nhiên theo tỷ lệ chuẩn:

```javascript
function generateIKMCExam(questionPool) {
  const pool3 = questionPool.filter(q => q.points === 3);
  const pool4 = questionPool.filter(q => q.points === 4);
  const pool5 = questionPool.filter(q => q.points === 5);

  const shuffle = arr => [...arr].sort(() => 0.5 - Math.random());

  const sectionA = shuffle(pool3).slice(0, 8);
  const sectionB = shuffle(pool4).slice(0, 8);
  const sectionC = shuffle(pool5).slice(0, 8);

  return [...sectionA, ...sectionB, ...sectionC];
}

```

#### B. Công thức tính điểm (Scoring Engine)

```javascript
function calculateScore(examQuestions, userAnswers) {
  const BASE_SCORE = 24;
  let correctCount = 0;
  let wrongCount = 0;
  let skippedCount = 0;
  let earnedScore = BASE_SCORE;

  examQuestions.forEach(q => {
    const selected = userAnswers[q.id];
    if (!selected) {
      skippedCount++;
    } else if (selected === q.correct_answer) {
      correctCount++;
      earnedScore += q.points;
    } else {
      wrongCount++;
      earnedScore -= (q.points * 0.25); // Phạt 1/4 số điểm
    }
  });

  return {
    totalScore: Math.max(0, earnedScore), // Không dưới 0 điểm
    correctCount,
    wrongCount,
    skippedCount
  };
}

```

---

### 5. Mã nguồn mẫu giao diện hoàn chỉnh (Single-File Web Prototype)

Dưới đây là mã nguồn HTML/CSS/JavaScript hoàn chỉnh, tích hợp sẵn câu hỏi mẫu, đồng hồ đếm ngược, giao diện thẻ câu hỏi lớn thân thiện với học sinh lớp 2, tự động chấm điểm và xem giải thích chi tiết:

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Luyện Thi Toán Kangaroo (IKMC) Lớp 2</title>
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: #FF7A00;
      --secondary: #4CAF50;
      --bg: #F4F8FB;
      --card: #FFFFFF;
      --text: #2D3748;
      --accent: #FFD166;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Nunito', sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding: 20px; }
    .container { max-width: 800px; margin: 0 auto; }
    
    header {
      background: var(--card); border-radius: 16px; padding: 16px 24px;
      display: flex; justify-content: space-between; align-items: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    .badge {
      background: var(--accent); padding: 6px 12px; border-radius: 20px;
      font-weight: 800; font-size: 14px; color: #8A5800;
    }
    .timer { font-size: 20px; font-weight: 800; color: #E63946; }

    .card {
      background: var(--card); border-radius: 20px; padding: 24px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.06); margin-bottom: 20px;
    }
    .question-header { display: flex; justify-content: space-between; margin-bottom: 12px; }
    .points-tag {
      background: #E8F5E9; color: #2E7D32; font-weight: 800;
      padding: 4px 10px; border-radius: 8px; font-size: 13px;
    }
    .question-text { font-size: 18px; line-height: 1.5; margin-bottom: 20px; font-weight: 700; }

    .options-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
    .option-btn {
      background: #F8FAFC; border: 2px solid #E2E8F0; border-radius: 14px;
      padding: 14px 18px; font-size: 17px; font-weight: 700; text-align: left;
      cursor: pointer; display: flex; align-items: center; gap: 14px;
      transition: all 0.2s;
    }
    .option-btn:hover { border-color: var(--primary); background: #FFF7ED; }
    .option-btn.selected { border-color: var(--primary); background: #FFEDD5; color: #C2410C; }
    .opt-circle {
      width: 32px; height: 32px; border-radius: 50%; background: #E2E8F0;
      display: flex; align-items: center; justify-content: center; font-weight: 800;
    }
    .option-btn.selected .opt-circle { background: var(--primary); color: white; }

    .actions { display: flex; justify-content: space-between; margin-top: 20px; }
    button.btn {
      padding: 12px 24px; border: none; border-radius: 12px;
      font-size: 16px; font-weight: 800; cursor: pointer;
    }
    .btn-prev { background: #E2E8F0; color: #475569; }
    .btn-next { background: var(--primary); color: white; }
    .btn-submit { background: var(--secondary); color: white; }

    .result-card { text-align: center; padding: 36px 20px; }
    .score-big { font-size: 48px; font-weight: 900; color: var(--primary); margin: 12px 0; }
    .explanation-box {
      background: #F0FDF4; border-left: 4px solid var(--secondary);
      padding: 14px; border-radius: 8px; margin-top: 16px; text-align: left;
    }
  </style>
</head>
<body>

<div class="container">
  <header>
    <div>
      <span class="badge">IKMC Level 1 (Lớp 2)</span>
      <h2 style="font-size: 18px; margin-top: 4px;">Đề Luyện Tập Tư Duy Số 01</h2>
    </div>
    <div class="timer" id="timer">75:00</div>
  </header>

  <div id="quiz-area">
    <div class="card">
      <div class="question-header">
        <span id="question-index" style="font-weight: 800; color: #64748B;">Câu hỏi 1 / 3</span>
        <span class="points-tag" id="question-points">Phần A: 3 điểm</span>
      </div>
      <div class="question-text" id="question-text">Đang tải câu hỏi...</div>
      <div class="options-grid" id="options-container"></div>
      
      <div class="actions">
        <button class="btn btn-prev" id="btn-prev" onclick="nav(-1)">Quay lại</button>
        <button class="btn btn-next" id="btn-next" onclick="nav(1)">Câu tiếp theo</button>
      </div>
    </div>
  </div>

  <div id="result-area" style="display: none;">
    <div class="card result-card">
      <h2>🎉 Hoàn thành bài thi!</h2>
      <div class="score-big" id="final-score">0 / 120</div>
      <p id="stats-summary" style="font-size: 16px; color: #64748B; margin-bottom: 24px;"></p>
      <div id="review-list"></div>
      <button class="btn btn-next" style="margin-top: 20px;" onclick="restart()">Làm lại bài thi</button>
    </div>
  </div>
</div>

<script>
  const questions = [
    {
      id: "q1",
      points: 3,
      section: "Phần A (3 điểm)",
      text: "Một chú thỏ có 3 củ cà rốt. Chú ăn 1 củ vào bữa sáng và được mẹ cho thêm 4 củ nữa vào bữa trưa. Hỏi bây giờ chú thỏ có tất cả bao nhiêu củ cà rốt?",
      options: [
        { k: "A", t: "5 củ" }, { k: "B", t: "6 củ" }, { k: "C", t: "7 củ" }, { k: "D", t: "8 củ" }, { k: "E", t: "4 củ" }
      ],
      correct: "B",
      explanation: "Sau bữa sáng thỏ còn: 3 - 1 = 2 (củ). Được mẹ cho thêm 4 củ thì tổng cộng có: 2 + 4 = 6 (củ cà rốt)."
    },
    {
      id: "q2",
      points: 4,
      section: "Phần B (4 điểm)",
      text: "Minh xếp các khối lập phương gỗ thành một hình chữ L trên bàn. Minh dùng 3 khối xếp thẳng đứng và 2 khối nằm ngang bên cạnh. Tổng cộng Minh đã dùng bao nhiêu khối gỗ?",
      options: [
        { k: "A", t: "4 khối" }, { k: "B", t: "5 khối" }, { k: "C", t: "6 khối" }, { k: "D", t: "7 khối" }, { k: "E", t: "8 khối" }
      ],
      correct: "B",
      explanation: "Minh dùng 3 khối theo hàng dọc và 2 khối xếp thêm ở hàng ngang. Tổng số khối là: 3 + 2 = 5 (khối)."
    },
    {
      id: "q3",
      points: 5,
      section: "Phần C (5 điểm)",
      text: "Trong một hàng dọc có 7 bạn học sinh. Bạn Nam đứng ở vị trí thứ 3 từ đầu hàng đếm xuống. Hỏi bạn Nam đứng ở vị trí thứ mấy nếu đếm từ dưới hàng lên?",
      options: [
        { k: "A", t: "Thứ 3" }, { k: "B", t: "Thứ 4" }, { k: "C", t: "Thứ 5" }, { k: "D", t: "Thứ 6" }, { k: "E", t: "Thứ 2" }
      ],
      correct: "C",
      explanation: "Đứng sau bạn Nam có: 7 - 3 = 4 bạn. Do đó, nếu đếm ngược từ dưới lên thì Nam đứng ở vị trí: 4 + 1 = thứ 5."
    }
  ];

  let currentIndex = 0;
  let answers = {};
  let timeLeft = 75 * 60;
  let timerInterval;

  function startTimer() {
    timerInterval = setInterval(() => {
      if (timeLeft <= 0) {
        clearInterval(timerInterval);
        submitQuiz();
        return;
      }
      timeLeft--;
      const m = Math.floor(timeLeft / 60);
      const s = timeLeft % 60;
      document.getElementById("timer").innerText = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }, 1000);
  }

  function renderQuestion() {
    const q = questions[currentIndex];
    document.getElementById("question-index").innerText = `Câu hỏi ${currentIndex + 1} / ${questions.length}`;
    document.getElementById("question-points").innerText = q.section;
    document.getElementById("question-text").innerText = q.text;

    const optContainer = document.getElementById("options-container");
    optContainer.innerHTML = "";

    q.options.forEach(opt => {
      const btn = document.createElement("div");
      btn.className = "option-btn" + (answers[q.id] === opt.k ? " selected" : "");
      btn.innerHTML = `<div class="opt-circle">${opt.k}</div><span>${opt.t}</span>`;
      btn.onclick = () => selectOption(q.id, opt.k);
      optContainer.appendChild(btn);
    });

    document.getElementById("btn-prev").style.visibility = currentIndex === 0 ? "hidden" : "visible";
    const nextBtn = document.getElementById("btn-next");
    if (currentIndex === questions.length - 1) {
      nextBtn.innerText = "Nộp bài";
      nextBtn.className = "btn btn-submit";
    } else {
      nextBtn.innerText = "Câu tiếp theo";
      nextBtn.className = "btn btn-next";
    }
  }

  function selectOption(qId, key) {
    if (answers[qId] === key) delete answers[qId]; // Hủy chọn
    else answers[qId] = key;
    renderQuestion();
  }

  function nav(dir) {
    if (dir === 1 && currentIndex === questions.length - 1) {
      submitQuiz();
      return;
    }
    currentIndex += dir;
    renderQuestion();
  }

  function submitQuiz() {
    clearInterval(timerInterval);
    document.getElementById("quiz-area").style.display = "none";
    document.getElementById("result-area").style.display = "block";

    let basePoints = 24;
    let earned = basePoints;
    let correct = 0, wrong = 0, skipped = 0;

    let reviewHtml = "";

    questions.forEach((q, idx) => {
      const userChoice = answers[q.id];
      let statusClass = "";
      if (!userChoice) {
        skipped++;
      } else if (userChoice === q.correct) {
        correct++;
        earned += q.points;
      } else {
        wrong++;
        earned -= (q.points * 0.25);
      }

      reviewHtml += `
        <div class="card" style="margin-top: 14px; text-align: left;">
          <h4>Câu ${idx + 1}: ${q.text}</h4>
          <p style="margin: 6px 0;"><strong>Lựa chọn của bé:</strong> ${userChoice ? userChoice : "Chưa trả lời"} | <strong>Đáp án đúng:</strong> ${q.correct}</p>
          <div class="explanation-box">
            <strong>💡 Hướng dẫn giải:</strong><br>${q.explanation}
          </div>
        </div>
      `;
    });

    document.getElementById("final-score").innerText = `${Math.max(0, earned)} / 120 điểm`;
    document.getElementById("stats-summary").innerText = `Đúng: ${correct} câu | Sai: ${wrong} câu | Bỏ qua: ${skipped} câu (Điểm xuất phát: +24)`;
    document.getElementById("review-list").innerHTML = reviewHtml;
  }

  function restart() {
    answers = {};
    currentIndex = 0;
    timeLeft = 75 * 60;
    document.getElementById("result-area").style.display = "none";
    document.getElementById("quiz-area").style.display = "block";
    startTimer();
    renderQuestion();
  }

  startTimer();
  renderQuestion();
</script>
</body>
</html>

```

---

### 6. Những điểm cần làm rõ để hoàn thiện hệ thống

Để tối ưu hóa website đúng với nhu cầu thực tế của bé và định hướng kỹ thuật của bạn, xin vui lòng cho biết thêm một số chi tiết sau:

1. **Ngăn xếp công nghệ (Tech Stack) mong muốn:**
* Bạn muốn xây dựng website dạng tĩnh đơn giản (Single Page Application - React/Vue/Vite) chạy trực tiếp trên trình duyệt, hay hệ thống đầy đủ có Backend (Node.js/Python, cơ sở dữ liệu Firebase/Supabase/PostgreSQL) để lưu tiến trình học tập?


2. **Chế độ học tập chính:**
* Bạn ưu tiên **Chế độ thi thử chuẩn** (bấm giờ 75 phút, không hiện đáp án giữa chừng) hay **Chế độ luyện tập từng câu** (làm câu nào biết đúng/sai và xem giải thích bằng hoạt họa/hình ảnh ngay câu đó)?


3. **Ngôn ngữ hiển thị:**
* Bạn muốn đề bài hiển thị hoàn toàn bằng **Tiếng Việt** hay **Song ngữ Anh – Việt** (đúng định dạng đề thi chính thức của IKMC Việt Nam)?