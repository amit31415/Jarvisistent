import os

# Base directory for Jarvis's local offline memory
MEMORY_DIR = "/home/kido1/Smartroom/data/jarvis_memory"
DEFAULT_FOLDER = "general"

def init_memory():
    """Creates the base memory directory and a default folder if they don't exist."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(os.path.join(MEMORY_DIR, DEFAULT_FOLDER), exist_ok=True)
    print(f"[INFO] Local memory initialized at: {MEMORY_DIR}")

def create_folder(folder_name):
    """Creates a new folder inside the memory directory."""
    if not folder_name:
        return False, "Folder name cannot be empty."
        
    path = os.path.join(MEMORY_DIR, folder_name)
    try:
        os.makedirs(path, exist_ok=True)
        return True, f"Folder '{folder_name}' is ready."
    except Exception as e:
        return False, f"Failed to create folder: {e}"

def save_note(folder_name, file_name, content):
    """Appends a new line with the content to a specific text file."""
    # Use default folder if none is provided
    if not folder_name:
        folder_name = DEFAULT_FOLDER
        
    create_folder(folder_name)
    
    # Force .txt extension
    if not file_name.endswith('.txt'):
        file_name += '.txt'
        
    file_path = os.path.join(MEMORY_DIR, folder_name, file_name)
    
    try:
        # Append mode ('a') adds to the end of the file. '\n' drops to a new line.
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"- {content}\n")
        return True, f"Note appended in {folder_name}/{file_name}."
    except Exception as e:
        return False, f"Failed to save note: {e}"

def read_full_file(folder_name, file_name):
    """Reads and returns the entire content of a specific file."""
    if not folder_name:
        folder_name = DEFAULT_FOLDER
        
    if not file_name.endswith('.txt'):
        file_name += '.txt'
        
    file_path = os.path.join(MEMORY_DIR, folder_name, file_name)
    
    if not os.path.exists(file_path):
        return False, "File not found."
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        if not content:
            return True, "The file is empty."
        return True, content
    except Exception as e:
        return False, f"Failed to read file: {e}"

def search_in_file(folder_name, file_name, search_term):
    """Scans a file line by line and returns only the lines containing the search term."""
    if not folder_name:
        folder_name = DEFAULT_FOLDER
        
    if not file_name.endswith('.txt'):
        file_name += '.txt'
        
    file_path = os.path.join(MEMORY_DIR, folder_name, file_name)
    
    if not os.path.exists(file_path):
        return False, "File not found."
        
    try:
        found_lines = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if search_term in line:
                    # Remove the prefix '- ' and clean whitespace for a natural TTS reading
                    clean_line = line.strip().lstrip('- ')
                    found_lines.append(clean_line)
        
        if not found_lines:
            return False, "No matching information found in this file."
            
        # Join multiple matches into a single readable string
        return True, ". ".join(found_lines)
    except Exception as e:
        return False, f"Failed to search file: {e}"

def delete_note_file(folder_name, file_name):
    """Deletes a specific text file entirely."""
    if not folder_name:
        folder_name = DEFAULT_FOLDER
        
    if not file_name.endswith('.txt'):
        file_name += '.txt'
        
    file_path = os.path.join(MEMORY_DIR, folder_name, file_name)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        return True, "File deleted."
    return False, "File does not exist."

# Auto-initialize when the module is imported
init_memory()
