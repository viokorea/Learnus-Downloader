import os
import re
from urllib.parse import unquote
from .utils import sanitize_filename
from .exceptions import SessionExpiredError
import json
from .parsers import AnnouncementParser, AnnouncementDetailParser

class DownloaderCore:
    def __init__(self, session):
        self.session = session

    def _refresh_cookies(self):
        """
        Reloads cookies from cookies.json to ensure the session has the latest tokens.
        """
        import json
        cookies_file = 'cookies.json'
        if os.path.exists(cookies_file):
            try:
                with open(cookies_file, 'r') as f:
                    cookies = json.load(f)
                
                cookie_dict = {}
                if isinstance(cookies, list):
                    for cookie in cookies:
                        name = cookie.get('name')
                        value = cookie.get('value')
                        if name and value:
                            cookie_dict[name] = value
                    self.session.cookies.update(cookie_dict)
                else:
                    # Generic dict format
                    import requests
                    requests.utils.add_dict_to_cookiejar(self.session.cookies, cookies)
            except Exception:
                pass # Silently fail if cookie reload fails, proceed with existing session

    def download_file(self, url, folder, filename=None):
        try:
            response = self.session.get(url, stream=True, allow_redirects=True)
            response.raise_for_status()

            # Check for Session Expiry
            if 'login.php' in response.url or 'sso' in response.url:
                raise SessionExpiredError("Redirected to login page during file download.")
            
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                 # If we expect a file but get HTML, it's likely an error page or login page
                 # However, we must be careful not to flag legit HTML files (though rare in this context)
                 # Usually course files are PDF/PPT etc.
                 # Let's inspect a bit of content if it's small?
                 prefix = response.raw.read(1024)
                 response.raw.seek(0) # Reset stream? requests stream raw might not be seekable easily.
                 # Easier: Just assume if it's HTML and we didn't ask for it, it might be an issue.
                 # But safer: check URL or known login markers.
                 pass

            if not filename:
                filename = self._get_filename_from_header(response.headers)
            if not filename:
                filename = "downloaded_file" 
            
            # Re-check content type if filename suggests binary but we got html? 
            # (Skipping complex check for now, relying on URL redirect mostly)

            filename = sanitize_filename(filename)
            filepath = os.path.join(folder, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
            
        except SessionExpiredError:
            raise # Propagate up
        except Exception as e:
            # print(f"Error downloading file {url}: {e}")
            return False

    def download_assignment(self, url, folder, assignment_name):
        try:
            # Create a subfolder for this assignment to keep things organized?
            # User wants "Assignment Name" -> HTML + Files.
            # Current `main.py` passes `week_dir` as `folder`. 
            # If we just dump HTML and files there, it might get cluttered if multiple assignments per week.
            # Let's create `Week/Assignment_Name/` folder.
            safe_name = sanitize_filename(assignment_name)
            assign_dir = os.path.join(folder, safe_name)
            if not os.path.exists(assign_dir):
                os.makedirs(assign_dir)
                
            if not os.path.exists(assign_dir):
                os.makedirs(assign_dir)
             
            # RELOAD COOKIES
            self._refresh_cookies()
   
            response = self.session.get(url)
            response.raise_for_status()

            if 'login.php' in response.url or 'sso' in response.url:
                raise SessionExpiredError("Redirected to login page during assignment check.")
            
            # Import locally to avoid circular import issues if any, though top-level is fine
            from .parsers import AssignmentParser
            parser = AssignmentParser(response.text)
            data = parser.parse()
            
            # 1. Download Instructor Files
            if data['instructor_files']:
                inst_dir = os.path.join(assign_dir, "instructor_files")
                if not os.path.exists(inst_dir):
                    os.makedirs(inst_dir)
                for f in data['instructor_files']:
                    self.download_file(f['url'], inst_dir, filename=f['name'])
                    # Update URL in data to point to local file?
                    # For simple HTML generation, we can just link to relative path.
                    f['local_url'] = f"instructor_files/{f['name']}"

            # 2. Download Submission Files
            if data['submission_files']:
                sub_dir = os.path.join(assign_dir, "submission")
                if not os.path.exists(sub_dir):
                    os.makedirs(sub_dir)
                for f in data['submission_files']:
                    self.download_file(f['url'], sub_dir, filename=f['name'])
                    f['local_url'] = f"submission/{f['name']}"
            
            # 3. Save as JSON
            data['original_url'] = url
            json_path = os.path.join(assign_dir, "assignment_data.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            return True
                
        except SessionExpiredError:
            raise
        except Exception as e:
            # print(f"Error downloading assignment {assignment_name}: {e}")
            return False



    def _get_filename_from_header(self, headers):
        content_disposition = headers.get('Content-Disposition')
        if content_disposition:
            # 1. Try filename*=UTF-8''... (RFC 5987)
            fname_utf = re.findall(r"filename\*=UTF-8''(.+)", content_disposition, re.IGNORECASE)
            if fname_utf:
                return unquote(fname_utf[0])
            
            # 2. Try filename="..."
            fname = re.findall('filename="?([^";]+)"?', content_disposition)
            if fname:
                filename = unquote(fname[0])
                # Check for encoding mismatch (Latin-1 vs UTF-8)
                try:
                    # Often server sends UTF-8 bytes but headers are interpreted as Latin-1
                    filename = filename.encode('iso-8859-1').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # If it wasn't Latin-1 encoded UTF-8, use as is
                    pass
                return filename
                
        return None

    def download_announcements(self, base_url, folder, dashboard_callback=None):
        """
        Downloads announcements from the given board URL.
        Returns the number of announcements saved.
        """
        count = 0
        try:
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            # Attachments folder
            attach_folder = os.path.join(folder, "attachments")
            if not os.path.exists(attach_folder):
                os.makedirs(attach_folder)

            # RELOAD COOKIES
            self._refresh_cookies()
                
            # 1. Fetch First Page to Determine Total Pages
            response = self.session.get(base_url)
            response.raise_for_status()
            
            if 'login.php' in response.url:
                raise SessionExpiredError("Redirected to login page during announcement list fetch.")
                
            parser = AnnouncementParser(response.text)
            total_pages = parser.parse_total_pages()
            
            if dashboard_callback:
                dashboard_callback(f"Found {total_pages} pages of announcements.")

            # 2. Iterate Pages
            for page in range(1, total_pages + 1):
                page_url = f"{base_url}&page={page}"
                if page > 1:
                   # Fetching again is safer to reuse loop logic.
                   response = self.session.get(page_url)
                   response.raise_for_status()
                   parser = AnnouncementParser(response.text)

                items = parser.parse()
                if not items:
                    continue

                for item in items:
                    try:
                        # 3. Handle File Naming 
                        safe_title = sanitize_filename(item['title'])
                        date_prefix = item['date'].split(' ')[0].replace('/', '-') if item['date'] else "0000-00-00"
                        
                        filename = f"[{date_prefix}] {safe_title}.json"
                        filepath = os.path.join(folder, filename)
            
                        if os.path.exists(filepath):
                            continue
                            
                        # Fetch Detail
                        res_detail = self.session.get(item['url'])
                        res_detail.raise_for_status()
                        
                        detail_parser = AnnouncementDetailParser(res_detail.text)
                        detail = detail_parser.parse()
                        
                        if not detail:
                            continue
                            
                        # Add Metadata
                        detail['original_url'] = item['url']

                        # 4. Download Attachments
                        if detail.get('attachments'):
                            for att in detail['attachments']:
                                att_name = sanitize_filename(att['name'])
                                att_url = att['url']
                                self.download_file(att_url, attach_folder, filename=att_name)
                                att['local_url'] = f"attachments/{att_name}" # Relative link for HTML

                        # Save as JSON
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(detail, f, ensure_ascii=False, indent=4)
                            
                        count += 1
                        
                    except Exception as e:
                        if dashboard_callback:
                            dashboard_callback(f"Failed to download announcement '{item.get('title')}': {e}")
                        continue
                        
        except SessionExpiredError:
            raise
        except Exception as e:
            if dashboard_callback:
                 dashboard_callback(f"Error downloading announcements: {e}")
            return count

        return count



