from bs4 import BeautifulSoup
import re

class DashboardParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def parse(self):
        courses = []
        course_items = self.soup.find_all('div', class_='course-box')
        
        course_items = self.soup.find_all('div', class_='course-box')
        
        for item in course_items:
            link_tag = item.find('a', class_='course-link')
            if not link_tag:
                continue
            
            url = link_tag.get('href')
            course_id = self._extract_id(url)
            
            title_div = item.find('div', class_='course-title')
            if title_div:
                title_h3 = title_div.find('h3')
                if title_h3:
                    title = title_h3.get_text(strip=True)
                else:
                    title = "Unknown Course"
            else:
                title = "Unknown Course"
                
            prof_span = item.find('span', class_='prof')
            prof = prof_span.get_text(strip=True) if prof_span else ""
            
            # Extract semester info if available (e.g. from title prefix "2025_20_...")
            # Format: YYYY_Semester_Code...
            # This is a heuristic; user might need to confirm/override.
            semester = "Unknown_Semester"
            if title.startswith("20"):
                parts = title.split('_')
                if len(parts) >= 2:
                    # 2025_10 -> 2025-1, 2025_20 -> 2025-2
                    year = parts[0]
                    sem_code = parts[1]
                    if sem_code == '10': semester = f"{year}-1"
                    elif sem_code == '20': semester = f"{year}-2"
                    elif sem_code == '11': semester = f"{year}-Winter" # Guessing codes
                    elif sem_code == '21': semester = f"{year}-Summer"

            courses.append({
                'id': course_id,
                'name': title,
                'prof': prof,
                'url': url,
                'semester': semester
            })
            
        return courses

    def _extract_id(self, url):
        match = re.search(r'[?&]id=(\d+)', url)
        return match.group(1) if match else None

class CourseParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def parse_announcement_url(self):
        # 1. Look for "Course Article" header button (Standard LearnUs layout)
        header = self.soup.find('div', class_='course-article-header')
        if header:
            actions = header.find('div', class_='actions')
            if actions:
                link = actions.find('a', class_='btn-more')
                if link:
                    return link.get('href')
        
        # 2. Fallback: Search for any link containing "mod/ubboard/view.php" AND ("공지" or "Notice") in text
        # This covers modules listed in the weekly sections.
        import re
        links = self.soup.find_all('a', href=re.compile(r'mod/ubboard/view\.php'))
        for link in links:
            text = link.get_text(strip=True)
            if "공지" in text or "Notice" in text:
                return link['href']
                
        return None

    def parse(self):
        week_data = []
        weeks = self.soup.find_all('li', class_='section')

        for week in weeks:
            section_name_tag = week.find('h3', class_='sectionname')
            if not section_name_tag:
                continue
            
            section_name = section_name_tag.get_text(strip=True)
            activities = []
            
            activity_list = week.find('ul', class_='section img-text')
            if activity_list:
                items = activity_list.find_all('li', class_='activity')
                for item in items:
                    activity_info = self._parse_activity(item)
                    if activity_info:
                        activities.append(activity_info)
            
            if activities:
                week_data.append({
                    'section_name': section_name,
                    'activities': activities
                })
        
        return week_data

    def _parse_activity(self, item_tag):
        classes = item_tag.get('class', [])
        
        activity_type = 'unknown'
        if 'modtype_ubfile' in classes:
            activity_type = 'file'
        elif 'modtype_vod' in classes:
            activity_type = 'vod'
        elif 'modtype_assign' in classes:
            activity_type = 'assignment'
        else:
            return None 
            
        instance = item_tag.find('div', class_='activityinstance')
        if not instance:
            return None
            
        link_tag = instance.find('a')
        if not link_tag:
            return None
            
        url = link_tag.get('href')
        
        name_span = instance.find('span', class_='instancename')
        if name_span:
            # Clone to not modify original if reused (though soup is throwaway here)
            # Remove hidden text
            name_text = ""
            for child in name_span.contents:
                if child.name == 'span' and 'accesshide' in child.get('class', []):
                    continue
                name_text += child.get_text(strip=False) if hasattr(child, 'get_text') else str(child)
            name = name_text.strip()
        else:
            name = "Untitled"

        return {
            'type': activity_type,
            'name': name,
            'url': url,
            'id': self._extract_id(url)
        }

    def _extract_id(self, url):
        match = re.search(r'[?&]id=(\d+)', url)
        return match.group(1) if match else None

class AnnouncementParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def parse(self):
        announcements = []
        
        # New structure: ubboard_table
        table = self.soup.find('table', class_='ubboard_table')
        if table:
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 4: 
                        continue
                    
                    # Column 0: Number/Notice status
                    is_notice = False
                    number_text = cols[0].get_text(strip=True)
                    if "공지" in number_text or "Notice" in number_text:
                        is_notice = True
                        
                    # Column 1: Title and Link
                    title_col = cols[1]
                    link = title_col.find('a')
                    if not link:
                        continue
                        
                    title = link.get_text(strip=True)
                    url = link.get('href', '')
                    
                    # Column 3: Date
                    date_col = cols[3]
                    date_str = date_col.get_text(strip=True) 
                    
                    announcements.append({
                        'title': title,
                        'url': url,
                        'date': date_str,
                        'is_notice': is_notice
                    })
            if announcements:
                return announcements

        # Fallback: Old structure (ul.article-list)
        list_container = self.soup.find('ul', class_='article-list')
        if not list_container:
            return announcements
            
        items = list_container.find_all('li', class_='article-list-item')
        for item in items:
            link = item.find('a')
            if not link:
                continue
            
            url = link.get('href')
            
            subject_div = link.find('div', class_='article-subject')
            title = subject_div.get_text(strip=True) if subject_div else "No Title"
            
            date_div = link.find('div', class_='article-date')
            date_str = date_div.get_text(strip=True) if date_div else ""
            
            # Identify if it's a notice (pinned) - often has distinct style or icon, but standard ones in sample don't show specific class here.
            # We treat all as standard items for now.
            
            announcements.append({
                'title': title,
                'url': url,
                'date': date_str,
                'is_notice': False 
            })
            
        return announcements

    def parse_total_pages(self):
        # Default to 1 page
        total_pages = 1
        
        # Look for pagination list
        pagination_ul = self.soup.find('ul', class_='pagination')
        if pagination_ul:
            page_items = pagination_ul.find_all('li', class_='page-item')
            for item in page_items:
                link = item.find('a', class_='page-link')
                if link and link.get_text(strip=True).isdigit():
                    page_num = int(link.get_text(strip=True))
                    if page_num > total_pages:
                        total_pages = page_num
        
        return total_pages

class AnnouncementDetailParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def parse(self):
        container = self.soup.find('div', class_='ubboard_view')
        if not container:
            return None
            
        title_div = container.find('div', class_='subject')
        title = title_div.get_text(strip=True) if title_div else "No Title"
        
        info_divs = container.find_all('div', class_='info')
        writer = ""
        date = ""
        hit = ""
        
        # Helper to extract text from info rows like "작성자: 홍길동"
        for info in info_divs:
            text = info.get_text(strip=True)
            if "작성자" in text:
                writer = text.replace("작성자:", "").strip()
            if "작성일" in text:
                date = text.replace("작성일:", "").strip()
            if "조회수" in text:
                hit = text.replace("조회수:", "").strip()

        content_div = container.find('div', class_='text_to_html')
        content_html = str(content_div) if content_div else ""
        
        # Attachments
        attachments = []
        files_ul = container.find('ul', class_='files')
        if files_ul:
            file_items = files_ul.find_all('li')
            for item in file_items:
                link = item.find('a')
                if link:
                    attachments.append({
                        'name': link.get_text(strip=True),
                        'url': link.get('href')
                    })

        # Nav Links
        prev_next = []
        pre_next_div = container.find('div', class_='pre_next_article')
        if pre_next_div:
            links = pre_next_div.find_all('a')
            for link in links:
                prev_next.append({
                    'text': link.get_text(strip=True),
                    'url': link.get('href')
                })

        return {
            'title': title,
            'writer': writer,
            'date': date,
            'hit': hit,
            'content_html': content_html,
            'attachments': attachments,
            'prev_next': prev_next
        }


class AssignmentParser:
    def __init__(self, html_content):
        self.soup = BeautifulSoup(html_content, 'lxml')

    def parse(self):
        # 1. Title
        title_tag = self.soup.find('h2')
        title = title_tag.get_text(strip=True) if title_tag else "Assignment"
        
        # 2. Description (Intro)
        # Usually in div id='intro' or class='box generalbox'
        description_div = self.soup.find('div', id='intro')
        if not description_div:
            description_div = self.soup.find('div', class_='generalbox')
        
        description_html = str(description_div) if description_div else "<p>No description available.</p>"
        
        # 3. Instructor Attachments (in description or intro)
        instructor_files = []
        if description_div:
            # Look for <a> links to files (pluginfile.php)
            links = description_div.find_all('a')
            for link in links:
                href = link.get('href')
                if href and 'pluginfile.php' in href:
                    instructor_files.append({
                        'name': link.get_text(strip=True),
                        'url': href
                    })

        # 4. Student Submission
        submission_files = []
        submission_div = self.soup.find('div', class_='fileuploadsubmission')
        if not submission_div:
            submission_div = self.soup.find('div', class_='submissionstatustable')
            
        if submission_div:
            links = submission_div.find_all('a')
            for link in links:
                href = link.get('href')
                if href and 'pluginfile.php' in href:
                    submission_files.append({
                        'name': link.get_text(strip=True),
                        'url': href
                    })
                    
        return {
            'title': title,
            'description_html': description_html,
            'instructor_files': instructor_files,
            'submission_files': submission_files
        }
