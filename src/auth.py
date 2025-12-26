import os
import json
import time
import requests
from rich.console import Console
from rich.prompt import Prompt

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

COOKIES_FILE = 'cookies.json'

def load_session(console: Console = None):
    """
    Loads a requests Session with cookies from cookies.json.
    """
    if console is None:
        console = Console()

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    if os.path.exists(COOKIES_FILE):
        try:
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            
            if isinstance(cookies, list):
                # EditThisCookie format (list of dicts)
                # Simplify: Convert to dict {name: value} to ensure they are sent.
                # This bypasses strict domain matching which can cause issues if domains don't match exactly.
                cookie_dict = {}
                for cookie in cookies:
                    name = cookie.get('name')
                    value = cookie.get('value')
                    if name and value:
                        cookie_dict[name] = value
                session.cookies.update(cookie_dict)
            else:
                # Python cookiejar dict format
                requests.utils.add_dict_to_cookiejar(session.cookies, cookies)
                
            console.print(f"[green]✔ Loaded cookies from {COOKIES_FILE}[/green]")
        except Exception as e:
            console.print(f"[red]✖ Error loading cookies: {e}[/red]")
    else:
        console.print(f"[yellow]⚠ {COOKIES_FILE} not found. Content access may fail.[/yellow]")
    
    return session

def login_with_selenium(username, password, console):
    """
    Uses Selenium to log in and save cookies.
    """
    console.print("[cyan]Launching Browser (Chrome) for automated login...[/cyan]")
    
    options = Options()
    # options.add_argument("--headless") # Commented out to verify login visually
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 1. Go to LearnUs Login
        login_url = "https://ys.learnus.org"
        driver.get(login_url)
        driver.find_element(By.CLASS_NAME, "btn-sso").click()

        # 2. Wait for redirect to SSO (Yonsei Portal)
        console.print("[yellow]Waiting for SSO page...[/yellow]")
        # Wait until URL contains sso or we see login inputs
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "loginId")) 
        )
        
        # 3. Input Credentials
        console.print("[cyan]Entering credentials...[/cyan]")
        driver.find_element(By.ID, "loginId").send_keys(username)
        driver.find_element(By.ID, "loginPasswd").send_keys(password)
        
        # 4. Click Login
        driver.find_element(By.ID, "loginBtn").click()
        
        # 5. Wait for redirection back to LearnUs
        console.print("[yellow]Waiting for successful login redirect...[/yellow]")
        # Wait for url to be ys.learnus.org or look for dashboard element
        WebDriverWait(driver, 30).until(
            lambda d: "ys.learnus.org" in d.current_url and "login" not in d.current_url
        )
        
        console.print("[green]Login detected![/green]")
        
        # 6. Export Cookies
        selenium_cookies = driver.get_cookies()
        
        # Convert to our format (EditThisCookie compatibility)
        cookies_to_save = []
        for cookie in selenium_cookies:
            cookies_to_save.append({
                "domain": cookie.get('domain'),
                "name": cookie.get('name'),
                "value": cookie.get('value'),
                "path": cookie.get('path', '/'),
            })
            
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies_to_save, f, indent=4)
            
        console.print(f"[bold green]✔ Cookies saved to {COOKIES_FILE}[/bold green]")
        
        driver.quit()
        return True
        
    except Exception as e:
        console.print(f"[bold red]Selenium Login Failed: {e}[/bold red]")
        try:
            driver.quit()
        except:
            pass
        return False
