"""FastAPI application: pages + JSON API for the watch market dashboard."""

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from watchscraper.database import get_session
from watchscraper.models import PortfolioHolding
from watchscraper.web import portfolio as portfolio_svc
from watchscraper.web import services

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Complications — watch market intelligence")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ── Pages ─────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {"nav": "dashboard"})


@app.get("/watches", response_class=HTMLResponse)
def page_watches(request: Request):
    return templates.TemplateResponse(request, "watches.html", {"nav": "watches"})


@app.get("/watches/{slug}", response_class=HTMLResponse)
def page_family(request: Request, slug: str):
    snapshot = services.get_market()
    row = snapshot.family_row(slug)
    if row is None:
        raise HTTPException(404, "Unknown watch family")
    return templates.TemplateResponse(
        request,
        "family.html",
        {"nav": "watches", "slug": slug, "family": row["family"], "brand": row["brand"]},
    )


@app.get("/refs/{slug}", response_class=HTMLResponse)
def page_ref(request: Request, slug: str):
    snapshot = services.get_market()
    row = snapshot.ref_row(slug)
    if row is None:
        raise HTTPException(404, "Unknown reference")
    return templates.TemplateResponse(
        request,
        "ref.html",
        {"nav": "watches", "slug": slug, "ref": row["ref"], "brand": row["brand"]},
    )


@app.get("/buying-guide", response_class=HTMLResponse)
def page_buying_guide(request: Request):
    return templates.TemplateResponse(request, "buying_guide.html", {"nav": "guide"})


@app.get("/portfolio", response_class=HTMLResponse)
def page_portfolio(request: Request):
    return templates.TemplateResponse(request, "portfolio.html", {"nav": "portfolio"})


# ── Market API ────────────────────────────────────────────────────────────


@app.get("/api/overview")
def api_overview():
    return services.overview_payload(services.get_market())


@app.get("/api/families")
def api_families():
    return {"families": services.signals_payload(services.get_market())}


@app.get("/api/families/{slug}")
def api_family(slug: str):
    payload = services.family_detail_payload(services.get_market(), slug)
    if payload is None:
        raise HTTPException(404, "Unknown watch family")
    return payload


@app.get("/api/refs")
def api_refs():
    return {"refs": services.refs_payload(services.get_market())}


@app.get("/api/refs/{slug}")
def api_ref(slug: str):
    payload = services.ref_detail_payload(services.get_market(), slug)
    if payload is None:
        raise HTTPException(404, "Unknown reference")
    return payload


@app.get("/api/buying-guide")
def api_buying_guide():
    return {"candidates": services.buying_guide_payload(services.get_market())}


# ── Portfolio API ─────────────────────────────────────────────────────────


class HoldingIn(BaseModel):
    brand: str = Field(min_length=1, max_length=100)
    family: str = Field(min_length=1, max_length=100)
    nickname: str | None = Field(default=None, max_length=200)
    reference_number: str | None = Field(default=None, max_length=50)
    purchase_price_usd: float | None = Field(default=None, gt=0)
    purchase_date: date | None = None
    condition: str | None = Field(default=None, max_length=20)
    notes: str | None = None


def _holding_dicts() -> list[dict]:
    session = get_session()
    try:
        rows = session.query(PortfolioHolding).order_by(PortfolioHolding.id).all()
        return [
            {
                "id": r.id,
                "nickname": r.nickname,
                "brand": r.brand,
                "family": r.family,
                "reference_number": r.reference_number,
                "purchase_price_usd": r.purchase_price_usd,
                "purchase_date": r.purchase_date,
                "condition": r.condition,
                "notes": r.notes,
            }
            for r in rows
        ]
    finally:
        session.close()


@app.get("/api/portfolio")
def api_portfolio():
    snapshot = services.get_market()
    return portfolio_svc.value_holdings(
        _holding_dicts(), snapshot.weekly, ref_values=snapshot.ref_values
    )


@app.post("/api/portfolio/holdings", status_code=201)
def api_add_holding(holding: HoldingIn):
    snapshot = services.get_market()
    known = set(snapshot.signals["family"])
    if holding.family not in known:
        raise HTTPException(422, f"Unknown family '{holding.family}'")
    session = get_session()
    try:
        row = PortfolioHolding(**holding.model_dump())
        session.add(row)
        session.commit()
        return {"id": row.id}
    finally:
        session.close()


@app.delete("/api/portfolio/holdings/{holding_id}", status_code=204)
def api_delete_holding(holding_id: int):
    session = get_session()
    try:
        row = session.get(PortfolioHolding, holding_id)
        if row is None:
            raise HTTPException(404, "Holding not found")
        session.delete(row)
        session.commit()
    finally:
        session.close()


@app.post("/api/refresh")
def api_refresh():
    services.get_market(refresh=True)
    return {"ok": True}
