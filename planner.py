import csv
import re
import sys
import os
import json
from colorama import Fore, Style
from tabulate import tabulate

DEFAULT_CSV_FILE = "disciplinas.csv"
DAY_CODES = {'2': 'Segunda', '3': 'Terça', '4': 'Quarta', '5': 'Quinta', '6': 'Sexta', '7': 'Sábado'}

class Disciplina:
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
        pattern = re.compile(r"([2-6][MTN])(\d+)")
        slots = set()
        if not code_str:
            return slots
        for part in code_str.split():
            for prefix, digits in pattern.findall(part):
                for d in digits:
                    slots.add(f"{prefix}{d}")
        return slots

# === Data Management Functions ===

def load_disciplinas(path, selections_file):
    disciplinas = []
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Normalize column names
            reader.fieldnames = [col.strip().lower() for col in reader.fieldnames]
            
            for row in reader:
                disciplinas.append(Disciplina(row))
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)
    
    # Load selections
    if os.path.exists(selections_file):
        try:
            with open(selections_file, 'r', encoding='utf-8') as sf:
                selected_names = json.load(sf)
            for d in disciplinas:
                if d.name in selected_names:
                    d.selected = True
        except Exception:
            pass
    return disciplinas

def save_selections(disciplinas, selections_file):
    selected = [d.name for d in disciplinas if d.selected]
    try:
        with open(selections_file, 'w', encoding='utf-8') as sf:
            json.dump(selected, sf, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar seleções: {e}")

def update_availability(disciplinas):
    occupied = set()
    occupied_by = {}  # Track which slots are occupied by which disciplines
    
    # First collect all occupied slots and which course occupies them
    for d in disciplinas:
        if d.selected:
            for slot in d.slots:
                occupied.add(slot)
                if slot not in occupied_by:
                    occupied_by[slot] = []
                occupied_by[slot].append(d)
    
    # Then update availability for each discipline
    for d in disciplinas:
        d.available = d.selected or d.slots.isdisjoint(occupied)
        
    return occupied_by  # Return the occupation map for conflict resolution

# === Search Functions ===

def find_by_code(code, disciplinas):
    """Find all courses by code"""
    code = code.upper()
    matches = []
    for d in disciplinas:
        if d.codigo.upper() == code:
            matches.append(d)
    return matches

def fuzzy_search(query, disciplinas):
    """Find courses by name using fuzzy matching"""
    query = query.upper()
    results = []

    for d in disciplinas:
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

def find_by_time_code(time_code, disciplinas):
    """Find courses available for a specific set of time codes (e.g. '2M123')"""
    # Parse the time code format (e.g., "2M123" -> day=2, period=M, hours=[1,2,3])
    pattern = re.compile(r"([2-6])([MTN])([1-6]+)")
    match = pattern.match(time_code)
    
    if not match:
        return [], f"Código de horário inválido: {time_code}. Use o formato 'dia[2-6]período[M/T/N]horas[1-6]'"
    
    day_code, period, hours = match.groups()
    
    # Generate individual time slots from the pattern
    time_slots = set()
    for hour in hours:
        time_slots.add(f"{day_code}{period}{hour}")
    
    # Find courses that have ALL their classes for this day within the specified slots
    result_courses = []
    
    for d in disciplinas:
        # Filter slots for the specified day
        day_slots = {slot for slot in d.slots if slot[0] == day_code}
        
        # Skip if no classes on this day
        if not day_slots:
            continue
            
        # Check if all slots for this day are within the specified time slots
        if day_slots.issubset(time_slots) and day_slots:  # Make sure it has at least one class in the range
            result_courses.append(d)
    
    return result_courses, None

# === Conflict Management ===

def get_conflicts(disciplina, occupied_by):
    """Return a list of conflicting disciplines and their slots"""
    conflicts = {}
    
    for slot in disciplina.slots:
        if slot in occupied_by:
            for conflicting in occupied_by[slot]:
                if conflicting.codigo != disciplina.codigo:  # Don't count itself
                    if conflicting not in conflicts:
                        conflicts[conflicting] = set()
                    conflicts[conflicting].add(slot)
    
    return conflicts

def print_conflicts(disciplina, occupied_by):
    """Print detailed information about conflicts"""
    conflicts = get_conflicts(disciplina, occupied_by)
    
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
            time = f"{hour}:00"
            slot_times.append(f"{day} {period} {time}")
        
        print(f"  → Conflito com '{conflicting.name}' ({conflicting.codigo}) - Turma {conflicting.turma}")
        print(f"    Horários conflitantes: {', '.join(slot_times)}")
    
    return True

# === Display Functions ===

def format_discipline_for_display(d, idx=None):
    """Format a discipline for display in a table"""
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
            f"{row_color}{d.turma}{Style.RESET_ALL}",  # Added turma to display
            f"{row_color}{name}{Style.RESET_ALL}",
            f"{row_color}{docente}{Style.RESET_ALL}",
            f"{row_color}{d.horario}{Style.RESET_ALL}",
            f"{row_color}{status}{Style.RESET_ALL}"
        ]
    else:
        return [
            orgao,
            d.codigo,
            d.turma,  # Added turma to display
            name,
            docente,
            d.horario,
            status
        ]

def print_table(disciplinas):
    """Print a table of all disciplines"""
    sorted_list = sorted(disciplinas, key=lambda x: x.name.lower())
    
    headers = ["#", "Curso", "Código", "Turma", "Disciplina", "Docente", "Horário", "Status"]  # Added Turma header
    table_data = [format_discipline_for_display(d, i+1) for i, d in enumerate(sorted_list)]
    
    print(tabulate(table_data, headers=headers, tablefmt="simple"))
    return sorted_list

def print_results(disciplinas, title, show_numbers=True):
    """Generic function to print a list of disciplines with a title"""
    if not disciplinas:
        print(f"Nenhum resultado encontrado para: {title}")
        return
    
    print(f"\n{title}")
    print('-' * len(title))
    
    headers = ["#", "Curso", "Código", "Turma", "Disciplina", "Docente", "Horário", "Status"] if show_numbers else \
              ["Curso", "Código", "Turma", "Disciplina", "Docente", "Horário", "Status"]  # Added Turma header
    
    if show_numbers:
        table_data = [format_discipline_for_display(d, i+1) for i, d in enumerate(disciplinas)]
    else:
        table_data = [format_discipline_for_display(d) for d in disciplinas]
    
    print(tabulate(table_data, headers=headers, tablefmt="simple"))
    return disciplinas

def print_cronograma(disciplinas):
    """Display the schedule in a tabular format showing selected courses by time and day."""
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
    for d in disciplinas:
        if d.selected:
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
                    # Check for conflicting slots
                    if hour in day_slots[day]:
                        raise ValueError(f"Conflicting slot detected for {d.codigo} at {day} {hour}:00")
                    
                    # Add course code to this day/hour
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

# === Command Handling ===

def handle_add_command(cmd_parts, disciplinas, sorted_list, selections_file):
    """Handle the 'add' command with various sub-commands"""
    if len(cmd_parts) < 2:
        print("O comando 'add' precisa de argumentos.")
        return
    
    # Get the sub-command
    subcmd = cmd_parts[1].lower()
    
    # Handle add by code
    if subcmd == '-c' and len(cmd_parts) >= 3:
        code = cmd_parts[2].lower()  # Case-insensitive code handling
        courses = find_by_code(code, disciplinas)
        if not courses:
            print(f"Código não encontrado: {code}")
            return
        
        # If multiple sections found, let user select which one
        if len(courses) > 1:
            print(f"\nEncontradas {len(courses)} turmas para o código {code.upper()}:")
            select_and_add_from_results(courses, f"Turmas para código {code.upper()}", 
                                        disciplinas, selections_file)
        else:
            add_course(courses[0], disciplinas, selections_file)
    
    # Handle add by name (fuzzy search)
    elif subcmd == '-n' and len(cmd_parts) >= 3:
        search_term = ' '.join(cmd_parts[2:])
        courses = fuzzy_search(search_term, disciplinas)
        if not courses:
            print(f"Nenhuma disciplina encontrada para: {search_term}")
            return
        
        # Show search results and let user choose
        select_and_add_from_results(courses, f"Disciplinas encontradas para '{search_term}'", 
                                    disciplinas, selections_file)
    
    # Handle add by time code
    elif subcmd == '-t' and len(cmd_parts) >= 3:
        time_code = cmd_parts[2]
        courses, error = find_by_time_code(time_code, disciplinas)
        if error:
            print(f"Erro: {error}")
            return
        
        if not courses:
            day_name = DAY_CODES.get(time_code[0], "?")
            print(f"Nenhuma disciplina disponível para os horários especificados ({day_name})")
            return
        
        period = "manhã" if time_code[1].upper() == "M" else "tarde" if time_code[1].upper() == "T" else "noite"
        hours = ", ".join([f"{(6 if time_code[1].upper() == 'M' else 12 if time_code[1].upper() == 'T' else 18) + int(h) - 1}:00" for h in time_code[2:]])
        title = f"Disciplinas disponíveis para {DAY_CODES.get(time_code[0], '?')} pela {period} nos horários: {hours}"
        
        select_and_add_from_results(courses, title, disciplinas, selections_file)
    
    # Handle add by number from last list
    elif subcmd.isdigit():
        idx = int(subcmd) - 1
        if not sorted_list:
            print("Execute 'list' primeiro para ver as disciplinas disponíveis.")
            return
            
        if 0 <= idx < len(sorted_list):
            add_course(sorted_list[idx], disciplinas, selections_file)
        else:
            print("Índice fora do intervalo.")
    else:
        print("Formato inválido para comando 'add'. Use 'help' para ver os comandos disponíveis.")

def handle_remove_command(cmd_parts, disciplinas, sorted_list, selections_file):
    """Handle the 'remove' command with various sub-commands"""
    if len(cmd_parts) < 2:
        print("O comando 'remove' precisa de argumentos.")
        return
    
    # Handle remove by code
    if cmd_parts[1] == '-c' and len(cmd_parts) >= 3:
        code = cmd_parts[2].lower()  # Case-insensitive code handling
        courses = find_by_code(code, disciplinas)
        if not courses:
            print(f"Código não encontrado: {code}")
            return
        
        # If multiple sections found, let user select which one to remove
        if len(courses) > 1:
            selected_courses = [c for c in courses if c.selected]
            
            if not selected_courses:
                print("Nenhuma turma deste código está no cronograma.")
                return
                
            if len(selected_courses) == 1:
                d = selected_courses[0]
            else:
                print(f"\nEncontradas {len(selected_courses)} turmas selecionadas para o código {code.upper()}:")
                selected_courses = print_results(selected_courses, f"Turmas selecionadas para código {code.upper()}")
                
                print("\nSelecione uma disciplina para remover do cronograma")
                print("Digite o número da disciplina ou 'c' para cancelar")
                choice = input("> ").strip()
                
                if choice.lower() == 'c':
                    return
                    
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(selected_courses):
                        d = selected_courses[idx]
                    else:
                        print("Índice inválido.")
                        return
                except ValueError:
                    print("Entrada inválida.")
                    return
        else:
            d = courses[0]
            
        if d.selected:
            d.selected = False
            update_availability(disciplinas)
            save_selections(disciplinas, selections_file)
            print(f"'{d.name}' ({d.codigo}) removida do cronograma.")
        else:
            print("Disciplina não está no cronograma.")
    
    # Handle remove by number from last list
    elif cmd_parts[1].isdigit():
        idx = int(cmd_parts[1]) - 1
        if not sorted_list:
            print("Execute 'list' primeiro para ver as disciplinas disponíveis.")
            return
            
        if 0 <= idx < len(sorted_list):
            d = sorted_list[idx]
            if d.selected:
                d.selected = False
                update_availability(disciplinas)
                save_selections(disciplinas, selections_file)
                print(f"'{d.name}' ({d.codigo}) removida do cronograma.")
            else:
                print("Disciplina não está no cronograma.")
        else:
            print("Índice fora do intervalo.")
    else:
        print("Formato inválido para comando 'remove'.")

# === Utility Functions ===

def add_course(disciplina, disciplinas, selections_file):
    """Add a course to the schedule"""
    if disciplina.selected:
        print("Disciplina já está no cronograma.")
    else:
        # Check for conflicts before adding
        occupied_by = update_availability(disciplinas)
        has_conflicts = print_conflicts(disciplina, occupied_by)
        
        if has_conflicts:
            print("Não é possível adicionar disciplina devido aos conflitos de horário.")
        else:
            disciplina.selected = True
            update_availability(disciplinas)
            save_selections(disciplinas, selections_file)
            print(f"'{disciplina.name}' ({disciplina.codigo}) adicionada ao cronograma.")

def select_and_add_from_results(courses, title, disciplinas, selections_file):
    """Show a list of courses and allow the user to select and add one"""
    # Show results
    print_results(courses, title)
    
    # Ask user to select a course
    print("\nSelecione uma disciplina para adicionar ao cronograma")
    print("Digite o número da disciplina ou 'c' para cancelar")
    choice = input("> ").strip()
    
    if choice.lower() == 'c':
        return
        
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(courses):
            add_course(courses[idx], disciplinas, selections_file)
        else:
            print("Índice inválido.")
    except ValueError:
        print("Entrada inválida.")

def print_help():
    """Print help information about available commands"""
    print("\nComandos disponíveis:")
    print("  'list'                         - Lista todas as disciplinas")
    print("  'print'                        - Mostra o cronograma")
    print("  'add <num>'                    - Adiciona disciplina pelo número da lista")
    print("  'add -c <código>'              - Adiciona disciplina pelo código")
    print("  'add -n <nome>'                - Adiciona disciplina pelo nome (busca aproximada)")
    print("  'add -t <horário>'             - Adiciona disciplina pelo código de horário")
    print("  'remove <num>'                 - Remove disciplina pelo número da lista")
    print("  'remove -c <código>'           - Remove disciplina pelo código")
    print("  'help'                         - Mostra esta ajuda")
    print("  'exit'                         - Sair do programa")

# === Main Function ===

def main():
    """Main program function"""
    # Find CSV file - first check command line argument, then look for default file
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    elif os.path.exists(DEFAULT_CSV_FILE):
        csv_file = DEFAULT_CSV_FILE
    else:
        # Look for any CSV file in the current directory
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        if csv_files:
            csv_file = csv_files[0]
            print(f"Usando arquivo CSV encontrado: {csv_file}")
        else:
            print("Nenhum arquivo CSV encontrado. Por favor, especifique o arquivo como argumento.")
            sys.exit(1)
    
    selections_file = 'selecoes.json'
    disciplinas = load_disciplinas(csv_file, selections_file)
    update_availability(disciplinas)
    
    print_help()
    
    sorted_list = None

    while True:
        try:
            cmd_input = input('> ').strip()
            cmd_parts = cmd_input.split()
            
            if not cmd_parts:
                continue
                
            action = cmd_parts[0].lower()
            
            if action == 'exit':
                break
            elif action == 'help':
                print_help()
            elif action == 'list':
                sorted_list = print_table(disciplinas)
            elif action == 'print':
                print_cronograma(disciplinas)
            elif action == 'add':
                handle_add_command(cmd_parts, disciplinas, sorted_list, selections_file)
            elif action == 'remove':
                handle_remove_command(cmd_parts, disciplinas, sorted_list, selections_file)
            else:
                print("Comando desconhecido. Use 'help' para ver a lista de comandos.")
        except KeyboardInterrupt:
            print("\nSaindo...")
            sys.exit(0)
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == '__main__':
    main()
