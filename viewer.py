import os
from flask import Flask, render_template, send_from_directory, abort, request
from urllib.parse import quote

app = Flask(__name__)

# Register URL quote filter
@app.template_filter('url_quote')
def url_quote_filter(s):
    return quote(s)

# Configuration
ARCHIVE_DIR = os.path.join(os.getcwd(), 'Archive')

@app.route('/')
def index():
    """List Semesters"""
    if not os.path.exists(ARCHIVE_DIR):
        return render_template('index.html', semesters=[])
    
    semesters = [d for d in os.listdir(ARCHIVE_DIR) if os.path.isdir(os.path.join(ARCHIVE_DIR, d))]
    semesters.sort(reverse=True) # Newest first
    return render_template('index.html', semesters=semesters)

@app.route('/semester/<semester>')
def semester_view(semester):
    """List Courses in a Semester"""
    sem_path = os.path.join(ARCHIVE_DIR, semester)
    if not os.path.exists(sem_path):
        abort(404)
        
    courses = [d for d in os.listdir(sem_path) if os.path.isdir(os.path.join(sem_path, d))]
    courses.sort()
    return render_template('semester.html', semester=semester, courses=courses)

import re

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    '''
    return [ int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text) ]

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.mp4', '.mkv', '.avi', '.mov']:
        return 'Video', 'bi-camera-video'
    elif ext in ['.pdf']:
        return 'PDF', 'bi-file-earmark-pdf'
    elif ext in ['.zip', '.rar', '.7z']:
        return 'Archive', 'bi-file-earmark-zip'
    elif ext in ['.doc', '.docx']:
        return 'Word', 'bi-file-earmark-word'
    elif ext in ['.ppt', '.pptx']:
        return 'PPT', 'bi-file-earmark-slides'
    elif ext in ['.xls', '.xlsx']:
        return 'Excel', 'bi-file-earmark-excel'
    else:
        return 'File', 'bi-file-earmark'

import json

@app.route('/course/<semester>/<course>')
def course_view(semester, course):
    """Course Dashboard"""
    course_path = os.path.join(ARCHIVE_DIR, semester, course)
    if not os.path.exists(course_path):
        abort(404)
        
    # Check for Announcements
    has_announcements = os.path.exists(os.path.join(course_path, 'Announcements'))
    
    # List Weeks (subdirectories excluding special ones)
    weeks = []
    for d in os.listdir(course_path):
        d_path = os.path.join(course_path, d)
        if os.path.isdir(d_path) and d != 'Announcements':
            files = []
            folders = []
            
            for f in os.listdir(d_path):
                f_path = os.path.join(d_path, f)
                if os.path.isfile(f_path) and not f.startswith('.'):
                    ftype, icon = get_file_type(f)
                    files.append({'name': f, 'type': ftype, 'icon': icon})
                elif os.path.isdir(f_path):
                    # Check if it's an assignment folder with assignment_data.json
                    has_json = os.path.exists(os.path.join(f_path, 'assignment_data.json'))
                    # Fallback check for old index.html
                    has_index = os.path.exists(os.path.join(f_path, 'index.html'))
                    
                    folders.append({
                        'name': f, 
                        'has_assignment': has_json,
                        'has_index': has_index
                    })
            
            files.sort(key=lambda x: x['name'])
            folders.sort(key=lambda x: x['name'])
            
            weeks.append({'name': d, 'files': files, 'folders': folders})
    # Sort weeks numerically
    weeks.sort(key=lambda x: natural_keys(x['name']))
    
    return render_template('course.html', semester=semester, course=course, has_announcements=has_announcements, weeks=weeks)

@app.route('/course/<semester>/<course>/announcements')
def announcement_list(semester, course):
    """List Announcements"""
    announce_path = os.path.join(ARCHIVE_DIR, semester, course, 'Announcements')
    if not os.path.exists(announce_path):
        abort(404)
        
    announcements = []
    for f in os.listdir(announce_path):
        # Support both new JSON and old HTML
        if f.endswith('.json') or f.endswith('.html'):
            # Parse filename format: "[YYYY-MM-DD] Title.ext"
            date_str = ""
            title_str = f
            ext_len = 5 if f.endswith('.json') or f.endswith('.html') else 0
            
            # Simple regex to extract date in brackets
            idx = f.find('] ')
            if f.startswith('[') and idx > 0:
                date_str = f[1:idx]
                title_str = f[idx+2:-ext_len] 
            else:
                title_str = f[:-ext_len] 
                
            announcements.append({
                'filename': f,
                'date': date_str,
                'title': title_str
            })
            
    # Sort by date descending (using date_str, fallback to filename)
    announcements.sort(key=lambda x: x['date'] if x['date'] else "0000-00-00", reverse=True)
    
    return render_template('announcements.html', semester=semester, course=course, announcements=announcements)

@app.route('/course/<semester>/<course>/announcements/<path:filename>')
def announcement_detail(semester, course, filename):
    """View Announcement Detail"""
    announce_path = os.path.join(ARCHIVE_DIR, semester, course, 'Announcements')
    
    if filename.endswith('.json'):
        filepath = os.path.join(announce_path, filename)
        if not os.path.exists(filepath):
            abort(404)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return render_template('announcement_detail.html', semester=semester, course=course, data=data)
    else:
        # Fallback for old HTML files or attachments?
        # Actually attachments are in 'attachments/' subfolder which this route might catch if filename includes path separators?
        # <path:filename> catches slashes.
        # If it's a file download (not .json/html), serve it.
        return send_from_directory(announce_path, filename)

@app.route('/course/<semester>/<course>/<week>/<folder>/view')
def assignment_detail(semester, course, week, folder):
    """View Assignment Detail (JSON View)"""
    file_path = os.path.join(ARCHIVE_DIR, semester, course, week, folder, 'assignment_data.json')
    if not os.path.exists(file_path):
        abort(404)
        
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    return render_template('assignment_detail.html', semester=semester, course=course, week=week, folder=folder, data=data)

import unicodedata

@app.route('/course/<semester>/<course>/<week>/<path:filename>')
def file_serve(semester, course, week, filename):
    """Serve generic files from week folders"""
    file_path = os.path.join(ARCHIVE_DIR, semester, course, week)
    
    # Try exact match
    full_path = os.path.join(file_path, filename)
    if not os.path.exists(full_path):
        # NFD normalization (common on Mac)
        filename_nfd = unicodedata.normalize('NFD', filename)
        full_path_nfd = os.path.join(file_path, filename_nfd)
        if os.path.exists(full_path_nfd):
            filename = filename_nfd
        else:
             # NFC normalization (common on Windows/Linux/Python)
            filename_nfc = unicodedata.normalize('NFC', filename)
            full_path_nfc = os.path.join(file_path, filename_nfc)
            if os.path.exists(full_path_nfc):
                filename = filename_nfc
            else:
                 abort(404)
                 
    return send_from_directory(file_path, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
