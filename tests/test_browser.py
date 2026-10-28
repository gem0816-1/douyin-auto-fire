import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.browser import (
    AuthenticationError,
    RiskControlError,
    SearchBoxNotReadyError,
    _collect_safe_diagnostic,
    _normalize_cookies,
    _safe_url,
    _wait_for_conversation_list,
    open_private_messages,
)
from app.config import ConfigError
from app.selectors import DOUYIN_CHAT_URL, LOGIN_REQUIRED_MARKERS, RISK_MARKERS


@pytest.fixture(autouse=True)
def list_wait(monkeypatch):
    wait = AsyncMock(return_value=True)
    monkeypatch.setattr("app.browser._wait_for_conversation_list", wait)
    return wait


@pytest.mark.asyncio
async def test_opens_chat_directly_before_checking_login() -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    with patch("app.browser._any_visible", new=AsyncMock(side_effect=[False, False])):
        with patch("app.browser._first_visible_selector", new=AsyncMock(return_value='input[placeholder*="搜索"]')):
            await open_private_messages(page)

    page.goto.assert_awaited_once_with(DOUYIN_CHAT_URL, wait_until="domcontentloaded", timeout=45_000)


def test_safe_url_strips_query_and_fragment() -> None:
    assert _safe_url("https://www.douyin.com/chat?token=SECRET&x=1#frag") == "https://www.douyin.com/chat"
    assert _safe_url("https://www.douyin.com/chat") == "https://www.douyin.com/chat"
    assert _safe_url("") == ""


@pytest.mark.asyncio
async def test_safe_diagnostic_excludes_content_and_nicknames() -> None:
    page = MagicMock()
    page.url = "https://www.douyin.com/chat?token=COOKIE_SECRET"
    page.title = AsyncMock(return_value="抖音私信")
    page.evaluate = AsyncMock(
        return_value={
            "inputs": [
                {
                    "tag": "input",
                    "type": "text",
                    "placeholder": "搜索联系人",
                    "role": None,
                    "aria_label": None,
                    "value": "张三 聊天内容",
                }
            ],
            "textareas": [{"tag": "textarea", "placeholder": "搜索", "role": None, "aria_label": None, "value": "body-inner-text"}],
            "contenteditable_count": 2,
            "role_textbox_count": 3,
        }
    )

    with patch("app.browser._any_visible", new=AsyncMock(return_value=False)):
        diagnostic = await _collect_safe_diagnostic(page, LOGIN_REQUIRED_MARKERS, RISK_MARKERS)

    # Safe attributes must show up.
    assert "url=https://www.douyin.com/chat" in diagnostic
    assert "title=抖音私信" in diagnostic
    assert '"placeholder": "搜索联系人"' in diagnostic
    assert "role_textbox_count=3" in diagnostic
    assert "contenteditable_count=2" in diagnostic
    assert "login_marker=false" in diagnostic
    assert "risk_marker=false" in diagnostic
    assert "private_marker=false" in diagnostic

    # Forbidden content must never leak.
    assert "COOKIE_SECRET" not in diagnostic
    assert "张三" not in diagnostic
    assert "聊天内容" not in diagnostic
    assert "body-inner-text" not in diagnostic
    assert "token=" not in diagnostic


@pytest.mark.asyncio
async def test_open_private_messages_logs_diagnostic_when_search_missing(caplog) -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    page.reload = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.url = "https://www.douyin.com/chat"
    page.title = AsyncMock(return_value="抖音私信")
    page.evaluate = AsyncMock(
        return_value={
            "inputs": [],
            "textareas": [],
            "contenteditable_count": 0,
            "role_textbox_count": 0,
        }
    )

    with patch("app.browser._any_visible", new=AsyncMock(return_value=False)):
        with patch("app.browser._first_visible_selector", new=AsyncMock(return_value=None)):
            with caplog.at_level(logging.ERROR, logger="douyin_sender"):
                with pytest.raises(SearchBoxNotReadyError, match="重试后仍未就绪"):
                    await open_private_messages(page)

    assert "多次重试后仍未检测到好友搜索框，页面安全诊断" in caplog.text
    assert "role_textbox_count=0" in caplog.text


@pytest.mark.asyncio
async def test_search_hit_waits_for_list_without_diagnostic(caplog, list_wait) -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    with patch("app.browser._any_visible", new=AsyncMock(side_effect=[False, False])):
        with patch("app.browser._first_visible_selector", new=AsyncMock(return_value='input[placeholder*="搜索"]')):
            with caplog.at_level(logging.ERROR, logger="douyin_sender"):
                await open_private_messages(page)

    assert "页面安全诊断" not in caplog.text
    list_wait.assert_awaited_once_with(page, 60_000)
    page.wait_for_timeout.assert_not_awaited()


@pytest.mark.asyncio
async def test_conversation_list_waits_for_delayed_rows(monkeypatch) -> None:
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.locator.return_value.count = AsyncMock(side_effect=[0, 0, 32])
    monkeypatch.setattr("app.browser._any_visible_now", AsyncMock(return_value=False))

    assert await _wait_for_conversation_list(page, 60_000) is True

    assert page.wait_for_timeout.await_count == 2
    # Hidden cached rows must not satisfy readiness.
    selector = page.locator.call_args.args[0]
    assert all(part.strip().endswith(":visible") for part in selector.split(","))


@pytest.mark.asyncio
async def test_empty_conversation_list_has_bounded_wait(monkeypatch, caplog) -> None:
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.locator.return_value.count = AsyncMock(return_value=0)
    monkeypatch.setattr("app.browser._any_visible_now", AsyncMock(return_value=False))
    loop = MagicMock()
    loop.time.side_effect = [0, 0, 0, 0.2]
    monkeypatch.setattr("app.browser.asyncio.get_running_loop", lambda: loop)

    with caplog.at_level(logging.WARNING, logger="douyin_sender"):
        assert await _wait_for_conversation_list(page, 200) is False

    page.wait_for_timeout.assert_awaited_once_with(200)
    assert "列表仍为空" in caplog.text
    assert "继续尝试好友搜索" in caplog.text


@pytest.mark.asyncio
async def test_conversation_sync_stops_if_risk_appears(monkeypatch) -> None:
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.locator.return_value.count = AsyncMock(return_value=0)
    monkeypatch.setattr(
        "app.browser._any_visible_now", AsyncMock(side_effect=[False, False, True])
    )

    with pytest.raises(RiskControlError, match="同步私信列表"):
        await _wait_for_conversation_list(page, 60_000)

    page.wait_for_timeout.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversation_sync_detects_expired_login(monkeypatch) -> None:
    page = MagicMock()
    monkeypatch.setattr(
        "app.browser._any_visible_now", AsyncMock(side_effect=[False, True])
    )

    with pytest.raises(AuthenticationError, match="同步私信列表时登录状态失效"):
        await _wait_for_conversation_list(page, 60_000)


@pytest.mark.asyncio
async def test_conversation_list_uses_requested_timeout(list_wait) -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    with patch("app.browser._any_visible", new=AsyncMock(return_value=False)):
        with patch("app.browser._first_visible_selector", new=AsyncMock(return_value='input[placeholder="搜索"]')):
            await open_private_messages(page, list_timeout_ms=25_000)

    list_wait.assert_awaited_once_with(page, 25_000)


@pytest.mark.asyncio
async def test_search_box_missing_recovers_on_retry() -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    page.reload = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    # 首轮未就绪，reload 后第二轮命中；login/risk 标记始终不出现。
    with patch("app.browser._any_visible", new=AsyncMock(return_value=False)):
        with patch(
            "app.browser._first_visible_selector",
            new=AsyncMock(side_effect=[None, 'input[placeholder="搜索"]']),
        ):
            await open_private_messages(page)

    page.reload.assert_awaited_once_with(wait_until="domcontentloaded", timeout=45_000)


@pytest.mark.asyncio
async def test_search_box_falls_back_to_goto_when_reload_fails() -> None:
    page = MagicMock()
    page.goto = AsyncMock()
    page.reload = AsyncMock(side_effect=RuntimeError("reload 失败"))
    page.wait_for_timeout = AsyncMock()

    with patch("app.browser._any_visible", new=AsyncMock(return_value=False)):
        with patch(
            "app.browser._first_visible_selector",
            new=AsyncMock(side_effect=[None, 'input[placeholder*="搜索"]']),
        ):
            await open_private_messages(page)

    page.reload.assert_awaited_once()
    assert page.goto.await_count >= 2  # 初次访问 + reload 失败后的重新访问


@pytest.mark.asyncio
async def test_risk_control_still_raises_before_search_check() -> None:
    page = MagicMock()
    page.goto = AsyncMock()

    with patch("app.browser._any_visible", new=AsyncMock(return_value=True)):
        with pytest.raises(RiskControlError, match="安全验证"):
            await open_private_messages(page)


@pytest.mark.asyncio
async def test_login_required_still_raises_before_search_check() -> None:
    page = MagicMock()
    page.goto = AsyncMock()

    with patch("app.browser._any_visible", new=AsyncMock(side_effect=[False, True])):
        with pytest.raises(AuthenticationError, match="登录状态失效"):
            await open_private_messages(page)


def test_normalizes_cookie_editor_export() -> None:
    cookies = [
        {
            "domain": ".douyin.com",
            "expirationDate": 1800175766.5,
            "hostOnly": False,
            "httpOnly": True,
            "name": "UIFID",
            "path": "/",
            "sameSite": "no_restriction",
            "secure": True,
            "session": False,
            "storeId": None,
            "value": "token",
        }
    ]

    assert _normalize_cookies(cookies) == [
        {
            "name": "UIFID",
            "value": "token",
            "domain": ".douyin.com",
            "path": "/",
            "expires": 1800175766.5,
            "httpOnly": True,
            "secure": True,
            "sameSite": "None",
        }
    ]


def test_session_cookie_ignores_expiration_date() -> None:
    cookies = [
        {
            "domain": ".douyin.com",
            "expirationDate": 1800175766.5,
            "name": "sessionid",
            "session": True,
            "value": "token",
        }
    ]

    assert _normalize_cookies(cookies)[0]["expires"] == -1


def test_ignores_cookie_editor_empty_name_artifact() -> None:
    cookies = [
        {"domain": "www.douyin.com", "name": "", "value": "douyin.com"},
        {"domain": ".douyin.com", "name": "sessionid", "value": "token"},
    ]

    assert [cookie["name"] for cookie in _normalize_cookies(cookies)] == ["sessionid"]


def test_rejects_cookie_without_domain() -> None:
    with pytest.raises(ConfigError, match="缺少有效的 domain"):
        _normalize_cookies([{"name": "UIFID", "value": "token"}])
