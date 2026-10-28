from fastapi import APIRouter, Request

from app.core.serialize import jsonable
from app.core.templates import templates
from app.services import catalog_service

router = APIRouter(tags=["pages"])


async def _ctx(request: Request, app_mode: str = "admin", **extra):
    meta = await catalog_service.metadata()
    return {
        "request": request,
        "meta": jsonable(meta),
        "app_mode": app_mode,
        "admin_identity": getattr(request.state, "admin_identity", None),
        **extra,
    }


@router.get("/")
async def landing(request: Request):
    return templates.TemplateResponse(
        request=request, name="landing.html", context=await _ctx(request, app_mode="home")
    )


@router.get("/user")
async def user_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="user.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/region")
async def user_region(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_region.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/facilities")
async def user_facilities(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_facilities.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/spaces")
async def user_spaces(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_spaces.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/voice")
async def user_voice(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_voice.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/planner")
async def user_planner(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_planner.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/ask")
async def user_ask(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="agent.html",
        context=await _ctx(request, app_mode="user", agent_mode="user"),
    )


@router.get("/user/guide")
async def user_guide(request: Request):
    return templates.TemplateResponse(
        request=request, name="guide.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/user/help")
async def user_help(request: Request):
    return templates.TemplateResponse(
        request=request, name="user_help.html", context=await _ctx(request, app_mode="user")
    )


@router.get("/gap")
async def gap_index(request: Request):
    return templates.TemplateResponse(
        request=request, name="gap_index.html", context=await _ctx(request)
    )


@router.get("/admin/login")
async def admin_login(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin_login.html", context=await _ctx(request, app_mode="home")
    )


@router.get("/admin/signup")
async def admin_signup(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin_signup.html", context=await _ctx(request, app_mode="home")
    )


@router.get("/admin")
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="admin_dashboard.html", context=await _ctx(request)
    )


@router.get("/gap/{region_code}")
async def gap_detail(request: Request, region_code: str):
    return templates.TemplateResponse(
        request=request,
        name="gap_detail.html",
        context=await _ctx(request, region_code=region_code[:5]),
    )


@router.get("/candidates")
async def candidates_index(request: Request):
    return templates.TemplateResponse(
        request=request, name="candidates.html", context=await _ctx(request, region_code="")
    )


@router.get("/gap/{region_code}/candidates")
async def candidates_page(request: Request, region_code: str):
    return templates.TemplateResponse(
        request=request,
        name="candidates.html",
        context=await _ctx(request, region_code=region_code[:5]),
    )


@router.get("/scenario")
async def scenario_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="scenario.html", context=await _ctx(request)
    )


@router.get("/scenario/compare")
async def compare_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="compare.html", context=await _ctx(request)
    )


@router.get("/scenario/plan")
async def plan_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="plan.html", context=await _ctx(request)
    )


@router.get("/agent")
async def agent_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="agent.html", context=await _ctx(request, agent_mode="admin")
    )


@router.get("/guide")
async def guide_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="guide.html", context=await _ctx(request, app_mode="home")
    )


@router.get("/data")
async def data_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="data_info.html", context=await _ctx(request)
    )
