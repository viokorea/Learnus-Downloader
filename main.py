import os
import queue
import argparse
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from src.auth import load_session, login_with_selenium
from src.parsers import DashboardParser, CourseParser
from src.downloaders import DownloaderCore
from src.utils import sanitize_filename
from src.ui import print_banner, display_courses_table, get_user_selection, create_progress, BackupDashboard
from src.exceptions import SessionExpiredError

console = Console()

def main():
    parser = argparse.ArgumentParser(description="LearnUs Backup Tool")
    parser.add_argument('--debug', action='store_true', help="Enable debug mode (use sample data on failure)")
    parser.add_argument('--threads', type=int, default=8, help="Number of parallel video download threads (default: 8)")
    args = parser.parse_args()

    # print_banner(console)
    session = load_session(console)
    
    # --- Dashboard Loop ---
    start_dashboard_check = True
    courses = [] # persistent
    
    while start_dashboard_check:
        start_dashboard_check = False 
        
        console.print("[bold green]Fetching Dashboard...[/bold green]")
        if True:
            try:
                dashboard_url = 'https://ys.learnus.org/'
                response = session.get(dashboard_url, allow_redirects=True)
                
                # Check for login redirection
                if '연세포털 로그인' in response.text:
                    console.print("[bold red]ERROR: Login failed (Redirected to Login Page).[/bold red]")
                    
                    if Confirm.ask("[bold yellow]Do you want to login via Yonsei Portal (Selenium)?[/bold yellow]"):
                         user_id = Prompt.ask("Portal ID")
                         user_pw = Prompt.ask("Password", password=True)
                         
                         if login_with_selenium(user_id, user_pw, console):
                             session = load_session(console)
                             start_dashboard_check = True
                             continue
                         else:
                             console.print("[red]Selenium login failed.[/red]")
                    
                    # Debug Fallback
                    if args.debug and os.path.exists('sample_dashboard.html'):
                         console.print("[yellow][DEBUG] Using 'sample_dashboard.html'...[/yellow]")
                         with open('sample_dashboard.html', 'r', encoding='utf-8') as f:
                             dashboard_html = f.read()
                    else:
                        console.print("[red]Exiting. Use --debug to test with sample data if available.[/red]")
                        return
                else:
                    dashboard_html = response.text

                dashboard_parser = DashboardParser(dashboard_html)
                courses = dashboard_parser.parse()
                
                if not courses:
                     # If we just logged in, we might need to retry or it's genuinely empty
                     if not start_dashboard_check:
                        console.print(f"[dim]Debug: URL={response.url}[/dim]")
                        console.print("[yellow]No courses found.[/yellow]")
                        
                        if args.debug and os.path.exists('sample_dashboard.html'):
                            console.print("[green][DEBUG] Loading 'sample_dashboard.html'...[/green]")
                            with open('sample_dashboard.html', 'r', encoding='utf-8') as f:
                                courses = DashboardParser(f.read()).parse()

            except Exception as e:
                console.print(f"[bold red]Error fetching dashboard: {e}[/bold red]")
                return

    if not courses:
        console.print("[red]No courses found.[/red]")
        return

    # --- Selection ---
    # --- Selection ---
    display_courses_table(console, courses)
    target_courses = get_user_selection(courses)
    
    if target_courses:
        default_sem = "2025-2" # Simple default
        # Try to guess from first selection
        try:
             # Heuristic: 2024_20 -> 2024-2
             parts = target_courses[0]['name'].split('_')
             if len(parts) > 1 and parts[0].isdigit():
                 if '10' in parts[1]: default_sem = f"{parts[0]}-1"
                 elif '20' in parts[1]: default_sem = f"{parts[0]}-2"
        except:
            pass
            
        semester_input = Prompt.ask("Enter Semester for Archive (e.g. 2025-2)", default=default_sem)
        semester_input = sanitize_filename(semester_input) # Ensure safe directory name
            
    if not target_courses:
        console.print("[yellow]No courses selected or invalid input. Exiting.[/yellow]")
        return

    # --- Execution Loop (with Session Recovery) ---
    execution_complete = False
    
    while not execution_complete:
        try:
            downloader = DownloaderCore(session)
            extraction_queue = queue.Queue()
            download_queue = queue.Queue() # New queue for actual file downloads
            
            # Initialize Dashboard
            dashboard = BackupDashboard(num_threads=args.threads)
            dashboard.update_parsing("Initializing...", total_courses=len(target_courses))

            # Run with Live Dashboard
            with dashboard.live:
                
                # 1. Start single VideoResolver (Extracts m3u8)
                from src.video import VideoResolver, VideoDownloader 
                
                resolver = VideoResolver(session, extraction_queue, download_queue, dashboard)
                resolver.start()
                
                # 2. Start Multiple VideoDownloaders (Runs FFmpeg)
                # They consume download_queue
                downloaders = []
                for i in range(args.threads):
                    # Pass video_task ID so they can advance the progress bar
                    d = VideoDownloader(download_queue, dashboard, thread_id=i)
                    d.start()
                    downloaders.append(d)
                
                files_found = 0
                assigns_found = 0
                videos_found = 0

                for idx, course in enumerate(target_courses, 1):
                    dashboard.update_parsing(f"Scanning: {course['name'][:40]}...", course_idx=idx, counts={"files": files_found, "assigns": assigns_found, "videos": videos_found})
                    
                    # Create Directory Structure: Archive/[Semester]/[Course]
                    course_dir = os.path.join(os.getcwd(), 'Archive', semester_input, sanitize_filename(course['name']))
                    os.makedirs(course_dir, exist_ok=True)
                    
                    # Fetch Course Page
                    course_res = session.get(course['url'])
                    
                    # Check URL for login redirect
                    if 'login' in course_res.url or 'sso' in course_res.url:
                        raise SessionExpiredError("Redirected to login page when fetching course.")

                    if args.debug and ('login' in course_res.url or os.path.exists('sample_course.html')):
                         # Only logic fallback for debug
                         if 'login' not in course_res.url:
                             course_html = course_res.text
                         elif os.path.exists('sample_course.html'):
                             course_html = open('sample_course.html').read()
                         else: 
                             raise SessionExpiredError("Login failed (Course Page) and no sample.")
                    else:
                        course_html = course_res.text

                    course_parser = CourseParser(course_html)
                    
                    # --- Archive Announcements ---
                    announce_url = course_parser.parse_announcement_url()
                    if announce_url:
                        dashboard.log(f"Archiving announcements...")
                        announce_dir = os.path.join(course_dir, "Announcements")
                        count = downloader.download_announcements(announce_url, announce_dir, dashboard_callback=dashboard.log)
                        if count > 0:
                            dashboard.log(f"Archived {count} announcements.")
                    else:
                        dashboard.log("No announcement link found for this course.")
                    
                    weeks = course_parser.parse()
                    
                    for week in weeks:
                        week_name = sanitize_filename(week['section_name'])
                        week_dir = os.path.join(course_dir, week_name)
                        
                        if not week['activities'] and not os.path.exists(week_dir):
                            continue
                            
                        os.makedirs(week_dir, exist_ok=True)
                        
                        for activity in week['activities']:
                            act_type = activity['type']
                            act_name = activity['name']
                            act_url = activity['url']
                            
                            if act_type == 'file':
                                files_found += 1
                                dashboard.update_parsing(f"Scanning...", counts={"files": files_found, "assigns": assigns_found, "videos": videos_found})
                                dashboard.log(f"Downloading file: {act_name}")
                                if downloader.download_file(act_url, week_dir):
                                    dashboard.log(f"Saved: {act_name}")
                            
                            elif act_type == 'assignment':
                                assigns_found += 1
                                dashboard.update_parsing(f"Scanning...", counts={"files": files_found, "assigns": assigns_found, "videos": videos_found})
                                dashboard.log(f"Checking assignment: {act_name}")
                                if downloader.download_assignment(act_url, week_dir, act_name):
                                    dashboard.log(f"Saved assignment: {act_name}")
                                else:
                                    pass # dashboard.log(f"No submission: {act_name}")
                                
                            elif act_type == 'vod':
                                videos_found += 1
                                dashboard.update_parsing(f"Scanning...", counts={"files": files_found, "assigns": assigns_found, "videos": videos_found})
                                dashboard.log(f"Queued video: {act_name}")
                                # Add to extraction queue
                                task = {
                                    'url': act_url,
                                    'folder': week_dir,
                                    'title': act_name,
                                    'referer': course['url'] 
                                }
                                extraction_queue.put(task)
                                dashboard.update_queue(extraction_queue.qsize(), download_queue.qsize())
                    
                dashboard.update_parsing("Finished Scanning. Waiting for downloads...", counts={"files": files_found, "assigns": assigns_found, "videos": videos_found})
                
                # Cleanup:
                # 1. Wait for extraction_queue to be empty (all tasks resolved)
                while not extraction_queue.empty() or resolver.active:
                     dashboard.update_queue(extraction_queue.qsize(), download_queue.qsize())
                     if extraction_queue.empty():
                         resolver.stop()
                         break
                     time.sleep(1)
                
                # 2. Wait for download_queue to be empty (all downloads finished)
                while not download_queue.empty() or any(d.active for d in downloaders):
                    dashboard.update_queue(extraction_queue.qsize(), download_queue.qsize())
                    if download_queue.empty():
                         for d in downloaders:
                             d.stop()
                         break
                    time.sleep(1)
                    
            console.print(Panel("[bold green]All Backup Tasks Completed![/bold green]", title="Success"))
            execution_complete = True 

        except SessionExpiredError:
            # Handle Session Expiry Re-authentication
            console.print("[bold red]\n⚠ SESSION EXPIRED DURING EXECUTION ⚠[/bold red]")
            
            # Stop all workers
            try:
                if 'resolver' in locals():
                    resolver.stop()
                if 'downloaders' in locals():
                    for d in downloaders:
                        d.stop()
            except: 
                pass

            if Confirm.ask("[bold yellow]Session expired. Do you want to login again and RESTART?[/bold yellow]"):
                 user_id = Prompt.ask("Portal ID")
                 user_pw = Prompt.ask("Password", password=True)
                 
                 if login_with_selenium(user_id, user_pw, console):
                     session = load_session(console)
                     console.print("[green]Session refreshed. Restarting tasks...[/green]")
                     # Loop will restart execution_complete is False
                 else:
                     console.print("[red]Login failed. Exiting.[/red]")
                     break
            else:
                console.print("[red]Exiting.[/red]")
                break

        except Exception as e:
             console.print(f"[bold red]Unexpected Error: {e}[/bold red]")
             import traceback
             console.print(traceback.format_exc())
             break

if __name__ == "__main__":
    main()
