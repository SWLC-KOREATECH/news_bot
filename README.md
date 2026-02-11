# 📰 AI 뉴스 요약 및 자동 발송 봇 (News Bot)

전담자들을 위한 일학습병행 이슈 및 학습기업 관련 뉴스를 매일 아침 AI로 요약하여 이메일로 발송해주는 자동화 시스템입니다.

---

## ⚠️ 필수 보안 주의사항 (중요!)

> [!CAUTION]
> **이 저장소는 반드시 비공개(Private)로 유지해야 합니다.**
> - `config.json`에 검색 키워드 정보가 포함됩니다.
> - GitHub Secrets에 이메일 주소 및 API 키가 저장됩니다.
> - **저장소를 Public으로 설정할 경우, 작성한 키워드나 수집된 데이터 내역이 외부에 노출될 수 있습니다.**

### 1. 템플릿으로 시작하기 (추천)
- 이 저장소 상단의 **[Use this template]** 버튼을 클릭하세요.
- **[Create a new repository]**를 선택합니다.
- 저장소 이름 설정 시 **[Private]**을 반드시 체크하여 생성하세요.
- 이렇게 하면 기존 코드를 그대로 복사하면서도 나만의 비공개 저장소로 안전하게 시작할 수 있습니다.

### 2. 직접 복제하기 (수동)
- 이 저장소의 코드를 ZIP으로 다운로드합니다.
- 본인의 GitHub 계정에 **새로운 저장소(New Repository)**를 만듭니다.
- 설정 화면에서 **Public 대신 [Private]**을 선택합니다.
- 다운로드한 파일들을 새 Private 저장소에 업로드합니다.

---

## 🛠️ 초기 설정 방법 (GitHub Secrets)

이메일 발송 및 AI 요약을 위해 GitHub 저장소 설정에서 아래 변수들을 등록해야 합니다.

1.  본인의 저장소 메뉴에서 **Settings** -> **Secrets and variables** -> **Actions**로 이동합니다.
2.  **New repository secret** 버튼을 눌러 아래 항목들을 하나씩 추가하세요.

| Secret 이름 | 설명 | 예시 |
|-------------|------|------|
| `GEMINI_API_KEY` | Google AI Studio에서 발급받은 Gemini API 키 | `AIzaSy...` |
| `EMAIL_USER` | 알림을 보낼 Gmail 계정 주소 | `yourname@gmail.com` |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 ([발급방법](https://myaccount.google.com/apppasswords)) | `abcd efgh ijkl mnop` |
| `EMAIL_RECEIVER` | 뉴스를 받을 수신자 이메일 (여러 명일 경우 쉼표로 구분) | `user1@test.com, user2@test.com` |

---

## 📝 커스터마이징 가이드

### 1. 검색 키워드 변경하기
`config.json` 파일을 열어 `keywords` 섹션을 수정하세요.

```json
"keywords": [
  {
    "name": "원하는키워드",
    "color": "#색상코드",
    "enabled": true
  }
]
```
*   **주의**: 기업명을 넣을 때 `(주)`, `주식회사` 등은 빼고 핵심 이름만 넣는 것이 검색 결과가 더 잘 나옵니다 (예: `한미약품`).

### 2. 수신자 추가/변경하기
두 가지 방법이 있습니다.
- **간편한 방법**: GitHub Secrets의 `EMAIL_RECEIVER` 값을 수정합니다 (추천).
- **파일 직접 수정**: `config.json`의 `receivers` 배열에 이메일 주소를 추가합니다.

---

## 🚀 작동 원리
1.  **매일 아침 자동 실행**: GitHub Actions가 매일 지정된 시간에 뉴스를 찾습니다.
2.  **구글 뉴스 RSS 크롤링**: 설정된 키워드로 최신 보도 자료를 수집합니다.
3.  **AI 요약 (Gemini 2.0 Flash)**: 복잡한 내용을 핵심/배경/영향 3줄로 요약합니다.
    - *할당량 준수*: 분당 10회 요청 제한을 지키기 위해 기사당 6초의 지연 시간을 가집니다.
4.  **이메일 발송**: 요약된 내용을 깔끔한 HTML 리포트로 발신합니다.

---

## 📄 기술 스택
- **Language**: Python 3.10
- **AI Model**: Google Gemini 2.0 Flash
- **Automation**: GitHub Actions
- **Crawler**: Google News RSS + googlenewsdecoder
