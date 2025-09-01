#!/usr/bin/env python3
import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, time

import requests
from colorama import Fore, Style
from tabulate import tabulate

# Default settings
DEFAULT_CSV_FILE = "disciplinas.csv"
DEFAULT_SELECTIONS_FILE = "selecoes.json"
DAY_CODES = {'2': 'Segunda', '3': 'Terça', '4': 'Quarta', '5': 'Quinta', '6': 'Sexta', '7': 'Sábado'}


class Disciplina:
    """Represents a course discipline with its properties and scheduling information."""
    
    def __init__(self, row):
        # Store all fields from the CSV
        self.orgao = row.get("órgão ofertante", "")
        self.periodo = row.get("período", "")
        self.turma = row.get("turma", "")
        self.codigo = row.get("código", "")
        self.name = row.get("disciplina", "")
        self.docente = row.get("docente", "")
        self.horario = row.get("horário", "")
        self.sala = row.get("sala/lab", "")
        
        self.slots = self.parse_codes(self.horario)
        self.selected = False
        self.available = True

    @staticmethod
    def parse_codes(code_str):
        """Parse SIGAA time codes into a set of individual time slots."""
        pattern = re.compile(r"([2-7][MTN])(\d+)")
        slots = set()
        if not code_str:
            return slots
        for part in code_str.split():
            for prefix, digits in pattern.findall(part):
                for d in digits:
                    slots.add(f"{prefix}{d}")
        return slots


class DataDownloader:
    """Downloads and merges Google Sheets data."""
    
    def __init__(self, url):
        self.url = url
        # Extract doc_id from the URL
        m = re.search(r'/d/e/([\w-]+)/pubhtml', self.url)
        if not m:
            raise ValueError("Could not extract doc_id from URL")
        self.doc_id = m.group(1)

    def get_gids_and_names(self, html):
        """Parse the HTML to extract (name, gid) pairs for each sheet/tab."""
        items = re.findall(r'items.push\(\{name: "([^"]+)", pageUrl: ".*?gid=(\d+)", gid: "(\d+)"', html)
        # Use gid_from_field for consistency
        return [(name, gid) for (name, _, gid) in items]

    def download_csv(self, gid):
        """Download a specific sheet as CSV."""
        url = f"https://docs.google.com/spreadsheets/d/e/{self.doc_id}/pub?gid={gid}&single=true&output=csv"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.content.decode('utf-8')

    def merge_csvs(self, csv_texts):
        """Merge multiple CSVs (as text) into one, keeping only the header from the first."""
        merged_rows = []
        header = None
        for csv_text in csv_texts:
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)
            if not rows:
                continue
            if header is None:
                header = rows[0]
                merged_rows.append(header)
            # Skip header for subsequent files
            merged_rows.extend(rows[1:])
        return merged_rows

    def download_and_merge(self):
        """Download all sheets and merge them into one CSV."""
        # Download the HTML page
        html = requests.get(self.url).text
        # Parse GIDs and names
        gids = self.get_gids_and_names(html)
        print(f"Found sheets: {[name for name, _ in gids]}")
        
        # Download all CSVs
        csv_texts = []
        for name, gid in gids:
            print(f"Downloading {name} (gid={gid})...")
            csv_texts.append(self.download_csv(gid))
            
        # Merge
        return self.merge_csvs(csv_texts)


class DataFormatter:
    """Formats raw course data into standardized format."""
    
    @staticmethod
    def split_codigo_disciplina(text):
        """Split code and discipline name."""
        # e.g., "CIN0130- SISTEMAS DIGITAIS" or "CIN0130 - SISTEMAS DIGITAIS"
        m = re.match(r"([A-Z]{2,}\d{3,})\s*-\s*(.+)", text)
        if m:
            return m.group(1), m.group(2)
        # fallback: try space
        parts = text.split(None, 1)
        if len(parts) == 2 and re.match(r"[A-Z]{2,}\d{3,}", parts[0]):
            return parts[0], parts[1]
        return '', text

    @staticmethod
    def split_horario_sala(horario):
        """Split schedule and classroom information."""
        # Find all (SALA) and remove from horario
        salas = re.findall(r"\(([^)]+)\)", horario)
        # Deduplicate and preserve order
        seen = set()
        salas_unique = []
        for s in salas:
            if s not in seen:
                salas_unique.append(s)
                seen.add(s)
        # Remove all (SALA) from horario
        horario_clean = re.sub(r"\([^)]*\)", "", horario)
        # Remove extra spaces and slashes
        horario_clean = re.sub(r"\s+/\s+", " / ", horario_clean)
        horario_clean = horario_clean.replace("  ", " ").strip()
        return horario_clean, " ".join(salas_unique)

    @staticmethod
    def clean_docente(docente):
        """Clean teacher name by removing extra spaces."""
        return re.sub(r'\s+', ' ', docente).strip()

    @staticmethod
    def normalize(s):
        """Normalize text by removing accents and converting to lowercase."""
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII').lower()

    @classmethod
    def horario_to_sigaa(cls, horario_raw):
        """Convert raw schedule text to SIGAA time code format."""
        if not horario_raw:
            return ''
            
        # Map day abbreviations to SIGAA numbers
        day_map = {
            'seg': '2', 'ter': '3', 'qua': '4',
            'qui': '5', 'sex': '6', 'sáb': '7', 'sab': '7',
        }
        
        # Map time to (period, hour) with slot start/end as datetime.time
        time_to_period_hour = [
            # Manhã
            ((time(6,0), time(6,50)), ('M', '1')),
            ((time(7,0), time(7,50)), ('M', '2')),
            ((time(8,0), time(8,50)), ('M', '3')),
            ((time(9,0), time(9,50)), ('M', '4')),
            ((time(10,0), time(10,50)), ('M', '5')),
            ((time(11,0), time(11,50)), ('M', '6')),
            # Tarde
            ((time(12,0), time(12,50)), ('T', '1')),
            ((time(13,0), time(13,50)), ('T', '2')),
            ((time(14,0), time(14,50)), ('T', '3')),
            ((time(15,0), time(15,50)), ('T', '4')),
            ((time(16,0), time(16,50)), ('T', '5')),
            ((time(17,0), time(17,50)), ('T', '6')),
            # Noite
            ((time(18,0), time(18,50)), ('N', '1')),
            ((time(18,50), time(19,40)), ('N', '2')),
            ((time(19,40), time(20,30)), ('N', '3')),
            ((time(20,30), time(21,20)), ('N', '4')),
            ((time(21,20), time(22,10)), ('N', '5')),
            ((time(22,10), time(23,0)), ('N', '6')),
        ]
        
        # Parse all time slots into (day, period, hour)
        slots = []
        parts = [p.strip() for p in horario_raw.split('/')]
        for part in parts:
            m = re.match(r'(seg|ter|qua|qui|sex|s[áa]b)\.\s*(\d{2}:\d{2})-(\d{2}:\d{2})', cls.normalize(part))
            if not m:
                continue
            day, start, end = m.group(1), m.group(2), m.group(3)
            day_code = day_map.get(day, '')
            t_start = datetime.strptime(start, '%H:%M').time()
            t_end = datetime.strptime(end, '%H:%M').time()
            
            # For each SIGAA slot, check if it overlaps with the class time range
            for (slot_start, slot_end), (period, hour) in time_to_period_hour:
                if (slot_start >= t_start and slot_start <= t_end) or (slot_end >= t_start and slot_end <= t_end):
                    slots.append((day_code, period, hour))
                    
        # Group by (day, period)
        grouped = defaultdict(list)
        for day, period, hour in slots:
            if day and period and hour:
                grouped[(day, period)].append(hour)
                
        # Sort hours and build code
        codes = []
        for (day, period), hours in grouped.items():
            hours_sorted = sorted(set(hours), key=lambda x: int(x))
            codes.append(f"{day}{period}{''.join(hours_sorted)}")
            
        return ' '.join(sorted(codes))

    @classmethod
    def process_row(cls, row):
        """Process a row from the merged CSV into a standardized format."""
        # Pad row if short
        while len(row) < 5:
            row.append('')
            
        # Extract data
        org, turma, disciplina_full, docente, horario = row[:5]
        codigo, disciplina = cls.split_codigo_disciplina(disciplina_full)
        docente = cls.clean_docente(docente)
        horario_raw, sala = cls.split_horario_sala(horario)
        
        # Convert horario_raw to SIGAA code(s)
        horario_sigaa = cls.horario_to_sigaa(horario_raw)
        
        return [org, turma, codigo, disciplina, docente, horario_sigaa, sala]

    @classmethod
    def format_data(cls, merged_rows):
        """Format all rows from merged data."""
        formatted_rows = [['Órgão ofertante', 'Turma', 'Código', 'Disciplina', 'Docente', 'Horário', 'Sala/Lab']]
        
        for row in merged_rows[1:]:  # Skip header
            if not row or row[0].startswith('Período:') or row[0].startswith('Órgão ofertante'):
                continue
                
            formatted = cls.process_row(row)
            # Only include if there's a code and discipline
            if formatted[2] and formatted[3]:
                formatted_rows.append(formatted)
                
        return formatted_rows


class CourseScheduler:
    """Core course scheduling functionality."""
    
    def __init__(self, csv_file=DEFAULT_CSV_FILE, selections_file=DEFAULT_SELECTIONS_FILE):
        self.csv_file = csv_file
        self.selections_file = selections_file
        self.disciplinas = []
        self.load_data()
        
    def load_data(self):
        """Load disciplines from CSV file and apply saved selections."""
        try:
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Normalize column names
                reader.fieldnames = [col.strip().lower() for col in reader.fieldnames]
                
                for row in reader:
                    self.disciplinas.append(Disciplina(row))
        except FileNotFoundError:
            print(f"Arquivo não encontrado: {self.csv_file}")
            sys.exit(1)
        
        # Load selections
        if os.path.exists(self.selections_file):
            try:
                with open(self.selections_file, 'r', encoding='utf-8') as sf:
                    selected_names = json.load(sf)
                for d in self.disciplinas:
                    if d.name in selected_names:
                        d.selected = True
            except Exception as e:
                print(f"Erro ao carregar seleções: {e}")
                
        self.update_availability()

    def save_selections(self):
        """Save current selections to file."""
        selected = [d.name for d in self.disciplinas if d.selected]
        try:
            with open(self.selections_file, 'w', encoding='utf-8') as sf:
                json.dump(selected, sf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar seleções: {e}")

    def update_availability(self):
        """Update availability status for all disciplines based on current selections."""
        occupied = set()
        occupied_by = {}  # Track which slots are occupied by which disciplines
        
        # First collect all occupied slots and which course occupies them
        for d in self.disciplinas:
            if d.selected:
                for slot in d.slots:
                    occupied.add(slot)
                    if slot not in occupied_by:
                        occupied_by[slot] = []
                    occupied_by[slot].append(d)
        
        # Then update availability for each discipline
        for d in self.disciplinas:
            d.available = d.selected or d.slots.isdisjoint(occupied)
            
        return occupied_by  # Return the occupation map for conflict resolution

    def get_conflicts(self, disciplina, occupied_by=None):
        """Return a list of conflicting disciplines and their slots."""
        if occupied_by is None:
            occupied_by = self.update_availability()
            
        conflicts = {}
        
        for slot in disciplina.slots:
            if slot in occupied_by:
                for conflicting in occupied_by[slot]:
                    if conflicting.codigo != disciplina.codigo:  # Don't count itself
                        if conflicting not in conflicts:
                            conflicts[conflicting] = set()
                        conflicts[conflicting].add(slot)
        
        return conflicts

    def print_conflicts(self, disciplina, occupied_by=None):
        """Print detailed information about scheduling conflicts."""
        if occupied_by is None:
            occupied_by = self.update_availability()
            
        conflicts = self.get_conflicts(disciplina, occupied_by)
        
        if not conflicts:
            return False
        
        print(f"Conflitos detectados para '{disciplina.name}' ({disciplina.codigo}) - Turma {disciplina.turma}:")
        
        for conflicting, slots in conflicts.items():
            slot_times = []
            for slot in slots:
                day = DAY_CODES.get(slot[0])
                if slot[1] == "M":
                    period = "Manhã"
                    hour = 6 + int(slot[2:]) - 1
                elif slot[1] == "T":
                    period = "Tarde"
                    hour = 12 + int(slot[2:]) - 1
                else:  # slot[1] == "N"
                    period = "Noite"
                    hour = 18 + int(slot[2:]) - 1
                time_str = f"{hour}:00"
                slot_times.append(f"{day} {period} {time_str}")
            
            print(f"  → Conflito com '{conflicting.name}' ({conflicting.codigo}) - Turma {conflicting.turma}")
            print(f"    Horários conflitantes: {', '.join(slot_times)}")
        
        return True

    def add_course(self, disciplina):
        """Add a course to the schedule if no conflicts exist."""
        if disciplina.selected:
            print(f"Disciplina '{disciplina.name}' já está no cronograma.")
            return False
        
        # Check for conflicts before adding
        occupied_by = self.update_availability()
        has_conflicts = self.print_conflicts(disciplina, occupied_by)
        
        if has_conflicts:
            print("Não é possível adicionar disciplina devido aos conflitos de horário.")
            return False
        else:
            disciplina.selected = True
            self.update_availability()
            self.save_selections()
            print(f"'{disciplina.name}' ({disciplina.codigo}) adicionada ao cronograma.")
            return True

    def remove_course(self, disciplina):
        """Remove a course from the schedule."""
        if not disciplina.selected:
            print(f"Disciplina '{disciplina.name}' não está no cronograma.")
            return False
            
        disciplina.selected = False
        self.update_availability()
        self.save_selections()
        print(f"'{disciplina.name}' ({disciplina.codigo}) removida do cronograma.")
        return True
            
    def find_by_code(self, code):
        """Find all courses by code."""
        code = code.upper()
        matches = []
        for d in self.disciplinas:
            if d.codigo.upper() == code:
                matches.append(d)
        return matches

    def fuzzy_search(self, query):
        """Find courses by name using fuzzy matching."""
        query = query.upper()
        results = []

        for d in self.disciplinas:
            name = d.name.upper()
            # Calculate a simple similarity score based on common substrings
            match_score = 0
            query_words = query.split()
            name_words = name.split()

            for q_word in query_words:
                for n_word in name_words:
                    # Check for common prefix or substring
                    if q_word in n_word or n_word in q_word:
                        match_score += len(q_word) / len(n_word) if len(n_word) >= len(q_word) else len(n_word) / len(q_word)

            # Normalize score by the number of words in the query
            normalized_score = match_score / len(query_words) if query_words else 0
            results.append((normalized_score, d))

        # Sort by score in descending order and return top 10 matches
        results.sort(reverse=True, key=lambda x: x[0])
        return [d for score, d in results[:10] if score > 0.3]  # Apply a cutoff threshold

    def find_by_time_code(self, time_code):
        """Find courses available for a specific time slot."""
        # Parse the time code format (e.g., "2M123" -> day=2, period=M, hours=[1,2,3])
        pattern = re.compile(r"([2-7])([MTN])([1-6]+)")
        match = pattern.match(time_code)
        
        if not match:
            return [], f"Código de horário inválido: {time_code}. Use o formato 'dia[2-7]período[M/T/N]horas[1-6]'"
        
        day_code, period, hours = match.groups()
        
        # Generate individual time slots from the pattern
        time_slots = set()
        for hour in hours:
            time_slots.add(f"{day_code}{period}{hour}")
        
        # Find courses that have ALL their classes for this day within the specified slots
        result_courses = []
        
        for d in self.disciplinas:
            # Filter slots for the specified day
            day_slots = {slot for slot in d.slots if slot[0] == day_code}
            
            # Skip if no classes on this day
            if not day_slots:
                continue
                
            # Check if all slots for this day are within the specified time slots
            if day_slots.issubset(time_slots) and day_slots:  # Make sure it has at least one class in the range
                result_courses.append(d)
        
        return result_courses, None

    def get_all_courses(self):
        """Return all courses sorted by name."""
        return sorted(self.disciplinas, key=lambda x: x.name.lower())

    def get_selected_courses(self):
        """Return all selected courses."""
        return [d for d in self.disciplinas if d.selected]


class ScheduleDisplay:
    """Handles display formatting for course schedules."""
    
    @staticmethod
    def format_discipline_for_display(d, idx=None):
        """Format a discipline for display in a table."""
        # Truncate columns to fit within 120 characters
        name = d.name[:35] + "…" if len(d.name) > 36 else d.name
        docente = d.docente[:15] + "…" if len(d.docente) > 16 else d.docente
        orgao = d.orgao[:10] + "…" if len(d.orgao) > 11 else d.orgao
        
        # Determine row color based on status
        if d.selected:
            row_color = Fore.YELLOW
            status = "Selecionada"
        elif d.available:
            row_color = Fore.GREEN
            status = "Disponível"
        else:
            row_color = Fore.RED
            status = "Indisponível"
            
        # Create colored row
        if idx is not None:
            return [
                f"{row_color}{idx}{Style.RESET_ALL}",
                f"{row_color}{orgao}{Style.RESET_ALL}",
                f"{row_color}{d.codigo}{Style.RESET_ALL}",
                f"{row_color}{d.turma}{Style.RESET_ALL}",
                f"{row_color}{name}{Style.RESET_ALL}",
                f"{row_color}{docente}{Style.RESET_ALL}",
                f"{row_color}{d.horario}{Style.RESET_ALL}",
                f"{row_color}{status}{Style.RESET_ALL}"
            ]
        else:
            return [
                orgao,
                d.codigo,
                d.turma,
                name,
                docente,
                d.horario,
                status
            ]

    @classmethod
    def print_table(cls, disciplinas, title=None):
        """Print a table of disciplines."""
        if not disciplinas:
            if title:
                print(f"Nenhum resultado encontrado para: {title}")
            return []
            
        if title:
            print(f"\n{title}")
            print('-' * len(title))
        
        headers = ["#", "Curso", "Código", "Turma", "Disciplina", "Docente", "Horário", "Status"]
        table_data = [cls.format_discipline_for_display(d, i+1) for i, d in enumerate(disciplinas)]
        
        print(tabulate(table_data, headers=headers, tablefmt="simple"))
        return disciplinas

    @staticmethod
    def print_cronograma(disciplinas):
        """Display the schedule in a tabular format showing selected courses by time and day."""
        selected = [d for d in disciplinas if d.selected]
        
        if not selected:
            print("Nenhuma disciplina selecionada no cronograma.")
            return
            
        # Define the specific time slots we want to show
        morning_afternoon_hours = list(range(6, 18))  # 6:00 to 17:00
        
        # Create mapping for night hours to their exact time representation
        night_hour_mapping = {
            18: "18:00",
            19: "18:50",
            20: "19:40", 
            21: "20:30",
            22: "21:20", 
            23: "22:10"
        }
        
        # Combine morning/afternoon hours with night hours
        time_slots = [(h, f"{h:02d}:00") for h in morning_afternoon_hours] + \
                     [(h, night_hour_mapping[h]) for h in range(18, 24) if h in night_hour_mapping]
        
        days = list(DAY_CODES.values())
        
        # Create schedule data structure
        schedule_data = []
        day_slots = {day: {} for day in days}
        
        # Map courses to their time slots
        for d in selected:
            for slot in d.slots:
                day_code = slot[0]
                period = slot[1]
                hour_num = int(slot[2:])
                
                # Calculate actual hour based on period
                if period == 'M':
                    hour = 6 + hour_num - 1  # Manhã: 6:00 - 11:00
                elif period == 'T':
                    hour = 12 + hour_num - 1  # Tarde: 12:00 - 18:00
                else:  # period == 'N'
                    hour = 18 + hour_num - 1  # Noite: 18:00 - 23:00
                
                # Get day name from code
                day = DAY_CODES.get(day_code)
                if day:
                    if hour in day_slots[day]:
                        # Handle conflicts
                        day_slots[day][hour] = f"{day_slots[day][hour]}, {d.codigo}"
                    else:
                        day_slots[day][hour] = d.codigo
        
        # Format data for tabulate
        for hour, display_time in time_slots:
            row = [display_time]
            
            # Add cell content for each day
            for day in days:
                cell = day_slots[day].get(hour, '-')
                row.append(cell)
                
            schedule_data.append(row)
        
        # Print using tabulate
        print(tabulate(schedule_data, headers=['Hora'] + days, 
                      tablefmt="github", stralign="center"))


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Planejador de Matrícula CIn')
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # download command
    download_parser = subparsers.add_parser('download', help='Baixa dados de disciplinas da planilha do Google')
    download_parser.add_argument('url', help='URL da planilha publicada do Google')
    download_parser.add_argument('--output', '-o', default='disciplinas.csv', help='Arquivo de saída (padrão: disciplinas.csv)')
    
    # list command
    list_parser = subparsers.add_parser('list', help='Lista disciplinas')
    list_parser.add_argument('--csv', '-c', default=DEFAULT_CSV_FILE, help=f'Arquivo CSV (padrão: {DEFAULT_CSV_FILE})')
    
    # search commands
    search_parser = subparsers.add_parser('search', help='Busca disciplinas')
    search_parser.add_argument('--csv', '-c', default=DEFAULT_CSV_FILE, help=f'Arquivo CSV (padrão: {DEFAULT_CSV_FILE})')
    search_subparsers = search_parser.add_subparsers(dest='search_type', help='Tipo de busca')
    
    code_parser = search_subparsers.add_parser('code', help='Busca por código')
    code_parser.add_argument('code', help='Código da disciplina')
    
    name_parser = search_subparsers.add_parser('name', help='Busca por nome')
    name_parser.add_argument('name', nargs='+', help='Nome da disciplina')
    
    time_parser = search_subparsers.add_parser('time', help='Busca por horário')
    time_parser.add_argument('time_code', help='Código de horário (ex: 2M123)')
    
    # add command
    add_parser = subparsers.add_parser('add', help='Adiciona disciplina ao cronograma')
    add_parser.add_argument('--csv', '-c', default=DEFAULT_CSV_FILE, help=f'Arquivo CSV (padrão: {DEFAULT_CSV_FILE})')
    add_parser.add_argument('--selections', '-s', default=DEFAULT_SELECTIONS_FILE, help=f'Arquivo de seleções (padrão: {DEFAULT_SELECTIONS_FILE})')
    add_subparsers = add_parser.add_subparsers(dest='add_type', help='Tipo de adição')
    
    add_code_parser = add_subparsers.add_parser('code', help='Adiciona por código')
    add_code_parser.add_argument('code', help='Código da disciplina')
    
    add_name_parser = add_subparsers.add_parser('name', help='Adiciona por nome')
    add_name_parser.add_argument('name', nargs='+', help='Nome da disciplina')
    
    # remove command
    remove_parser = subparsers.add_parser('remove', help='Remove disciplina do cronograma')
    remove_parser.add_argument('--csv', '-c', default=DEFAULT_CSV_FILE, help=f'Arquivo CSV (padrão: {DEFAULT_CSV_FILE})')
    remove_parser.add_argument('--selections', '-s', default=DEFAULT_SELECTIONS_FILE, help=f'Arquivo de seleções (padrão: {DEFAULT_SELECTIONS_FILE})')
    remove_subparsers = remove_parser.add_subparsers(dest='remove_type', help='Tipo de remoção')
    
    remove_code_parser = remove_subparsers.add_parser('code', help='Remove por código')
    remove_code_parser.add_argument('code', help='Código da disciplina')
    
    # schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Mostra o cronograma')
    schedule_parser.add_argument('--csv', '-c', default=DEFAULT_CSV_FILE, help=f'Arquivo CSV (padrão: {DEFAULT_CSV_FILE})')
    schedule_parser.add_argument('--selections', '-s', default=DEFAULT_SELECTIONS_FILE, help=f'Arquivo de seleções (padrão: {DEFAULT_SELECTIONS_FILE})')
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is provided, show help
    if not args.command:
        parser.print_help()
        return
    
    # Handle commands
    if args.command == 'download':
        try:
            downloader = DataDownloader(args.url)
            merged_data = downloader.download_and_merge()
            formatter = DataFormatter()
            formatted_data = formatter.format_data(merged_data)
            
            # Write to CSV
            with open(args.output, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(formatted_data)
                
            print(f"Dados baixados e salvos em {args.output}")
            
        except Exception as e:
            print(f"Erro ao baixar dados: {e}")
            sys.exit(1)
            
    elif args.command == 'list':
        scheduler = CourseScheduler(args.csv)
        all_courses = scheduler.get_all_courses()
        ScheduleDisplay.print_table(all_courses, "Todas as disciplinas")
        
    elif args.command == 'search':
        scheduler = CourseScheduler(args.csv)
        
        if args.search_type == 'code':
            courses = scheduler.find_by_code(args.code)
            ScheduleDisplay.print_table(courses, f"Disciplinas com código {args.code}")
            
        elif args.search_type == 'name':
            name = ' '.join(args.name)
            courses = scheduler.fuzzy_search(name)
            ScheduleDisplay.print_table(courses, f"Disciplinas com nome similar a '{name}'")
            
        elif args.search_type == 'time':
            courses, error = scheduler.find_by_time_code(args.time_code)
            if error:
                print(f"Erro: {error}")
            else:
                day_name = DAY_CODES.get(args.time_code[0], "?")
                period = "manhã" if args.time_code[1].upper() == "M" else "tarde" if args.time_code[1].upper() == "T" else "noite"
                hours = ", ".join([f"{(6 if args.time_code[1].upper() == 'M' else 12 if args.time_code[1].upper() == 'T' else 18) + int(h) - 1}:00" for h in args.time_code[2:]])
                title = f"Disciplinas disponíveis para {day_name} pela {period} nos horários: {hours}"
                ScheduleDisplay.print_table(courses, title)
                
    elif args.command == 'add':
        scheduler = CourseScheduler(args.csv, args.selections)
        
        if args.add_type == 'code':
            courses = scheduler.find_by_code(args.code)
            if not courses:
                print(f"Nenhuma disciplina encontrada com código {args.code}")
            elif len(courses) == 1:
                scheduler.add_course(courses[0])
            else:
                print(f"Encontradas {len(courses)} turmas para o código {args.code}:")
                ScheduleDisplay.print_table(courses, f"Turmas para código {args.code}")
                print("\nEspecifique a turma desejada usando o comando 'add code' com o código específico da turma")
                
        elif args.add_type == 'name':
            name = ' '.join(args.name)
            courses = scheduler.fuzzy_search(name)
            if not courses:
                print(f"Nenhuma disciplina encontrada com nome similar a '{name}'")
            elif len(courses) == 1:
                scheduler.add_course(courses[0])
            else:
                print(f"Encontradas {len(courses)} disciplinas com nome similar a '{name}':")
                ScheduleDisplay.print_table(courses, f"Disciplinas com nome similar a '{name}'")
                print("\nEspecifique a disciplina desejada usando o comando 'add code' com o código da disciplina")
                
    elif args.command == 'remove':
        scheduler = CourseScheduler(args.csv, args.selections)
        
        if args.remove_type == 'code':
            courses = [d for d in scheduler.find_by_code(args.code) if d.selected]
            if not courses:
                print(f"Nenhuma disciplina selecionada com código {args.code}")
            elif len(courses) == 1:
                scheduler.remove_course(courses[0])
            else:
                print(f"Encontradas {len(courses)} turmas selecionadas para o código {args.code}:")
                ScheduleDisplay.print_table(courses, f"Turmas selecionadas para código {args.code}")
                print("\nEspecifique a turma desejada para remover usando o código completo")
                
    elif args.command == 'schedule':
        scheduler = CourseScheduler(args.csv, args.selections)
        selected_courses = scheduler.get_selected_courses()
        
        if not selected_courses:
            print("Nenhuma disciplina selecionada no cronograma.")
        else:
            print("\nDisciplinas no cronograma:")
            ScheduleDisplay.print_table(selected_courses, "Disciplinas selecionadas")
            print("\nCronograma:")
            ScheduleDisplay.print_cronograma(scheduler.disciplinas)


if __name__ == '__main__':
    main()
