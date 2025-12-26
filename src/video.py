import threading
import queue
import re
import subprocess
import os
import time
from .utils import sanitize_filename
from .exceptions import SessionExpiredError

class VideoResolver:
    def __init__(self, session, extraction_queue, download_queue, dashboard=None):
        self.session = session
        self.extraction_queue = extraction_queue
        self.download_queue = download_queue
        self.dashboard = dashboard
        self.active = True
        self.thread = threading.Thread(target=self._process_queue)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def stop(self):
        self.active = False

    def _process_queue(self):
        while self.active or not self.extraction_queue.empty():
            if self.dashboard:
                 self.dashboard.update_queue(self.extraction_queue.qsize(), self.download_queue.qsize())
                 
            try:
                task = self.extraction_queue.get(timeout=1)
            except queue.Empty:
                if self.dashboard: self.dashboard.update_resolver("Idle")
                continue

            try:
                if self.dashboard: self.dashboard.update_resolver(f"Resolving: {task.get('title')[:30]}")
                self._resolve_task(task)
            except SessionExpiredError:
                 self._log("[bold red]Session Expired in Video Resolver! Skipping.[/bold red]")
            except Exception as e:
                self._log(f"[red]Error resolving {task.get('title')}: {e}[/red]")
            finally:
                self.extraction_queue.task_done()
                if self.dashboard: self.dashboard.update_resolver("Idle")

    def _resolve_task(self, task):
        # ... logic remains same ...
        # Can remove print statements or replace with self._log
        # Keeping existing logic but suppressing prints if dashboard is used

        viewer_url = task['url']
        folder = task['folder']
        title = task['title']
        
        cookies_from_file = {}
        if os.path.exists('cookies.json'):
            try:
                import json
                with open('cookies.json', 'r') as f:
                    file_cookies = json.load(f)
                if isinstance(file_cookies, list):
                    for c in file_cookies:
                        if c.get('name') and c.get('value'):
                            cookies_from_file[c['name']] = c['value']
                elif isinstance(file_cookies, dict):
                    cookies_from_file = file_cookies
            except Exception as e:
                 self._log(f"Error reading local cookies.json: {e}")

        viewer_url = viewer_url.replace('view', 'viewer')
        response = self.session.get(viewer_url, cookies=cookies_from_file)
        # response.raise_for_status() # Let exceptions handle it
        
        if 'login.php' in response.url or 'sso' in response.url:
            raise SessionExpiredError("Redirected to login page during video viewer fetch.")

        html = response.text
        m3u8_url = None
        
        # ... Extraction Logic (same) ...
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            source = soup.find('source', type='application/x-mpegURL')
            if not source:
                source = soup.find('source', src=re.compile(r'\.m3u8'))
            if source:
                m3u8_url = source.get('src')
        except:
             pass

        if not m3u8_url:
            m3u8_match = re.search(r'"file":"(https:[^"]+\.m3u8[^"]*)"', html)
            if not m3u8_match:
                m3u8_match = re.search(r'"file":"(https:[^"]+\.m3u8[^"]*)"'.replace('/', r'\\/'), html)
            if m3u8_match:
                 m3u8_url = m3u8_match.group(1).replace('\\/', '/')

        if not m3u8_url:
             simple_match = re.search(r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)', html)
             if simple_match:
                 m3u8_url = simple_match.group(1)

        if not m3u8_url:
            self._log(f"[yellow]Could not find m3u8 for {title}[/yellow]")
            with open("debug_video_dump.html", "w", encoding='utf-8') as f:
                f.write(html)
            return

        # Found URL
        self._log(f"Resolved: {title}")
        self.download_queue.put({'m3u8_url': m3u8_url, 'folder': folder, 'title': title})

    def _log(self, msg):
        if self.dashboard:
            self.dashboard.log(msg)
        else:
            print(msg)


class VideoDownloader:
    def __init__(self, download_queue, dashboard=None, thread_id=None):
        self.download_queue = download_queue
        self.dashboard = dashboard
        self.thread_id = thread_id
        self.active = True
        self.thread = threading.Thread(target=self._process_queue)
        self.thread.daemon = True

    def start(self):
        self.thread.start()

    def stop(self):
        self.active = False

    def _process_queue(self):
        while self.active or not self.download_queue.empty():
            try:
                task = self.download_queue.get(timeout=1)
            except queue.Empty:
                if self.dashboard: 
                    self.dashboard.update_worker(self.thread_id, "Idle", "-", "")
                continue
            
            try:
                self._download_task(task)
            except Exception as e:
                self._log(f"Error downloading {task.get('title')}: {e}")
                if self.dashboard: 
                    self.dashboard.update_worker(self.thread_id, "Error", task.get('title'), str(e))
            finally:
                self.download_queue.task_done()

    def _download_task(self, task):
        m3u8_url = task['m3u8_url']
        folder = task['folder']
        title = task['title']
        
        filename = f"{sanitize_filename(title)}.mp4"
        filepath = os.path.join(folder, filename)
        
        if self.dashboard:
            self.dashboard.update_worker(self.thread_id, "Starting", title[:40])

        if os.path.exists(filepath):
            self._log(f"Exist, skipping: {filename}")
            if self.dashboard:
                self.dashboard.update_worker(self.thread_id, "Skipped", title[:40], "Exists")
            time.sleep(0.5) # Short pause to show status
            return

        cmd = [
            "ffmpeg", "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
            filepath, "-y", "-loglevel", "error"
        ]
        
        if self.dashboard:
            self.dashboard.update_worker(self.thread_id, "Downloading", title[:40], "FFmpeg")
            
        start_time = time.time()
        subprocess.run(cmd, check=True)
        elapsed = time.time() - start_time
        
        self._log(f"Downloaded: {filename} ({elapsed:.1f}s)")
        if self.dashboard:
             self.dashboard.update_worker(self.thread_id, "Finished", title[:40], f"{elapsed:.1f}s")
             time.sleep(0.5)

    def _log(self, msg):
        if self.dashboard:
            self.dashboard.log(msg)
        else:
            print(msg)
