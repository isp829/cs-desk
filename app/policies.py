POLICIES = [
    {
        "name": "환불 정책 1조",
        "category": "환불",
        "text": "상품 발송 전에는 환불을 요청할 수 있습니다.",
        "keywords": ("환불", "취소", "발송 전"),
    },
    {
        "name": "환불 정책 2조",
        "category": "환불",
        "text": "배송 완료 후 7일 이내이고 상품이 미개봉이면 환불할 수 있습니다.",
        "keywords": ("환불", "배송 완료", "미개봉", "7일"),
    },
    {
        "name": "교환 정책 1조",
        "category": "교환",
        "text": "교환은 상품 수령 후 7일 이내에 요청할 수 있습니다.",
        "keywords": ("교환", "7일", "수령"),
    },
    {
        "name": "교환 정책 2조",
        "category": "교환",
        "text": "상품의 하자나 오배송은 확인 후 무상 교환을 진행합니다.",
        "keywords": ("교환", "하자", "오배송"),
    },
    {
        "name": "배송 정책 1조",
        "category": "배송",
        "text": "배송준비 상태가 3영업일을 초과하면 배송 지연 안내를 제공합니다.",
        "keywords": ("배송", "배송준비", "지연", "3영업일"),
    },
    {
        "name": "배송 정책 2조",
        "category": "배송",
        "text": "배송중 상품은 택배사 사정에 따라 도착일이 달라질 수 있습니다.",
        "keywords": ("배송", "배송중", "도착"),
    },
]


def search_policies(query: str) -> list[dict[str, str]]:
    lowered = query.lower()
    matches = [
        policy
        for policy in POLICIES
        if policy["category"].lower() in lowered
        or any(keyword.lower() in lowered for keyword in policy["keywords"])
    ]
    return matches or POLICIES