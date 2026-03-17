# 4Bro - AI 광고 어시스턴트

> 광고 마케터를 위한 데스크톱 AI 어시스턴트 (Gemini 2.5 Flash 기반)

## 주요 기능

### 💬 AI 채팅
- Gemini 2.5 Flash 기반 실시간 스트리밍 응답
- 마크다운 렌더링 (코드 블록, 볼드, 헤더, 리스트)
- 코드 블록 복사 버튼
- 응답 재생성 (🔄) / 생성 중지
- 메시지 수정 후 재전송
- 대화 내 검색 (Ctrl+F)

### 📎 파일 처리
- PDF, Word, Excel, PowerPoint, CSV, 텍스트 파일 첨부 및 분석
- 이미지 첨부 및 분석 (Gemini Vision)
- 스캔 PDF 자동 이미지 변환
- 드래그 앤 드롭 파일 첨부
- 50만자 이상 대용량 문서 지원

### 🤖 에이전트 워크플로우
- 매체별 광고 변형 (GFA, GDN, 유튜브, 인벤, SNS)
- 캠페인 패키지 자동 생성 (5단계)
- 경쟁사 분석 (웹 검색 연동)
- 대량 카피 생성 (50개 헤드라인)
- 보고서 자동 작성

### 📁 프로젝트 관리
- 프로젝트별 컨텍스트 자동 주입 (장르, 타겟, 톤앤매너, KPI 등)
- 대화 히스토리 관리 (이름 변경, 검색, 페이지네이션)
- 북마크 + 라벨 태그
- 프롬프트 템플릿 저장/재사용

### 📤 내보내기
- Word (.docx) / PDF / 텍스트 파일 저장
- 클립보드 복사 (마크다운)
- 에이전트 결과 Word 자동 저장

### ⚙️ 기타
- Catppuccin Mocha 다크 테마
- 자동 업데이트 (GitHub Release 연동)
- 창 위치/크기 자동 기억
- 키보드 단축키 (Ctrl+N, Ctrl+F, Ctrl+E)
- 8개 매체 광고 규격 내장

## 기술 스택

| 구분 | 기술 |
|------|------|
| GUI | PyQt6 |
| AI | Google Gemini 2.5 Flash (google-genai SDK) |
| 데이터베이스 | SQLite (WAL mode, 인덱싱) |
| 웹 검색 | DuckDuckGo Search |
| 문서 처리 | PyPDF2, pdfplumber, python-docx, openpyxl |
| 빌드 | PyInstaller |
| 테마 | Catppuccin Mocha |

## 아키텍처

```
src/
├── main.py              # Entry point
├── app.py               # Bootstrap (splash, engine/db init)
├── core/
│   ├── api_client.py    # Gemini API 클라이언트
│   ├── engine.py        # AI 엔진 (스트리밍, 이미지 생성)
│   ├── worker.py        # QThread 스트리밍 워커
│   ├── agent.py         # 5개 에이전트 워크플로우
│   ├── database.py      # SQLite CRUD + 인덱싱
│   ├── prompts.py       # 시스템 프롬프트 + 텍스트 처리
│   ├── document_io.py   # PDF/Word/Excel 읽기, Word/PDF 내보내기
│   ├── web_search.py    # DuckDuckGo 검색 + TTL 캐싱
│   ├── media_specs.py   # 8개 매체 광고 규격
│   ├── logger.py        # 파일 로깅 시스템
│   ├── updater.py       # GitHub Release 자동 업데이트
│   └── version.py       # 버전 관리
└── gui/
    ├── main_window.py   # 메인 윈도우 (채팅, 에이전트, 내보내기)
    ├── chat_widget.py   # 메시지 버블 + 마크다운 렌더링
    ├── input_bar.py     # 입력바 (파일/이미지 첨부, 중지 버튼)
    ├── sidebar.py       # 프로젝트/대화/템플릿 관리
    ├── settings_dialog.py  # API 키 설정 + 테스트
    ├── project_dialog.py   # 프로젝트 CRUD
    ├── styles.py        # Catppuccin Mocha QSS
    └── update_dialog.py # 자동 업데이트 UI
```

## 설치 및 실행

### exe 다운로드 (권장)
[최신 릴리즈](https://github.com/dbwjdtn10/4Bro/releases/latest)에서 `4Bro-vX.X.X-win64.zip`을 다운로드하고 압축 해제 후 `4Bro.exe` 실행

### 소스에서 실행
```bash
git clone https://github.com/dbwjdtn10/4Bro.git
cd 4Bro
pip install -r requirements.txt
python src/main.py
```

## API 키 설정
1. [Google AI Studio](https://aistudio.google.com)에서 무료 API 키 발급
2. 앱 실행 → 상단 [설정] → Gemini API 키 입력 → [API 키 테스트]로 확인

## 라이선스
MIT License
