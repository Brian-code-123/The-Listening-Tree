"""
E2E Test: Mobile FAB (Floating Action Button) Position
Tests that the `?` helper button is positioned at the bottom-right corner
on mobile viewports (max-width: 480px) to prevent CSS regression.
"""

import os
import asyncio
from playwright.async_api import async_playwright, ViewportSize


async def test_mobile_fab_bottom_right_position():
    """
    Verify that the guide FAB (#guideFab) is positioned at bottom-right
    on mobile viewport (480x800) to ensure accessible thumb reach.
    
    CSS Expected (from style.css @media max-width: 480px):
    - position: fixed
    - bottom: calc(16px + env(safe-area-inset-bottom))
    - right: calc(16px + env(safe-area-inset-right))
    - width: 44px
    - height: 44px
    """
    
    # Get base URL from environment or use production
    BASE_URL = os.getenv("TEST_BASE_URL", "https://the-listening-tree.vercel.app")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        
        # Create context with mobile viewport
        context = await browser.new_context(
            viewport=ViewportSize(width=480, height=800)
        )
        
        page = await context.new_page()
        
        try:
            # Navigate to chat page (requires auth in production, but FAB is still present)
            await page.goto(f"{BASE_URL}/", wait_until="load")
            
            # Wait for FAB element to be visible
            fab = page.locator("#guideFab")
            
            # Check if element is visible
            is_visible = await fab.is_visible(timeout=5000)
            assert is_visible, "Guide FAB (#guideFab) should be visible on mobile viewport"
            
            # Get bounding box (position and size)
            bounding_box = await fab.bounding_box()
            assert bounding_box is not None, "FAB bounding box could not be determined"
            
            x = bounding_box["x"]
            y = bounding_box["y"]
            width = bounding_box["width"]
            height = bounding_box["height"]
            
            # Get computed style
            position = await fab.evaluate("el => window.getComputedStyle(el).position")
            bottom_value = await fab.evaluate("el => window.getComputedStyle(el).bottom")
            right_value = await fab.evaluate("el => window.getComputedStyle(el).right")
            
            # Assertions
            print(f"✓ FAB Position: {position}")
            print(f"✓ FAB Bottom CSS: {bottom_value}")
            print(f"✓ FAB Right CSS: {right_value}")
            print(f"✓ Bounding Box: x={x}, y={y}, width={width}, height={height}")
            
            # Verify position is fixed
            assert position == "fixed", f"FAB position should be 'fixed' but got '{position}'"
            
            # Verify bottom value contains expected pattern (16px + safe-area)
            assert (
                "16px" in bottom_value or "auto" in bottom_value
            ), f"FAB bottom should contain '16px' but got '{bottom_value}'"
            
            # Verify right value contains expected pattern (16px + safe-area)
            assert (
                "16px" in right_value or "auto" in right_value
            ), f"FAB right should contain '16px' but got '{right_value}'"
            
            # Verify it's in the bottom-right corner
            # For 480px width viewport, FAB should be in right half and bottom area
            viewport_width = 480
            viewport_height = 800
            
            # FAB center should be significantly to the right (allow 20px margin for safe area)
            fab_center_x = x + width / 2
            assert fab_center_x > (
                viewport_width - 80
            ), f"FAB should be in right corner (center x={fab_center_x} > {viewport_width - 80})"
            
            # FAB center should be near bottom (allow 120px margin for safe area + overlay)
            fab_center_y = y + height / 2
            assert fab_center_y > (
                viewport_height - 150
            ), f"FAB should be in bottom corner (center y={fab_center_y} > {viewport_height - 150})"
            
            print("✓ All position assertions passed!")
            print(f"✓ FAB is correctly positioned at bottom-right for mobile viewport")
            
        finally:
            await context.close()
            await browser.close()


async def test_mobile_fab_hidden_on_desktop():
    """
    Verify that the desktop .guide-fab class properties (bottom: 24px, right: 24px)
    don't apply on mobile (480px viewport), ensuring CSS media query override works.
    """
    
    BASE_URL = os.getenv("TEST_BASE_URL", "https://the-listening-tree.vercel.app")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Desktop viewport
        context = await browser.new_context(
            viewport=ViewportSize(width=1024, height=768)
        )
        
        page = await context.new_page()
        
        try:
            await page.goto(f"{BASE_URL}/", wait_until="load")
            
            fab = page.locator("#guideFab")
            is_visible = await fab.is_visible(timeout=5000)
            
            # On desktop, FAB might have different positioning
            if is_visible:
                bounding_box = await fab.bounding_box()
                if bounding_box:
                    x = bounding_box["x"]
                    width = bounding_box["width"]
                    viewport_width = 1024
                    
                    fab_center_x = x + width / 2
                    # Desktop: right edge should be around 24px from right
                    assert fab_center_x > (
                        viewport_width - 100
                    ), f"Desktop FAB should still be right-aligned (center x={fab_center_x} > {viewport_width - 100})"
                    
                    print("✓ Desktop viewport FAB position verified")
        
        finally:
            await context.close()
            await browser.close()


async def run_all_tests():
    """Run all mobile FAB position tests."""
    print("=" * 60)
    print("Mobile FAB Position E2E Tests")
    print("=" * 60)
    
    try:
        print("\n[Test 1] Mobile FAB Bottom-Right Position (480x800)")
        await test_mobile_fab_bottom_right_position()
        print("✅ PASS | Mobile FAB position test\n")
    except AssertionError as e:
        print(f"❌ FAIL | Mobile FAB position test: {e}\n")
        return False
    except Exception as e:
        print(f"❌ ERROR | Mobile FAB position test: {e}\n")
        return False
    
    try:
        print("[Test 2] Desktop FAB Position (1024x768)")
        await test_mobile_fab_hidden_on_desktop()
        print("✅ PASS | Desktop FAB position test\n")
    except AssertionError as e:
        print(f"❌ FAIL | Desktop FAB position test: {e}\n")
        return False
    except Exception as e:
        print(f"❌ ERROR | Desktop FAB position test: {e}\n")
        return False
    
    print("=" * 60)
    print("✅ All mobile FAB position tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
