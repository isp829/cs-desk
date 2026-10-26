from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .agents import AnswerInterpretationError, generate_answer_with_retry
from .secrets import load_secrets
from .storage import REFUND_STATUSES, Storage, inquiry_timestamp

try:
    from azure.monitor.opentelemetry import configure_azure_monitor
except ImportError:
    configure_azure_monitor = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
for azure_logger_name in (
    "azure",
    "azure.core",
    "azure.identity",
    "azure.keyvault",
    "azure.data.tables",
):
    logging.getLogger(azure_logger_name).setLevel(logging.WARNING)
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING") and configure_azure_monitor:
        configure_azure_monitor()
    app.state.admin_password = load_secrets()
    app.state.storage = Storage(os.environ.get("STORAGE_TABLE_URL", ""))
    app.state.storage.initialize()
    yield


app = FastAPI(title="쇼핑몰 문의 응대 데스크", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent.parent / "static")), name="static")


def storage_from(request: Request) -> Storage:
    return request.app.state.storage


@app.get("/", response_class=HTMLResponse)
async def home() -> RedirectResponse:
    return RedirectResponse("/inquiries", status_code=303)


@app.get("/inquiries", response_class=HTMLResponse)
async def inquiries(request: Request, status: str = "전체"):
    selected_status = status if status in REFUND_STATUSES else "전체"
    try:
        items = storage_from(request).list_inquiries(
            None if selected_status == "전체" else selected_status
        )
        error = None
    except Exception:
        logger.exception("문의 목록 조회 실패")
        items = []
        error = "일시적인 저장 오류입니다"
    return templates.TemplateResponse(
        request=request,
        name="inquiries.html",
        context={"inquiries": items, "selected_status": selected_status, "error": error},
    )


@app.post("/inquiries/process", response_class=HTMLResponse)
async def process_inquiry(
    request: Request,
    customer_name: str = Form(""),
    order_number: str = Form(""),
    inquiry_text: str = Form(""),
):
    order_number = order_number.strip().upper()
    storage = storage_from(request)
    try:
        order = storage.get_order(order_number) if order_number else None
    except Exception:
        logger.exception("주문 조회 실패")
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": [],
                "selected_status": "전체",
                "error": "일시적인 저장 오류입니다",
            },
            status_code=503,
        )
    if not order:
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": storage.list_inquiries(),
                "selected_status": "전체",
                "error": "주문번호를 확인해 주세요",
                "form_values": {
                    "customer_name": customer_name,
                    "order_number": order_number,
                    "inquiry_text": inquiry_text,
                },
            },
            status_code=400,
        )
    if not inquiry_text.strip():
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": storage.list_inquiries(),
                "selected_status": "전체",
                "error": "문의 내용을 입력해 주세요",
                "form_values": {
                    "customer_name": customer_name,
                    "order_number": order_number,
                    "inquiry_text": inquiry_text,
                },
            },
            status_code=400,
        )
    try:
        result, evidence = await generate_answer_with_retry(
            storage, customer_name, order_number, inquiry_text
        )
        inquiry = {
            "id": str(uuid4()),
            "customer_name": customer_name,
            "order_number": order_number,
            "inquiry_text": inquiry_text,
            "category": result["category"],
            "anger": result["anger"],
            "reply": result["reply"],
            "evidence": evidence,
            "refund_status": "환불 대기" if result["needs_refund"] else "없음",
            "created_at": inquiry_timestamp(),
        }
        storage.save_inquiry(inquiry)
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"inquiry": inquiry},
        )
    except AnswerInterpretationError as error:
        logger.exception("AI 결과 해석 실패: %s", error)
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": storage.list_inquiries(),
                "selected_status": "전체",
                "error": str(error),
            },
            status_code=502,
        )
    except (RuntimeError, TimeoutError):
        logger.exception("AI 답변 생성 실패")
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": storage.list_inquiries(),
                "selected_status": "전체",
                "error": "답변 생성에 실패했습니다. 다시 시도해 주세요",
            },
            status_code=502,
        )
    except Exception:
        logger.exception("문의 처리 중 저장 오류")
        return templates.TemplateResponse(
            request=request,
            name="inquiries.html",
            context={
                "inquiries": storage.list_inquiries(),
                "selected_status": "전체",
                "error": "일시적인 저장 오류입니다",
            },
            status_code=503,
        )


@app.get("/inquiries/{inquiry_id}", response_class=HTMLResponse)
async def inquiry_detail(request: Request, inquiry_id: str, error: str | None = None):
    inquiry = storage_from(request).get_inquiry(inquiry_id)
    if not inquiry:
        return RedirectResponse("/inquiries", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"inquiry": inquiry, "error": error},
    )


@app.post("/inquiries/{inquiry_id}/approve")
async def approve_inquiry(request: Request, inquiry_id: str):
    try:
        storage_from(request).update_refund_status(inquiry_id, "환불완료")
    except Exception:
        logger.exception("환불 승인 저장 실패")
        return RedirectResponse(
            f"/inquiries/{inquiry_id}?error=일시적인 저장 오류입니다",
            status_code=303,
        )
    return RedirectResponse(f"/inquiries/{inquiry_id}", status_code=303)


@app.post("/inquiries/{inquiry_id}/reject")
async def reject_inquiry(request: Request, inquiry_id: str):
    try:
        storage_from(request).update_refund_status(inquiry_id, "반려")
    except Exception:
        logger.exception("환불 반려 저장 실패")
        return RedirectResponse(
            f"/inquiries/{inquiry_id}?error=일시적인 저장 오류입니다",
            status_code=303,
        )
    return RedirectResponse(f"/inquiries/{inquiry_id}", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={})


@app.post("/admin/reset", response_class=HTMLResponse)
async def admin_reset(request: Request, admin_password: str = Form("")):
    if admin_password != request.app.state.admin_password:
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"error": "관리자 비밀번호가 올바르지 않습니다"},
            status_code=403,
        )
    try:
        storage_from(request).clear_and_seed()
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"message": "샘플 데이터로 초기화했습니다"},
        )
    except Exception:
        logger.exception("데이터 초기화 실패")
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={"error": "일시적인 저장 오류입니다"},
            status_code=503,
        )