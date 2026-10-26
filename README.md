소규모 쇼핑몰 운영자를 위한 근거 기반 고객 문의 응대 웹 앱입니다.

대상 사용자: 하루 수십 건의 고객 문의를 직접 처리하는 소규모 온라인 쇼핑몰 운영자

기획서: [기획서(PRD).md](<기획서(PRD).md>)

배포 링크: https://cs-desk-isp829.azurewebsites.net

## 구성 요약

- Agent Framework 순차 워크플로(분류 → 답변, 도구 2개)
- Azure Table Storage
- Azure Key Vault
- Managed Identity
- Application Insights

## 로컬 실행

```powershell
az login
$env:KEY_VAULT_URL="https://csdesk-kv-isp829.vault.azure.net/"
$env:STORAGE_TABLE_URL="https://csdeskisp829.table.core.windows.net"
$env:APPLICATIONINSIGHTS_CONNECTION_STRING="Application Insights 연결 문자열"
npm install -g @github/copilot
uvicorn app.main:app
```

애플리케이션 시작 시 Managed Identity 기반으로 Key Vault의 `GITHUB-TOKEN`, `ADMIN-PASSWORD`를 읽습니다. Application Insights 연결 문자열이 없으면 모니터링 설정을 건너뜁니다.

## 사용 예시

- 샘플 주문번호: `ORD-1001` ~ `ORD-1020`
- `고객명 고객 3 / ORD-1003 / 배송이 언제 오나요?`
- `고객명 고객 7 / ORD-1007 / 환불해 주세요`
- AI 응답까지 1~2분 걸릴 수 있습니다.