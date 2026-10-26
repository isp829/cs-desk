from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any

from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential


ORDER_TABLE = "orders"
INQUIRY_TABLE = "inquiries"
DELIVERY_STATUSES = ("배송준비", "배송중", "배송완료")
REFUND_STATUSES = ("없음", "환불 대기", "환불완료", "반려")


class Storage:
    def __init__(self, endpoint: str) -> None:
        if not endpoint:
            raise RuntimeError("STORAGE_TABLE_URL 환경변수가 필요합니다")
        self.service = TableServiceClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )
        self.orders = self.service.get_table_client(ORDER_TABLE)
        self.inquiries = self.service.get_table_client(INQUIRY_TABLE)

    def initialize(self) -> None:
        self.service.create_table_if_not_exists(ORDER_TABLE)
        self.service.create_table_if_not_exists(INQUIRY_TABLE)
        if not any(self.orders.list_entities(results_per_page=1)):
            self.seed_orders()

    def seed_orders(self) -> None:
        for number in range(1001, 1021):
            entity = {
                "PartitionKey": "orders",
                "RowKey": f"ORD-{number}",
                "order_number": f"ORD-{number}",
                "customer_name": f"고객 {number - 1000}",
                "contact": f"010-5555-{number - 1000:04d}",
                "product_name": random.choice(("무선 이어폰", "텀블러", "노트북 파우치", "생활용품 세트")),
                "amount": random.choice((29000, 39000, 59000, 89000)),
                "order_date": f"2026-10-{(number - 1000):02d}",
                "delivery_status": DELIVERY_STATUSES[(number - 1001) % len(DELIVERY_STATUSES)],
                "refund_status": "없음",
            }
            self.orders.upsert_entity(entity)

    def clear_and_seed(self) -> None:
        for table in (self.orders, self.inquiries):
            for entity in table.list_entities():
                table.delete_entity(entity["PartitionKey"], entity["RowKey"])
        self.seed_orders()

    def get_order(self, order_number: str) -> dict[str, Any] | None:
        if not order_number:
            return None
        try:
            entity = self.orders.get_entity("orders", order_number.strip().upper())
        except Exception as error:
            if getattr(error, "status_code", None) == 404:
                return None
            raise
        result = dict(entity)
        result.pop("PartitionKey", None)
        result.pop("RowKey", None)
        return result

    def get_masked_order(self, order_number: str) -> dict[str, Any] | None:
        order = self.get_order(order_number)
        if not order:
            return None
        order["contact"] = mask_contact(str(order.get("contact", "")))
        return order

    def save_inquiry(self, inquiry: dict[str, Any]) -> None:
        entity = {
            "PartitionKey": "inquiries",
            "RowKey": inquiry["id"],
            **inquiry,
            "evidence": json.dumps(inquiry["evidence"], ensure_ascii=False),
        }
        self.inquiries.upsert_entity(entity)

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any] | None:
        try:
            entity = self.inquiries.get_entity("inquiries", inquiry_id)
        except Exception as error:
            if getattr(error, "status_code", None) == 404:
                return None
            raise
        return self._normalize_inquiry(entity)

    def list_inquiries(self, refund_status: str | None = None) -> list[dict[str, Any]]:
        inquiries = [
            self._normalize_inquiry(entity)
            for entity in self.inquiries.list_entities()
        ]
        if refund_status in REFUND_STATUSES:
            inquiries = [
                inquiry
                for inquiry in inquiries
                if inquiry["refund_status"] == refund_status
            ]
        return sorted(
            inquiries,
            key=lambda inquiry: (-int(inquiry.get("anger", 0)), inquiry["created_at"]),
        )

    def update_refund_status(self, inquiry_id: str, status: str) -> dict[str, Any] | None:
        inquiry = self.get_inquiry(inquiry_id)
        if not inquiry:
            return None
        inquiry["refund_status"] = status
        self.save_inquiry(inquiry)
        order = self.get_order(inquiry["order_number"])
        if order:
            order["refund_status"] = status
            self.orders.upsert_entity(
                {
                    "PartitionKey": "orders",
                    "RowKey": order["order_number"],
                    **order,
                }
            )
        return inquiry

    @staticmethod
    def _normalize_inquiry(entity: dict[str, Any]) -> dict[str, Any]:
        result = dict(entity)
        result.pop("PartitionKey", None)
        result.pop("RowKey", None)
        raw_evidence = result.get("evidence", "[]")
        try:
            result["evidence"] = json.loads(raw_evidence)
        except (TypeError, json.JSONDecodeError):
            result["evidence"] = []
        return result


def mask_contact(contact: str) -> str:
    if contact.startswith("010-") and len(contact.split("-")) == 3:
        prefix, middle, suffix = contact.split("-")
        return f"{prefix}-****-{suffix}"
    if len(contact) > 4:
        return f"{'*' * (len(contact) - 4)}{contact[-4:]}"
    return "****"


def inquiry_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()