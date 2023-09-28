# Allow for keeping added files list between dir changes
# CSV untick doesnt display [DIR]

import os
import sys
import time
from datetime import datetime
import yaml
import PySimpleGUIWeb as sg
import pgpy
import paramiko
from termcolor import cprint

class FileUtils:
    @staticmethod
    def human_readable_size(size, decimal_places=2):
        unit = 'B'
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                break
            size /= 1024.0
        return f"{size:.{decimal_places}f} {unit}"

    @staticmethod
    def safe_file_read(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            log_msg = f"Error reading file {filepath}, err:{e}"
            cprint(log_msg, 'red')
            return None

    @staticmethod
    def load_key_file(filepath):
        private_key_file = PRIV_SSHKEY_FILEPATH
        try:
            if os.path.exists(private_key_file):
                return private_key_file
            else:
                return 'Key not found'
        except Exception as e:
            log_msg = f"Error loading key file {filepath}, err:{e}"
            cprint(log_msg, 'red')
            return None

    @staticmethod
    def load_config(config_file):
        with open(config_file, 'r', encoding='utf-8') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

    @staticmethod
    def encrypt_file(filepath, encrypted_dir):
        key, _ = pgpy.PGPKey.from_blob(PGP_PUBLIC_KEY)
        contents = FileUtils.safe_file_read(filepath)
        if contents is None:
            return None, "Error reading file", "Encryption failed"
        message = pgpy.PGPMessage.new(contents)
        encrypted_message = key.encrypt(message)
        encrypted_filepath = os.path.join(encrypted_dir, os.path.basename(filepath) + '.pgp')
        with open(encrypted_filepath, 'wb') as f:
            f.write(str(encrypted_message).encode())
        log_text_source = f"SOURCE FILE: \n{filepath}\n"
        log_text_encrypt = f"ENCRYPTED FILE: \n{filepath}\n"
        return encrypted_filepath, log_text_source, log_text_encrypt

    @staticmethod
    def is_valid_file(filename):
        if filename is None:
            return False
        return filename.lower().endswith('.csv')

#########
CONFIG_FILE = 'config.yaml'  # Note: config file must be in same directory as main.py
config = FileUtils.load_config(CONFIG_FILE)
if config is None:
    cprint("Failed to load config.", 'red')
    sys.exit(1)
#########
FONT_COMMON = tuple(config['Font']['Common'])
FONT_HEADER = tuple(config['Font']['Header'])
COLOR_COMMON_BG = config['Colors']['CommonBG']
FILES_WINDOW_SIZE = tuple(config['WindowSizes']['Files'])
DIR_WINDOW_SIZE = tuple(config['WindowSizes']['Dir'])
ADD_FILES_WINDOW_SIZE = tuple(config['WindowSizes']['AddFiles'])
LOGS_WINDOW_SIZE = tuple(config['WindowSizes']['Logs'])
BTN_SIZE = tuple(config['Button']['Size'])
THEME = config['Theme']
#########
SFTP_HOSTNAME = config['SFTP']['Hostname']
SFTP_PORT = config['SFTP']['Port']
SFTP_USERNAME = config['SFTP']['Username']
SFTP_HOST_FILEPATH = config['SFTP']['HostFilepath']
#########
ENCRYPTED_FILES_FOLDER = config['FilePaths']['ENCRYPTED_FILES_FOLDER']
PRIV_SSHKEY_FILEPATH = config['FilePaths']['PRIV_SSHKEY_FILEPATH']
PGP_PUBLIC_KEY = config['PGP_PUBLIC_KEY']
SOURCE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class SFTPUtils:
    @staticmethod
    def open_sftp_connection():
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        get_key = FileUtils.load_key_file(PRIV_SSHKEY_FILEPATH)
        mykey = paramiko.RSAKey(filename=get_key)
        client.connect(hostname=SFTP_HOSTNAME, port=SFTP_PORT, username=SFTP_USERNAME, pkey=mykey)
        sftp = client.open_sftp()
        sftp.chdir('upload')  # Note: Change dir to upload folder
        sftp_dir = sftp.getcwd()
        log_msg = 'After dir change: ' + str(sftp_dir)
        cprint(log_msg, 'green')
        return client, sftp

    @staticmethod
    def upload_file_to_sftp(local_file_path, remote_file_path, sftp, file_window):
        try:
            if sftp is not None:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                start_time = time.time()
                msg = '(SFTP_func) Uploading file from: ' + local_file_path
                cprint(msg, 'blue')
                msg = '(SFTP_func) To: ' + remote_file_path
                cprint(msg, 'green')
                sftp.put(local_file_path, remote_file_path)
                end_time = time.time()
                elapsed_time = end_time - start_time
                minutes, seconds = divmod(elapsed_time, 60)
                time_str = f"{minutes} minutes {seconds:.2f} seconds" if minutes else f"{seconds:.2f} seconds"
                if os.path.basename(remote_file_path) in sftp.listdir('.'):
                    cprint(f"(SFTP_func) Upload Confirmed: {remote_file_path}", 'green')
                    log_msg = f"(SFTP_func)Upload took: {time_str}"
                    cprint(log_msg, 'white')
                    log_window_entry = f"\n{timestamp}\n### SFTP UPLOAD RESULT ###\n"
                    log_window_entry += f"LOCAL FILE: {local_file_path}\n"
                    log_window_entry += f"REMOTE FILE: {remote_file_path}\n"
                    log_window_entry += f"TIME TAKEN FOR UPLOAD: {time_str}\n"
                    file_window['-LOG_BLUE-'].update(log_window_entry + '\n', append=True)
                local_file_size = os.path.getsize(local_file_path)  # Note: Get size in bytes
                remote_file_size = sftp.stat(remote_file_path).st_size  # Note: Get size in bytes
                local_file_size_human = FileUtils.human_readable_size(local_file_size)  # Note: Convert to human readable size
                remote_file_size_human = FileUtils.human_readable_size(remote_file_size)  # Note: Convert to human readable size
                log_window_entry = f"LOCAL FILESIZE: {local_file_size_human} REMOTE FILESIZE: {remote_file_size_human}"
                file_window['-LOG_BLUE-'].update(log_window_entry + '\n', append=True)

                if local_file_size == remote_file_size:
                    log_msg = "FILESIZES MATCH -> UPLOAD VERIFIED SUCCESSFULLY"
                    cprint(log_msg, 'green')
                    file_window['-LOG_BLUE-'].update(log_msg + '\n', append=True)
                else:
                    log_msg = "WARNING| FILESIZES DO NOT MATCH -> UPLOAD MAY HAVE FAILED"
                    cprint(log_msg, 'red')
                    file_window['-LOG_RED-'].update(log_msg + '\n', append=True)
            else:
                cprint("(SFTP_func)sftp is None, cannot upload file.", 'red')
        except Exception as e:
            log_msg = f"\n(SFTP_Func)Failed to upload \n{local_file_path} To \n{remote_file_path}: \nError: {e}\n"
            cprint(log_msg, 'red')
            file_window['-LOG_RED-'].update(log_msg + '\n', append=True)
            raise

class GUIUtils:
    @staticmethod
    def create_main_window(breadcrumbs):
        all_entries = os.listdir(SOURCE_DIRECTORY)
        dir_list = sorted(all_entries, key=lambda x: (not os.path.isdir(os.path.join(SOURCE_DIRECTORY, x)), x))
        dir_list = [f"[DIR] {d}" if os.path.isdir(os.path.join(SOURCE_DIRECTORY, d)) else d for d in dir_list]
        layout = [
            [sg.Text(f'{breadcrumbs}', key='-BREADCRUMBS-', auto_size_text=True, text_color='red', background_color='white', justification='left', pad=(5,1), click_submits=None, enable_events=False, border_width=5, font=FONT_COMMON, margins=1, tooltip='KYC', visible=True, metadata=None),
             sg.Text(f'{"No key loaded, click browse to load a key." if PRIV_SSHKEY_FILEPATH is None else f"Loaded Key: {PRIV_SSHKEY_FILEPATH}"}', key='-KEY_TEXT-', auto_size_text=True, text_color='red', background_color='white', justification='center', pad=(20,1), border_width=10, font=FONT_COMMON, margins=1),
             sg.Button('Browse Key', auto_size_button=True, key='-BROWSE_KEY-', button_color=('white', 'purple'))],
            [sg.Text('Select Directory:', font=FONT_HEADER)],
            [sg.Listbox(values=dir_list, size=DIR_WINDOW_SIZE, key='-DIR-', enable_events=True, background_color=COLOR_COMMON_BG, font=FONT_COMMON, auto_size_text=True, default_values=[dir_list[0]] if dir_list else [])],
            [sg.Button('Next', auto_size_button=True, key='-NEXT-', disabled=True, button_color=('white', 'purple')),
             sg.Text('', size=(65, 1)),
             sg.Checkbox('Show only .csv files', key='-SHOW_CSV-', enable_events=True),
             sg.Button('Exit', auto_size_button=True, button_color=('white', 'Red'))
             ]]
        return sg.Window('Select Files to Encrypt', layout)

    @staticmethod
    def create_file_window(all_files_in_dir, breadcrumbs, current_source_directory):
        all_files_in_dir = sorted(all_files_in_dir, key=lambda x: (not os.path.isdir(os.path.join(current_source_directory, x)), x))
        all_files_in_dir = [f if not os.path.isdir(os.path.join(current_source_directory, f)) else f"[DIR] {f}" for f in all_files_in_dir]
        file_layout = [
            [sg.Text(f'{breadcrumbs}', key='-BREADCRUMBS-', auto_size_text=True, text_color='red', background_color='white', justification='left', pad=(5,1), click_submits=None, enable_events=False, border_width=5, font=FONT_COMMON, margins=1, tooltip='KYC', visible=True, metadata=None),
             sg.Text(f'{"No key loaded, click browse to load a key." if PRIV_SSHKEY_FILEPATH is None else f"Loaded Key: {PRIV_SSHKEY_FILEPATH}"}', key='-KEY_TEXT-', auto_size_text=True, text_color='red', background_color='white', justification='center', pad=(20,1), border_width=10, font=FONT_COMMON, margins=1),
             sg.Button('Browse Key', auto_size_button=True, key='-BROWSE_KEY-', button_color=('white', 'purple'))],
            [sg.Column([[sg.Text('Select Files/DIR:', font=FONT_HEADER, background_color='white', text_color='purple')
                         ],
                        [sg.Listbox(values=all_files_in_dir, size=FILES_WINDOW_SIZE, select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED, key='-FILE-', auto_size_text=True, enable_events=True, background_color=COLOR_COMMON_BG, font=FONT_COMMON)
                         ]], pad=(10, 0)), sg.VerticalSeparator(), sg.Column(
                             [[sg.Text('Selected Files:', font=FONT_HEADER, key='-SELECTED_FILES_TEXT-', background_color='white', text_color='red')],
                              [sg.Listbox(values=[], size=ADD_FILES_WINDOW_SIZE, select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED, key='-ADDED_FILES-', auto_size_text=True, background_color=COLOR_COMMON_BG, font=FONT_COMMON)]], pad=(10, 0)), sg.VerticalSeparator(), sg.Column(
                                  [[sg.Text('Input Files and SFTP Logs:', font=FONT_HEADER)],
                                   [sg.Multiline(size=LOGS_WINDOW_SIZE, key='-LOG_BLUE-', autoscroll=True, auto_size_text=True, disabled=False, background_color=COLOR_COMMON_BG, font=FONT_COMMON, text_color='blue')]], pad=(10, 0)), sg.Column(
                                       [[sg.Text('Encryption Logs:', font=FONT_HEADER)],
                                        [sg.Multiline(size=LOGS_WINDOW_SIZE, key='-LOG_RED-', autoscroll=True, auto_size_text=True, disabled=False, background_color=COLOR_COMMON_BG, font=FONT_COMMON, text_color='red')]], pad=(10, 0))], [
                                            sg.Button('Next', auto_size_button=True, key='-FILE_NEXT-', button_color=('white', 'purple')),
                                            sg.Button('Add CSV to list', auto_size_button=True, button_color=('white', 'green')),
                                            sg.Button('Add All CSV', auto_size_button=True, button_color=('white', 'blue')),
                                            sg.Button('Delete CSV from list', auto_size_button=True, button_color=('black', 'yellow')),
                                            sg.Button('Encrypt', auto_size_button=True, button_color=('white', 'black')),
                                            sg.Button('SFTP Upload', auto_size_button=True, button_color=('white', 'blue')),
                                            sg.Button('Back', auto_size_button=True, button_color=('white', 'orange')),
                                            sg.Checkbox('Show only .csv files', key='-SHOW_CSV-', enable_events=True),
                                            sg.Button('Exit', auto_size_button=True, button_color=('white', 'red'))]]
        return sg.Window('Select Files/DIR', file_layout, resizable=True)

    @staticmethod
    def create_key_browse_window(current_key_directory):
        all_entries = os.listdir(current_key_directory)
        dir_list = sorted(all_entries, key=lambda x: (not os.path.isdir(os.path.join(current_key_directory, x)), x))
        dir_list = [f"[DIR] {d}" if os.path.isdir(os.path.join(current_key_directory, d)) else d for d in dir_list]

        layout = [
            [sg.Text('Select your key file:', font=FONT_HEADER)],
            [sg.Listbox(values=dir_list, size=(50, 20), key='-KEY_LIST-', enable_events=True, background_color=COLOR_COMMON_BG, font=FONT_COMMON)],
            [sg.Button('Select', auto_size_button=True, key='-SELECT_KEY-', button_color=('white', 'green')),
             sg.Button('Cancel', auto_size_button=True, key='-CANCEL-', button_color=('white', 'red')),
             sg.Button('Exit', auto_size_button=True, button_color=('white', 'Red'))]
        ]
        return sg.Window('Select Key File', layout)

class GUIHandlers:

    @staticmethod
    def handle_add_to_list(f_values, selected_files_global, file_window):
        if f_values['-FILE-']:
            valid_files = [f for f in f_values['-FILE-'] if FileUtils.is_valid_file(f)]
            selected_files_global.update(valid_files)
            sorted_list = sorted(list(selected_files_global))
            file_window['-ADDED_FILES-'].update(values=sorted_list)

    @staticmethod
    def handle_delete_from_list(f_values, selected_files_global, file_window):
        if f_values['-ADDED_FILES-']:
            selected_files_global.difference_update(f_values['-ADDED_FILES-'])
            sorted_list = sorted(list(selected_files_global))
            file_window['-ADDED_FILES-'].update(values=sorted_list)

    @staticmethod
    def handle_encrypt(f_values, selected_files_global, user_selected_dir, file_window):
        encrypted_files = []
        if not selected_files_global:
            return
        selected_files = selected_files_global if selected_files_global else f_values['-FILE-']
        encrypted_dir = os.path.join(SOURCE_DIRECTORY, user_selected_dir, ENCRYPTED_FILES_FOLDER.lstrip('\\'))
        if not os.path.exists(encrypted_dir):
            os.makedirs(encrypted_dir)
        logs_blue, logs_red = [], []
        for f in selected_files:
            encrypted_filepath, log_blue, log_red = FileUtils.encrypt_file(os.path.join(SOURCE_DIRECTORY, user_selected_dir, f), encrypted_dir)
            encrypted_files.append(encrypted_filepath)
            # cprint(f"Encrypted file: {encrypted_filepath}")  # Debug cprint
            if encrypted_filepath is None:
                continue
            logs_blue.append(log_blue)
            logs_red.append(log_red)
        file_window['-LOG_BLUE-'].update('\n'.join(logs_blue), append=True)
        file_window['-LOG_RED-'].update('\n'.join(logs_red), append=True)
        return encrypted_files

    @staticmethod
    def handle_update_file_list(file_window, all_files_in_dir, current_source_directory):
        if file_window is None:
            print("file_window is None")
            return
        show_csv_elem = file_window['-SHOW_CSV-']
        if show_csv_elem is None:
            print("show_csv_elem is None")
            return
        if show_csv_elem.Widget is not None and show_csv_elem.get():
            all_files_in_dir = [f for f in all_files_in_dir if f.lower().endswith('.csv')]
        else:
            all_files_in_dir = os.listdir(current_source_directory)
        file_elem = file_window['-FILE-']
        if file_elem is None:
            print("file_elem is None")
            return
        if file_elem.Widget is not None:
            file_elem.update(values=all_files_in_dir)
        else:
            print("Widget is empty")

def main():
    sg.theme(THEME)
    breadcrumbs = SOURCE_DIRECTORY
    global PRIV_SSHKEY_FILEPATH  # pylint: disable=global-statement
    # cprint(f"Initial breadcrumbs: {breadcrumbs}")  # Debug cprint
    PRIV_SSHKEY_FILEPATH = FileUtils.load_key_file(PRIV_SSHKEY_FILEPATH)
    window = GUIUtils.create_main_window(breadcrumbs)
    selected_files_global = set()
    current_source_directory = SOURCE_DIRECTORY
    sftp = None
    log_msg = "INFO| KEYFILE FULL FILEPATH | ", PRIV_SSHKEY_FILEPATH
    log_msg_str = " ".join(str(elem) for elem in log_msg)
    cprint(log_msg_str, 'white')
    encrypted_files = []
    while True:
        event, values = window.read()  # type: ignore
        # cprint(f"Main window event: {event}, values: {values}")  # Debug cprint
        PRIV_SSHKEY_FILEPATH = FileUtils.load_key_file(PRIV_SSHKEY_FILEPATH)
        window['-KEY_TEXT-'].update(f"{'No key loaded, click browse to load a key.' if PRIV_SSHKEY_FILEPATH == 'Key not found' else f'Loaded Key: {PRIV_SSHKEY_FILEPATH}'}")
        if event == '-BROWSE_KEY-':  # Note
            current_key_directory = "."  # Set this to your starting directory
            key_window = GUIUtils.create_key_browse_window(current_key_directory)
            while True:
                k_event, k_values = key_window.read()  # pylint : disable=unpacking-non-sequence # Ignore this error
                if k_event in (None, '-CANCEL-'):
                    key_window.close()
                    break
                if k_event == '-SELECT_KEY-':
                    selected_key = k_values['-KEY_LIST-'][0]
                    selected_key_path = os.path.abspath(os.path.join(current_key_directory, selected_key.lstrip("[DIR] ").strip()))

                    if os.path.isdir(selected_key_path):
                        # Update the listbox for the new directory
                        current_key_directory = selected_key_path
                        new_list = os.listdir(current_key_directory)
                        key_window['-KEY_LIST-'].update(new_list)
                    else:
                        # It's a file, use as the key
                        PRIV_SSHKEY_FILEPATH = selected_key_path
                        window['-KEY_TEXT-'].update(f"Loaded Key: {PRIV_SSHKEY_FILEPATH}")
                        key_window.close()
                        break
        if event == 'Exit':  # Note
            window.close()
            break
        if event == '-DIR-':  # Note
            # cprint("-DIR- event triggered, updating -NEXT- button")  # Debug cprint
            if values['-DIR-']:
                window['-NEXT-'].update(disabled=False)  # type: ignore
            else:
                window['-NEXT-'].update(disabled=True)  # type: ignore
        if event == '-NEXT-':  # Note
            if values['-DIR-']:
                selected_dir = values['-DIR-'][0].lstrip("[DIR] ").strip()
            else:
                continue
            breadcrumbs += "/" + selected_dir
            window['-BREADCRUMBS-'].update(f'{breadcrumbs}')
            current_source_directory = os.path.join(current_source_directory, selected_dir)
            # cprint(f"Updated current_source_directory to: {current_source_directory}")  # Debug cprint
            user_selected_dir = values['-DIR-'][0].replace("[DIR] ", "")
            try:
                all_files_in_dir = os.listdir(current_source_directory)
            except FileNotFoundError as e:
                sg.popup_ok(f"Directory {user_selected_dir} not found, err:{e}")
                continue
            file_window = GUIUtils.create_file_window(all_files_in_dir, breadcrumbs, current_source_directory)
            while True:
                f_event, f_values = file_window.read()  # pylint : disable=unpacking-non-sequence # Ignore this error
                # cprint(f"File window event: {f_event}, values: {f_values}")  # Debug cprint
                if f_event == '-SHOW_CSV-':  # Note
                    GUIHandlers.handle_update_file_list(file_window, all_files_in_dir, current_source_directory)

                if f_event == '-BROWSE_KEY-':  # Note
                    current_key_directory = "."  # Set this to your starting directory
                    key_window = GUIUtils.create_key_browse_window(current_key_directory)
                    while True:
                        k_event, k_values = key_window.read()  # pylint disable=E0633 # Ignore this error
                        if k_event in (None, '-CANCEL-'):
                            key_window.close()
                            break
                        if k_event == '-SELECT_KEY-':
                            selected_key = k_values['-KEY_LIST-'][0]
                            selected_key_path = os.path.abspath(os.path.join(current_key_directory, selected_key.lstrip("[DIR] ").strip()))
                            if os.path.isdir(selected_key_path):
                                # Update the listbox for the new directory
                                current_key_directory = selected_key_path
                                new_list = os.listdir(current_key_directory)
                                key_window['-KEY_LIST-'].update(new_list)
                            else:
                                # It's a file, use as the key
                                PRIV_SSHKEY_FILEPATH = selected_key_path
                                file_window['-KEY_TEXT-'].update(f"Loaded Key: {PRIV_SSHKEY_FILEPATH}")
                                key_window.close()
                                break

                if f_event == 'Exit':  # Note
                    file_window.close()
                    window.close()
                    sys.exit(0)

                if f_event == 'Back':  # Note
                    if os.path.normpath(current_source_directory) != os.path.normpath(SOURCE_DIRECTORY):
                        breadcrumbs = breadcrumbs.rsplit('/', 1)[0]
                        selected_files_global.clear()
                        current_source_directory = os.path.dirname(current_source_directory)
                        file_window.close()
                        all_files_in_dir = os.listdir(current_source_directory)
                        file_window = GUIUtils.create_file_window(all_files_in_dir, breadcrumbs, current_source_directory)
                        if file_window:  # Check if new file_window is created successfully
                            GUIHandlers.handle_update_file_list(file_window, all_files_in_dir, current_source_directory)
                    else:
                        pass

                if f_event == '-FILE-':  # Note
                    if f_values['-FILE-']:
                        file_window['-FILE_NEXT-'].update(disabled=False)
                    else:
                        file_window['-FILE_NEXT-'].update(disabled=True)
                if f_event == '-FILE_NEXT-':
                    if not f_values['-FILE-']:
                        continue
                    if f_values['-FILE-'] and f_values['-FILE-'][0]:
                        selected_subdir = f_values['-FILE-'][0].lstrip("[DIR] ").strip()
                    else:
                        continue
                    breadcrumbs += "/" + selected_subdir
                    file_window['-BREADCRUMBS-'].update(f'{breadcrumbs}')
                    current_source_directory = os.path.join(current_source_directory, selected_subdir)
                    file_window.close()
                    all_files_in_dir = os.listdir(current_source_directory)
                    file_window = GUIUtils.create_file_window(all_files_in_dir, breadcrumbs, current_source_directory)
                    GUIHandlers.handle_update_file_list(file_window, all_files_in_dir, current_source_directory)
                if f_event == 'Add CSV to list':  # Note
                    GUIHandlers.handle_add_to_list(f_values, selected_files_global, file_window)
                if f_event == 'Add All CSV':  # Note
                    if all_files_in_dir is not None:
                        valid_files = [f for f in all_files_in_dir if FileUtils.is_valid_file(f)]
                        selected_files_global.update(valid_files)
                        sorted_list = sorted(list(selected_files_global))
                        if file_window is not None:
                            file_window['-ADDED_FILES-'].update(values=sorted_list)
                if f_event == 'Delete CSV from list':  # Note
                    GUIHandlers.handle_delete_from_list(f_values, selected_files_global, file_window)
                if f_event == 'Encrypt':  # Note
                    new_encrypted_files = GUIHandlers.handle_encrypt(f_values, selected_files_global, current_source_directory, file_window)
                    if new_encrypted_files is not None:
                        encrypted_files = new_encrypted_files
                    if file_window is not None:
                        # Let's remove full path from GUI and just show the filename

                        gui_encrypted_files = [os.path.basename(f) for f in encrypted_files]
                        file_window['-ADDED_FILES-'].update(values=gui_encrypted_files)
                        file_window['-SELECTED_FILES_TEXT-'].update('Encrypted Files')
                        # cprint("Encrypted files: ", encrypted_files)  # Debug cprint
                if f_event == 'SFTP Upload':  # Note
                    logs_red = []
                    files = []
                    try:
                        client, sftp = SFTPUtils.open_sftp_connection()
                        cprint("(Main_func) SFTP SESSION OPENED SUCCESSFULLY", 'green')
                        try:
                            for files in encrypted_files:
                                remote_file_path = os.path.basename(files)
                                # log_msg = f"(Main_func) Remote file path: {remote_file_path}"  # Debug cprint
                                # cprint(log_msg, 'green')  # Debug cprint
                                SFTPUtils.upload_file_to_sftp(files, remote_file_path, sftp, file_window)
                                log_msg = f"(Main_func) Uploaded {files} to {remote_file_path}"
                                # cprint(log_msg, 'green')  # Debug cprint
                        except Exception as e:
                            cprint(f"(Main) Failed to upload {files} to remote file path. Exception: {e}", 'red')  # type: ignore
                            logs_red.append(f"(Main) Failed to upload {files} to remote file path. Exception: {e}")
                            file_window['-LOG_RED-'].update('\n'.join(logs_red), append=True)
                            if sftp is not None:
                                sftp.close()
                                cprint("(Main_func) SFTP session closed", 'cyan')
                            client.close()
                            cprint("(Main_func) SSH client closed, goodbye.", 'cyan')
                    except Exception as e:
                        cprint(f"(Main_func1 ) Failed to initialize SFTP session: {e}", 'red')
                        if PRIV_SSHKEY_FILEPATH is not None:
                            logs_red.append(f"Incorrect Keyfile: {PRIV_SSHKEY_FILEPATH}\n")
                            file_window['-LOG_RED-'].update('\n'.join(logs_red), append=True)
                            cprint(f"Key file used: {PRIV_SSHKEY_FILEPATH}", 'green')
                        else:
                            cprint("Key file used: None", PRIV_SSHKEY_FILEPATH, 'red')
                            logs_red.append(f"Key file not found: {PRIV_SSHKEY_FILEPATH}")
                            file_window['-LOG_RED-'].update('\n'.join(logs_red), append=True)
                        print("out-logsred: ", logs_red)
                        logs_red.append(f"\n\n#################################################\n\nFailed to initialize SFTP session: \nError:{e}\n\n#################################################\n")
                        file_window['-LOG_RED-'].update('\n'.join(logs_red), append=True)

if __name__ == '__main__':
    main()
