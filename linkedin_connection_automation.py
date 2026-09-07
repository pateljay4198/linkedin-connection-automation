import os
import time
import random
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

SESSION_FILE = "auth/linkedin_state.json"

def human_delay(min_sec=2, max_sec=5):
    """Randomize wait times to avoid statistical detection"""
    time.sleep(random.uniform(min_sec, max_sec))

def automate_connections_only(search_url, target_invites, max_pages=50):
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    
    successful_invites = 0

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(
                    headless=False,
                    channel="chrome", 
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )    
        
        if os.path.exists(SESSION_FILE):
            print("Found saved session. Loading state...")
            context = browser.new_context(
                storage_state=SESSION_FILE,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"            
            )
            page = context.new_page()
        else:
            print("No saved session. Launching for manual login...")
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/132.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            page.goto("https://www.linkedin.com/login")
            print("Log in manually in the browser window.")
            print("Once you are on the LinkedIn feed, type 'c' and press Enter here in the terminal to continue.")
            input("Waiting for you to log in... ")
            
            context.storage_state(path=SESSION_FILE)
            print(f"Session saved to {SESSION_FILE}!")
        
        print(f"Navigating to search URL...")
        page.goto(search_url)
        page.wait_for_load_state("domcontentloaded")
        human_delay(3, 5)
                
        # --- OUTER LOOP FOR PAGINATION ---
        for current_page in range(1, max_pages + 1):
            
            if successful_invites >= target_invites:
                break
                
            print(f"\n========== PROCESSING PAGE {current_page} ==========")
            
            print("Scrolling to load dynamic profiles...")
            for _ in range(4):
                try:
                    page.mouse.wheel(delta_x=0, delta_y=500)
                except Exception:
                    pass 
                human_delay(1, 2)
            
            print("Waiting for 'Connect' buttons to appear...")
            
            # ULTRA-BROAD LOCATOR: Looks anywhere on the page for links or buttons containing 'to connect' 
            # or exact text 'Connect' (case-insensitive)
            locator_string = (
                "a[aria-label*='to connect' i], "
                "button[aria-label*='to connect' i], "
                "button:has-text('Connect')"
            )
            
            try:
                page.wait_for_selector(locator_string, timeout=7000)
            except Exception:
                print("Could not find any 'Connect' elements on this page.")
                
            connect_buttons = page.locator(locator_string)
            total_buttons = connect_buttons.count()
            
            print(f"Found {total_buttons} 'Connect' buttons on Page {current_page}.")
            
            # --- INNER LOOP FOR PROFILES ---
            # Added min(total_buttons, 10) back so we only process the main feed and ignore the footer
            for i in range(min(total_buttons, 10)):
                
                if successful_invites >= target_invites:
                    break
                    
                try:
                    button = page.locator(locator_string).nth(i)
                    
                    button.evaluate("node => node.scrollIntoView({block: 'center'})")
                    human_delay(1, 3)
                    
                    if button.is_visible():
                        button.click(force=True)
                        human_delay(2, 3)
                        
                        send_button = page.locator("[aria-label='Send without a note'], button:has-text('Send')").first
                        
                        if send_button.is_visible(timeout=5000):
                            send_button.click() # <--- ACTUALLY SENDS THE REQUEST
                            
                            successful_invites += 1
                            print(f"--> Invite sent to profile {i+1} | Total Successful: {successful_invites}/{target_invites}")
                            
                            page.keyboard.press("Escape")
                            human_delay(1, 2)
                        else:
                            print(f"--> Blocked by privacy settings. Skipping.")
                            page.keyboard.press("Escape")
                            human_delay(1, 2)
                            
                except Exception as e:
                    print(f"Skipping profile {i+1} due to UI interruption.")
                    page.keyboard.press("Escape") 
                    human_delay(1, 2)
            
            # End of page check before clicking "Next"
            if successful_invites >= target_invites:
                print(f"\n✅ Target of {target_invites} successful invites reached! Stopping this search.")
                break
                
            # --- PAGINATION LOGIC ---
            if current_page < max_pages:
                print("\nScrolling to the bottom to find the 'Next' page button...")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                human_delay(2, 4)
                
                next_button = page.locator("button[aria-label='Next'], button:has-text('Next')").first
                
                if next_button.is_visible() and not next_button.is_disabled():
                    print(f"Clicking 'Next' to go to Page {current_page + 1}...")
                    next_button.click()
                    page.wait_for_load_state("domcontentloaded")
                    human_delay(3, 5)
                else:
                    print("No more pages found, or 'Next' button is disabled. Finishing up.")
                    break 

        print(f"\nAutomation run complete for this target. Total sent: {successful_invites}/{target_invites}")
        browser.close()

if __name__ == "__main__":
    search_targets = [
        {
            "category_name": "AI Leaders & Data Managers",
            "url": "https://www.linkedin.com/search/results/people/?keywords=(%22Lead%20AI%20Engineer%22%20OR%20%22Senior%20AI%20Engineer%22%20OR%20%22Head%20of%20AI%22%20OR%20%22Director%20of%20Data%20%26%20AI%22%20OR%20%22Data%20Platform%20Manager%22%20OR%20%22AI%20Architect%22)",            "target_count": 80
        },
        {
            "category_name": "Tech Recruiters & HR",
            "url": "https://www.linkedin.com/search/results/people/?keywords=(%22Talent%20Acquisition%22%20OR%20%22Technical%20Recruiter%22%20OR%20%22HR%22)%20AND%20(%22AI%22%20OR%20%22Data%22%20OR%20%22Cloud%22)",
            "target_count": 20
        }
    ]
    
    for i, target in enumerate(search_targets):
        print(f"\n\n*** STARTING NEW SEARCH: {target['category_name']} ***")
        
        automate_connections_only(target['url'], target_invites=target['target_count'], max_pages=50)
        
        if i < len(search_targets) - 1:
            print("Taking a 2-minute break before the next category...")
            time.sleep(120)