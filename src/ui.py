from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.console import Group
from rich.prompt import Prompt
from rich import box
import time

console = Console()

class BackupDashboard:
    def __init__(self, num_threads):
        self.num_threads = num_threads
        
        # State
        self.parsing_status = "Idle"
        self.total_courses = 0
        self.current_course_idx = 0
        self.parsed_counts = {"files": 0, "assigns": 0, "videos": 0}
        
        self.queue_counts = {"extraction": 0, "download": 0}
        
        # Worker State: {thread_id: {"status": "Idle", "task": "-", "info": ""}}
        self.workers = {}
        for i in range(num_threads):
            self.workers[i] = {"status": "Idle", "task": "-", "info": ""}
            
        self.resolver_status = "Idle"
        
        self.logs = []
        self.max_logs = 8

        self.live = Live(self.get_renderable(), refresh_per_second=4, console=console)

    def refresh(self):
        self.live.update(self.get_renderable())

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        clean_msg = f"[{timestamp}] {msg}"
        self.logs.append(clean_msg)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
        self.refresh()

    def update_parsing(self, status, course_idx=0, total_courses=0, counts=None):
        self.parsing_status = status
        if total_courses: self.total_courses = total_courses
        if course_idx: self.current_course_idx = course_idx
        if counts: self.parsed_counts = counts
        self.refresh()
    
    def update_queue(self, ext_q, dl_q):
        self.queue_counts["extraction"] = ext_q
        self.queue_counts["download"] = dl_q
        self.refresh()
        
    def update_worker(self, thread_index, status, task="-", info=""):
        if thread_index in self.workers:
            self.workers[thread_index] = {"status": status, "task": task, "info": info}
        self.refresh()

    def update_resolver(self, status):
        self.resolver_status = status
        self.refresh()

    def get_renderable(self):
        # 1. Header / Banner
        header = Panel(f"[bold cyan]LearnUs Backup Tool[/bold cyan] - [dim]Processing {self.current_course_idx}/{self.total_courses} Courses[/dim]", style="blue")
        
        # 2. Status & Queues Grid
        # Table for Parsing Stats
        parse_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        parse_table.add_column("Key", style="dim")
        parse_table.add_column("Value")
        parse_table.add_row("Status", self.parsing_status)
        parse_table.add_row("Found Files", str(self.parsed_counts['files']))
        parse_table.add_row("Found Assignments", str(self.parsed_counts['assigns']))
        parse_table.add_row("Found Videos", str(self.parsed_counts['videos']))
        
        # Table for Queues
        queue_table = Table(box=box.SIMPLE, show_header=False, expand=True)
        queue_table.add_column("Queue", style="bold")
        queue_table.add_column("Count", justify="right")
        queue_table.add_row("[yellow]Extraction Queue[/yellow]", str(self.queue_counts['extraction']))
        queue_table.add_row("[green]Download Queue[/green]", str(self.queue_counts['download']))
        queue_table.add_row("Resolver Status", self.resolver_status)
        
        grid = Table.grid(expand=True)
        grid.add_row(parse_table, queue_table)

        stats_panel = Panel(
            grid,
            title="System Status",
            border_style="green"
        )

        # 3. Worker Table
        worker_table = Table(box=box.ROUNDED, expand=True, title="Download Workers")
        worker_table.add_column("ID", justify="center", width=4)
        worker_table.add_column("Status", width=12)
        worker_table.add_column("Current Task", ratio=1)
        worker_table.add_column("Info", justify="right")
        
        for i in range(self.num_threads):
            w = self.workers[i]
            style = "dim" if w['status'] == "Idle" else "bold"
            status_style = "green" if w['status'] == "Downloading" else "yellow" if w['status'] == "Starting" else "dim"
            worker_table.add_row(
                str(i), 
                f"[{status_style}]{w['status']}[/{status_style}]", 
                w['task'], 
                w['info'],
                style=style
            )
            
        # 4. Logs
        log_text = "\n".join(self.logs)
        log_panel = Panel(log_text, title="Activity Log", height=10, border_style="dim")

        return Group(header, stats_panel, worker_table, log_panel)

def print_banner(console):
    console.print(Panel("[bold blue]LearnUs Backup Tool[/bold blue]\n[dim]v2.0 - Rich UI[/dim]", expand=False))

def display_courses_table(console, courses):
    table = Table(title="Available Courses", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Course Name")
    table.add_column("Professor")
    table.add_column("Course ID")

    for idx, course in enumerate(courses, 1):
        prof = course.get('professor', course.get('prof', '')) # Handle naming diff
        table.add_row(str(idx), course['name'], prof, course['id'])

    console.print(table)

def get_user_selection(courses):
    selection = Prompt.ask("Enter course numbers to backup (comma separated or 'all')", default="all")
    if selection.lower() == 'all':
        return courses
    
    try:
        indices = [int(x.strip()) - 1 for x in selection.split(',')]
        return [courses[i] for i in indices if 0 <= i < len(courses)]
    except:
        return []

def create_progress(console):
    # Fallback or used for file downloads if needed separately, but Dashboard replaces main progress
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        expand=True
    )
