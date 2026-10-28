from unittest.mock import AsyncMock

import pytest
from playwright.async_api import async_playwright

from app.browser import AuthenticationError, RiskControlError, _first_visible_selector, verify_login
from app.douyin import PageOperationError, first_visible


@pytest.fixture
async def page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        yield page
        await browser.close()


@pytest.mark.asyncio
async def test_visible_fallback_does_not_wait_for_missing_selectors(page, monkeypatch):
    await page.set_content('<div class="editor" hidden></div><div class="editor">ready</div>')
    monkeypatch.setattr(page, "wait_for_timeout", AsyncMock(side_effect=AssertionError("unnecessary wait")))

    editor = await first_visible(page, (".old-editor", ".editor"), timeout_ms=60_000)

    assert await editor.inner_text() == "ready"


@pytest.mark.asyncio
async def test_element_lookup_waits_for_delayed_mount(page):
    await page.set_content('<script>setTimeout(() => document.body.innerHTML = \'<input class="editor">\', 150)</script>')

    editor = await first_visible(page, (".old-editor", ".editor"), timeout_ms=2_000)

    assert await editor.is_visible()


@pytest.mark.asyncio
async def test_missing_elements_share_one_timeout(page, monkeypatch):
    wait = AsyncMock(side_effect=AssertionError("timeout exhausted"))
    monkeypatch.setattr(page, "wait_for_timeout", wait)

    with pytest.raises(PageOperationError):
        await first_visible(page, (".missing-a", ".missing-b"), timeout_ms=0)
    assert await _first_visible_selector(page, (".missing-a", ".missing-b"), 0) is None
    wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_verification_does_not_wait_for_absent_prompts(page, monkeypatch):
    await page.set_content('<input placeholder="搜索">')
    monkeypatch.setattr(page, "wait_for_timeout", AsyncMock(side_effect=AssertionError("unnecessary wait")))

    await verify_login(page, timeout_ms=3_000)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("prompt", "error"), [("安全验证", RiskControlError), ("扫码登录", AuthenticationError)]
)
async def test_login_checks_prompts_before_accepting_search_input(page, prompt, error):
    await page.set_content(f'<input placeholder="搜索"><div>{prompt}</div>')

    with pytest.raises(error):
        await verify_login(page, timeout_ms=3_000)


@pytest.mark.asyncio
async def test_login_detects_risk_prompt_appearing_during_wait(page):
    await page.set_content('<script>setTimeout(() => document.body.innerHTML = "安全验证", 100)</script>')

    with pytest.raises(RiskControlError):
        await verify_login(page, timeout_ms=250)
